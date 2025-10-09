#!/usr/bin/env python3
"""
RBAC API Endpoints

FastAPI router for Role-Based Access Control endpoints including:
- Authentication (login, register, password management)
- User management (CRUD operations, role assignments)
- Role and permission management
- Admin operations and system monitoring
- Security audit logs and analytics

Usage:
    from rbac_endpoints import rbac_router
    app.include_router(rbac_router, prefix="/api/auth")
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

from utils.rbac_models import (
    User, Role, Permission, CreateUserRequest, UpdateUserRequest,
    LoginRequest, TokenResponse, ChangePasswordRequest, 
    ResetPasswordRequest, ConfirmPasswordResetRequest,
    UserResponse, RoleResponse, PermissionResponse,
    CreateRoleRequest, UpdateRoleRequest, CreatePermissionRequest,
    RoleAssignmentRequest, PermissionCheckRequest, PermissionCheckResponse,
    BulkUserOperation, BulkOperationResponse, APIResponse, ErrorResponse,
    PermissionLevel, UserStatus, PaginatedResponse
)
from utils.auth_system import (
    AuthManager, get_current_user, get_current_active_user,
    get_auth_manager, require_permission, require_admin, require_user_management
)
from utils.rbac_middleware import (
    RBACManager, get_rbac_manager, require_permissions,
    require_role, require_admin as middleware_require_admin,
    require_user_management as middleware_require_user_management
)
from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
rbac_router = APIRouter()
security = HTTPBearer()


# Helper functions
def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


# Authentication Endpoints
@rbac_router.post("/login", response_model=TokenResponse, tags=["Authentication"])
async def login(
    login_data: LoginRequest,
    request: Request,
    auth_manager: AuthManager = Depends(get_auth_manager)
):
    """Authenticate user and return JWT tokens."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    
    try:
        token_response = await auth_manager.authenticate_user(
            login_data.email,
            login_data.password,
            client_ip
        )
        
        return token_response
        
    except Exception as e:
        logger.error(f"Login failed for {login_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )


@rbac_router.post("/register", response_model=APIResponse, tags=["Authentication"])
async def register(
    user_data: CreateUserRequest,
    request: Request,
    auth_manager: AuthManager = Depends(get_auth_manager),
    current_user: User = Depends(require_user_management())
):
    """Register a new user account (admin only)."""
    client_ip = get_client_ip(request)
    
    try:
        user = await auth_manager.create_user(user_data, current_user.id)
        
        return APIResponse(
            success=True,
            message="User created successfully",
            data={
                "user_id": user.id,
                "email": user.email,
                "verification_required": not user.verified
            }
        )
        
    except Exception as e:
        logger.error(f"User registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@rbac_router.post("/refresh", response_model=TokenResponse, tags=["Authentication"])
async def refresh_token(
    refresh_token_request: dict,
    auth_manager: AuthManager = Depends(get_auth_manager)
):
    """Refresh access token using refresh token."""
    try:
        refresh_token = refresh_token_request.get("refresh_token")
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token required"
            )
        
        token_response = await auth_manager.refresh_access_token(refresh_token)
        return token_response
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@rbac_router.post("/change-password", response_model=APIResponse, tags=["Authentication"])
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    auth_manager: AuthManager = Depends(get_auth_manager)
):
    """Change user password."""
    try:
        success = await auth_manager.change_password(
            current_user.id,
            password_data.current_password,
            password_data.new_password
        )
        
        if success:
            return APIResponse(
                success=True,
                message="Password changed successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to change password"
            )
            
    except Exception as e:
        logger.error(f"Password change failed for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@rbac_router.post("/reset-password", response_model=APIResponse, tags=["Authentication"])
async def reset_password(
    reset_data: ResetPasswordRequest,
    auth_manager: AuthManager = Depends(get_auth_manager)
):
    """Request password reset."""
    try:
        # TODO: Implement password reset functionality
        return APIResponse(
            success=True,
            message="Password reset instructions sent to your email"
        )
        
    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process password reset request"
        )


