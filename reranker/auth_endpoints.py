from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='auth_endpoints',
    log_level='INFO',
    log_file=f'/app/logs/auth_endpoints_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

"""
Authentication endpoints for JWT token management and user authentication.
"""

try:
    import bcrypt
except ImportError as exc:
    raise RuntimeError("bcrypt dependency is required for authentication") from exc

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from reranker.jwt_auth import JWTAuthenticator, User, validate_authentication

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Request/Response Models
class LoginRequest(BaseModel):
    """Login request model."""

    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")

class LoginResponse(BaseModel):
    """Login response model."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    user: dict = Field(..., description="User information")
    expires_in: int = Field(..., description="Token expiration in seconds")
    token_type: str = Field(default="Bearer", description="Token type")

class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""

    refresh_token: str = Field(..., description="Refresh token")

class RefreshTokenResponse(BaseModel):
    """Refresh token response model."""

    access_token: str = Field(..., description="New JWT access token")
    expires_in: int = Field(..., description="Token expiration in seconds")
    token_type: str = Field(default="Bearer", description="Token type")
    user: dict = Field(..., description="Current user information")

class UserResponse(BaseModel):
    """User information response model."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    role: str = Field(..., description="User role (admin, user, viewer)")
    role_id: int = Field(..., description="Numeric role ID")
    role_name: str = Field(..., description="Normalized role name")
    is_active: bool = Field(..., description="User active status")
    password_change_required: bool = Field(..., description="Password change required flag")

class TokenValidationResponse(BaseModel):
    """Token validation response model."""

    valid: bool = Field(..., description="Token validity")
    user: Optional[UserResponse] = Field(None, description="User info if valid")
    expires_in: Optional[int] = Field(None, description="Seconds until expiration")

async def get_authenticated_user(authorization: str = Header(..., alias="Authorization")) -> User:
    """Dependency to get current authenticated user from Authorization header."""
    user, error = validate_authentication(authorization)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Authentication failed",
        )
    return user

