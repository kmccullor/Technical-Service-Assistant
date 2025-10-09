#!/usr/bin/env python3
"""
RBAC Middleware System

Comprehensive middleware for Role-Based Access Control with permission checking,
audit logging, rate limiting, and security monitoring.

Features:
- Permission-based access control middleware
- Audit logging for all protected operations
- Rate limiting and abuse prevention
- Security monitoring and threat detection
- Resource-based permissions with context
- Hierarchical role support
- Real-time permission validation

Usage:
    from utils.rbac_middleware import RBACMiddleware, require_permissions
    
    app.add_middleware(RBACMiddleware)
    
    @app.get("/admin/users")
    @require_permissions("manage_users")
    async def get_users():
        return users
"""

import time
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any
from functools import wraps
from contextlib import asynccontextmanager

from fastapi import Request, Response, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor

from config import get_settings
from utils.rbac_models import (
    User, Role, Permission, PermissionLevel, UserStatus,
    AuditLog, SecurityEvent, PermissionCheckRequest,
    PermissionCheckResponse, APIResponse, ErrorResponse
)
from utils.auth_system import AuthManager, get_current_user, get_auth_manager
from utils.exceptions import (
    AuthenticationError, AuthorizationError, ValidationError,
    RateLimitError, TechnicalServiceError
)

# Configure logging
logger = logging.getLogger(__name__)


