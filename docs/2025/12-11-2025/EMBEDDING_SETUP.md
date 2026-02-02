# VibeAgent Embedding Setup

## Quick Start

### 1. Environment Variables

Add to `.env`:

```bash
# SSO Configuration
SSO_JWT_SECRET=your-secret-key-here
SSO_JWT_ALGORITHM=HS256
SSO_JWT_EXPIRY_MINUTES=15

# VibeAgent URL
VIBEAGENT_URL=http://localhost:3000

# Allowed origins for iframe embedding
EMBED_ALLOWED_ORIGINS=http://localhost:8000,https://daena.mas-ai.co
```

### 2. Access Embedded VibeAgent

Navigate to: `http://localhost:8000/apps/vibeagent`

### 3. Test SSO

```bash
# Issue token
curl http://localhost:8000/sso/issue \
  -H "Cookie: access_token=..." \
  | jq

# Verify token
curl "http://localhost:8000/sso/verify?token=..." | jq
```

## Files Created

- `backend/routes/sso.py` - SSO endpoints
- `backend/middleware/csp_middleware.py` - CSP headers
- `frontend/templates/apps/vibeagent.html` - Embed template
- Route `/apps/vibeagent` in `main.py`

## Documentation

See `VibeAgent/docs/EMBEDDING.md` for complete documentation.












