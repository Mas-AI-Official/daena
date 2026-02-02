# Architecture: Daena = Brain + Governance; DaenaBot Hands = Tool Runtime

This document validates the right architecture for all **8 departments** and the single path from any agent to tool execution.

## Right Architecture

- **Daena** = Brain + Governance (planning, policy, approvals, audit).
- **DaenaBot Hands** (OpenClaw Gateway) = Tool runtime only. No department or agent talks to Hands directly.

## Flow (all 8 departments)

1. **Any department/agent** submits a tool request to **ToolBroker** (e.g. via chat/stream → `async_broker_request`, or any future department API that calls the broker).
2. **ToolBroker** checks policy + risk level (`backend.services.tool_broker`):
   - Allowlist for low-risk actions (e.g. `browser.navigate`, `filesystem.list`).
   - **Medium/high/critical** risk → create an item in **Approvals Inbox** (tool request store); no execution until approved.
3. **Only after approval** (Control Panel → DaenaBot Tools → Approve): ToolBroker calls **Hands** using `DAENABOT_HANDS_URL` / `DAENABOT_HANDS_TOKEN` (or legacy `OPENCLAW_GATEWAY_*`).
4. **Everything is audited**: who, what, when, result. Audit entries are written for:
   - submit (queued_for_approval / blocked)
   - approve / reject (founder)
   - execute (after approval or low-risk auto)

This gives **powerful automation** without turning it into a security nightmare.

## 8 Departments (canonical)

The system uses an **8×6** structure (8 departments × 6 agents). Departments are registered in `backend.utils.sunflower_registry` / `init_agents.py`. All agents in any department must use **ToolBroker** for tool execution; no direct calls to OpenClaw/Hands.

| # | Department   | Role (examples) |
|---|--------------|------------------|
| 1 | Engineering  | Advisor A/B, Scout Internal/External, Synthesizer, Executor |
| 2 | Product      | Same structure |
| 3 | Sales        | Same structure |
| 4 | Marketing    | Same structure |
| 5 | Finance      | Same structure |
| 6 | HR           | Same structure |
| 7 | Legal        | Same structure |
| 8 | Customer     | Same structure |

Tool requests from chat/stream use `requested_by` (e.g. "daena" or agent id); department can be inferred from identity. All such requests go through `async_broker_request` → ToolBroker → policy → Approvals Inbox or Hands.

## Single Gateway to Hands

- **ToolBroker** (`backend.services.tool_broker`) and **DaenaBot Tools API** (`backend.routes.daena_bot_tools`) are the only components that call the OpenClaw gateway client (`backend.integrations.openclaw_gateway_client`).
- Execution path: **approve** in UI → `POST /api/v1/tools/{id}/approve` → `tool_broker.execute_approved_request(req_id)` → OpenClaw client `execute_tool(action)`.

## Env Vars (no token in logs)

- **Preferred:** `DAENABOT_HANDS_URL`, `DAENABOT_HANDS_TOKEN`.
- **Backward compatible:** `OPENCLAW_GATEWAY_URL`, `OPENCLAW_GATEWAY_TOKEN`.
- Helper: `env_first("DAENABOT_HANDS_URL", "OPENCLAW_GATEWAY_URL", default=...)` in `backend.config.settings`.
- **Token is never logged or returned** in API responses; redact everywhere.

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/hands/status` | Configured, reachable (Control UI), url (redacted), last_check, message. For UI "DaenaBot Hands: Connected/Disconnected" and Test button. |
| `GET /api/v1/tools/status` | Connection status (connected, authenticated, display_name). |
| `GET /api/v1/tools/ping-hands` | Test Hands connection (short WS ping). |
| `GET /api/v1/system/capabilities` | Full awareness (hands_gateway, local_llm, governance, tool_catalog). |

## Install DaenaBot Hands (Windows + Docker)

From Daena repo root:

```powershell
.\scripts\setup_daenabot_hands.ps1
```

This script:

- Clones OpenClaw under `.\tools\daenabot-hands\openclaw`
- Generates a Windows-safe token (no `openssl` required)
- Builds and starts the gateway with Docker
- Binds host port to **127.0.0.1 only** (loopback)
- Writes `DAENABOT_HANDS_URL`, `DAENABOT_HANDS_TOKEN`, and legacy `OPENCLAW_*` into `.env`

Control UI: `http://127.0.0.1:18789/`. Do not expose the gateway to LAN or internet.

## Smoke Test

1. Start Daena backend: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
2. (Optional) Start DaenaBot Hands: run `.\scripts\setup_daenabot_hands.ps1` or start OpenClaw gateway separately.
3. Open UI: `http://localhost:8000/ui/control-panel` → DaenaBot Tools tab; confirm status and "Test Hands Connection".
4. Call `GET /api/v1/hands/status`: expect `configured`, `reachable` (if gateway is up), `message`; **no token** in response or logs.
