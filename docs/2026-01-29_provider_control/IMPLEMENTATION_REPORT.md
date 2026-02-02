# Provider Control Implementation Report (2026-01-29)

File-by-file list of changes for Moltbot-style provider control + onboarding. No proprietary code copied; no duplicate apps or folders; existing Execution Layer and lockdown/deception preserved.

---

## New files

| Path | What |
|------|------|
| `backend/providers/__init__.py` | Package init; exports ProviderBase, ProviderStatus, InboundMessage, get_provider_registry. |
| `backend/providers/base.py` | Abstract interface: connect(), disconnect(), status(), send_message(), receive_message(), verify_webhook(). ProviderStatus, InboundMessage, OutboundMessage dataclasses. |
| `backend/providers/config.py` | Provider config (enabled, allowed_tools, standing_instructions) in `config/provider_config.json`. Default: all disabled. Credentials never stored. |
| `backend/providers/discord_adapter.py` | Discord adapter: credentials from DISCORD_BOT_TOKEN; connect (validate token), send_message (channel), receive_message (webhook payload), verify_webhook (optional). |
| `backend/providers/telegram_adapter.py` | Telegram adapter: credentials from TELEGRAM_BOT_TOKEN; connect (getMe), send_message (sendMessage), receive_message (webhook payload), verify_webhook (optional secret). |
| `backend/providers/registry.py` | get_adapter(provider_id), list_provider_ids(), get_provider_registry(); credentials from env only. |
| `backend/services/provider_tool_request.py` | create_tool_request_from_message() → ProviderToolRequest; submit_tool_request() → Execution Layer (allowlist, approval, audit). Intent map: health check, git status, git diff, list tools. |
| `backend/routes/providers.py` | GET/POST /api/v1/providers, /config; POST /{id}/connect, /disconnect, /test; POST /webhook/discord, /webhook/telegram. |
| `frontend/templates/provider_onboarding.html` | Onboarding wizard (4 steps): choose providers, tokens/connect, standing instructions + allowlist, test send. Extends base.html; reuses dashboard-style layout. |
| `tests/test_provider_tool_request_smoke.py` | Smoke tests: create ToolRequest from mock message; denial when provider disabled; denial when tool not in allowlist; submit health_check succeeds; approval mode respected. |
| `docs/2026-01-29_provider_control/README.md` | Setup, credentials, onboarding, webhooks, security rules, smoke test. |
| `docs/2026-01-29_provider_control/IMPLEMENTATION_REPORT.md` | This file. |

---

## Modified files

| Path | What changed |
|------|----------------|
| `backend/config/settings.py` | Added optional env: discord_bot_token, telegram_bot_token, telegram_webhook_secret_token. |
| `backend/main.py` | safe_import_router("providers") so /api/v1/providers* is registered. |
| `backend/routes/ui.py` | Added GET /ui/provider-onboarding → provider_onboarding.html. |
| `frontend/templates/partials/sidebar.html` | Added "Provider onboarding" nav link. |
| `frontend/templates/dashboard.html` | Added "Provider onboarding" quick button. |
| `requirements.txt` | Comments: httpx for providers; pytest-asyncio for smoke test; provider/smoke note. |
| `scripts/run_provider_smoke_test.bat` | Runs provider smoke test; venv detection; pip install pytest/pytest-asyncio/httpx. |
| `run_smoke_tests.bat` | Project-root launcher for smoke tests (calls scripts\run_provider_smoke_test.bat). |
| `scripts/install_dependencies.bat` | Verify httpx and pytest; note run_provider_smoke_test.bat. |
| `START_DAENA.bat` | Added Provider onboarding URL to startup output. |
| `_daena_backend_launcher.bat` | Added Provider onboarding URL to backend console output. |

---

## Unchanged (reused as-is)

- **Execution Layer**: `backend/tools/registry.py`, `backend/tools/audit_log.py`, `backend/tools/policies.py`, `backend/services/execution_layer_config.py`, `backend/routes/execution_layer.py` — provider ToolRequests flow through existing execute_tool(), audit, approval, budget.
- **Lockdown / deception**: `backend/middleware/lockdown_middleware.py`, `backend/routes/deception.py` — no changes.
- **CMP / tool run**: `backend/services/cmp_service.py` — no changes; provider_tool_request calls execute_tool directly for tool runs.

---

## Summary

- **Provider adapters**: 2 (Discord, Telegram) with common interface; credentials from env only.
- **Onboarding**: 4-step wizard inside existing dashboard UI.
- **Security**: Provider messages → ToolRequest → Execution Layer (allowlist, approval, budget, audit); default providers disabled; no control plane exposed to internet.
- **Deliverables**: Implementation report (this doc), smoke test script, dated docs folder for setup and safe exposure.
