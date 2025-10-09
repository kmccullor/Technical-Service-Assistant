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

import os
import jwt
import bcrypt
import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import logging
from contextlib import asynccontextmanager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import get_settings
from utils.rbac_models import (
    User, Role, Permission, TokenData, TokenResponse, LoginRequest,
    CreateUserRequest, ChangePasswordRequest, ResetPasswordRequest,
    ConfirmPasswordResetRequest, UserResponse, AuditLog, SecurityEvent,
    UserStatus, PermissionLevel, APIResponse, ErrorResponse
)
from utils.exceptions import (
    AuthenticationError, AuthorizationError, ValidationError,
    RateLimitError, AccountLockedError
)

# Configure logging
logger = logging.getLogger(__name__)

# FastAPI security scheme
security = HTTPBearer()


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
    
    async def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            self.db_connection_string,
            cursor_factory=RealDictCursor
        )
    
    # Password Management
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
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
            jti=self.generate_secure_token(16)
        )
        
        return jwt.encode(
            payload.dict(),
            self.jwt_secret_key,
            algorithm=self.jwt_algorithm
        )
    
    def create_refresh_token(self, user: User) -> str:
        """Create JWT refresh token."""
        now = datetime.utcnow()
        payload = {
            "user_id": user.id,
            "type": "refresh",
            "exp": now + self.refresh_token_expire,
            "iat": now,
            "jti": self.generate_secure_token(16)
        }
        
        return jwt.encode(
            payload,
            self.jwt_secret_key,
            algorithm=self.jwt_algorithm
        )
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret_key,
                algorithms=[self.jwt_algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    # Health Check
    async def health_check(self) -> Dict[str, Any]:
        """Perform a lightweight health check of auth subsystem.

        Returns dict with status and optional detail.
        Avoids heavy queries; simple connection + role table presence.
        """
        try:
            conn = await self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM roles LIMIT 1;")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return {"status": "healthy"}
        except Exception as e:  # pragma: no cover
            logger.error(f"Auth health check error: {e}")
            return {"status": "unhealthy", "error": str(e)}

    # Rate Limiting
    def check_rate_limit(self, identifier: str) -> bool:
        """Check if identifier is within rate limits."""
        now = datetime.utcnow()
        
        if identifier not in self.login_attempts:
            self.login_attempts[identifier] = []
        
        # Clean old attempts
        self.login_attempts[identifier] = [
            attempt for attempt in self.login_attempts[identifier]
            if now - attempt < self.rate_limit_window
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
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Detect minimal schema (legacy) vs extended schema
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
            cols = {r['column_name'] if isinstance(r, dict) else r[0] for r in cursor.fetchall()}
            extended = {'password_hash','role_id','verified','login_attempts','preferences'}.issubset(cols)
            # Check if user already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = %s",
                (user_data.email.lower(),)
            )
            if cursor.fetchone():
                raise ValidationError("User with this email already exists")
            
            # Validate role exists
            cursor.execute("SELECT id FROM roles WHERE id = %s", (user_data.role_id,))
            if not cursor.fetchone():
                raise ValidationError("Invalid role ID")
            
            # Hash password
            password_hash = self.hash_password(user_data.password)
            
            if extended:
                cursor.execute("""
                        INSERT INTO users (email, name, password_hash, first_name, last_name, role_id, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, email, name, first_name, last_name, role_id, status, verified, created_at, updated_at
                """, (
                    user_data.email.lower(),
                        f"{user_data.first_name or ''} {user_data.last_name or ''}".strip() or user_data.email.split('@')[0],
                    password_hash,
                    user_data.first_name,
                    user_data.last_name,
                    user_data.role_id,
                    UserStatus.PENDING_VERIFICATION.value
                ))
            else:
                # Minimal fallback: only columns email, name, status maybe exist
                cursor.execute("""
                        INSERT INTO users (email, name, status)
                        VALUES (%s, %s, %s)
                        RETURNING id, email, name, status, created_at, updated_at
                """, (
                    user_data.email.lower(),
                    f"{user_data.first_name or ''} {user_data.last_name or ''}".strip() or user_data.email.split('@')[0],
                    'active'
                ))
            
            user_row = cursor.fetchone()
            conn.commit()
            
            # Create user object
            user = User(**dict(user_row)) if extended else User(
                id=user_row['id'] if isinstance(user_row, dict) else user_row[0],
                email=user_row['email'] if isinstance(user_row, dict) else user_row[1],
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                role_id=user_data.role_id,
                status=UserStatus.ACTIVE,
                verified=True,
                created_at=user_row.get('created_at') if isinstance(user_row, dict) else None,
                updated_at=user_row.get('updated_at') if isinstance(user_row, dict) else None,
            )
            
            # Log user creation
            await self.log_audit_event(
                user_id=created_by,
                action="user_created",
                resource_type="user",
                resource_id=str(user.id),
                details={"created_user_email": user.email}
            )
            
            # TODO: Send verification email
            await self.send_verification_email(user)
            
            return user
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, email, password_hash, first_name, last_name, role_id,
                       status, verified, last_login, login_attempts, locked_until,
                       preferences, created_at, updated_at
                FROM users WHERE id = %s
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return User(**dict(row))
            return None
            
        finally:
            cursor.close()
            conn.close()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, email, password_hash, first_name, last_name, role_id,
                       status, verified, last_login, login_attempts, locked_until,
                       preferences, created_at, updated_at
                FROM users WHERE email = %s
            """, (email.lower(),))
            
            row = cursor.fetchone()
            if row:
                return User(**dict(row))
            return None
            
        finally:
            cursor.close()
            conn.close()
    
    async def get_user_permissions(self, user_id: int) -> List[str]:
        """Get all permissions for a user."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT DISTINCT p.name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                JOIN role_permissions rp ON r.id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE u.id = %s AND u.status = 'active' AND u.verified = true
            """, (user_id,))
            
            return [row['name'] for row in cursor.fetchall()]
            
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
                details={"email": email, "type": "login"}
            )
            raise RateLimitError("Too many login attempts. Please try again later.")
        
        # Get user
        user = await self.get_user_by_email(email)
        if not user:
            await self.log_security_event(
                event_type="login_failed",
                severity="low",
                ip_address=ip_address,
                details={"email": email, "reason": "user_not_found"}
            )
            raise AuthenticationError("Invalid email or password")
        
        # Check if account is locked
        if user.is_locked:
            await self.log_security_event(
                event_type="locked_account_access",
                severity="medium",
                user_id=user.id,
                ip_address=ip_address,
                details={"email": email}
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
                details={"email": email, "reason": "invalid_password"}
            )
            raise AuthenticationError("Invalid email or password")
        
        # Check account status
        if not user.is_active:
            await self.log_security_event(
                event_type="inactive_account_access",
                severity="medium",
                user_id=user.id,
                ip_address=ip_address,
                details={"email": email, "status": user.status.value}
            )
            raise AuthenticationError("Account is not active")
        
        # Reset login attempts on successful login
        await self.reset_login_attempts(user.id)
        
        # Update last login
        await self.update_last_login(user.id)
        
        # Get user permissions
        permissions = await self.get_user_permissions(user.id)
        
        # Create tokens
        access_token = self.create_access_token(user, permissions)
        refresh_token = self.create_refresh_token(user)
        
        # Log successful login
        await self.log_audit_event(
            user_id=user.id,
            action="login_success",
            resource_type="auth",
            ip_address=ip_address,
            details={"method": "password"}
        )
        
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
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.access_token_expire.total_seconds()),
            user=user_response
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
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,  # Keep same refresh token
                expires_in=int(self.access_token_expire.total_seconds()),
                user=user_response
            )
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise AuthenticationError("Invalid refresh token")
    
    # Account Security
    async def increment_login_attempts(self, user_id: int):
        """Increment failed login attempts and lock if necessary."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET login_attempts = login_attempts + 1,
                    locked_until = CASE 
                        WHEN login_attempts + 1 >= %s 
                        THEN %s 
                        ELSE locked_until 
                    END
                WHERE id = %s
            """, (
                self.max_login_attempts,
                datetime.utcnow() + self.lockout_duration,
                user_id
            ))
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()
    
    async def reset_login_attempts(self, user_id: int):
        """Reset login attempts on successful login."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET login_attempts = 0, locked_until = NULL
                WHERE id = %s
            """, (user_id,))
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()
    
    async def update_last_login(self, user_id: int):
        """Update user's last login timestamp."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET last_login = %s
                WHERE id = %s
            """, (datetime.utcnow(), user_id))
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
                details={"reason": "invalid_old_password"}
            )
            raise AuthenticationError("Current password is incorrect")
        
        # Hash new password
        new_hash = self.hash_password(new_password)
        
        # Update password
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                UPDATE users 
                SET password_hash = %s, updated_at = %s
                WHERE id = %s
                """,
                (new_hash, datetime.utcnow(), user_id)
            )
            conn.commit()

            # Log password change
            await self.log_audit_event(
                user_id=user_id,
                action="password_changed",
                resource_type="user",
                resource_id=str(user_id),
                details={"method": "self_service"}
            )
            return True
        finally:
            cursor.close()
            conn.close()
    
    # Email Verification
    async def send_verification_email(self, user: User):
        """Send email verification (placeholder implementation)."""
        # TODO: Implement actual email sending
        verification_token = self.generate_secure_token()
        logger.info(f"Verification email would be sent to {user.email} with token: {verification_token}")
        
        # Store verification token in database
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO verification_tokens (user_id, token, token_type, expires_at)
                VALUES (%s, %s, 'email_verification', %s)
            """, (
                user.id,
                verification_token,
                datetime.utcnow() + timedelta(hours=24)
            ))
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()
    
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
        error_message: Optional[str] = None
    ):
        """Log audit event."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Ensure details is JSON serializable for jsonb column
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
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security event."""
        conn = await self.get_db_connection()
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
        conn = await self.get_db_connection(); cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT vt.id, vt.user_id, vt.token_type, vt.expires_at, vt.used, u.verified, u.status
                FROM verification_tokens vt
                JOIN users u ON vt.user_id = u.id
                WHERE vt.token = %s
                """,
                (token,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValidationError("Invalid verification token")
            row_d = dict(row)
            if row_d.get("token_type") != "email_verification":
                raise ValidationError("Token type mismatch")
            if row_d.get("used"):
                # Already used: treat idempotently
                return False
            expires_at = row_d.get("expires_at")
            if expires_at and expires_at < datetime.utcnow():
                await self.log_security_event(
                    event_type="verification_token_expired",
                    severity="low",
                    user_id=row_d.get("user_id"),
                    details={"token": token}
                )
                raise ValidationError("Verification token expired")
            user_id = row_d.get("user_id")
            already_verified = bool(row_d.get("verified"))
            # Mark token used regardless to support one-time consumption semantics
            cursor.execute("UPDATE verification_tokens SET used=true WHERE id=%s", (row_d.get("id"),))
            if already_verified:
                conn.commit()
                return False
            # Activate + verify user
            cursor.execute(
                """
                UPDATE users SET verified=true, status = CASE WHEN status = 'pending_verification' THEN 'active' ELSE status END, updated_at=%s
                WHERE id=%s
                """,
                (datetime.utcnow(), user_id)
            )
            conn.commit()
            await self.log_audit_event(
                user_id=user_id,
                action="email_verified",
                resource_type="user",
                resource_id=str(user_id),
                details={"method": "token"}
            )
            return True
        except ValidationError:
            raise
        except Exception as e:  # pragma: no cover
            logger.error(f"Email verification failed: {e}")
            raise ValidationError("Failed to verify email")
        finally:
            cursor.close(); conn.close()


# FastAPI Dependencies
async def get_auth_manager() -> AuthManager:
    """Get authentication manager instance."""
    settings = get_settings()
    db_url = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    
    # Use a secure JWT secret key
    jwt_secret = getattr(settings, 'JWT_SECRET_KEY', os.getenv('JWT_SECRET_KEY', 'dev-secret-key-change-in-production'))
    
    return AuthManager(db_url, jwt_secret)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_manager: AuthManager = Depends(get_auth_manager)
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


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user (additional validation)."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_permission(permission: PermissionLevel):
    """Decorator to require specific permission."""
    async def permission_dependency(
        current_user: User = Depends(get_current_user),
        auth_manager: AuthManager = Depends(get_auth_manager)
    ) -> User:
        # Get user permissions
        permissions = await auth_manager.get_user_permissions(current_user.id)
        
        if permission.value not in permissions:
            await auth_manager.log_security_event(
                event_type="unauthorized_access",
                severity="medium",
                user_id=current_user.id,
                details={
                    "required_permission": permission.value,
                    "user_permissions": permissions
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required"
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