# User Management Endpoints
@rbac_router.get("/users", response_model=PaginatedResponse, tags=["User Management"])
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    role_id: Optional[int] = Query(None),
    status: Optional[UserStatus] = Query(None),
    current_user: User = Depends(require_user_management()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Get paginated list of users with filtering."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        # Build query with filters
        where_conditions = []
        params = []
        
        if search:
            where_conditions.append("(u.email ILIKE %s OR u.first_name ILIKE %s OR u.last_name ILIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if role_id:
            where_conditions.append("u.role_id = %s")
            params.append(role_id)
        
        if status:
            where_conditions.append("u.status = %s")
            params.append(status.value)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*)
            FROM users u
            {where_clause}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()['count']
        
        # Get paginated users
        offset = (page - 1) * page_size
        users_query = f"""
            SELECT u.id, u.email, u.first_name, u.last_name, u.role_id,
                   u.status, u.verified, u.last_login, u.created_at, u.updated_at,
                   r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            {where_clause}
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])
        cursor.execute(users_query, params)
        
        users = []
        for row in cursor.fetchall():
            user_dict = dict(row)
            user_response = UserResponse(
                id=user_dict['id'],
                email=user_dict['email'],
                first_name=user_dict['first_name'],
                last_name=user_dict['last_name'],
                full_name=f"{user_dict['first_name'] or ''} {user_dict['last_name'] or ''}".strip() or user_dict['email'],
                role_id=user_dict['role_id'],
                role_name=user_dict['role_name'],
                status=UserStatus(user_dict['status']),
                verified=user_dict['verified'],
                last_login=user_dict['last_login'],
                is_active=user_dict['status'] == UserStatus.ACTIVE.value and user_dict['verified'],
                is_locked=False,  # TODO: Implement lock checking
                created_at=user_dict['created_at'],
                updated_at=user_dict['updated_at']
            )
            users.append(user_response)
        
        total_pages = (total + page_size - 1) // page_size
        
        return PaginatedResponse(
            items=users,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
        
    finally:
        cursor.close()
        conn.close()


@rbac_router.get("/users/{user_id}", response_model=UserResponse, tags=["User Management"])
async def get_user(
    user_id: int,
    current_user: User = Depends(require_user_management()),
    auth_manager: AuthManager = Depends(get_auth_manager)
):
    """Get user by ID."""
    try:
        user = await auth_manager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )


@rbac_router.put("/users/{user_id}", response_model=APIResponse, tags=["User Management"])
async def update_user(
    user_id: int,
    user_data: UpdateUserRequest,
    current_user: User = Depends(require_user_management()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Update user information."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        # Build update query
        update_fields = []
        params = []
        
        if user_data.first_name is not None:
            update_fields.append("first_name = %s")
            params.append(user_data.first_name)
        
        if user_data.last_name is not None:
            update_fields.append("last_name = %s")
            params.append(user_data.last_name)
        
        if user_data.role_id is not None:
            # Validate role exists
            cursor.execute("SELECT id FROM roles WHERE id = %s", (user_data.role_id,))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid role ID"
                )
            update_fields.append("role_id = %s")
            params.append(user_data.role_id)
        
        if user_data.status is not None:
            update_fields.append("status = %s")
            params.append(user_data.status.value)
        
        if user_data.preferences is not None:
            update_fields.append("preferences = %s")
            params.append(user_data.preferences)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("updated_at = %s")
        params.append(datetime.utcnow())
        params.append(user_id)
        
        update_query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, params)
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        conn.commit()
        
        # Invalidate user cache
        await rbac_manager.invalidate_user_cache(user_id)
        
        return APIResponse(
            success=True,
            message="User updated successfully"
        )
        
    finally:
        cursor.close()
        conn.close()


@rbac_router.delete("/users/{user_id}", response_model=APIResponse, tags=["User Management"])
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Delete user (admin only)."""
    try:
        # Don't allow users to delete themselves
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Delete user (cascade will handle related records)
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        
        # Log user deletion
        await rbac_manager.log_audit_event(
            user_id=current_user.id,
            action="user_deleted",
            resource_type="user",
            resource_id=str(user_id),
            details={"deleted_user_email": user_row['email']}
        )
        
        return APIResponse(
            success=True,
            message="User deleted successfully"
        )
        
    finally:
        cursor.close()
        conn.close()


# Role Management Endpoints
@rbac_router.get("/roles", response_model=List[RoleResponse], tags=["Role Management"])
async def get_roles(
    current_user: User = Depends(require_user_management()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Get all roles."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.id, r.name, r.description, r.is_system_role, r.created_at, r.updated_at,
                   COUNT(u.id) as user_count
            FROM roles r
            LEFT JOIN users u ON r.id = u.role_id
            GROUP BY r.id, r.name, r.description, r.is_system_role, r.created_at, r.updated_at
            ORDER BY r.name
        """)
        
        roles = []
        for row in cursor.fetchall():
            role_dict = dict(row)
            
            # Get permissions for this role
            cursor.execute("""
                SELECT p.name
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id = %s
            """, (role_dict['id'],))
            
            permissions = [perm_row['name'] for perm_row in cursor.fetchall()]
            
            role_response = RoleResponse(
                id=role_dict['id'],
                name=role_dict['name'],
                description=role_dict['description'],
                permissions=permissions,
                is_system_role=role_dict['is_system_role'],
                user_count=role_dict['user_count'],
                created_at=role_dict['created_at'],
                updated_at=role_dict['updated_at']
            )
            roles.append(role_response)
        
        return roles
        
    finally:
        cursor.close()
        conn.close()


@rbac_router.post("/roles", response_model=APIResponse, tags=["Role Management"])
async def create_role(
    role_data: CreateRoleRequest,
    current_user: User = Depends(require_admin()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Create new role (admin only)."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        # Check if role already exists
        cursor.execute("SELECT id FROM roles WHERE name = %s", (role_data.name,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role with this name already exists"
            )
        
        # Create role
        cursor.execute("""
            INSERT INTO roles (name, description, is_system_role, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            role_data.name,
            role_data.description,
            False,  # New roles are not system roles
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        role_id = cursor.fetchone()['id']
        
        # Assign permissions to role
        if role_data.permissions:
            for permission in role_data.permissions:
                cursor.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT %s, p.id
                    FROM permissions p
                    WHERE p.name = %s
                """, (role_id, permission.value))
        
        conn.commit()
        
        # Log role creation
        await rbac_manager.log_audit_event(
            user_id=current_user.id,
            action="role_created",
            resource_type="role",
            resource_id=str(role_id),
            details={
                "role_name": role_data.name,
                "permissions": [p.value for p in role_data.permissions]
            }
        )
        
        return APIResponse(
            success=True,
            message="Role created successfully",
            data={"role_id": role_id}
        )
        
    finally:
        cursor.close()
        conn.close()


# Permission Management Endpoints
@rbac_router.get("/permissions", response_model=List[PermissionResponse], tags=["Permission Management"])
async def get_permissions(
    current_user: User = Depends(require_user_management()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Get all permissions."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, resource, action, created_at, updated_at
            FROM permissions
            ORDER BY resource, name
        """)
        
        permissions = []
        for row in cursor.fetchall():
            perm_dict = dict(row)
            permission = PermissionResponse(
                id=perm_dict['id'],
                name=perm_dict['name'],
                description=perm_dict['description'],
                resource=perm_dict['resource'],
                action=PermissionLevel(perm_dict['action']) if perm_dict['action'] in [p.value for p in PermissionLevel] else perm_dict['action'],
                created_at=perm_dict['created_at'],
                updated_at=perm_dict['updated_at']
            )
            permissions.append(permission)
        
        return permissions
        
    finally:
        cursor.close()
        conn.close()


@rbac_router.post("/check-permission", response_model=PermissionCheckResponse, tags=["Permission Management"])
async def check_permission(
    permission_request: PermissionCheckRequest,
    current_user: User = Depends(get_current_user),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Check if user has specific permission."""
    try:
        # Only admins or the user themselves can check permissions
        if current_user.id != permission_request.user_id:
            user_permissions = await rbac_manager.get_user_permissions(current_user.id)
            if 'admin' not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only check your own permissions"
                )
        
        result = await rbac_manager.check_permission(
            permission_request.user_id,
            permission_request.permission.value,
            permission_request.resource
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Permission check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check permission"
        )


# Profile Management
@rbac_router.get("/profile", response_model=UserResponse, tags=["Profile"])
async def get_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=current_user.full_name,
        role_id=current_user.role_id,
        status=current_user.status,
        verified=current_user.verified,
        last_login=current_user.last_login,
        is_active=current_user.is_active,
        is_locked=current_user.is_locked,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


@rbac_router.put("/profile", response_model=APIResponse, tags=["Profile"])
async def update_profile(
    profile_data: UpdateUserRequest,
    current_user: User = Depends(get_current_active_user),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Update current user profile."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        # Build update query (excluding role_id and status for profile updates)
        update_fields = []
        params = []
        
        if profile_data.first_name is not None:
            update_fields.append("first_name = %s")
            params.append(profile_data.first_name)
        
        if profile_data.last_name is not None:
            update_fields.append("last_name = %s")
            params.append(profile_data.last_name)
        
        if profile_data.preferences is not None:
            update_fields.append("preferences = %s")
            params.append(profile_data.preferences)
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("updated_at = %s")
        params.append(datetime.utcnow())
        params.append(current_user.id)
        
        update_query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, params)
        conn.commit()
        
        return APIResponse(
            success=True,
            message="Profile updated successfully"
        )
        
    finally:
        cursor.close()
        conn.close()


# System Status
@rbac_router.get("/system/status", response_model=Dict[str, Any], tags=["System"])
async def get_system_status(
    current_user: User = Depends(require_admin()),
    rbac_manager: RBACManager = Depends(get_rbac_manager)
):
    """Get system status (admin only)."""
    try:
        conn = await rbac_manager.get_db_connection()
        cursor = conn.cursor()
        
        # Get user counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM users
            GROUP BY status
        """)
        user_stats = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Get role counts
        cursor.execute("SELECT COUNT(*) as count FROM roles")
        role_count = cursor.fetchone()['count']
        
        # Get permission counts  
        cursor.execute("SELECT COUNT(*) as count FROM permissions")
        permission_count = cursor.fetchone()['count']
        
        # Get recent audit events
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM audit_logs
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        recent_audit_events = cursor.fetchone()['count']
        
        # Get security events
        cursor.execute("""
            SELECT severity, COUNT(*) as count
            FROM security_events
            WHERE created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY severity
        """)
        security_events = {row['severity']: row['count'] for row in cursor.fetchall()}
        
        return {
            "system_health": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "users": user_stats,
                "roles": role_count,
                "permissions": permission_count,
                "recent_audit_events_24h": recent_audit_events,
                "security_events_24h": security_events
            }
        }
        
    finally:
        cursor.close()
        conn.close()