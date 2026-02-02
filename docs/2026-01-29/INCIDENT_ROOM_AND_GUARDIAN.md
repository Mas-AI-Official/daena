# Incident Room & Security Guardian Linkage

## Lockdown Mode

- **Config**: `SECURITY_LOCKDOWN_MODE` in `backend/config/settings.py` (env: `SECURITY_LOCKDOWN_MODE`, default `False`).
- **Runtime**: `backend/config/security_state.py` provides `is_lockdown_active()` and `set_lockdown(active: bool)`. When the founder panel calls **System lockdown** (`POST /api/v1/founder-panel/system/emergency/lockdown`), it sets the runtime lockdown flag to `True` and returns a response. The rest of the app can call `is_lockdown_active()` to enforce containment (e.g. reject non-essential API calls, show maintenance page).
- **Clearing**: Operator can call `POST /api/v1/founder-panel/system/emergency/unlock` to clear the runtime lockdown; or set `SECURITY_LOCKDOWN_MODE=0` and restart for env-based lockdown.
- **Lockdown middleware**: When lockdown is active, `backend.middleware.lockdown_middleware` returns 503 for all requests except whitelisted paths (health, docs, static, /ui/*, /incident-room, emergency status/unlock, decoy hits, cmp-canvas). Operators can still open Incident Room and unlock.

## Deception Hits → Guardian

- Decoy routes in `backend/routes/deception.py` emit `security.deception_hit` via `backend.routes.events.emit` (when available).
- QA Guardian and any Security Guardian logic can subscribe to this event to:
  - Update Incident Room UI (deception hits list, timeline).
  - Run containment playbooks (e.g. block IP, revoke token, enable lockdown).
- Decoy hit list is also available via `GET /api/v1/_decoy/hits?limit=100` for dashboards.

## Incident Room UI (Implemented)

- **URL**: `/incident-room` (served by `cmp_canvas_router` in `backend/routes/qa_guardian.py`).
- **Page**: `frontend/templates/incident_room.html` – shows lockdown status (from `GET /api/v1/founder-panel/system/emergency/status`), Lockdown / Unlock buttons (POST to founder-panel), and a table of decoy hits (`GET /api/v1/_decoy/hits?limit=100`).
- **Nav**: QA Guardian Dashboard header includes an “Incident Room” link to `/incident-room`.
- **Guardian playbooks (future)**: Containment actions (token revocation, service quarantine, auto-block IP) can be added to Guardian or a dedicated security service.
