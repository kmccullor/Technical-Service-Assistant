from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='jwt_auth',
    log_level='INFO',
    log_file=f'/app/logs/jwt_auth_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

"""
JWT-based authentication and authorization system for Technical Service Assistant API.

Features:
- JWT token generation and validation
- API key support for service-to-service authentication
- Rate limiting per user/API key
- Role-based access control (RBAC)
- Token expiration and refresh
"""

import hashlib
import hmac
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from config import get_settings
try:
    import jwt
except ImportError:
    jwt = None  # type: ignore

try:
    import redis
except ImportError:
    redis = None  # type: ignore

# Configuration
_settings = get_settings()

JWT_SECRET = _settings.jwt_secret
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = int(os.getenv("JWT_TOKEN_EXPIRY_HOURS", "24"))
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRY_DAYS", "7"))


def _require_jwt_secret() -> str:
    if not JWT_SECRET or JWT_SECRET.strip() == "":
        raise RuntimeError("JWT_SECRET is not configured")
    return JWT_SECRET

# Rate limiting configuration (requests per minute)
RATE_LIMITS = {
    "admin": 1000,  # Admins: 1000 req/min
    "user": 100,  # Users: 100 req/min
    "viewer": 20,  # Viewers: 20 req/min
    "api_key": 50,  # API keys: 50 req/min
}

# Redis for rate limiting (optional - falls back to in-memory if unavailable)
_redis_client: Optional["redis.Redis"] = None

