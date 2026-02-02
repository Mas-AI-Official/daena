# Token Revocation for Containment (2026-01-29)

## Overview

When an IP is blocked by security containment (manual block or auto-block after deception hits), any JWT sessions that were issued to that IP are revoked so the blocked client cannot continue using existing tokens.

## Behavior

1. **At login/refresh**  
   When `POST /api/v1/auth/login` or `POST /api/v1/auth/refresh` is called, the client IP is taken from `X-Forwarded-For` or `request.client.host`. The issued access and refresh tokens are recorded in the JWT service under that IP (`record_tokens_for_ip`).

2. **At block**  
   When containment blocks an IP (`block_ip()` in `security_containment.py`), it calls `jwt_service.revoke_tokens_for_ip(ip)`. All tokens ever recorded for that IP are added to the revocation list and removed from the IP→tokens map. Subsequent requests using those tokens get 401 (token revoked).

3. **Request handling**  
   Blocked IPs are already rejected with **403** by the lockdown middleware before any route runs. Revocation ensures that if the IP is later unblocked, previously issued tokens still cannot be used.

## Code

- **JWT service** (`backend/services/jwt_service.py`):
  - `_ip_to_tokens: Dict[str, Set[str]]` – maps client IP to set of tokens.
  - `record_tokens_for_ip(ip, access_token, refresh_token)` – called from auth routes after issuing tokens.
  - `revoke_tokens_for_ip(ip)` – revokes all tokens for that IP; returns count.
  - Per-IP token count is capped via `JWT_MAX_TOKENS_PER_IP` (default 50).

- **Auth routes** (`backend/routes/auth.py`):
  - `login` and `refresh` use `Request` to get client IP and call `jwt_service.record_tokens_for_ip(...)` after generating the token pair.

- **Containment** (`backend/services/security_containment.py`):
  - `block_ip()` calls `jwt_service.revoke_tokens_for_ip(ip)` inside a try/except so missing or failing JWT service does not break containment.

## Configuration

- `JWT_MAX_TOKENS_PER_IP` (default `50`) – maximum number of tokens stored per IP; older entries are dropped when over cap.

## Notes

- When auth is disabled (`DISABLE_AUTH=1`), login/refresh may not be used; revocation still runs on block and has no negative effect.
- Revocation storage is in-memory; restart clears the revocation list and IP→tokens map. For production, consider Redis or a DB for revocation and IP→token mapping.
