#!/usr/bin/env python3
"""
RBAC Data Models

Comprehensive Pydantic models for Role-Based Access Control system.
Provides data validation, serialization, and type safety for all RBAC entities.

Features:
- User management with secure password handling
- Role-based permissions with hierarchical support
- JWT token models with security validation
- Audit logging models for security compliance
- Database integration models for PostgreSQL

Usage:
    from utils.rbac_models import User, Role, Permission, CreateUserRequest
    
    user = User(email="admin@example.com", role_id=1, verified=True)
    role = Role(name="admin", permissions=["read", "write", "admin"])
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, EmailStr, validator
from pydantic import model_validator
from enum import Enum
import re


class PermissionLevel(str, Enum):
    """Permission levels for granular access control."""
    READ = "read"
    WRITE = "write" 
    ADMIN = "admin"
    DELETE = "delete"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    SYSTEM_CONFIG = "system_config"
    EXPORT_DATA = "export_data"
    VIEW_ANALYTICS = "view_analytics"


class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class RoleType(str, Enum):
    """Built-in role types with predefined permissions."""
    ADMIN = "admin"
    EMPLOYEE = "employee"
    GUEST = "guest"
    SYSTEM = "system"


# Base Models
class TimestampedModel(BaseModel):
    """Base model with timestamp fields."""
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


# Permission Models
class Permission(TimestampedModel):
    """Permission entity model."""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    resource: str = Field(..., min_length=1, max_length=100)
    action: PermissionLevel
    
    @validator('name')
    def validate_permission_name(cls, v):
        """Validate permission name format."""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Permission name must contain only alphanumeric characters and underscores')
        return v.lower()

    class Config:
        from_attributes = True


class CreatePermissionRequest(BaseModel):
    """Request model for creating permissions."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    resource: str = Field(..., min_length=1, max_length=100)
    action: PermissionLevel


class PermissionResponse(BaseModel):
    """Response model for permission data."""
    id: int
    name: str
    description: Optional[str]
    resource: str
    action: PermissionLevel
    created_at: datetime
    updated_at: datetime


# Role Models
class Role(TimestampedModel):
    """Role entity model."""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    permissions: List[str] = Field(default_factory=list)
    is_system_role: bool = Field(default=False)
    
    @validator('name')
    def validate_role_name(cls, v):
        """Validate role name format."""
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', v):
            raise ValueError('Role name contains invalid characters')
        return v.lower()
    
    @validator('permissions')
    def validate_permissions(cls, v):
        """Validate permission format."""
        valid_permissions = [p.value for p in PermissionLevel]
        for perm in v:
            if perm not in valid_permissions:
                raise ValueError(f'Invalid permission: {perm}')
        return list(set(v))  # Remove duplicates

    class Config:
        from_attributes = True


class CreateRoleRequest(BaseModel):
    """Request model for creating roles."""
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    permissions: List[PermissionLevel] = Field(default_factory=list)


class UpdateRoleRequest(BaseModel):
    """Request model for updating roles."""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    permissions: Optional[List[PermissionLevel]] = None


class RoleResponse(BaseModel):
    """Response model for role data."""
    id: int
    name: str
    description: Optional[str]
    permissions: List[str]
    is_system_role: bool
    user_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime


# User Models
class User(TimestampedModel):
    """User entity model."""
    id: Optional[int] = None
    email: EmailStr
    password_hash: Optional[str] = Field(None, exclude=True)  # Never serialize password hash
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role_id: int
    status: UserStatus = Field(default=UserStatus.PENDING_VERIFICATION)
    verified: bool = Field(default=False)
    last_login: Optional[datetime] = None
    login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('email')
    def validate_email(cls, v):
        """Additional email validation."""
        # Convert to lowercase for consistency
        return v.lower()
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email
    
    @property
    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False
    
    @property
    def is_active(self) -> bool:
        """Check if user account is active."""
        return (
            self.status == UserStatus.ACTIVE and 
            self.verified and 
            not self.is_locked
        )

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    """Request model for user creation."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role_id: int = Field(..., gt=0)
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UpdateUserRequest(BaseModel):
    """Request model for user updates."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role_id: Optional[int] = Field(None, gt=0)
    status: Optional[UserStatus] = None
    preferences: Optional[Dict[str, Any]] = None


