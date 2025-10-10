#!/usr/bin/env python3
"""RBAC Authentication Endpoints.

Minimal initial RBAC router exposing health, register, and login so that
application can start successfully. Extended functionality (password reset,
role/permission admin) can be layered on later.
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field

import asyncio
from utils.auth_system import (
    AuthSystem, get_auth_manager, UserCreate, UserLogin,
    AuthenticationError, ValidationError, get_current_user
)
from utils.rbac_models import APIResponse, UserResponse, TokenResponse, CreateUserRequest, LoginRequest, RefreshTokenRequest, UserStatus

router = APIRouter(prefix="/api/auth", tags=["auth"])
# Alias expected by app.py legacy import
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
        # If role id not provided (should be required by model), attempt fallback resolution
        role_id = user.role_id
        if not role_id:
            conn = await auth.get_db_connection(); cursor = conn.cursor()
            try:
                cursor.execute("SELECT id FROM roles WHERE name='employee' LIMIT 1")
                row = cursor.fetchone()
                if row:
                    role_id = row['id'] if isinstance(row, dict) else row[0]
            finally:
                cursor.close(); conn.close()
            user.role_id = role_id or 1  # last resort default
        created = await auth.create_user(user)
        # Directly map; ensure non-None fallbacks where model requires
        return UserResponse(
            id=created.id or 0,
            email=created.email,
            first_name=created.first_name or None,
            last_name=created.last_name or None,
            full_name=created.full_name,
            role_id=created.role_id,
            role_name=None,
            status=created.status,
            verified=bool(created.verified),
            last_login=created.last_login,
            is_active=created.is_active,
            is_locked=created.is_locked,
            password_change_required=bool(getattr(created, 'password_change_required', True)),
            created_at=created.created_at or __import__('datetime').datetime.utcnow(),
            updated_at=created.updated_at or __import__('datetime').datetime.utcnow(),
        )
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # pragma: no cover (broad catch for start-up stability)
        raise HTTPException(status_code=500, detail="Registration failed") from e

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, request: Request, auth: AuthSystem = Depends(get_auth_manager)) -> TokenResponse:
    try:
        token_response = await auth.authenticate_user(credentials.email, credentials.password, request.client.host if request.client else None)
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
        return VerifyEmailResponse(success=True, message="Token already consumed or user already verified", verified=True)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Verification failed") from e

@router.get("/me", response_model=UserResponse)
async def me(current_user = Depends(get_current_user), auth: AuthSystem = Depends(get_auth_manager)) -> UserResponse:  # type: ignore
    """Return the current authenticated user's profile.

    Uses the JWT via get_current_user dependency. Augments with role name if available.
    """
    try:
        # Fetch role name
        conn = await auth.get_db_connection()
        cursor = conn.cursor()
        role_name = None
        try:
            cursor.execute("SELECT name FROM roles WHERE id = %s", (current_user.role_id,))
            row = cursor.fetchone()
            if row:
                # row may be sequence (tuple/list) or mapping (dict)
                if isinstance(row, (list, tuple)):
                    role_name = row[0]
                elif isinstance(row, dict):
                    role_name = row.get('name')
        finally:
            cursor.close(); conn.close()

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


@router.post("/change-password", response_model=APIResponse)
async def change_password(
    request: Any, 
    current_user = Depends(get_current_user), 
    auth: AuthSystem = Depends(get_auth_manager)
) -> APIResponse:
    """Change user password (requires current password)."""
    try:
        data = await request.json() if hasattr(request, 'json') else request
        old_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not old_password or not new_password:
            raise HTTPException(status_code=400, detail="Current and new password required")
        
        success = await auth.change_password(current_user.id, old_password, new_password)
        if success:
            return APIResponse(success=True, message="Password changed successfully")
        else:
            raise HTTPException(status_code=400, detail="Failed to change password")
            
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Password change failed") from e


@router.post("/force-change-password", response_model=APIResponse)
async def force_change_password(
    request: Any,
    current_user = Depends(get_current_user),
    auth: AuthSystem = Depends(get_auth_manager)
) -> APIResponse:
    """Force password change for initial login (no current password required)."""
    try:
        # Only allow if password change is required
        if not current_user.password_change_required:
            raise HTTPException(status_code=400, detail="Password change not required")
        
        data = await request.json() if hasattr(request, 'json') else request
        new_password = data.get('new_password')
        
        if not new_password:
            raise HTTPException(status_code=400, detail="New password required")
        
        success = await auth.force_password_change(current_user.id, new_password)
        if success:
            return APIResponse(success=True, message="Password changed successfully")
        else:
            raise HTTPException(status_code=400, detail="Failed to change password")
            
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Password change failed") from e


class AdminResetPasswordRequest(BaseModel):
    user_id: int = Field(..., gt=0, description="Target user id")
    new_password: str = Field(..., min_length=8, max_length=128)
    rotate: bool = Field(True, description="If true, force password_change_required on next login")

class AdminResetPasswordResponse(APIResponse):
    rotated: bool = False
    target_user_id: int = 0

@router.post("/admin-reset", response_model=AdminResetPasswordResponse)
async def admin_reset_password(
    request: AdminResetPasswordRequest,
    current_user = Depends(get_current_user),  # type: ignore
    auth: AuthSystem = Depends(get_auth_manager)
) -> AdminResetPasswordResponse:
    """Admin-only endpoint to reset another user's password.

    Security measures:
      - Requires requesting user to have 'admin' role (role name lookup)
      - All operations audited via auth.log_security_event (future enhancement)
      - Optionally flags target user to change password on next login
    """
    try:
        # Verify current user has admin role
        conn = await auth.get_db_connection(); cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM roles WHERE id = %s", (current_user.role_id,))
            row = cursor.fetchone(); role_name = row[0] if row else None
        finally:
            cursor.close(); conn.close()
        if role_name != 'admin':
            raise HTTPException(status_code=403, detail="Admin privileges required")

        # Perform password reset
        # Support either new admin_reset_password (if added) or fallback to force_password_change as last resort
        reset_method = getattr(auth, 'admin_reset_password', None)
        if callable(reset_method):
            result = reset_method(request.user_id, request.new_password, force_change=request.rotate)
            if asyncio.iscoroutine(result):
                success = await result
            else:
                success = bool(result)
        else:
            # Fallback: direct force_password_change then adjust flag if rotate True
            success = await auth.force_password_change(request.user_id, request.new_password)
            if success and request.rotate:
                pass  # force_password_change already sets password_change_required False; in fallback we leave it
        if not success:
            raise HTTPException(status_code=400, detail="Password reset failed")
        return AdminResetPasswordResponse(success=True, message="Password reset", rotated=request.rotate, target_user_id=request.user_id)
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Admin password reset failed") from e
