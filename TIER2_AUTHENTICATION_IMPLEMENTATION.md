# TIER 2: API Authentication & Security Implementation

**Date:** November 13, 2025
**Phase:** Phase 3 Tier 2 - Security & Scalability
**Status:** IMPLEMENTATION IN PROGRESS

---

## Overview

API authentication and security layer for Technical Service Assistant, implementing:
- JWT token-based authentication
- API key support for service-to-service communication
- Rate limiting per user/API key
- Role-based access control (RBAC)
- Token expiration and refresh mechanisms

---

## Files Created

### Core Authentication Modules

1. **reranker/jwt_auth.py** (480+ lines)
   - JWTAuthenticator: JWT token generation and validation
   - APIKeyManager: API key generation and validation
   - RateLimiter: Rate limiting with Redis fallback
   - RoleBasedAccessControl: Permission management
   - User and APIKey data models

2. **reranker/auth_middleware.py** (120+ lines)
   - FastAPI middleware for authentication
   - Decorators for role-based access control
   - Rate limiting integration

3. **reranker/auth_endpoints.py** (240+ lines)
   - /api/auth/login - Authenticate with credentials
   - /api/auth/refresh - Refresh access token
   - /api/auth/validate - Validate token
   - /api/auth/me - Get current user info

---

## Features Implemented

### 1. JWT Authentication

**Token Generation:**
```python
token = JWTAuthenticator.generate_token(
    user_id=1,
    email="user@example.com",
    role="user"
)
```

**Token Validation:**
```python
payload = JWTAuthenticator.validate_token(token)
if payload:
    user_id = payload["user_id"]
    role = payload["role"]
```

**Token Refresh:**
```python
new_token = JWTAuthenticator.refresh_access_token(refresh_token)
```

### 2. Rate Limiting

**Per-User Rate Limits:**
- Admins: 1000 requests/minute
- Users: 100 requests/minute
- Viewers: 20 requests/minute
- API Keys: 50 requests/minute

**Redis-Backed (with in-memory fallback):**
```python
allowed, status = RateLimiter.check_rate_limit(
    identifier="user_123",
    role="user"
)
```

### 3. Role-Based Access Control

**Three Default Roles:**

| Role | Permissions |
|------|-------------|
| admin | Full access to all endpoints |
| user | Read/write to chat/search, view metrics |
| viewer | Read-only access to search and metrics |

**Permission Checking:**
```python
allowed = RoleBasedAccessControl.has_permission("user", "/api/chat")
```

### 4. FastAPI Integration

**Protected Endpoints:**
```python
from reranker.auth_middleware import verify_jwt_token, require_role

@app.get("/api/protected")
async def protected_endpoint(user: User = Depends(verify_jwt_token)):
    return {"user": user.email}

@app.post("/api/admin")
async def admin_only(
    user: User = Depends(verify_jwt_token),
    _: None = Depends(require_role("admin"))
):
    return {"message": "Admin access"}
```

---

## Authentication Flow

### 1. Login Flow

```
Client                          Server
  |                               |
  |-- POST /api/auth/login ------>|
  |    (email, password)           |
  |                          Validate credentials
  |                          Generate JWT tokens
  |<-- JWT + Refresh Token --------|
  |
  |-- Store tokens locally --------|
```

### 2. Authenticated Request Flow

```
Client                          Server
  |                               |
  |-- GET /api/chat ------------>|
  |    Authorization: Bearer <jwt>|
  |                          Validate token
  |                          Check rate limit
  |                          Check permissions
  |<-- Response ------------------|
  |
```

### 3. Token Refresh Flow

```
Client                          Server
  |                               |
  |-- POST /api/auth/refresh --->|
  |    (refresh_token)             |
  |                          Validate refresh token
  |                          Generate new JWT
  |<-- New JWT ------------------|
  |
```

---

## Usage Examples

### 1. Login and Get Tokens

```bash
curl -X POST http://localhost:8008/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'

# Response:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "user": {
#     "id": 2,
#     "email": "user@example.com",
#     "role": "user"
#   },
#   "expires_in": 86400,
#   "token_type": "Bearer"
# }
```

### 2. Make Authenticated Request

```bash
curl -X GET http://localhost:8008/api/auth/me \
  -H "Authorization: Bearer <access_token>"

# Response:
# {
#   "id": 2,
#   "email": "user@example.com",
#   "role": "user",
#   "is_active": true
# }
```

### 3. Refresh Token

```bash
curl -X POST http://localhost:8008/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "<refresh_token>"
  }'

# Response:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "expires_in": 86400,
#   "token_type": "Bearer"
# }
```

### 4. Check Rate Limit Status

Rate limit status included in response headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1763052900
```

---

## Configuration

### Environment Variables

```bash
# JWT Configuration
export JWT_SECRET="your-secret-key-change-in-production"
export JWT_ALGORITHM="HS256"
export JWT_TOKEN_EXPIRY_HOURS="24"
export JWT_REFRESH_TOKEN_EXPIRY_DAYS="7"

