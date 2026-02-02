# Rate Limiting & WAF

## Global HTTP rate limiting (app layer)

- **Config**: `RATE_LIMIT_ENABLED` in `backend/config/settings.py` (env: `RATE_LIMIT_ENABLED`, default `False`).
- **Middleware**: `backend/middleware/rate_limit.py` – when enabled, applies per-client, per-endpoint limits before the request reaches route handlers.
- **Behavior**:
  - Client ID: `X-Forwarded-For` (first hop) or `request.client.host`.
  - Limit keys: `auth` (10/min), `council` (50/min), `founder` (200/min), `chat` (configurable via `CHAT_RATE_LIMIT_PER_MIN`, default 60), `default` (500/min).
  - Skips: health, docs, static, dashboard paths; in development/test, skips 127.0.0.1, localhost, ::1.
  - On exceed: `429 Too Many Requests` with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`.
- **Enable in production**: set `RATE_LIMIT_ENABLED=1` (or `true`/`yes`) in env.

## Tenant rate limiting (optional)

- **Router**: `backend/routes/tenant_rate_limit.py` (mounted at `/api/v1`) – tenant-specific limits when tenant context is available.
- **Middleware**: `backend/middleware/tenant_rate_limit.py` – currently commented out in `main.py`; enable alongside global rate limit if you use tenant IDs.

## WAF / edge (recommendations)

- **Cloudflare**: Put Daena behind Cloudflare; use Rate Limiting rules, WAF managed rules, and DDoS protection at the edge. Trust `CF-Connecting-IP` or `X-Forwarded-For` for client IP in app rate limit.
- **Google Cloud Armor**: If hosting on GCP, use Cloud Armor policies for rate limiting and WAF at load balancer; forward client IP via `X-Forwarded-For`.
- **Lockdown**: When `SECURITY_LOCKDOWN_MODE` or runtime lockdown is active, consider rejecting non-essential API traffic at edge or in a middleware (future enhancement).

## Related

- **System summary**: `GET /api/v1/system-summary` (when available) can expose `rate_limiting` stats from `backend.middleware.rate_limit.rate_limiter`.
- **report bug.txt**: Edge defense and rate limiting were called out; this implements app-layer rate limiting and documents edge options.
