#!/usr/bin/env python3
"""
Authentication System

Comprehensive JWT-based authentication system with user management,
password security, session handling, and security monitoring.

Features:
- JWT token generation and validation
- Secure password hashing with bcrypt
- User registration and email verification
- Password reset functionality
- Session management with refresh tokens
- Rate limiting and account lockout protection
- Comprehensive audit logging

Usage:
    from utils.auth_system import AuthManager, get_current_user

    auth = AuthManager(db_connection, jwt_secret)
    token = await auth.authenticate_user(email, password)
    user = await get_current_user(token, auth)
"""

import asyncio
import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

import bcrypt
import jwt
import psycopg2
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg2.extras import Json, RealDictCursor

from config import get_settings
from utils.exceptions import AccountLockedError, AuthenticationError, RateLimitError, ValidationError
from utils.logging_config import setup_logging
from utils.rbac_models import (
    CreateUserRequest,
    LoginRequest,
    PermissionLevel,
    ResetPasswordRequest,
    TokenData,
    TokenResponse,
    User,
    UserResponse,
    UserStatus,
)

# Configure logging with standardized setup
_settings_for_logging = get_settings()
logger = setup_logging(
    program_name="auth_system",
    log_level=getattr(_settings_for_logging, "log_level", "INFO"),
    log_file=f"/app/logs/auth_system_{datetime.utcnow().strftime('%Y%m%d')}.log"
    if os.getenv("LOG_DIR") or os.getenv("AUTH_SYSTEM_LOG_TO_FILE", "1") == "1"
    else None,
    console_output=True,
)

# FastAPI security scheme
security = HTTPBearer()

T = TypeVar("T")

_auth_manager_instance: Optional["AuthManager"] = None
_auth_manager_lock = asyncio.Lock()