# Mock database for demo - replace with real database queries
USERS_DB = {
    "admin@example.com": {
        "id": 1,
        "email": "admin@example.com",
        "password_hash": "hashed_password_123",  # Replace with real hash
        "role": "admin",
        "is_active": True,
    },
    "user@example.com": {
        "id": 2,
        "email": "user@example.com",
        "password_hash": "hashed_password_456",
        "role": "user",
        "is_active": True,
    },
}

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash.

    Args:
        password: Plain text password
        password_hash: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def get_user_from_db(email: str) -> Optional[dict]:
    """Get user from database by email.

    Args:
        email: User email

    Returns:
        User data dict if found, None otherwise
    """
    try:
        from psycopg2.extras import RealDictCursor

        from reranker.cache import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT 
                u.id,
                u.email,
                u.name,
                u.first_name,
                u.last_name,
                u.password_hash,
                u.status,
                u.verified,
                u.password_change_required,
                COALESCE(ur.role_id, u.role_id) as role_id,
                COALESCE(r.name, ro.name) as role_name
            FROM users u
            LEFT JOIN user_roles ur ON u.id = ur.user_id
            LEFT JOIN roles r ON ur.role_id = r.id
            LEFT JOIN roles ro ON u.role_id = ro.id
            WHERE u.email = %s AND u.status = 'active'
            LIMIT 1
        """,
            [email.lower()],
        )
        user_row = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_row:
            role_id = user_row.get("role_id")
            role_name = user_row.get("role_name")
            if not role_id or not role_name:
                logger.warning("User %s missing role assignment", email)
                return None
            return {
                "id": user_row["id"],
                "email": user_row["email"],
                "password_hash": user_row.get("password_hash", ""),
                "role": role_name,
                "role_id": role_id,
                "role_name": role_name,
                "is_active": user_row.get("status") == "active" and user_row.get("verified", False),
                "password_change_required": user_row.get("password_change_required", False),
            }
    except Exception as e:
        logger.error(f"Error querying user {email}: {e}")

        return None


def _normalize_user_payload(user_data: Dict[str, Any]) -> Dict[str, Any]:
    role_name = (user_data.get("role_name") or user_data.get("role") or "employee").lower()
    role_id = user_data.get("role_id")
    if not isinstance(role_id, int):
        role_id = 1 if role_name == "admin" else 2
    return {
        "id": user_data["id"],
        "email": user_data["email"],
        "role": user_data.get("role") or role_name,
        "role_id": role_id,
        "role_name": role_name,
        "is_active": user_data.get("is_active", True),
        "password_change_required": bool(user_data.get("password_change_required", False)),
    }


def _user_response_from_data(user_data: Dict[str, Any]) -> UserResponse:
    return UserResponse(**_normalize_user_payload(user_data))

@router.post("/login", response_model=LoginResponse, operation_id="auth_login")
async def login(request: LoginRequest) -> LoginResponse:
    """Login endpoint to generate JWT tokens.

    Args:
        request: Login credentials

    Returns:
        Access token, refresh token, and user info

    Raises:
        HTTPException: If credentials invalid
    """
    user_data = get_user_from_db(request.email)

    if not user_data or not verify_password(request.password, user_data["password_hash"]):
        logger.warning(f"Failed login attempt for {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user_data.get("is_active"):
        logger.warning(f"Login attempt for inactive user {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # Generate tokens
    access_token = JWTAuthenticator.generate_token(
        user_id=user_data["id"],
        email=user_data["email"],
        role=user_data["role"],
    )
    refresh_token = JWTAuthenticator.generate_refresh_token(
        user_id=user_data["id"],
        email=user_data["email"],
        role=user_data["role"],
    )

    logger.info(f"User logged in: {request.email}")
    user_payload = _normalize_user_payload(user_data)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_payload,
        expires_in=24 * 60 * 60,  # 24 hours
    )

@router.post("/refresh", response_model=RefreshTokenResponse, operation_id="auth_refresh_token")
async def refresh_token(request: RefreshTokenRequest) -> RefreshTokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Refresh token

    Returns:
        New access token

    Raises:
        HTTPException: If refresh token invalid
    """
    payload = JWTAuthenticator.validate_token(request.refresh_token)
    if not payload or payload.get("type") != "refresh":
        logger.warning("Failed refresh token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_data = get_user_from_db(payload["email"])
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    new_token = JWTAuthenticator.generate_token(
        user_id=user_data["id"],
        email=user_data["email"],
        role=user_data["role"],
    )

    logger.debug("Token refreshed successfully")

    user_payload = _normalize_user_payload(user_data)

    return RefreshTokenResponse(
        access_token=new_token,
        expires_in=24 * 60 * 60,  # 24 hours
        user=user_payload,
    )

@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(authorization: Optional[str] = None) -> TokenValidationResponse:
    """Validate JWT token and return user info.

    Args:
        authorization: Authorization header value

    Returns:
        Token validity and user info if valid
    """
    if not authorization:
        return TokenValidationResponse(
            valid=False,
            user=None,
            expires_in=None,
        )

    user, error = validate_authentication(authorization)

    if not user:
        logger.debug(f"Token validation failed: {error}")
        return TokenValidationResponse(
            valid=False,
            user=None,
            expires_in=None,
        )

    user_data = get_user_from_db(user.email)
    if not user_data:
        user_data = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
        }

    return TokenValidationResponse(
        valid=True,
        user=_user_response_from_data(user_data),
        expires_in=24 * 60 * 60,  # TODO: Calculate actual expiration
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user(user: User = Depends(get_authenticated_user)) -> UserResponse:
    """Get current authenticated user information.

    Args:
        user: Current authenticated user (from dependency)

    Returns:
        Current user information

    Raises:
        HTTPException: If not authenticated
    """
    user_data = get_user_from_db(user.email)
    if not user_data:
        user_data = {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "password_change_required": False,
        }

    return _user_response_from_data(user_data)
