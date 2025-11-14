"""
Authentication endpoints for JWT token management and user authentication.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from reranker.jwt_auth import JWTAuthenticator, User, validate_authentication

logger = logging.getLogger(__name__)

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


class UserResponse(BaseModel):
    """User information response model."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    role: str = Field(..., description="User role (admin, user, viewer)")
    is_active: bool = Field(..., description="User active status")


class TokenValidationResponse(BaseModel):
    """Token validation response model."""

    valid: bool = Field(..., description="Token validity")
    user: Optional[UserResponse] = Field(None, description="User info if valid")
    expires_in: Optional[int] = Field(None, description="Seconds until expiration")


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
    try:
        import bcrypt

        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ImportError:
        # Fallback for demo
        return password == password_hash


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
            SELECT id, email, name, first_name, last_name, password_hash, role_id, status, verified, is_active
            FROM users
            WHERE email = %s AND status = 'active'
        """,
            [email.lower()],
        )
        user_row = cursor.fetchone()
        cursor.close()
        conn.close()

        if user_row:
            return {
                "id": user_row["id"],
                "email": user_row["email"],
                "password_hash": user_row.get("password_hash", ""),
                "role": "admin" if user_row.get("role_id") == 1 else "employee",
                "is_active": user_row.get("status") == "active" and user_row.get("verified", False),
            }
    except Exception as e:
        logger.error(f"Error querying user {email}: {e}")

    return None


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
    )

    logger.info(f"User logged in: {request.email}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user_data["id"],
            "email": user_data["email"],
            "role": user_data["role"],
        },
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
    new_token = JWTAuthenticator.refresh_access_token(request.refresh_token)

    if not new_token:
        logger.warning("Failed refresh token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    logger.debug("Token refreshed successfully")

    return RefreshTokenResponse(
        access_token=new_token,
        expires_in=24 * 60 * 60,  # 24 hours
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

    return TokenValidationResponse(
        valid=True,
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        ),
        expires_in=24 * 60 * 60,  # TODO: Calculate actual expiration
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: User = Depends(validate_authentication)) -> UserResponse:
    """Get current authenticated user information.

    Args:
        user: Current authenticated user (from dependency)

    Returns:
        Current user information

    Raises:
        HTTPException: If not authenticated
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )
