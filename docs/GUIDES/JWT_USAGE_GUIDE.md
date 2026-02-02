# JWT Authentication Usage Guide

**Date**: 2025-01-XX  
**Service**: `backend/services/jwt_service.py`  
**Status**: Production-Ready

---

## Overview

Daena uses JWT (JSON Web Tokens) for authentication with token rotation support. The system provides:
- **Access tokens**: Short-lived (15 minutes) for API requests
- **Refresh tokens**: Long-lived (7 days) for token rotation
- **Token rotation**: Old refresh token revoked, new pair issued on refresh
- **Role-based claims**: founder, admin, agent, client, guest

---

## Quick Start

### 1. Login and Get Tokens

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "founder",
    "email": "founder@daena.ai",
    "tenant_id": "default",
    "project_id": "default"
  }'
```

**Response**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user_id": "founder",
  "role": "founder"
}
```

### 2. Use Access Token

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/v1/auth/me
```

### 3. Refresh Token (Token Rotation)

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "X-Refresh-Token: <refresh_token>"
```

**Response**: New token pair (old refresh token is revoked)

### 4. Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>"
```

---

## Token Structure

### Access Token Payload
```json
{
  "sub": "founder",           // User ID
  "role": "founder",          // User role
  "email": "founder@daena.ai", // Email (optional)
  "tenant_id": "default",     // Tenant ID (optional)
  "project_id": "default",    // Project ID (optional)
  "iat": 1704067200,         // Issued at (Unix timestamp)
  "exp": 1704068100,         // Expiration (Unix timestamp)
  "type": "access"            // Token type
}
```

### Refresh Token Payload
```json
{
  "sub": "founder",           // User ID
  "iat": 1704067200,         // Issued at
  "exp": 1704672000,         // Expiration (7 days)
  "type": "refresh"           // Token type
}
```

---

## User Roles

### Role Hierarchy
1. **founder** (Level 5) - Highest privileges
2. **admin** (Level 4) - Administrative access
3. **agent** (Level 3) - Agent operations
4. **client** (Level 2) - Standard user
5. **guest** (Level 1) - Limited access

### Role Assignment
Roles are determined by `user_id` prefix:
- `founder` or `founder_*` → `founder` role
- `admin_*` → `admin` role
- `agent_*` → `agent` role
- Default → `client` role

---

## Token Rotation

### Why Token Rotation?
- **Security**: Limits exposure if refresh token is compromised
- **Revocation**: Old refresh token is immediately invalidated
- **Compliance**: Meets security best practices

### How It Works

1. **Initial Login**: Get access + refresh token pair
2. **Access Token Expires**: Use refresh token to get new pair
3. **Old Refresh Token Revoked**: Cannot be reused
4. **New Pair Issued**: New access + refresh tokens

### Example Flow

```python
# 1. Login
response = requests.post("/api/v1/auth/login", json={
    "user_id": "founder",
    "email": "founder@daena.ai"
})
access_token = response.json()["access_token"]
refresh_token = response.json()["refresh_token"]

# 2. Use access token (expires in 15 minutes)
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get("/api/v1/auth/me", headers=headers)

# 3. Access token expired? Refresh it
response = requests.post("/api/v1/auth/refresh", 
    headers={"X-Refresh-Token": refresh_token})
new_access_token = response.json()["access_token"]
new_refresh_token = response.json()["refresh_token"]

# 4. Old refresh token is now invalid
# Use new tokens going forward
```

---

## Token Revocation

### Revoke Single Token
```python
from backend.services.jwt_service import jwt_service

# Revoke a specific token
jwt_service.revoke_token(token_string)
```

### Revoke All User Tokens
```python
# Revoke all tokens for a user
jwt_service.revoke_user_tokens("founder")
```

### Revoked Token Check
Revoked tokens are stored in `jwt_service.revoked_tokens` set. The `verify_token()` method automatically checks this set.

---

## Configuration

### Environment Variables

```bash
# JWT Secret Key (REQUIRED in production)
JWT_SECRET_KEY=<strong-random-secret-key>

# Or use existing secret key
SECRET_KEY=<strong-random-secret-key>  # Falls back to JWT_SECRET_KEY
```

### Token Expiration Times

Default values (configurable in `jwt_service.py`):
- **Access Token**: 15 minutes (`access_token_expiry`)
- **Refresh Token**: 7 days (`refresh_token_expiry`)

To change:
```python
from backend.services.jwt_service import jwt_service

jwt_service.access_token_expiry = timedelta(minutes=30)  # 30 minutes
jwt_service.refresh_token_expiry = timedelta(days=14)   # 14 days
```

---

## API Endpoints

### POST `/api/v1/auth/login`
Login and get token pair.

**Request**:
```json
{
  "user_id": "founder",
  "email": "founder@daena.ai",
  "password": "optional",  // Not verified in current implementation
  "tenant_id": "default",
  "project_id": "default"
}
```

**Response**: Token pair (access + refresh)

---

### POST `/api/v1/auth/refresh`
Refresh access token (token rotation).

**Headers**:
- `X-Refresh-Token`: Valid refresh token

**Response**: New token pair (old refresh token revoked)

---

### POST `/api/v1/auth/logout`
Logout and revoke tokens.

**Headers**:
- `Authorization: Bearer <access_token>`

**Response**: `{"success": true, "message": "Logged out successfully"}`

---

### GET `/api/v1/auth/me`
Get current user information.

**Headers**:
- `Authorization: Bearer <access_token>`

**Response**:
```json
{
  "user_id": "founder",
  "role": "founder",
  "email": "founder@daena.ai",
  "tenant_id": "default",
  "project_id": "default",
  "plan": "enterprise"  // From billing service
}
```

---

## Frontend Integration

### Store Tokens
```javascript
// After login
const response = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: 'founder',
    email: 'founder@daena.ai'
  })
});

const { access_token, refresh_token } = await response.json();

// Store in localStorage (or secure storage)
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);
```

### Use Access Token
```javascript
// Add to all API requests
const accessToken = localStorage.getItem('access_token');
const response = await fetch('/api/v1/auth/me', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
```

### Refresh Token on Expiry
```javascript
// When access token expires (401 error)
async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('refresh_token');
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: {
      'X-Refresh-Token': refreshToken
    }
  });
  
  const { access_token, refresh_token } = await response.json();
  
  // Update stored tokens
  localStorage.setItem('access_token', access_token);
  localStorage.setItem('refresh_token', refresh_token);
  
  return access_token;
}
```

---

## Security Best Practices

### 1. Secret Key Management
- ✅ Use strong, random secret keys (32+ characters)
- ✅ Store in environment variables (never commit to git)
- ✅ Rotate keys periodically
- ✅ Use different keys for different environments

### 2. Token Storage
- ✅ Store tokens securely (httpOnly cookies or secure storage)
- ✅ Never expose tokens in URLs or logs
- ✅ Clear tokens on logout

### 3. Token Validation
- ✅ Always verify token signature
- ✅ Check token expiration
- ✅ Verify token type (access vs refresh)
- ✅ Check revocation list

### 4. Token Rotation
- ✅ Rotate tokens regularly (on refresh)
- ✅ Revoke old tokens immediately
- ✅ Never reuse refresh tokens

---

## Troubleshooting

### "Invalid or expired token"
- **Cause**: Token expired or signature invalid
- **Fix**: Refresh token or login again

### "Token type mismatch"
- **Cause**: Using refresh token as access token (or vice versa)
- **Fix**: Use correct token type for endpoint

### "Token is revoked"
- **Cause**: Token was revoked (logout or admin action)
- **Fix**: Login again to get new tokens

### "Authorization header missing"
- **Cause**: No Authorization header in request
- **Fix**: Add `Authorization: Bearer <token>` header

---

## Code Examples

### Python Client
```python
import requests

class DaenaClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
    
    def login(self, user_id, email):
        response = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"user_id": user_id, "email": email}
        )
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        return data
    
    def refresh(self):
        response = requests.post(
            f"{self.base_url}/api/v1/auth/refresh",
            headers={"X-Refresh-Token": self.refresh_token}
        )
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        return data
    
    def get_me(self):
        response = requests.get(
            f"{self.base_url}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        return response.json()
```

### JavaScript Client
```javascript
class DaenaClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.accessToken = null;
    this.refreshToken = null;
  }
  
  async login(userId, email) {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, email })
    });
    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    return data;
  }
  
  async refresh() {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'X-Refresh-Token': this.refreshToken }
    });
    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    return data;
  }
  
  async getMe() {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/me`, {
      headers: { 'Authorization': `Bearer ${this.accessToken}` }
    });
    return response.json();
  }
}
```

---

## Related Documentation

- **Auth Service**: `backend/services/auth_service.py` (legacy, being phased out)
- **Role Middleware**: `backend/middleware/role_middleware.py`
- **CSRF Middleware**: `backend/middleware/csrf_middleware.py`
- **Go-Live Checklist**: `docs/GO_LIVE_CHECKLIST.md`

---

**Last Updated**: 2025-01-XX  
**Version**: 1.0

