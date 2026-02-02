## Automation / Operator System (2025-12-13)

### Overview
Daena includes a **safe-by-default Operator/Automation layer** that can:
- **Scrape** web pages (HTTP fetch + structured extraction)
- **Optionally** control a browser session (click/type/navigate) using **Playwright (Python)** — disabled by default
- **Optionally** perform desktop automation using **pyautogui** — disabled by default

All actions are callable via:
- `/api/v1/automation/*`
- CMP tool calls via `/api/v1/cmp/tools` + `/api/v1/cmp/tools/execute`

### Endpoints
- **POST** `/api/v1/automation/scrape`
  - Body: `{ "url": "...", "selector": null, "mode": "text|links|tables" }`
- **POST** `/api/v1/automation/process/start`
- **GET** `/api/v1/automation/process/{id}`
- **GET** `/api/v1/automation/processes`
- **POST** `/api/v1/automation/process/{id}/cancel`

Optional browser endpoints (require `AUTOMATION_ENABLE_BROWSER=1` + Playwright installed):
- `/api/v1/automation/browser/session/create`
- `/api/v1/automation/browser/navigate`
- `/api/v1/automation/browser/click`
- `/api/v1/automation/browser/type`
- `/api/v1/automation/browser/screenshot`

Optional desktop endpoints (require `AUTOMATION_ENABLE_DESKTOP=1` + pyautogui installed):
- `/api/v1/automation/desktop/click`
- `/api/v1/automation/desktop/type`

### CMP Tools
Canonical tools are registered in `backend/tools/registry.py`:
- `web_scrape_bs4`
- `browser_automation_selenium` *(optional + gated)*
- `desktop_automation_pyautogui` *(optional + gated)*

Canonical executor endpoint:
- `POST /api/v1/tools/execute`
  - Body includes: `tool_name, args, department, agent_id, reason`

Legacy/CMP compatibility:
- `/api/v1/cmp/tools` and `/api/v1/cmp/tools/execute` exist but delegate to the canonical tool runner.

### Security model
- **Safe mode default**: `AUTOMATION_SAFE_MODE=true`
- **Allowlist**: `AUTOMATION_ALLOWED_DOMAINS=...`
- **Redaction**: common secret-like fields are redacted in logs/outputs
- **Timeouts**: `AUTOMATION_REQUEST_TIMEOUT_SEC`, `AUTOMATION_ACTION_TIMEOUT_SEC`
- **Rate limiting**: `AUTOMATION_RATE_LIMIT_PER_MIN` (basic per-process)


