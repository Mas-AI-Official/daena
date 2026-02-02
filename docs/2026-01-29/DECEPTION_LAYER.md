# Deception Layer (Decoy Routes)

## Purpose

Attract and detect probing or attacks by exposing fake high-value endpoints. Any access is logged and emitted for the Security Guardian and Incident Room.

## Endpoints (all under `/api/v1/_decoy`)

| Path | Method | Description |
|------|--------|-------------|
| `/admin` | GET | Fake admin panel; returns Unauthorized |
| `/admin/login` | POST | Fake login; logs body presence, returns Invalid credentials |
| `/api/keys` | GET | Fake API keys list; returns empty list |
| `/env` | GET | Fake env dump; returns safe fake values |
| `/hits` | GET | Recent decoy hits (for Incident Room / Guardian); auth recommended in production |

## Behavior

- Each decoy handler calls `_log_hit()` with request metadata (path, method, label, client_host, x_forwarded_for, user_agent).
- Hits are stored in memory (max 500); for production, persist to DB or forward to SIEM.
- Logger emits `[DECOY HIT]` at WARNING level.
- If `backend.routes.events.emit` is available, emits `security.deception_hit` with the hit payload for Guardian/monitoring.

## Registration

The deception router is registered in `backend/main.py` immediately after the security router:

```python
from backend.routes.deception import router as deception_router
app.include_router(deception_router)
```

## Security Note

- Do not advertise `/api/v1/_decoy` in public docs; keep it unlisted so only real attackers or scanners hit it.
- Protect `/hits` with auth in production so only operators/Guardian can read.