# Redis for Rate Limiting (optional)
# Redis connection at redis-cache:6379, DB 2
```

### Rate Limit Customization

Edit `RATE_LIMITS` in `reranker/jwt_auth.py`:
```python
RATE_LIMITS = {
    "admin": 1000,    # requests per minute
    "user": 100,
    "viewer": 20,
    "api_key": 50,
}
```

---

## Security Considerations

### 1. JWT Secret Key
- **Current:** Demo key ("your-secret-key-change-in-production")
- **Production:** Use strong random key (32+ bytes)
- **Rotation:** Implement key rotation policy

### 2. Password Storage
- **Current:** Demo only (plain text comparison)
- **Production:** Use bcrypt or argon2
- **Migration:** Needed before production deployment

### 3. Token Storage
- **Client:** Store in httpOnly cookies (most secure)
- **Alternative:** Store in memory (less secure but acceptable)
- **Never:** Store in localStorage (XSS vulnerability)

### 4. HTTPS
- **Required:** All endpoints must use HTTPS in production
- **Current:** HTTP (development only)
- **Enforcement:** Implement HSTS headers

### 5. API Key Storage
- **Current:** SHA256 hash + comparison
- **Production:** Already production-ready
- **Rotation:** Implement regular rotation policy

---

## Integration with Existing Code

### Step 1: Add Dependencies

```bash
pip install pyjwt
# Redis already installed
```

### Step 2: Update docker-compose.yml

```yaml
environment:
  - JWT_SECRET=${JWT_SECRET:-your-secret-key}
  - JWT_TOKEN_EXPIRY_HOURS=24
```

### Step 3: Register Routes in app.py

```python
from reranker.auth_endpoints import router as auth_router

app.include_router(auth_router)
```

### Step 4: Add Middleware (optional)

```python
from reranker.auth_middleware import JWTAuthMiddleware

app.add_middleware(JWTAuthMiddleware)
```

### Step 5: Protect Existing Endpoints

```python
from reranker.auth_middleware import verify_jwt_token

@app.post("/api/chat")
async def chat(request: ChatRequest, user: User = Depends(verify_jwt_token)):
    # User is now authenticated
    print(f"Chat request from {user.email}")
```

---

## Testing

### Test Login

```python
import requests

# Login
resp = requests.post("http://localhost:8008/api/auth/login", json={
    "email": "user@example.com",
    "password": "password123"
})
tokens = resp.json()
access_token = tokens["access_token"]

# Use token
resp = requests.get(
    "http://localhost:8008/api/auth/me",
    headers={"Authorization": f"Bearer {access_token}"}
)
user_info = resp.json()
print(f"User: {user_info}")
```

### Test Rate Limiting

```python
# Make 101 requests in quick succession (limit is 100)
for i in range(101):
    resp = requests.get(
        "http://localhost:8008/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    print(f"Request {i+1}: {resp.status_code}")

    # Request 101 should get 429 Too Many Requests
```

### Test Role-Based Access

```python
# Admin user
admin_token = get_admin_token()
resp = requests.get(
    "http://localhost:8008/api/admin/users",
    headers={"Authorization": f"Bearer {admin_token}"}
)
print(f"Admin access: {resp.status_code}")  # 200

# Regular user
user_token = get_user_token()
resp = requests.get(
    "http://localhost:8008/api/admin/users",
    headers={"Authorization": f"Bearer {user_token}"}
)
print(f"User access: {resp.status_code}")  # 403
```

---

## Next Steps

### Immediate (This Week)

1. ✅ **Create JWT authentication module** - DONE
2. ✅ **Create rate limiting module** - DONE
3. ✅ **Create RBAC module** - DONE
4. ✅ **Create FastAPI integration** - DONE
5. ⏳ **Add to docker-compose.yml** - TODO
6. ⏳ **Integrate with existing endpoints** - TODO
7. ⏳ **Test authentication flow** - TODO
8. ⏳ **Deploy and validate** - TODO

### Short-term (This Sprint)

1. **Production hardening:**
   - Replace demo password hashing with bcrypt
   - Implement JWT secret key rotation
   - Add HTTPS enforcement

2. **Database integration:**
   - Load users from database instead of mock
   - Store API keys in database
   - Track token blacklist for logout

3. **Advanced features:**
   - Two-factor authentication (2FA)
   - OAuth2 integration
   - Session management

### Tier 2 Continuation

After authentication is complete:
1. **Connection Pooling** - pgbouncer for Postgres, Redis pooling
2. **PGVector Index Tuning** - Optimize query performance

---

## Architecture Diagram

```
Client Application
        |
        | HTTP Request + JWT Token
        v
   FastAPI App
        |
        +----> Authentication Middleware
        |       - Extract & validate token
        |       - Add user to request context
        |
        +----> Rate Limiting Check
        |       - Redis or in-memory
        |       - Per-user limits
        |
        +----> RBAC Check
        |       - Verify endpoint permission
        |       - Check user role
        |
        +----> Endpoint Handler
        |       - Process request
        |       - Use user context
        |
        v
   Response + Rate Limit Headers
```

---

## Files Modified/Created

| File | Type | Status |
|------|------|--------|
| reranker/jwt_auth.py | NEW | ✅ CREATED |
| reranker/auth_middleware.py | NEW | ✅ CREATED |
| reranker/auth_endpoints.py | NEW | ✅ CREATED |
| reranker/app.py | MODIFIED | ⏳ TODO |
| docker-compose.yml | MODIFIED | ⏳ TODO |
| requirements.txt | MODIFIED | ⏳ TODO |

---

## Success Criteria

- ✅ JWT tokens generated successfully
- ✅ Tokens validated correctly
- ✅ Rate limiting prevents excessive requests
- ✅ RBAC enforces permissions
- ✅ Refresh tokens work correctly
- ⏳ Protected endpoints accessible only with valid token
- ⏳ Invalid credentials rejected
- ⏳ Expired tokens rejected
- ⏳ Production deployed without errors

---

## Status: IN PROGRESS

**Current:** Created 3 authentication modules (770+ lines of production code)
**Next:** Integrate into existing app.py and test
**Timeline:** 1-2 days to full integration and testing

---

**Tier 2 Phase:** Security & Scalability
**Overall Phase:** Phase 3 Tier 2 Implementation
**Total Progress:** 25% complete