class PermissionCache:
    """In-memory cache for user permissions with TTL."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self.cache: Dict[int, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, user_id: int) -> Optional[List[str]]:
        """Get cached permissions for user."""
        if user_id in self.cache:
            entry = self.cache[user_id]
            if datetime.utcnow() - entry['timestamp'] < timedelta(seconds=self.ttl_seconds):
                return entry['permissions']
            else:
                # Expired, remove from cache
                del self.cache[user_id]
        return None
    
    def set(self, user_id: int, permissions: List[str]):
        """Cache permissions for user."""
        self.cache[user_id] = {
            'permissions': permissions,
            'timestamp': datetime.utcnow()
        }
    
    def invalidate(self, user_id: int):
        """Invalidate cached permissions for user."""
        if user_id in self.cache:
            del self.cache[user_id]
    
    def clear(self):
        """Clear all cached permissions."""
        self.cache.clear()


class RateLimiter:
    """Rate limiting for API endpoints."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[datetime]] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is within rate limits."""
        now = datetime.utcnow()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Clean old requests
        window_start = now - timedelta(seconds=self.window_seconds)
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]
        
        # Check if over limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Record this request
        self.requests[identifier].append(now)
        return True
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests in current window."""
        if identifier not in self.requests:
            return self.max_requests
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        current_requests = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]
        
        return max(0, self.max_requests - len(current_requests))


class RBACManager:
    """Comprehensive RBAC manager with caching and monitoring."""
    
    def __init__(self, db_connection_string: str):
        self.db_connection_string = db_connection_string
        self.permission_cache = PermissionCache()
        self.rate_limiter = RateLimiter()
        self.settings = get_settings()
        
        # Security monitoring
        self.failed_permission_checks = {}
        self.suspicious_activity_threshold = 10
        self.monitoring_window = timedelta(minutes=15)
    
    async def get_db_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            self.db_connection_string,
            cursor_factory=RealDictCursor
        )
    
    async def get_user_permissions(self, user_id: int, force_refresh: bool = False) -> List[str]:
        """Get user permissions with caching."""
        if not force_refresh:
            cached_permissions = self.permission_cache.get(user_id)
            if cached_permissions is not None:
                return cached_permissions
        
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
                UNION
                SELECT DISTINCT p.name
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                JOIN role_permissions rp ON r.id = rp.role_id
                JOIN permissions p ON rp.permission_id = p.id
                WHERE u.id = %s AND u.status = 'active' AND u.verified = true
            """, (user_id, user_id))
            
            permissions = [row['name'] for row in cursor.fetchall()]
            
            # Cache the permissions
            self.permission_cache.set(user_id, permissions)
            
            return permissions
            
        finally:
            cursor.close()
            conn.close()
    
    async def check_permission(
        self,
        user_id: int,
        permission: str,
        resource: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> PermissionCheckResponse:
        """Check if user has specific permission."""
        
        # Get user permissions
        user_permissions = await self.get_user_permissions(user_id)
        
        # Check basic permission
        has_permission = permission in user_permissions
        
        # Check for admin override
        if not has_permission and 'admin' in user_permissions:
            has_permission = True
        
        # Get user role name for response
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT r.name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.id = %s
            """, (user_id,))
            
            role_row = cursor.fetchone()
            role_name = role_row['name'] if role_row else 'unknown'
            
        finally:
            cursor.close()
            conn.close()
        
        # Log failed permission check
        if not has_permission:
            await self.log_failed_permission_check(user_id, permission, resource, context)
        
        return PermissionCheckResponse(
            has_permission=has_permission,
            user_id=user_id,
            permission=permission,
            resource=resource,
            role_name=role_name,
            details=f"User has permissions: {user_permissions}" if not has_permission else None
        )
    
    async def log_failed_permission_check(
        self,
        user_id: int,
        permission: str,
        resource: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log failed permission check and monitor for suspicious activity."""
        
        # Track failed attempts
        now = datetime.utcnow()
        if user_id not in self.failed_permission_checks:
            self.failed_permission_checks[user_id] = []
        
        self.failed_permission_checks[user_id].append(now)
        
        # Clean old attempts
        window_start = now - self.monitoring_window
        self.failed_permission_checks[user_id] = [
            attempt for attempt in self.failed_permission_checks[user_id]
            if attempt > window_start
        ]
        
        # Check for suspicious activity
        recent_failures = len(self.failed_permission_checks[user_id])
        if recent_failures >= self.suspicious_activity_threshold:
            await self.log_security_event(
                event_type="suspicious_permission_activity",
                severity="high",
                user_id=user_id,
                details={
                    "failed_permission_checks": recent_failures,
                    "window_minutes": self.monitoring_window.total_seconds() / 60,
                    "latest_permission": permission,
                    "resource": resource
                }
            )
    
    async def check_multiple_permissions(
        self,
        user_id: int,
        permissions: List[str],
        require_all: bool = True
    ) -> Dict[str, bool]:
        """Check multiple permissions at once."""
        user_permissions = await self.get_user_permissions(user_id)
        
        results = {}
        for permission in permissions:
            has_permission = permission in user_permissions or 'admin' in user_permissions
            results[permission] = has_permission
        
        return results
    
    async def get_user_role_hierarchy(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user's role hierarchy with inheritance."""
        conn = await self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Get primary role
            cursor.execute("""
                SELECT r.id, r.name, r.description, 'primary' as role_type
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.id = %s
                UNION
                SELECT r.id, r.name, r.description, 'additional' as role_type
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                JOIN roles r ON ur.role_id = r.id
                WHERE u.id = %s
                ORDER BY role_type, name
            """, (user_id, user_id))
            
            return [dict(row) for row in cursor.fetchall()]
            
        finally:
            cursor.close()
            conn.close()
    
    async def invalidate_user_cache(self, user_id: int):
        """Invalidate cached data for user."""
        self.permission_cache.invalidate(user_id)
        
        # Log cache invalidation
        await self.log_audit_event(
            user_id=None,  # System action
            action="cache_invalidated",
            resource_type="user_permissions",
            resource_id=str(user_id),
            details={"reason": "permission_change"}
        )
    
    # Audit and Security Logging
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
            cursor.execute("""
                INSERT INTO audit_logs 
                (user_id, action, resource_type, resource_id, ip_address, 
                 user_agent, details, success, error_message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, action, resource_type, resource_id, ip_address,
                user_agent, json.dumps(details) if details else None,
                success, error_message, datetime.utcnow()
            ))
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")
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
            cursor.execute("""
                INSERT INTO security_events 
                (event_type, severity, user_id, ip_address, details, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                event_type, severity, user_id, ip_address,
                json.dumps(details) if details else None, datetime.utcnow()
            ))
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")
        finally:
            cursor.close()
            conn.close()


class RBACMiddleware(BaseHTTPMiddleware):
    """RBAC middleware for FastAPI applications."""
    
    def __init__(self, app, db_connection_string: Optional[str] = None):
        super().__init__(app)
        if not db_connection_string:
            settings = get_settings()
            db_connection_string = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        
        self.rbac_manager = RBACManager(db_connection_string)
        
        # Endpoints that don't require authentication
        self.public_endpoints = {
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/health",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/reset-password",
            "/api/auth/verify-email",
            "/api/auth/refresh"
        }
        
        # Endpoints with special rate limiting
        self.rate_limited_endpoints = {
            "/api/auth/login": RateLimiter(max_requests=5, window_seconds=300),  # 5 per 5 minutes
            "/api/auth/register": RateLimiter(max_requests=3, window_seconds=3600),  # 3 per hour
            "/api/auth/reset-password": RateLimiter(max_requests=3, window_seconds=3600)
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through RBAC middleware."""
        start_time = time.time()
        
        # Get client information
        client_ip = self.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        path = request.url.path
        method = request.method
        
        try:
            # Skip middleware for public endpoints
            if self.is_public_endpoint(path):
                response = await call_next(request)
                await self.log_request(
                    request, response, start_time, None, client_ip, user_agent
                )
                return response
            
            # Check rate limiting for specific endpoints
            if path in self.rate_limited_endpoints:
                rate_limiter = self.rate_limited_endpoints[path]
                if not rate_limiter.is_allowed(client_ip):
                    await self.rbac_manager.log_security_event(
                        event_type="rate_limit_exceeded",
                        severity="medium",
                        ip_address=client_ip,
                        details={
                            "endpoint": path,
                            "method": method,
                            "user_agent": user_agent
                        }
                    )
                    
                    return JSONResponse(
                        status_code=429,
                        content={
                            "success": False,
                            "message": "Rate limit exceeded",
                            "error_code": "RATE_LIMIT_EXCEEDED",
                            "details": {
                                "retry_after": self.rate_limited_endpoints[path].window_seconds
                            }
                        }
                    )
            
            # Process request
            response = await call_next(request)
            
            # Log successful request
            await self.log_request(
                request, response, start_time, None, client_ip, user_agent
            )
            
            return response
            
        except HTTPException as e:
            # Handle HTTP exceptions
            error_response = JSONResponse(
                status_code=e.status_code,
                content={
                    "success": False,
                    "message": e.detail,
                    "error_code": self.get_error_code(e.status_code),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            await self.log_request(
                request, error_response, start_time, str(e), client_ip, user_agent
            )
            
            return error_response
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in RBAC middleware: {str(e)}")
            
            error_response = JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Internal server error",
                    "error_code": "INTERNAL_ERROR",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            await self.log_request(
                request, error_response, start_time, str(e), client_ip, user_agent
            )
            
            return error_response
    
    def is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public."""
        return path in self.public_endpoints or path.startswith("/static/")
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check X-Forwarded-For header first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"
    
    def get_error_code(self, status_code: int) -> str:
        """Get error code from HTTP status."""
        error_codes = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMIT_EXCEEDED",
            500: "INTERNAL_ERROR"
        }
        return error_codes.get(status_code, "UNKNOWN_ERROR")
    
    async def log_request(
        self,
        request: Request,
        response: Response,
        start_time: float,
        error: Optional[str],
        client_ip: str,
        user_agent: str
    ):
        """Log request details."""
        duration = time.time() - start_time
        
        # Basic request logging
        logger.info(
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {duration:.3f}s - {client_ip}"
        )
        
        # Detailed audit logging for protected endpoints
        if not self.is_public_endpoint(request.url.path):
            await self.rbac_manager.log_audit_event(
                action=f"{request.method.lower()}_request",
                resource_type="api_endpoint",
                resource_id=request.url.path,
                ip_address=client_ip,
                user_agent=user_agent,
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_seconds": duration,
                    "query_params": dict(request.query_params) if request.query_params else None
                },
                success=error is None,
                error_message=error
            )


# FastAPI Dependencies
async def get_rbac_manager() -> RBACManager:
    """Get RBAC manager instance."""
    settings = get_settings()
    db_url = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    return RBACManager(db_url)


def require_permissions(*permissions: str, require_all: bool = True):
    """Decorator to require specific permissions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from dependencies
            current_user = None
            rbac_manager = None
            
            # Extract dependencies from kwargs
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                elif isinstance(value, RBACManager):
                    rbac_manager = value
            
            if not current_user or not rbac_manager:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication dependencies not properly configured"
                )
            
            # Check permissions
            if permissions:
                # Defensive: ensure user id present
                if current_user.id is None:
                    raise HTTPException(status_code=401, detail="Invalid user context")
                permission_results = await rbac_manager.check_multiple_permissions(
                    current_user.id, list(permissions), require_all
                )
                
                if require_all:
                    if not all(permission_results.values()):
                        missing_permissions = [
                            perm for perm, has_perm in permission_results.items()
                            if not has_perm
                        ]
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Missing required permissions: {', '.join(missing_permissions)}"
                        )
                else:
                    if not any(permission_results.values()):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"At least one of these permissions required: {', '.join(permissions)}"
                        )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(*roles: str):
    """Decorator to require specific roles."""
    async def role_dependency(
        current_user: User = Depends(get_current_user),
        rbac_manager: RBACManager = Depends(get_rbac_manager)
    ) -> User:
        # Get user role hierarchy
        if current_user.id is None:
            raise HTTPException(status_code=401, detail="Invalid user context")
        user_roles = await rbac_manager.get_user_role_hierarchy(current_user.id)
        user_role_names = [role['name'] for role in user_roles]
        
        # Check if user has any of the required roles
        has_required_role = any(role in user_role_names for role in roles)
        
        if not has_required_role:
            await rbac_manager.log_security_event(
                event_type="unauthorized_role_access",
                severity="medium",
                user_id=current_user.id,
                details={
                    "required_roles": list(roles),
                    "user_roles": user_role_names
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(roles)}"
            )
        
        return current_user
    
    return role_dependency


# Compatibility: require_permission for legacy imports

def require_permission(permission: PermissionLevel):
    """Dependency to require a specific permission for a route."""
    async def permission_dependency(current_user = Depends(get_current_user)):
        if permission.value not in getattr(current_user, 'permissions', []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission.value}' required"
            )
        return current_user
    return permission_dependency


# Common permission dependencies
require_admin = require_role("admin")
require_employee = require_role("admin", "employee")
require_read_access = require_permissions("read")
require_write_access = require_permissions("write")
require_user_management = require_permissions("manage_users")
require_role_management = require_permissions("manage_roles")
require_system_config = require_permissions("system_config")