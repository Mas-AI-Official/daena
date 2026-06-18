# Security Ops Fix Report

Date: 2026-04-30

## Finding

The 404 probe against `/api/v1/security/dashboard` was not the route the page uses. Source inspection shows `SecurityDashboardPage.tsx` calls:

- `/security/status`
- `/security/tools`
- `/security/shields`
- `/security/opsec/status`

Those are mounted under `/api/v1/security/*` by `backend/app/api/v1/__init__.py`.

## Actual Risk

The page was not a permanent skeleton in source, because `fetchAll()` has a `finally` that clears `loading`. But it could look stuck for the global 30-second Axios timeout, especially when the backend is unreachable.

## Patch Applied

`frontend/src/pages/SecurityDashboardPage.tsx` now:

- Uses a 10-second request timeout for the four Security Ops cold-load calls.
- Shows explicit error copy: `Security Ops backend request failed: ...`.
- Keeps the existing empty/error state path instead of leaving skeletons indefinitely.

## Verification

Vite transformed `/src/pages/SecurityDashboardPage.tsx` with:

- `SECURITY_REQUEST_TIMEOUT_MS` present.
- explicit backend request failure copy present.
- no Vite internal server error.

## Remaining Blocker

Backend is currently offline due WSL/Windows runtime failure, so live endpoint behavior could not be re-probed after the patch.
