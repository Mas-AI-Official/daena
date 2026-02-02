# Changelog – 2026-01-29

All changes from the report bug.txt takeaways and session summary, documented under `docs/2026-01-29/`.

## Configuration & Brain

- **MODELS_ROOT**: `backend/config/settings.py` uses `models_root` for Ollama and XTTS paths; `ollama_models_path` and `xtts_model_path` derived when not set.
- **Ollama fallback**: `ollama_fallback_port`, `ollama_use_local_brain_fallback`; `local_brain_manager.py` and primary-then-fallback in `local_llm_ollama.py` and `brain_status.py`.
- **Startup**: `START_DAENA.bat`, `scripts/START_OLLAMA.bat`, `start_xtts.bat` set `MODELS_ROOT` and GPU-related env for Ollama/XTTS.

## Execution Layer

- **Config**: `config/execution_layer_config.json`, `backend/services/execution_layer_config.py`.
- **Routes**: `backend/routes/execution_layer.py` (tool list, execute, audit log).
- **Registry**: `backend/tools/registry.py` – dry_run, secure workspace path resolution; budget guard in `tool_playbooks.py`.
- **Frontend**: `api-client.js` supports `X-Execution-Token` and execution APIs; `dashboard.html` execution panel.

## Dashboard & App Setup

- **Dashboard**: 2x2 grid layout; brain/voice status from API; execution layer panel.
- **App Setup**: `frontend/templates/app_setup.html` and route in `main.py`; sidebar/nav links.

## Security

- **Deception layer**: `backend/routes/deception.py` – decoy routes under `/api/v1/_decoy`, hit logging, `security.deception_hit` emit; router registered in `main.py`.
- **Lockdown**: `SECURITY_LOCKDOWN_MODE` in settings; `backend/config/security_state.py` runtime flag; founder panel `POST .../system/emergency/lockdown` sets runtime lockdown and returns response.
- **Docs**: `DECEPTION_LAYER.md`, `INCIDENT_ROOM_AND_GUARDIAN.md`, `REPORT_TAKEAWAYS.md`.

## Frontend & Status

- **Brain status**: `brain_status.py` connected logic and configurable URLs; dashboard and realtime-status-manager use API.
- **Voice status**: `realtime-status-manager.js`, `voice-widget.js` – stable ON/OFF display.
- **Connections**: Duplicate `{% block scripts %}` removed in `connections.html`; `handleApiError` in `base.html`.
- **Brain test**: `/api/v1/brain/test` accepts optional `model_name` in body.

## Incident Room UI

- **Route**: `GET /incident-room` (cmp_canvas_router in `qa_guardian.py`); template `incident_room.html`.
- **API**: `GET /api/v1/founder-panel/system/emergency/status` (lockdown status); api-client methods `getDecoyHits`, `getLockdownStatus`, `postLockdown`, `postUnlock`.
- **Page**: Lockdown bar (status + Lockdown/Unlock), decoy hits table; link from QA Guardian Dashboard header.

## Rate limiting & WAF

- **Setting**: `rate_limit_enabled` in settings (env `RATE_LIMIT_ENABLED`, default `False`). When `True`, global rate limit middleware is applied (`backend.middleware.rate_limit`).
- **Doc**: `docs/2026-01-29/RATE_LIMITING_AND_WAF.md` – middleware behavior, env vars, Cloudflare/Cloud Armor recommendations.

## Lockdown middleware

