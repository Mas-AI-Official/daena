# Daena Upgrade Plan (2026-01-29)

## Scope

This plan covers upgrades derived from:

1. **report bug.txt** – ChatGPT conversation on security hardening (deception layer, Guardian, incident response).
2. **Session summary** – MODELS_ROOT, execution layer, brain/voice sync, Ollama fallback, dashboard, App Setup, frontend fixes.

## Objectives

- **Security**: Deception pack (decoy routes), lockdown mode, Guardian linkage, incident visibility.
- **Reliability**: Ollama fallback (“local brain”), brain/voice status accuracy.
- **Operability**: Execution layer (tool registry, dry-run, audit), App Setup UI, dashboard layout.
- **Documentation**: All changes recorded under `docs/2026-01-29/`.

## Deliverables

| Item | Status | Notes |
|------|--------|-------|
| MODELS_ROOT & Ollama/XTTS paths | Done | settings, START_DAENA.bat, start_xtts.bat |
| Execution layer (config, routes, registry) | Done | execution_layer_config.json, execution_layer.py, dry_run, budget guard |
| Brain status (primary + fallback) | Done | brain_status.py, local_llm_ollama.py, local_brain_manager |
| Voice status fixes | Done | realtime-status-manager.js, voice-widget.js |
| Dashboard 2x2 + App Setup | Done | dashboard.html, app_setup.html |
| Deception layer (decoy routes) | Done | backend/routes/deception.py |
| Register deception router | Done | main.py |
| SECURITY_LOCKDOWN_MODE + founder lockdown | Done | settings, security_state, founder_panel |
| Incident Room / Guardian docs | Done | INCIDENT_ROOM_AND_GUARDIAN.md |
| docs/2026-01-29 | Done | PLAN, REPORT_TAKEAWAYS, DECEPTION_LAYER, CHANGELOG, etc. |

## Incident Room UI (Done)

- **URL**: `/incident-room` – lockdown status, Lockdown/Unlock buttons, decoy hits table; link from QA Guardian Dashboard.
- **API**: `GET /founder-panel/system/emergency/status`; api-client methods for decoy hits and lockdown/unlock.

## Rate limiting & WAF (Done)

- **Config**: `RATE_LIMIT_ENABLED`; when set, global rate limit middleware is applied. See `RATE_LIMITING_AND_WAF.md` for behavior and edge (Cloudflare/Cloud Armor) recommendations.

## Guardian containment playbooks (Done)

- **Containment service**: Auto-block IP after N deception hits; block/unblock/lockdown playbook API; lockdown middleware returns 403 for blocked IPs. See `CONTAINMENT_PLAYBOOKS.md`.

## Token revocation for containment (Done)

- **JWT**: `record_tokens_for_ip` at login/refresh; `revoke_tokens_for_ip(ip)` when containment blocks an IP. See `TOKEN_REVOCATION_CONTAINMENT.md`.

## Frontend XSS – escapeHtml (Done)

- **Applied**: base.html (model label), dashboard.html (brain, activity list, task dept names), realtime-status-manager.js (activeModel), agent_detail.js (response, error, message). Incident Room already used escapeHtml/escapeAttr.
- **Doc**: `docs/2026-01-29/XSS_ESCAPE_AUDIT.md` – where escapeHtml is used and recommendation for remaining scripts (department-chat, change-audit, agents, etc.).

## Future Work (from report bug.txt)

- **Lockdown middleware (Done)**: When lockdown is active, non-whitelisted requests return 503; whitelist includes /ui/*, /incident-room, emergency status/unlock, decoy hits, containment API. See `INCIDENT_ROOM_AND_GUARDIAN.md`.
