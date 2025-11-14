"""
FastAPI authentication middleware and decorators for JWT and API key authentication.
"""

import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from reranker.jwt_auth import (
    AuthenticationMiddleware,
    RateLimiter,
    RoleBasedAccessControl,
    User,
    validate_authentication,
)

logger = logging.getLogger(__name__)


async def verify_jwt_token(request: Request) -> User:
    """Dependency to verify JWT token in request.

    Usage:
        @app.get("/protected")
        async def protected_endpoint(user: User = Depends(verify_jwt_token)):
            return {"message": f"Hello {user.email}"}

    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")
    user, error = validate_authentication(auth_header)

    if not user:
        logger.warning(f"Authentication failed: {error}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_role(*allowed_roles: str) -> Callable:
    """Dependency factory to require specific roles.

    Usage:
        @app.get("/admin")
        async def admin_endpoint(
            user: User = Depends(verify_jwt_token),
            _: None = Depends(require_role("admin"))
        ):
            return {"message": "Admin access"}

    Args:
        allowed_roles: Role names allowed to access endpoint

    Returns:
        Dependency function
    """

    async def check_role(request: Request, user: User = Depends(verify_jwt_token)) -> None:
        if user.role not in allowed_roles:
            logger.warning(
                f"Insufficient permissions: {user.email} (role: {user.role}) " f"tried to access restricted endpoint"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of: {', '.join(allowed_roles)}",
            )

    return check_role


async def verify_rate_limit(request: Request, user: User) -> None:
    """Check rate limit for user.

    Args:
        request: FastAPI Request
        user: Authenticated user

    Raises:
        HTTPException: If rate limit exceeded
    """
    rate_limiter = RateLimiter()
    allowed, status_dict = rate_limiter.check_rate_limit(
        identifier=str(user.id),
        role=user.role,
    )

    if not allowed:
        logger.warning(
            f"Rate limit exceeded for user {user.email} " f"({status_dict['current']}/{status_dict['limit']})"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(status_dict["limit"]),
                "X-RateLimit-Remaining": str(status_dict["remaining"]),
                "X-RateLimit-Reset": str(status_dict["reset_at"]),
            },
        )


async def check_endpoint_permission(request: Request, user: User) -> None:
    """Check if user has permission to access endpoint.

    Args:
        request: FastAPI Request
        user: Authenticated user

    Raises:
        HTTPException: If no permission
    """
    rbac = RoleBasedAccessControl()
    if not rbac.has_permission(user.role, request.url.path):
        logger.warning(
            f"Insufficient permissions: {user.email} (role: {user.role}) " f"tried to access {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this endpoint",
        )


class JWTAuthMiddleware:
    """Middleware to add JWT authentication to FastAPI app."""

    def __init__(self, app):
        """Initialize middleware.

        Args:
            app: FastAPI application
        """
        self.app = app
        self.middleware = AuthenticationMiddleware()

    async def __call__(self, scope, receive, send):
        """Process request through authentication using ASGI interface.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        # Only process HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create a request object for processing
        from starlette.requests import Request

        request = Request(scope, receive)

        # Add user info to request state if authenticated
        auth_header = request.headers.get("Authorization")
        if auth_header:
            user, error = validate_authentication(auth_header)
            if user:
                request.state.user = user
                request.state.user_id = user.id
                request.state.user_role = user.role

        # Create a wrapper for the send callable to add headers
        original_send = send
        response_started = False
        user_info = getattr(request.state, "user", None)

        async def wrapped_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start" and user_info:
                # Add rate limit headers to response
                rate_limiter = RateLimiter()
                _, status_dict = rate_limiter.check_rate_limit(
                    identifier=str(user_info.id),
                    role=user_info.role,
                )
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        [b"X-RateLimit-Limit", str(status_dict["limit"]).encode()],
                        [b"X-RateLimit-Remaining", str(status_dict["remaining"]).encode()],
                        [b"X-RateLimit-Reset", str(status_dict["reset_at"]).encode()],
                    ]
                )
                message["headers"] = headers
            await original_send(message)

        # Call next app
        await self.app(scope, receive, wrapped_send)