- **Module**: `backend/middleware/lockdown_middleware.py` – when `is_lockdown_active()` is true, returns 503 for requests that are not on a whitelist.
- **Whitelist**: health, docs, static, /ui/*, /incident-room, /api/v1/qa/ui, founder-panel emergency status and unlock, /api/v1/_decoy/hits, /api/v1/security/containment, cmp-canvas, control-center.
- **Registration**: Middleware added in `main.py` (always active; when lockdown is off, passes through). Blocked IPs (containment blocklist) get 403 before lockdown check.

## Guardian containment playbooks

- **Service**: `backend/services/security_containment.py` – in-memory blocked IPs, `on_deception_hit(hit)` (count per IP, auto-block after N hits, optional auto lockdown), `block_ip`/`unblock_ip`/`run_playbook`/`get_status`.
- **API**: `backend/routes/security_containment.py` – GET `/api/v1/security/containment/status`, POST `block-ip`, `unblock-ip`, `playbook` (action: lockdown \| block_ip \| unblock_ip).
- **Deception**: After each decoy hit, `on_deception_hit(hit)` is called; threshold and window configurable via `DECEPTION_HITS_BEFORE_BLOCK`, `DECEPTION_HITS_WINDOW_SEC`, `AUTO_LOCKDOWN_ON_BLOCK`.
- **Middleware**: Lockdown middleware returns 403 for requests whose client IP is in the containment blocklist.
- **Doc**: `docs/2026-01-29/CONTAINMENT_PLAYBOOKS.md`.

## Token revocation for containment

- **JWT**: `backend/services/jwt_service.py` – `record_tokens_for_ip(ip, access_token, refresh_token)` (called at login/refresh), `revoke_tokens_for_ip(ip)` (revokes all tokens for that IP). Per-IP token count capped via `JWT_MAX_TOKENS_PER_IP` (default 50).
- **Auth routes**: `backend/routes/auth.py` – login and refresh record client IP and call `record_tokens_for_ip` after issuing token pair.
- **Containment**: `block_ip()` in `security_containment.py` calls `jwt_service.revoke_tokens_for_ip(ip)` so blocked IPs’ sessions are invalidated.
- **Doc**: `docs/2026-01-29/TOKEN_REVOCATION_CONTAINMENT.md`.

## Frontend XSS – escapeHtml

- **base.html**: Brain status indicator – `modelLabel` from API escaped when setting `indicator.innerHTML`.
- **dashboard.html**: Brain `activeModel`, activity list `formatEventText(event)` and `timeAgo`, task progress department name escaped.
- **realtime-status-manager.js**: `activeModel` escaped for brain indicator innerHTML.
- **agent_detail.js**: API `data.response` escaped before `formatResponse()`; `data.error` and `error.message` escaped; local `escapeHtml` made null-safe.
- **Doc**: `docs/2026-01-29/XSS_ESCAPE_AUDIT.md` – audit and recommendation for remaining scripts.

## START_DAENA.bat launch fix

- **Problem**: Launcher/backend window auto-closed due to nested quotes in `start "DAENA - BACKEND" cmd /k "cd /d "%ROOT%" && ..."`.
- **Fix**: Backend and audio started via helper batches `_daena_backend_launcher.bat` and `_daena_audio_launcher.bat` (no nested quotes). Port fallback: `if not defined BACKEND_PORT set BACKEND_PORT=8000`. Audio venv check uses `%ROOT%venv_...`.
- **Scripts**: `scripts\start_backend.bat`, `quick_start_backend.bat`, `simple_start_backend.bat` – venv fallback (main then audio), `PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend`.
- **Doc**: `docs/2026-01-29/LAUNCH_FIX_START_DAENA.md`. If backend fails with `ModuleNotFoundError: pydantic_settings`, install backend deps: `venv_daena_main_py310\Scripts\pip install -r backend\requirements.txt`.

## UI/UX & dashboard coverage

- **Sidebar**: Added Connections (`/ui/connections`), Incident Room (`/incident-room`), QA Guardian (`/api/v1/qa/ui`), System Monitor (`/ui/system-monitor`).
- **Dashboard**: Quick actions for Connections, Incident Room, QA Guardian.
- **Lockdown banner**: Base layout shows a red “System in lockdown” banner with link to Incident Room when `GET /api/v1/founder-panel/system/emergency/status` returns `lockdown_active: true`.
- **XSS**: Global `window.escapeHtml(s)` in base.html for safe display of user content; use when setting innerHTML from user/API data.
- **Doc**: `docs/2026-01-29/UI_UX_COVERAGE.md` – backend → UI mapping, sidebar, quick actions, consistency.

## Department Office – real-time data and Send fix

- **Backend**: `serve_department_office` in `main.py` now loads agents from `sunflower_registry.get_department_agents(department_id)` and passes `agents` and `agent_count` to the template. If the registry returns fewer than 6 agents, a fallback list (rep + Advisor A/B, Scout Internal/External, Synth, Executor) is used so the UI always shows 6 agents per department.
- **Template**: `department_office.html` – Department Stats uses `agent_count`; Team section loops over `agents` with safe `agent.name | default('Agent')` and `agent.role | default('')`; `repInitials` uses `rep_initials` from backend (no dependency on `agents[0]`). Content block structure fixed: sidebar and office-container are properly closed before `{% endblock %}`.
- **Send button**: Inline script already used `getElementById('messageInput')`; made `loadChatSessions` and `renderChatHistoryList` null-safe for missing `chat-history-list` so page init does not throw and Send/Enter keep working.
- **Voice widget**: `voice-widget.js` now looks for `message-input` or `messageInput` so department office pages get voice-to-input and auto-send; when no `chat-form` exists, calls `window.sendMessage()` if defined.

## Brain status – real-time recovery when offline

- **realtime-status-manager.js**: When brain status is offline, a 3s polling interval is started (`startBrainOfflinePoll`) so the UI updates as soon as Ollama is back. When brain is online, the fast interval is cleared (`stopBrainOfflinePoll`). General status still polls every 10s.

## Incident Room – same layout as app, left menu, error fixes

- **Layout**: `incident_room.html` now **extends `base.html`** so the page has the same left sidebar and top bar as Dashboard, Daena Office, etc. Users can go back via the sidebar (Dashboard, QA Guardian, etc.) or the “Dashboard” button in the page header.
- **Sidebar**: Incident Room link in the sidebar is highlighted when on the page (`bg-white/10 text-white`).
- **Script errors**: API helper now uses `window.DAENA_API_BASE` when available; on non-OK responses the error body is parsed as JSON for `detail`/`message` before throwing. All `escapeHtml`/`escapeAttr` calls are null-safe (handle `null`/`undefined`). Inline handlers are namespaced (`incidentRoomRefreshHits`, `incidentRoomDoLockdown`, etc.) to avoid clashes with base scripts.
- **Styling**: Page-specific styles are scoped under `.incident-room` and use the app theme (glass panels, gold accents, same borders). “Dashboard” and “Refresh hits” buttons added in the header.

## Documentation

- **docs/2026-01-29/**: `PLAN.md`, `REPORT_TAKEAWAYS.md`, `DECEPTION_LAYER.md`, `INCIDENT_ROOM_AND_GUARDIAN.md`, `RATE_LIMITING_AND_WAF.md`, `CONTAINMENT_PLAYBOOKS.md`, `BAT_FILES_UPGRADE.md`, `UI_UX_COVERAGE.md`, `CHANGELOG.md`, `FRONTEND_AND_SECURITY_SUGGESTIONS.md`, `IMPLEMENTATION_SUMMARY.md`.