def get_redis_client() -> Optional["redis.Redis"]:
    """Get or create Redis client for rate limiting."""
    global _redis_client
    if _redis_client is None and redis is not None:
        try:
            _redis_client = redis.Redis(
                host="redis-cache",
                port=6379,
                db=2,  # Use DB 2 for rate limiting
                decode_responses=True,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            logger.info("Redis connected for rate limiting")
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting: {e}")
            _redis_client = None
    return _redis_client

# In-memory rate limiting (fallback)
_rate_limit_buckets: Dict[str, List[float]] = {}

@dataclass
class User:
    """User model for authentication."""

    id: int
    email: str
    role: str  # admin, user, viewer
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class APIKey:
    """API Key model for service-to-service authentication."""

    key_id: str
    user_id: int
    name: str
    key_hash: str  # SHA256 hash of actual key
    role: str
    is_active: bool = True
    created_at: Optional[str] = None
    last_used: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

class JWTAuthenticator:
    """JWT token generation and validation."""

    @staticmethod
    def generate_token(
        user_id: int,
        email: str,
        role: str,
        expires_in_hours: int = TOKEN_EXPIRY_HOURS,
    ) -> str:
        """Generate JWT token for user.

        Args:
            user_id: User ID
            email: User email
            role: User role (admin, user, viewer)
            expires_in_hours: Token expiration time in hours

        Returns:
            JWT token string
        """
        if jwt is None:
            raise RuntimeError("PyJWT not installed")

        now = datetime.utcnow()
        expire = now + timedelta(hours=expires_in_hours)

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "access",
        }

        secret = _require_jwt_secret()
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        logger.info(f"Generated token for user {email} (role: {role})")
        return token

    @staticmethod
    def generate_refresh_token(user_id: int, email: str, role: str = "user") -> str:
        """Generate refresh token for user.

        Args:
            user_id: User ID
            email: User email

        Returns:
            Refresh token string
        """
        if jwt is None:
            raise RuntimeError("PyJWT not installed")

        now = datetime.utcnow()
        expire = now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",
        }

        secret = _require_jwt_secret()
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        return token

    @staticmethod
    def validate_token(token: str) -> Optional[Dict]:
        """Validate JWT token and return payload.

        Args:
            token: JWT token string

        Returns:
            Token payload dict if valid, None if invalid
        """
        if jwt is None:
            logger.error("PyJWT not installed")
            return None

        try:
            # Add 5 second leeway for clock skew
            secret = _require_jwt_secret()
            payload = jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                options={"verify_iat": False, "leeway": 10},
            )
            logger.debug(f"Token validated for user {payload.get('email')}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[str]:
        """Generate new access token from refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            New access token if valid, None otherwise
        """
        payload = JWTAuthenticator.validate_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        return JWTAuthenticator.generate_token(
            user_id=payload["user_id"],
            email=payload["email"],
            role=payload.get("role", "user"),
        )

class APIKeyManager:
    """Manage API keys for service-to-service authentication."""

    @staticmethod
    def generate_api_key(user_id: int, name: str, role: str = "user") -> Tuple[str, str]:
        """Generate new API key.

        Args:
            user_id: User ID
            name: Key name/description
            role: Key role (admin, user, viewer)

        Returns:
            Tuple of (key_id, actual_key) - actual key should be shown to user once
        """
        import secrets

        key_id = f"key_{int(time.time())}_{secrets.token_hex(4)}"
        actual_key = f"sk_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(actual_key.encode()).hexdigest()

        api_key = APIKey(
            key_id=key_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            role=role,
            created_at=datetime.utcnow().isoformat(),
        )

        logger.info(f"Generated API key {key_id} for user {user_id}")
        return key_id, actual_key

    @staticmethod
    def validate_api_key(api_key: str, stored_key_hash: str) -> bool:
        """Validate API key against stored hash.

        Args:
            api_key: Actual API key
            stored_key_hash: Stored SHA256 hash

        Returns:
            True if valid, False otherwise
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        return hmac.compare_digest(key_hash, stored_key_hash)

class RateLimiter:
    """Rate limiting using Redis or in-memory storage."""

    @staticmethod
    def check_rate_limit(identifier: str, role: str, limit: Optional[int] = None) -> Tuple[bool, Dict]:
        """Check if request is within rate limit.

        Args:
            identifier: User ID or API key ID
            role: User role (determines limit)
            limit: Optional custom limit (req/min)

        Returns:
            Tuple of (allowed, status_dict)
            Status dict contains:
              - allowed: bool
              - limit: requests per minute allowed
              - remaining: requests remaining
              - reset_at: Unix timestamp when limit resets
        """
        if limit is None:
            limit = RATE_LIMITS.get(role, 50)

        redis_client = get_redis_client()
        now = time.time()
        reset_at = int(now + 60)  # Reset in 1 minute

        if redis_client is not None:
            # Use Redis for distributed rate limiting
            key = f"rate_limit:{identifier}"
            current = redis_client.get(key)

            if current is None:
                redis_client.setex(key, 60, "1")
                count = 1
            else:
                count = int(current) + 1
                redis_client.incr(key)

            allowed = count <= limit
            remaining = max(0, limit - count)

            logger.debug(f"Rate limit check: {identifier} - {count}/{limit}")

            return allowed, {
                "allowed": allowed,
                "limit": limit,
                "remaining": remaining,
                "reset_at": reset_at,
                "current": count,
            }
        else:
            # Fallback to in-memory rate limiting
            if identifier not in _rate_limit_buckets:
                _rate_limit_buckets[identifier] = []

            bucket = _rate_limit_buckets[identifier]

            # Remove expired entries (older than 60 seconds)
            bucket[:] = [ts for ts in bucket if now - ts < 60]

            if len(bucket) < limit:
                bucket.append(now)
                allowed = True
            else:
                allowed = False

            remaining = max(0, limit - len(bucket))

            return allowed, {
                "allowed": allowed,
                "limit": limit,
                "remaining": remaining,
                "reset_at": reset_at,
                "current": len(bucket),
            }

class RoleBasedAccessControl:
    """Role-based access control for endpoints."""

    # Define permissions by role
    PERMISSIONS = {
        "admin": {
            "/api/chat",
            "/api/search",
            "/api/conversations",
            "/api/admin/users",
            "/api/admin/roles",
            "/api/load-balancer-stats",
            "/api/advanced-cache-stats",
            "/api/system/config",
        },
        "user": {
            "/api/chat",
            "/api/search",
            "/api/conversations",
            "/api/load-balancer-stats",
            "/api/advanced-cache-stats",
        },
        "viewer": {
            "/api/search",
            "/api/conversations",
            "/api/load-balancer-stats",
            "/api/advanced-cache-stats",
        },
    }

    @staticmethod
    def has_permission(role: str, endpoint: str) -> bool:
        """Check if role has permission to access endpoint.

        Args:
            role: User role
            endpoint: API endpoint

        Returns:
            True if permitted, False otherwise
        """
        if role not in RoleBasedAccessControl.PERMISSIONS:
            return False

        permissions = RoleBasedAccessControl.PERMISSIONS[role]
        return endpoint in permissions

    @staticmethod
    def get_role_permissions(role: str) -> Set[str]:
        """Get all permissions for a role.

        Args:
            role: User role

        Returns:
            Set of permitted endpoints
        """
        return RoleBasedAccessControl.PERMISSIONS.get(role, set())

class AuthenticationMiddleware:
    """FastAPI middleware for JWT authentication and rate limiting."""

    def __init__(self):
        """Initialize middleware."""
        self.jwt_auth = JWTAuthenticator()
        self.rate_limiter = RateLimiter()
        self.rbac = RoleBasedAccessControl()

    def extract_token(self, authorization_header: Optional[str]) -> Optional[str]:
        """Extract JWT token from Authorization header.

        Args:
            authorization_header: Authorization header value

        Returns:
            Token string if valid format, None otherwise
        """
        if not authorization_header:
            return None

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    def extract_api_key(self, authorization_header: Optional[str]) -> Optional[str]:
        """Extract API key from Authorization header.

        Args:
            authorization_header: Authorization header value

        Returns:
            API key string if valid format, None otherwise
        """
        if not authorization_header:
            return None

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != "apikey":
            return None

        return parts[1]

def validate_authentication(
    authorization_header: Optional[str],
) -> Tuple[Optional[User], Optional[str]]:
    """Validate authentication from Authorization header.

    Supports:
    - JWT tokens (Bearer <token>)
    - API keys (ApiKey <key>)

    Args:
        authorization_header: Authorization header value

    Returns:
        Tuple of (User, error_message)
        If authentication succeeds: (User, None)
        If authentication fails: (None, error_message)
    """
    if not authorization_header:
        return None, "Missing Authorization header"

    middleware = AuthenticationMiddleware()

    # Try JWT token
    token = middleware.extract_token(authorization_header)
    if token:
        payload = middleware.jwt_auth.validate_token(token)
        if payload:
            user = User(
                id=payload.get("user_id"),
                email=payload.get("email"),
                role=payload.get("role", "user"),
            )
            return user, None
        else:
            return None, "Invalid or expired token"

    # Try API key
    api_key = middleware.extract_api_key(authorization_header)
    if api_key:
        # Note: In production, validate against database
        logger.warning("API key validation not yet implemented")
        return None, "API key validation not implemented"

    return None, "Invalid authorization header format"