class ChangePasswordRequest(BaseModel):
    """Request model for password changes."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    
    @model_validator(mode='after')
    def validate_password_match(self):  # type: ignore[override]
        """Validate password confirmation using Pydantic v2 style validator."""
        if self.new_password != self.confirm_password:
            raise ValueError('New password and confirmation do not match')
        return self
    
    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    role_id: int
    role_name: Optional[str] = None
    status: UserStatus
    verified: bool
    last_login: Optional[datetime]
    is_active: bool
    is_locked: bool
    created_at: datetime
    updated_at: datetime


# Authentication Models
class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str = Field(..., min_length=1)
    remember_me: bool = Field(default=False)


class TokenData(BaseModel):
    """JWT token payload data."""
    user_id: int
    email: str
    role_id: int
    permissions: List[str]
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for token revocation


class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class ConfirmPasswordResetRequest(BaseModel):
    """Password reset confirmation."""
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)
    
    @model_validator(mode='after')
    def validate_password_match(self):  # type: ignore[override]
        """Validate password confirmation using Pydantic v2 style validator."""
        if self.new_password != self.confirm_password:
            raise ValueError('New password and confirmation do not match')
        return self


# Audit and Security Models
class AuditLog(TimestampedModel):
    """Audit log entry model."""
    id: Optional[int] = None
    user_id: Optional[int] = None
    action: str = Field(..., min_length=1, max_length=100)
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    success: bool = Field(default=True)
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SecurityEvent(TimestampedModel):
    """Security event model for monitoring."""
    id: Optional[int] = None
    event_type: str = Field(..., min_length=1, max_length=50)
    severity: str = Field(..., pattern=r'^(low|medium|high|critical)$')
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = Field(default=False)
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# API Response Models
class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Utility Models for RBAC Operations
class RoleAssignmentRequest(BaseModel):
    """Request to assign role to user."""
    user_id: int = Field(..., gt=0)
    role_id: int = Field(..., gt=0)


class PermissionCheckRequest(BaseModel):
    """Request to check user permissions."""
    user_id: int = Field(..., gt=0)
    permission: PermissionLevel
    resource: Optional[str] = None


class PermissionCheckResponse(BaseModel):
    """Response for permission check."""
    has_permission: bool
    user_id: int
    permission: str
    resource: Optional[str]
    role_name: str
    details: Optional[str] = None


# Bulk Operations
class BulkUserOperation(BaseModel):
    """Bulk user operation request."""
    user_ids: List[int] = Field(..., min_length=1, max_length=100)
    operation: str = Field(..., pattern=r'^(activate|deactivate|suspend|delete|assign_role)$')
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class BulkOperationResponse(BaseModel):
    """Bulk operation response."""
    total_requested: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


# System Configuration Models
class RBACConfig(BaseModel):
    """RBAC system configuration."""
    password_policy: Dict[str, Any] = Field(default_factory=lambda: {
        "min_length": 8,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_digits": True,
        "require_special_chars": True
    })
    session_config: Dict[str, Any] = Field(default_factory=lambda: {
        "access_token_expire_minutes": 30,
        "refresh_token_expire_days": 7,
        "max_login_attempts": 5,
        "lockout_duration_minutes": 15
    })
    audit_config: Dict[str, Any] = Field(default_factory=lambda: {
        "log_all_actions": True,
        "log_failed_attempts": True,
        "retention_days": 90
    })


# Default role configurations
DEFAULT_ROLES = {
    RoleType.ADMIN: {
        "name": "admin",
        "description": "Full system administrator with all permissions",
        "permissions": [p.value for p in PermissionLevel]
    },
    RoleType.EMPLOYEE: {
        "name": "employee", 
        "description": "Standard employee with chat and document access",
        "permissions": [
            PermissionLevel.READ.value,
            PermissionLevel.WRITE.value,
            PermissionLevel.EXPORT_DATA.value
        ]
    },
    RoleType.GUEST: {
        "name": "guest",
        "description": "Limited guest access for read-only operations",
        "permissions": [
            PermissionLevel.READ.value
        ]
    }
}


class UserRoleAssignment(BaseModel):
    user_id: int
    role_id: int
    assigned_at: Optional[datetime] = None

class RolePermissionAssignment(BaseModel):
    role_id: int
    permission_id: int
    assigned_at: Optional[datetime] = None