class AuthManager:
    """Comprehensive authentication and authorization manager."""

    def __init__(self, db_connection_string: str, jwt_secret_key: str):
        """Initialize authentication manager."""
        self.db_connection_string = db_connection_string
        self.jwt_secret_key = jwt_secret_key
        self.jwt_algorithm = "HS256"
        self.settings = get_settings()

        # Security configuration
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=15)
        self.access_token_expire = timedelta(minutes=30)
        self.refresh_token_expire = timedelta(days=7)
        self.password_reset_expire = timedelta(hours=1)

        # Rate limiting (simple in-memory store)
        self.login_attempts = {}
        self.rate_limit_window = timedelta(minutes=5)
        self.max_attempts_per_window = 10

    def _open_connection(self):
        """Create a new psycopg2 connection."""
        override = self.__dict__.get("get_db_connection")
        if callable(override):
            logger.debug("Using override for DB connection")
            result = override()
            if asyncio.iscoroutine(result):
                return asyncio.run(result)
            return result
        masked_dsn = self.db_connection_string
        if "@" in masked_dsn and ":" in masked_dsn.split("@")[0]:
            creds, host_part = masked_dsn.split("@", 1)
            user_part = creds.split("://")[-1].split(":")[0]
            masked_dsn = masked_dsn.replace(creds, f"{user_part}:***")
        logger.debug("Opening psycopg2 connection to %s", masked_dsn)
        return psycopg2.connect(self.db_connection_string, cursor_factory=RealDictCursor)

    async def _run_in_thread(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute blocking work in a worker thread."""
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except RuntimeError:
            # asyncio.to_thread requires a running loop; fall back for sync usage (e.g. tests)
            return func(*args, **kwargs)

    async def get_db_connection(self):
        """Get database connection (legacy – prefer helper methods that run in thread pools)."""
        return await self._run_in_thread(self._open_connection)

    # Password Management
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure token."""
        return secrets.token_urlsafe(length)

    # JWT Token Management
    def create_access_token(self, user: User, permissions: List[str]) -> str:
        """Create JWT access token."""
        now = datetime.utcnow()
        payload = TokenData(
            user_id=user.id,
            email=user.email,
            role_id=user.role_id,
            permissions=permissions,
            exp=now + self.access_token_expire,
            iat=now,
            jti=self.generate_secure_token(16),
        )

        return jwt.encode(payload.dict(), self.jwt_secret_key, algorithm=self.jwt_algorithm)

    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        payload = {
            "user_id": user.id,
            "type": "refresh",
            "exp": now + self.refresh_token_expire,
            "iat": now,
            "jti": self.generate_secure_token(16),
        }

        return jwt.encode(payload, self.jwt_secret_key, algorithm=self.jwt_algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret_key, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.PyJWTError as e:
            # Catch all PyJWT validation issues (signature, decode errors)
            raise AuthenticationError(f"Invalid token: {str(e)}")

    # Health Check
    async def health_check(self) -> Dict[str, Any]:
        """Perform a lightweight health check of auth subsystem.

        Returns dict with status and optional detail.
        Avoids heavy queries; simple connection + role table presence.
        """
        return await self._run_in_thread(self._health_check_sync)

    def _health_check_sync(self) -> Dict[str, Any]:
        conn = None
        cursor = None
        try:
            conn = self._open_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM roles LIMIT 1;")
            cursor.fetchone()
            return {"status": "healthy"}
        except Exception as e:  # pragma: no cover
            logger.error(f"Auth health check error: {e}")
            return {"status": "unhealthy", "error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # Rate Limiting
    def check_rate_limit(self, identifier: str) -> bool:
        """Check if identifier is within rate limits."""
        now = datetime.utcnow()

        if identifier not in self.login_attempts:
            self.login_attempts[identifier] = []

        # Clean old attempts
        self.login_attempts[identifier] = [
            attempt for attempt in self.login_attempts[identifier] if now - attempt < self.rate_limit_window
        ]

        # Check if over limit
        if len(self.login_attempts[identifier]) >= self.max_attempts_per_window:
            return False

        # Record this attempt
        self.login_attempts[identifier].append(now)
        return True

    # User Management
    async def create_user(self, user_data: CreateUserRequest, created_by: Optional[int] = None) -> User:
        """Create new user account."""
        # Auto-assign employee role for @xylem.com emails
        if user_data.email.lower().endswith("@xylem.com"):
            employee_role_id = await self.get_role_id_by_name("employee")
            if employee_role_id:
                user_data.role_id = employee_role_id
                logger.info("Auto-assigned employee role to @xylem.com user: %s", user_data.email)

        logger.info(
            "Attempting to create user email=%s role_id=%s",
            user_data.email,
            user_data.role_id,
        )
        try:
            user = await self._run_in_thread(self._create_user_sync, user_data)
        except Exception:
            logger.exception("Error creating user %s", user_data.email)
            raise

        await self.log_audit_event(
            user_id=created_by,
            action="user_created",
            resource_type="user",
            resource_id=str(user.id),
            details={"created_user_email": user.email},
        )

        await self.send_verification_email(user)
        return user

    def _create_user_sync(self, user_data: CreateUserRequest) -> User:
        logger.debug("Opening DB connection for user creation")
        conn = self._open_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
            cols = {r["column_name"] if isinstance(r, dict) else r[0] for r in cursor.fetchall()}
            extended = {"password_hash", "role_id", "verified", "login_attempts", "preferences"}.issubset(cols)

            cursor.execute("SELECT id FROM users WHERE email = %s", (user_data.email.lower(),))
            if cursor.fetchone():
                raise ValidationError("User with this email already exists")

            cursor.execute("SELECT id FROM roles WHERE id = %s", (user_data.role_id,))
            if not cursor.fetchone():
                logger.warning(
                    "Role ID %s not found while creating user %s",
                    user_data.role_id,
                    user_data.email,
                )
                raise ValidationError("Invalid role ID")

            password_hash = self.hash_password(user_data.password)
            display_name = (
                f"{user_data.first_name or ''} {user_data.last_name or ''}".strip() or user_data.email.split("@")[0]
            )

            if extended:
                cursor.execute(
                    """
                    INSERT INTO users (email, name, password_hash, first_name, last_name, role_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, email, name, first_name, last_name, role_id, status, verified,
                              created_at, updated_at, password_change_required
                    """,
                    (
                        user_data.email.lower(),
                        display_name,
                        password_hash,
                        user_data.first_name,
                        user_data.last_name,
                        user_data.role_id,
                        UserStatus.PENDING_VERIFICATION.value,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO users (email, name, status)
                    VALUES (%s, %s, %s)
                    RETURNING id, email, name, status, created_at, updated_at
                    """,
                    (
                        user_data.email.lower(),
                        display_name,
                        "active",
                    ),
                )

            user_row = cursor.fetchone()
            conn.commit()

            if not user_row:
                logger.error("User creation returned no row for %s", user_data.email)
                raise ValidationError("Failed to create user record")

            if isinstance(user_row, dict):
                base = user_row
            else:
                keys = ["id", "email", "name", "status", "created_at", "updated_at"]
                base = dict(zip(keys, user_row))

            return User(
                id=base.get("id"),
                email=base.get("email"),
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                role_id=user_data.role_id,
                status=base.get("status", UserStatus.PENDING_VERIFICATION),
                verified=base.get("verified", not extended),
                last_login=base.get("last_login"),
                login_attempts=base.get("login_attempts", 0),
                locked_until=base.get("locked_until"),
                password_change_required=base.get("password_change_required", True),
                password_changed_at=base.get("password_changed_at"),
                preferences=base.get("preferences", {}),
                created_at=base.get("created_at"),
                updated_at=base.get("updated_at"),
            )
        except Exception:
            conn.rollback()
            logger.exception("Transaction rolled back while creating user %s", user_data.email)
            raise
        finally:
            cursor.close()
            conn.close()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await self._run_in_thread(self._get_user_by_id_sync, user_id)

    def _get_user_by_id_sync(self, user_id: int) -> Optional[User]:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, email, password_hash, first_name, last_name, role_id,
                       status, verified, last_login, login_attempts, locked_until,
                       password_change_required, password_changed_at,
                       preferences, created_at, updated_at
                FROM users WHERE id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            return User(**dict(row)) if row else None
        finally:
            cursor.close()
            conn.close()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self._run_in_thread(self._get_user_by_email_sync, email.lower())

    def _get_user_by_email_sync(self, email: str) -> Optional[User]:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, email, password_hash, first_name, last_name, role_id,
                       status, verified, last_login, login_attempts, locked_until,
                       password_change_required, password_changed_at,
                       preferences, created_at, updated_at
                FROM users WHERE email = %s
                """,
                (email,),
            )
            row = cursor.fetchone()
            return User(**dict(row)) if row else None
        finally:
            cursor.close()
            conn.close()

    async def get_user_permissions(self, user_id: int) -> List[str]:
        """Get all permissions for a user."""
        return await self._run_in_thread(self._get_user_permissions_sync, user_id)

    def _get_user_permissions_sync(self, user_id: int) -> List[str]:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT DISTINCT p.name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                JOIN role_permissions rp ON r.id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE u.id = %s AND u.status = 'active' AND u.verified = true
                """,
                (user_id,),
            )
            return [row["name"] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    async def get_role_name(self, role_id: int) -> Optional[str]:
        """Return role name for the given role id."""
        return await self._run_in_thread(self._get_role_name_sync, role_id)

    def _get_role_name_sync(self, role_id: int) -> Optional[str]:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM roles WHERE id = %s", (role_id,))
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return row.get("name")
            return row[0]
        finally:
            cursor.close()
            conn.close()

    async def get_role_id_by_name(self, role_name: str) -> Optional[int]:
        """Return role id for the given role name."""
        return await self._run_in_thread(self._get_role_id_by_name_sync, role_name)

    def _get_role_id_by_name_sync(self, role_name: str) -> Optional[int]:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return row.get("id")
            return row[0]
        finally:
            cursor.close()
            conn.close()

    # Authentication
    async def authenticate_user(self, email: str, password: str, ip_address: Optional[str] = None) -> TokenResponse:
        """Authenticate user and return tokens."""

        # Check rate limiting
        rate_limit_key = ip_address or email
        if not self.check_rate_limit(rate_limit_key):
            await self.log_security_event(
                event_type="rate_limit_exceeded",
                severity="medium",
                ip_address=ip_address,
                details={"email": email, "type": "login"},
            )
            raise RateLimitError("Too many login attempts. Please try again later.")

        # Get user
        user = await self.get_user_by_email(email)
        if not user:
            await self.log_security_event(
                event_type="login_failed",
                severity="low",
                ip_address=ip_address,
                details={"email": email, "reason": "user_not_found"},
            )
            raise AuthenticationError("Invalid email or password")

        # Check if account is locked
        if user.is_locked:
            await self.log_security_event(
                event_type="locked_account_access",
                severity="medium",
                user_id=user.id,
                ip_address=ip_address,
                details={"email": email},
            )
            raise AccountLockedError("Account is locked due to too many failed login attempts")

        # Verify password
        if not self.verify_password(password, user.password_hash):
            await self.increment_login_attempts(user.id)
            await self.log_security_event(
                event_type="login_failed",
                severity="low",
                user_id=user.id,
                ip_address=ip_address,
                details={"email": email, "reason": "invalid_password"},
            )
            raise AuthenticationError("Invalid email or password")

        # Check account status
        if not user.is_active:
            await self.log_security_event(
                event_type="inactive_account_access",
                severity="medium",
                user_id=user.id,
                ip_address=ip_address,
                details={"email": email, "status": user.status.value},
            )
            raise AuthenticationError("Account is not active")

        # Reset login attempts on successful login
        await self.reset_login_attempts(user.id)

        # Update last login
        await self.update_last_login(user.id)

        # Get user permissions
        permissions = await self.get_user_permissions(user.id)

        # Get role name - hardcoded mapping for reliability
        role_name = None
        if user.role_id == 1:
            role_name = "admin"
        elif user.role_id == 2:
            role_name = "employee"
        elif user.role_id == 3:
            role_name = "guest"

        # Create tokens
        access_token = self.create_access_token(user, permissions)
        refresh_token = self.create_refresh_token(user)

        # Log successful login
        await self.log_audit_event(
            user_id=user.id,
            action="login_success",
            resource_type="auth",
            ip_address=ip_address,
            details={"method": "password"},
        )

        # Create response
        user_response = UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            role_id=user.role_id,
            role_name=role_name,
            status=user.status,
            verified=user.verified,
            last_login=user.last_login,
            is_active=user.is_active,
            is_locked=user.is_locked,
            password_change_required=user.password_change_required,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.access_token_expire.total_seconds()),
            user=user_response,
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Create new access token from refresh token."""
        try:
            payload = self.decode_token(refresh_token)

            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid refresh token")

            user_id = payload.get("user_id")
            user = await self.get_user_by_id(user_id)

            if not user or not user.is_active:
                raise AuthenticationError("User account is not active")

            # Get fresh permissions
            permissions = await self.get_user_permissions(user.id)

            # Create new access token
            access_token = self.create_access_token(user, permissions)

            # Create response
            user_response = UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                full_name=user.full_name,
                role_id=user.role_id,
                status=user.status,
                verified=user.verified,
                last_login=user.last_login,
                is_active=user.is_active,
                is_locked=user.is_locked,
                password_change_required=user.password_change_required,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,  # Keep same refresh token
                expires_in=int(self.access_token_expire.total_seconds()),
                user=user_response,
            )

        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise AuthenticationError("Invalid refresh token")

    # Account Security
    async def increment_login_attempts(self, user_id: int):
        """Increment failed login attempts and lock if necessary."""
        await self._run_in_thread(self._increment_login_attempts_sync, user_id)

    def _increment_login_attempts_sync(self, user_id: int):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET login_attempts = login_attempts + 1,
                    locked_until = CASE
                        WHEN login_attempts + 1 >= %s
                        THEN %s
                        ELSE locked_until
                    END
                WHERE id = %s
                """,
                (
                    self.max_login_attempts,
                    datetime.utcnow() + self.lockout_duration,
                    user_id,
                ),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def reset_login_attempts(self, user_id: int):
        """Reset login attempts on successful login."""
        await self._run_in_thread(self._reset_login_attempts_sync, user_id)

    def _reset_login_attempts_sync(self, user_id: int):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET login_attempts = 0, locked_until = NULL
                WHERE id = %s
                """,
                (user_id,),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def update_last_login(self, user_id: int):
        """Update user's last login timestamp."""
        await self._run_in_thread(self._update_last_login_sync, user_id)

    def _update_last_login_sync(self, user_id: int):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET last_login = %s
                WHERE id = %s
                """,
                (datetime.utcnow(), user_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def set_password_change_required(self, user_id: int, required: bool):
        """Toggle password change requirement flag."""
        await self._run_in_thread(self._set_password_change_required_sync, user_id, required)

    def _set_password_change_required_sync(self, user_id: int, required: bool):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET password_change_required = %s, updated_at=%s
                WHERE id = %s
                """,
                (required, datetime.utcnow(), user_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    # Password Management
    async def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")

        # Verify old password
        if not self.verify_password(old_password, user.password_hash):
            await self.log_security_event(
                event_type="password_change_failed",
                severity="medium",
                user_id=user_id,
                details={"reason": "invalid_old_password"},
            )
            raise AuthenticationError("Current password is incorrect")

        # Hash new password
        new_hash = self.hash_password(new_password)

        await self._run_in_thread(
            self._update_password_sync,
            user_id,
            new_hash,
            False,
        )

        await self.log_audit_event(
            user_id=user_id,
            action="password_changed",
            resource_type="user",
            resource_id=str(user_id),
            details={"method": "self_service"},
        )
        return True

    def _update_password_sync(self, user_id: int, new_hash: str, force_change: bool):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s, password_change_required = %s,
                    password_changed_at = %s, updated_at = %s
                WHERE id = %s
                """,
                (new_hash, force_change, datetime.utcnow(), datetime.utcnow(), user_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def force_password_change(self, user_id: int, new_password: str) -> bool:
        """Force password change for initial login (no old password required)."""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")

        # Hash new password
        new_hash = self.hash_password(new_password)

        try:
            await self._run_in_thread(
                self._update_password_sync,
                user_id,
                new_hash,
                False,
            )
        except Exception as e:
            logger.error(f"Force password change failed: {str(e)}")
            return False

        await self.log_audit_event(
            user_id=user_id,
            action="password_force_changed",
            resource_type="user",
            resource_id=str(user_id),
            details={"method": "initial_login"},
        )

        return True

    async def admin_reset_password(self, user_id: int, new_password: str, force_change: bool = True) -> bool:
        """Admin-initiated password reset.

        Sets a new password hash and optionally flags user to change it on next login.
        Records an audit event. Returns True on success.
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")

        new_hash = self.hash_password(new_password)
        try:
            await self._run_in_thread(
                self._admin_reset_password_sync,
                user_id,
                new_hash,
                force_change,
            )
        except Exception as e:
            logger.error(f"Admin reset password failed: {e}")
            return False

        await self.log_audit_event(
            user_id=user_id,
            action="password_admin_reset",
            resource_type="user",
            resource_id=str(user_id),
            details={"force_change": force_change},
        )
        return True

    def _admin_reset_password_sync(self, user_id: int, new_hash: str, force_change: bool):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s, password_change_required = %s,
                    password_changed_at = %s, updated_at = %s
                WHERE id = %s
                """,
                (new_hash, force_change, datetime.utcnow(), datetime.utcnow(), user_id),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    async def initiate_password_reset(self, email: str) -> bool:
        """Generate and dispatch a password reset token for the given email.

        Returns True when a notification was queued for an existing user, False otherwise.
        Caller should always present a generic success response to avoid account enumeration.
        """
        normalized_email = email.strip().lower()
        user = await self.get_user_by_email(normalized_email)

        if not user:
            await self.log_security_event(
                event_type="password_reset_requested",
                severity="low",
                details={"email": normalized_email, "matched": False},
            )
            return False

        token = self.generate_secure_token()
        token_hash = self._hash_token(token)
        expires_at = datetime.utcnow() + self.password_reset_expire

        try:
            await self._run_in_thread(
                self._store_password_reset_token_sync,
                user.id,
                token_hash,
                expires_at,
            )
            sent = await self._run_in_thread(
                self._dispatch_password_reset_email_sync,
                user,
                token,
                expires_at,
            )
        except Exception as exc:
            await self.log_security_event(
                event_type="password_reset_failed",
                severity="high",
                user_id=user.id,
                details={"email": normalized_email, "error": str(exc)},
            )
            logger.error("Password reset initiation failed for %s: %s", normalized_email, exc)
            raise

        await self.log_security_event(
            event_type="password_reset_requested",
            severity="low",
            user_id=user.id,
            details={"email": normalized_email, "email_dispatched": sent},
        )
        await self.log_audit_event(
            user_id=user.id,
            action="password_reset_requested",
            resource_type="user",
            resource_id=str(user.id),
            details={"email_dispatched": sent, "expires_at": expires_at.isoformat()},
        )

        return sent

    def _store_password_reset_token_sync(self, user_id: int, token_hash: str, expires_at: datetime):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE verification_tokens
                SET used = true
                WHERE user_id = %s AND token_type = 'password_reset'
                """,
                (user_id,),
            )
            cursor.execute(
                """
                INSERT INTO verification_tokens (user_id, token, token_type, expires_at)
                VALUES (%s, %s, 'password_reset', %s)
                """,
                (user_id, token_hash, expires_at),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _dispatch_password_reset_email_sync(self, user: User, token: str, expires_at: datetime) -> bool:
        recipient = user.email
        if not recipient:
            logger.warning("Cannot send password reset email without recipient address")
            return False

        sender = self.settings.password_reset_email_sender or self.settings.verification_email_sender
        subject = self.settings.password_reset_email_subject
        reset_url = f"{self.settings.password_reset_email_link_base}?token={token}"

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject

        body = (
            f"Hello {user.full_name or user.email},\n\n"
            "We received a request to reset the password for your Technical Service Assistant account.\n\n"
            f"Password reset token: {token}\n"
            f"Reset link: {reset_url}\n\n"
            f"This token expires at {expires_at.isoformat()} UTC. "
            "If you did not request this change, please ignore this email or contact support.\n\n"
            "Regards,\nTechnical Service Assistant"
        )
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.sendmail(sender, [recipient], msg.as_string())
            return True
        except Exception as exc:
            logger.error("Failed to send password reset email to %s: %s", recipient, exc)
            return False

    async def confirm_password_reset(self, token: str, new_password: str) -> bool:
        """Validate reset token and apply new password."""
        token = token.strip()
        if len(token) < 8:
            raise ValidationError("Password reset token is invalid")

        if len(new_password) < 8:
            raise ValidationError("Password must be at least 8 characters long")

        new_hash = self.hash_password(new_password)

        try:
            user_id = await self._run_in_thread(
                self._apply_password_reset_sync,
                self._hash_token(token),
                token,
                new_hash,
            )
        except ValidationError as exc:
            await self.log_security_event(
                event_type="password_reset_invalid",
                severity="medium",
                details={"error": str(exc)},
            )
            raise
        except Exception as exc:
            logger.error("Password reset confirmation failed: %s", exc)
            raise

        if not user_id:
            return False

        await self.log_audit_event(
            user_id=user_id,
            action="password_reset_completed",
            resource_type="user",
            resource_id=str(user_id),
            details={"method": "self_service_token"},
        )
        await self.log_security_event(
            event_type="password_reset_completed",
            severity="low",
            user_id=user_id,
            details={"method": "token"},
        )
        return True

    def _apply_password_reset_sync(self, token_hash: str, raw_token: str, new_hash: str) -> int:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, expires_at, used
                FROM verification_tokens
                WHERE token = %s AND token_type = 'password_reset'
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    """
                    SELECT id, user_id, expires_at, used
                    FROM verification_tokens
                    WHERE token = %s AND token_type = 'password_reset'
                    """,
                    (raw_token,),
                )
                row = cursor.fetchone()
            if not row:
                raise ValidationError("Invalid password reset token")

            row_d = dict(row)
            token_id = row_d.get("id")
            user_id = row_d.get("user_id")
            expires_at = row_d.get("expires_at")
            used = row_d.get("used")

            if not user_id:
                raise ValidationError("Password reset token is not linked to a user")
            if used:
                raise ValidationError("Password reset token has already been used")
            if expires_at and expires_at < datetime.utcnow():
                raise ValidationError("Password reset token has expired")

            now = datetime.utcnow()
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    password_change_required = false,
                    password_changed_at = %s,
                    login_attempts = 0,
                    locked_until = NULL,
                    updated_at = %s
                WHERE id = %s
                """,
                (new_hash, now, now, user_id),
            )
            if cursor.rowcount == 0:
                raise ValidationError("Unable to update password for the provided token")

            cursor.execute(
                """
                UPDATE verification_tokens
                SET used = true
                WHERE id = %s
                """,
                (token_id,),
            )
            conn.commit()
            return int(user_id)
        except ValidationError:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # Email Verification
    async def send_verification_email(self, user: User) -> bool:
        """Send verification email with secure token storage."""
        verification_token = self.generate_secure_token()
        token_hash = self._hash_token(verification_token)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        logger.info(
            "Generating verification token for user_id=%s email=%s expires_at=%s",
            user.id,
            user.email,
            expires_at.isoformat(),
        )

        await self._run_in_thread(
            self._store_verification_token_sync,
            user.id,
            token_hash,
            expires_at,
        )

        logger.debug(
            "Stored verification token hash_prefix=%s for user_id=%s",
            token_hash[:8],
            user.id,
        )

        sent = await self._run_in_thread(
            self._dispatch_verification_email_sync,
            user,
            verification_token,
            expires_at,
        )
        if not sent:
            logger.warning(
                "Verification email dispatch failed for %s (token hash prefix=%s)",
                user.email,
                token_hash[:8],
            )
        else:
            logger.info(
                "Verification email sent to %s (token hash prefix=%s)",
                user.email,
                token_hash[:8],
            )
        return sent

    def _store_verification_token_sync(self, user_id: int, token_hash: str, expires_at: datetime):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO verification_tokens (user_id, token, token_type, expires_at)
                VALUES (%s, %s, 'email_verification', %s)
                """,
                (user_id, token_hash, expires_at),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _dispatch_verification_email_sync(self, user: User, token: str, expires_at: datetime) -> bool:
        recipient = user.email
        if not recipient:
            logger.warning("Cannot send verification email without recipient address")
            return False

        sender = self.settings.verification_email_sender
        subject = self.settings.verification_email_subject
        verification_url = f"{self.settings.verification_email_link_base}?token={token}"

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject

        body = (
            f"Hello {user.full_name or user.email},\n\n"
            "Thanks for registering with Technical Service Assistant. "
            "Please verify your email address by using the token below or visiting the verification link.\n\n"
            f"Verification token: {token}\n"
            f"Verification link: {verification_url}\n\n"
            f"This token expires at {expires_at.isoformat()} UTC.\n\n"
            "If you did not create this account, you can ignore this email.\n\n"
            "Regards,\nTechnical Service Assistant"
        )
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as server:
                if self.settings.smtp_use_tls:
                    server.starttls()
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.sendmail(sender, [recipient], msg.as_string())
            logger.debug("Verification email dispatched via SMTP host=%s", self.settings.smtp_host)
            return True
        except Exception:
            logger.exception("Failed to send verification email to %s", recipient)
            return False

    # Audit Logging
    async def log_audit_event(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[int] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Log audit event."""
        await self._run_in_thread(
            self._log_audit_event_sync,
            action,
            resource_type,
            user_id,
            resource_id,
            ip_address,
            user_agent,
            details,
            success,
            error_message,
        )

    def _log_audit_event_sync(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[int],
        resource_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        details: Optional[Dict[str, Any]],
        success: bool,
        error_message: Optional[str],
    ):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            json_details = Json(details) if details is not None else None
            cursor.execute(
                """
                INSERT INTO audit_logs
                (user_id, action, resource_type, resource_id, ip_address,
                 user_agent, details, success, error_message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    action,
                    resource_type,
                    resource_id,
                    ip_address,
                    user_agent,
                    json_details,
                    success,
                    error_message,
                    datetime.utcnow(),
                ),
            )
            conn.commit()
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to log audit event action=%s resource=%s err=%s details=%s",
                action,
                resource_type,
                e,
                details,
            )
        finally:
            cursor.close()
            conn.close()

    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log security event."""
        await self._run_in_thread(
            self._log_security_event_sync,
            event_type,
            severity,
            user_id,
            ip_address,
            details,
        )

    def _log_security_event_sync(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[int],
        ip_address: Optional[str],
        details: Optional[Dict[str, Any]],
    ):
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            json_details = Json(details) if details is not None else None
            cursor.execute(
                """
                INSERT INTO security_events
                (event_type, severity, user_id, ip_address, details, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event_type,
                    severity,
                    user_id,
                    ip_address,
                    json_details,
                    datetime.utcnow(),
                ),
            )
            conn.commit()
        except Exception as e:  # pragma: no cover
            logger.error(
                "Failed to log security event type=%s severity=%s err=%s details=%s",
                event_type,
                severity,
                e,
                details,
            )
        finally:
            cursor.close()
            conn.close()

    # Email Verification
    async def verify_email_token(self, token: str) -> bool:
        """Consume an email verification token and mark user verified.

        Workflow:
        - Look up token in verification_tokens
        - Validate: exists, type=email_verification, not used, not expired
        - Update users: set verified=true, status='active' (if pending verification)
        - Mark token used
        - Audit log event

        Returns True if verification completed, False if already verified.
        Raises ValidationError for invalid/expired token.
        """
        token_hash = self._hash_token(token)

        try:
            status, user_id = await self._run_in_thread(
                self._consume_verification_token_sync,
                token_hash,
                token,
            )
        except ValidationError:
            raise
        except Exception as e:  # pragma: no cover
            logger.error(f"Email verification failed: {e}")
            raise ValidationError("Failed to verify email")

        if status == "expired":
            await self.log_security_event(
                event_type="verification_token_expired",
                severity="low",
                user_id=user_id,
                details={"token_hash_prefix": token_hash[:8]},
            )
            raise ValidationError("Verification token expired")

        if status == "already_used" or status == "already_verified":
            return False

        if status == "verified":
            if user_id is not None:
                await self.log_audit_event(
                    user_id=user_id,
                    action="email_verified",
                    resource_type="user",
                    resource_id=str(user_id),
                    details={"method": "token"},
                )
            return True

        raise ValidationError("Invalid verification token")

    def _consume_verification_token_sync(self, token_hash: str, raw_token: str) -> Tuple[str, Optional[int]]:
        conn = self._open_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT vt.id, vt.user_id, vt.token_type, vt.expires_at, vt.used, u.verified, u.status
                FROM verification_tokens vt
                JOIN users u ON vt.user_id = u.id
                WHERE vt.token = %s
                """,
                (token_hash,),
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    """
                    SELECT vt.id, vt.user_id, vt.token_type, vt.expires_at, vt.used, u.verified, u.status
                    FROM verification_tokens vt
                    JOIN users u ON vt.user_id = u.id
                    WHERE vt.token = %s
                    """,
                    (raw_token,),
                )
                row = cursor.fetchone()
            if not row:
                raise ValidationError("Invalid verification token")

            row_d = dict(row)
            token_type = row_d.get("token_type")
            if token_type != "email_verification":
                raise ValidationError("Token type mismatch")

            user_id = row_d.get("user_id")
            token_id = row_d.get("id")
            expires_at = row_d.get("expires_at")
            if expires_at and expires_at < datetime.utcnow():
                return ("expired", user_id)

            if row_d.get("used"):
                return ("already_used", user_id)

            already_verified = bool(row_d.get("verified"))

            cursor.execute("UPDATE verification_tokens SET used=true WHERE id=%s", (token_id,))

            if already_verified:
                conn.commit()
                return ("already_verified", user_id)

            cursor.execute(
                """
                UPDATE users
                SET verified=true,
                    status = CASE WHEN status = 'pending_verification' THEN 'active' ELSE status END,
                    updated_at=%s
                WHERE id=%s
                """,
                (datetime.utcnow(), user_id),
            )
            conn.commit()
            return ("verified", user_id)
        except ValidationError:
            conn.rollback()
            raise
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()


# FastAPI Dependencies
async def get_auth_manager() -> AuthManager:
    """Get authentication manager instance."""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        async with _auth_manager_lock:
            if _auth_manager_instance is None:
                settings = get_settings()
                db_url = (
                    f"postgresql://{settings.db_user}:{settings.db_password}"
                    f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
                )
                # Use the configured JWT secret (allows JWT_SECRET to override JWT_SECRET_KEY)
                jwt_secret = getattr(settings, "jwt_secret", os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production"))
                _auth_manager_instance = AuthManager(db_url, jwt_secret)
    return _auth_manager_instance


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), auth_manager: AuthManager = Depends(get_auth_manager)
) -> User:
    """Get current authenticated user from JWT token."""
    try:
        # Decode token
        payload = auth_manager.decode_token(credentials.credentials)
        user_id = payload.get("user_id")

        if not user_id:
            raise AuthenticationError("Invalid token payload")

        # Get user from database
        user = await auth_manager.get_user_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("User account is not active")

        return user

    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user (additional validation)."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


def require_permission(permission: PermissionLevel):
    """Decorator to require specific permission."""

    async def permission_dependency(
        current_user: User = Depends(get_current_user), auth_manager: AuthManager = Depends(get_auth_manager)
    ) -> User:
        # Get user permissions
        permissions = await auth_manager.get_user_permissions(current_user.id)

        if permission.value not in permissions:
            await auth_manager.log_security_event(
                event_type="unauthorized_access",
                severity="medium",
                user_id=current_user.id,
                details={"required_permission": permission.value, "user_permissions": permissions},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission '{permission.value}' required"
            )

        return current_user

    return permission_dependency


def require_admin():
    """Require admin permission."""
    return require_permission(PermissionLevel.ADMIN)


def require_user_management():
    """Require user management permission."""
    return require_permission(PermissionLevel.MANAGE_USERS)


# Backward compatibility aliases expected by legacy import usage
AuthSystem = AuthManager
UserCreate = CreateUserRequest
UserLogin = LoginRequest
PasswordResetRequest = ResetPasswordRequest
