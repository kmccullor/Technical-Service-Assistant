from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='rbac_endpoints',
    log_level='INFO',
    log_file=f'/app/logs/rbac_endpoints_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

#!/usr/bin/env python3
"""RBAC Authentication Endpoints.

Clean implementation of authentication and password management endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from utils.auth_system import AuthenticationError, AuthSystem, ValidationError, get_auth_manager, get_current_user
from utils.rbac_models import (
    APIResponse,
    ConfirmPasswordResetRequest,
    CreateUserRequest,
    LoginRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
rbac_router = router

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "auth"

@router.get("/health")
async def health(auth: AuthSystem = Depends(get_auth_manager)):
    result = await auth.health_check()
    return result

@router.post("/register", response_model=UserResponse)
async def register(user: CreateUserRequest, auth: AuthSystem = Depends(get_auth_manager)) -> UserResponse:
    try:
        created = await auth.create_user(user)
        return UserResponse(
            id=created.id or 0,
            email=created.email,
            first_name=created.first_name,
            last_name=created.last_name,
            full_name=created.full_name,
            role_id=created.role_id,
            role_name=None,
            status=created.status,
            verified=created.verified,
            last_login=created.last_login,
            is_active=created.is_active,
            is_locked=created.is_locked,
            password_change_required=getattr(created, "password_change_required", True),
            created_at=created.created_at or __import__("datetime").datetime.utcnow(),
            updated_at=created.updated_at or __import__("datetime").datetime.utcnow(),
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # pragma: no cover
        logger.exception("Registration failed for %s", getattr(user, "email", "<unknown>"))
        raise HTTPException(status_code=500, detail="Registration failed") from e

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest, request: Request, auth: AuthSystem = Depends(get_auth_manager)
) -> TokenResponse:
    try:
        token_response = await auth.authenticate_user(
            credentials.email, credentials.password, request.client.host if request.client else None
        )
        return token_response
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Login failed") from e

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshTokenRequest, auth: AuthSystem = Depends(get_auth_manager)) -> TokenResponse:
    """Refresh access token using a valid refresh token.

    Returns new access token (refresh token reused) or 401 if invalid/expired.
    """
    try:
        return await auth.refresh_access_token(req.refresh_token)
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Token refresh failed") from e

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=8)

class VerifyEmailResponse(BaseModel):
    success: bool
    message: str
    verified: bool

@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(req: VerifyEmailRequest, auth: AuthSystem = Depends(get_auth_manager)) -> VerifyEmailResponse:
    """Verify a user's email using a one-time token.

    Returns success status; if token was already used but user is verified,
    returns success with verified=True for idempotency.
    """
    try:
        result = await auth.verify_email_token(req.token)
        if result:
            return VerifyEmailResponse(success=True, message="Email verified", verified=True)
        # result False means token used or already verified
        return VerifyEmailResponse(
            success=True, message="Token already consumed or user already verified", verified=True
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Verification failed") from e

@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user), auth: AuthSystem = Depends(get_auth_manager)) -> UserResponse:  # type: ignore
    """Return the current authenticated user's profile.

    Uses the JWT via get_current_user dependency. Augments with role name if available.
    """
    try:
        role_name = await auth.get_role_name(current_user.role_id)

        return UserResponse(
            id=current_user.id,
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            full_name=current_user.full_name,
            role_id=current_user.role_id,
            role_name=role_name,
            status=current_user.status,
            verified=current_user.verified,
            last_login=current_user.last_login,
            is_active=current_user.is_active,
            is_locked=current_user.is_locked,
            password_change_required=current_user.password_change_required,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Failed to load profile") from e

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: Optional[str] = None

@router.post("/change-password", response_model=APIResponse)
async def change_password(
    payload: ChangePasswordRequest, current_user=Depends(get_current_user), auth: AuthSystem = Depends(get_auth_manager)
) -> APIResponse:
    try:
        if payload.confirm_password and payload.new_password != payload.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")
        success = await auth.change_password(current_user.id, payload.current_password, payload.new_password)
        if success:
            return APIResponse(success=True, message="Password changed successfully")
        raise HTTPException(status_code=400, detail="Failed to change password")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Password change failed") from e

class ForceChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: Optional[str] = None

@router.post("/force-change-password", response_model=APIResponse)
async def force_change_password(
    payload: ForceChangePasswordRequest,
    current_user=Depends(get_current_user),
    auth: AuthSystem = Depends(get_auth_manager),
) -> APIResponse:
    try:
        if not current_user.password_change_required:
            # Idempotent: treat as success so clients/tests can re-run safely
            return APIResponse(success=True, message="Password change not required")
        if payload.confirm_password and payload.new_password != payload.confirm_password:
            raise HTTPException(status_code=400, detail="Passwords do not match")
        success = await auth.force_password_change(current_user.id, payload.new_password)
        if success:
            return APIResponse(success=True, message="Password changed successfully")
        raise HTTPException(status_code=400, detail="Failed to change password")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Password change failed") from e

@router.post("/forgot-password", response_model=APIResponse)
async def forgot_password(payload: ResetPasswordRequest, auth: AuthSystem = Depends(get_auth_manager)) -> APIResponse:
    """Initiate password reset by emailing a one-time token."""
    try:
        dispatched = await auth.initiate_password_reset(payload.email)
    except Exception as exc:
        logger.exception("Failed to initiate password reset for %s", payload.email)
        raise HTTPException(status_code=500, detail="Failed to process password reset request") from exc

    message = "If an account exists for that email, you'll receive password reset instructions shortly."
    return APIResponse(success=True, message=message, data={"email_dispatched": dispatched})

@router.post("/reset-password", response_model=APIResponse)
async def reset_password(
    payload: ConfirmPasswordResetRequest, auth: AuthSystem = Depends(get_auth_manager)
) -> APIResponse:
    """Complete password reset using a previously issued token."""
    try:
        await auth.confirm_password_reset(payload.token, payload.new_password)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to complete password reset")
        raise HTTPException(status_code=500, detail="Failed to reset password") from exc

    return APIResponse(success=True, message="Password reset successfully", data={"reset": True})

class AdminResetPasswordRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    new_password: str = Field(..., min_length=8, max_length=128)
    rotate: bool = Field(True)

class AdminResetPasswordResponse(APIResponse):
    rotated: bool = False
    target_user_id: int = 0

@router.post("/admin-reset", response_model=AdminResetPasswordResponse)
async def admin_reset_password(
    payload: AdminResetPasswordRequest,
    current_user=Depends(get_current_user),
    auth: AuthSystem = Depends(get_auth_manager),
) -> AdminResetPasswordResponse:
    try:
        # Verify admin
        role_name = await auth.get_role_name(current_user.role_id)
        if role_name != "admin":
            raise HTTPException(status_code=403, detail="Admin privileges required")
        # Perform reset
        reset_method = getattr(auth, "admin_reset_password", None)
        success = False
        if callable(reset_method):
            result = reset_method(payload.user_id, payload.new_password, force_change=payload.rotate)
            if hasattr(result, "__await__"):
                success = await result  # type: ignore
            else:
                success = bool(result)
        else:
            success = await auth.force_password_change(payload.user_id, payload.new_password)
            if success and payload.rotate:
                await auth.set_password_change_required(payload.user_id, True)
        if not success:
            raise HTTPException(status_code=400, detail="Password reset failed")
        return AdminResetPasswordResponse(
            success=True, message="Password reset", rotated=payload.rotate, target_user_id=payload.user_id
        )
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Admin password reset failed") from e
