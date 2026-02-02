# DAENA Wiring Map (Control Plane Integration)

## Frontend → Backend

| Frontend (control_plane_v2.html) | Backend | Notes |
|----------------------------------|---------|--------|
| WebSocket `/ws/events` | `backend/routes/websocket.py` | event_bus connects here |
| `POST /api/v1/governance/toggle-autopilot` | `backend/routes/governance.py` | Broadcasts governance_autopilot_changed |
| `GET /api/v1/governance/pending` | `backend/routes/governance.py` | Pending actions table |
| `POST /api/v1/governance/approve/{id}` | `backend/routes/governance.py` | Approve by ID |
| `POST /api/v1/governance/reject/{id}` | `backend/routes/governance.py` | Reject by ID |
| `GET /api/v1/brain/autopilot` | `backend/routes/brain_status.py` | Topbar + Governance tab sync |
| `POST /api/v1/chat` | `backend/routes/chat.py` | Think→Plan→Act pipeline, broadcasts governance_pipeline |

## Event flow

- **event_bus.broadcast(event_type, data, message)** → all WebSocket clients receive `{ event_type, entity_type, entity_id, payload, timestamp }`.
- **handleWSEvent(ev)** uses `ev.event_type || ev.type` and `ev.payload`; routes to brainFeed, govFeed, pkgFeed, etc.; calls `animatePipeline(payload.stage)` for governance_pipeline.

## Pipeline stages (chat)

1. **think** — broadcast governance_pipeline(stage: think)
2. **plan** — broadcast governance_pipeline(stage: plan)
3. **act** — governance_loop.assess(action); broadcast act or blocked
4. **report** — broadcast governance_pipeline(stage: report)

## Files modified (this pass)

- `backend/services/event_bus.py` — added `broadcast()`
- `backend/services/governance_loop.py` — added `assess()`
- `backend/routes/chat.py` — fixed event_bus usage, _broadcast_stage uses broadcast()
- `backend/routes/governance.py` — toggle broadcasts event; added approve/{id}, reject/{id}
- `frontend/templates/control_plane_v2.html` — WebSocket reconnect backoff; handleWSEvent uses event_type + payload
- `backend/main.py` — registered governance_router, chat_router, treasury_router
- `backend/routes/treasury.py` — GET /api/v1/treasury/status
- `backend/routes/brain_status.py` — GET /api/v1/brain/health
- `backend/services/llm_service.py` — should_execute_action (governance gate)
- `docs/TOKENOMICS.md` — $DAENA token design
- `contracts/DAENA_TOKEN_SPEC.md` — contract spec
- `frontend/templates/control_plane_v2.html` — loadTreasury() fetches API
- `.github/dependabot.yml` — new
- `SECURITY.md` — vulnerability reporting + patch timeline
- `docs/DAENA_IMPLEMENTATION_PLAN.md` — new
- `docs/WIRING_MAP.md` — this file
- `frontend/.npmrc` — new
