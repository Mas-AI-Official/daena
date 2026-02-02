# Frontend–Backend Wiring Audit

Summary of key clickable/functional elements and their backend/pipeline integration. Use this to ensure every UI control is wired to the correct API and pipeline.

## Project rule: no deletion without wiring

- **Do not delete** files, routes, or categories unless you are intentionally modifying that area.
- **Before removing anything:** identify all callers (imports, API consumers, UI links) and update or remove those references.
- **After removing:** confirm wiring is intact (no broken imports, no 404s for linked endpoints, no orphaned UI).
- **Prefer adding** new endpoints or fields over deleting existing ones; deprecate first if needed.

---

## 1. Control Panel (control_plane_v2.html) – Primary UX

| Element / Action | Backend / Pipeline | Notes |
|------------------|--------------------|--------|
| **AGI Autopilot toggle** (governance panel) | GET `/api/v1/brain/autopilot` (load), POST `/api/v1/governance/toggle-autopilot` (toggle) | Synced: governance loop + brain DB; topbar uses brain/autopilot; both stay in sync. |
| **Skills** (tab) | GET `/api/v1/skills`, GET `/api/v1/skills/stats`, POST `/api/v1/skills/toggle` | Toggle uses `apiExecution()` (X-Execution-Token when set). |
| **Packages** | GET `/api/v1/packages`, `/stats`, POST `/audit`, `/audit/{id}/run|approve|reject|install` | — |
| **Governance** | GET `/api/v1/governance/stats`, `/pending`, POST `/approve`, `/reject`, `/toggle-autopilot` | Autopilot load on init + when switching to governance tab. |
| **Execution** | GET `/api/v1/execution/auth-status`, `/logs`; POST (with token) `/config`, `/run` | Token in sessionStorage; `apiExecution()` adds header. |
| **DaenaBot Tools** | GET `/api/v1/tools/status`, `/queue`, `/history`, `/ping-hands`; GET `/api/v1/hands/status` (configured, reachable, message); POST `/api/v1/tools/{id}/approve`, `/{id}/reject` | All tool execution goes through ToolBroker; approve/reject/execute are audited. |
| **Integrations** | GET `/api/v1/integrations`, `/mcp-servers` | — |
| **Proactive** | GET `/api/v1/proactive/rules`, `/events` | — |
| **Council, Trust, Shadow, Treasury, Agents** | GET/POST to respective `/api/v1/{council|...}` routes | — |
| **Capability handshake** | GET `/api/v1/execution/logs`, `/api/v1/integrations/mcp-servers` | Run on init; summary shown in Execution tab. |

---

## 2. Topbar (partials/topbar.html + base.html)

| Element | Backend | Notes |
|---------|---------|--------|
| **AGI Autopilot** | GET/POST `/api/v1/brain/autopilot` | `window.loadTopbarAutopilot` exposed for Control Panel to refresh after toggle. |

---

## 3. Brain Settings (brain_settings.html)

| Element | Backend | Notes |
|---------|---------|--------|
| **Autopilot checkbox** | GET/POST `/api/v1/brain/autopilot` | Same source as topbar; governance loop synced on POST. |
| **Models root, Open folder** | GET/POST `/api/v1/brain/models_root`, POST `/api/v1/brain/open-models-folder` | — |

---

## 4. Chat Pipeline (Daena awareness)

| Path | Backend | Notes |
|------|---------|--------|
| **Stream chat** | POST `/api/v1/daena/chat/stream` | Tool path → `detect_and_execute_tool`; search path → `deep_search_service.search_then_answer`; LLM path → full prompt with capabilities_block + AWARENESS line. |
| **Capability injection** | `daena.py` stream prompt: capabilities_block (tools + skills), AWARENESS line, WORKSPACE & FILES. | Daena says she has access when asked. |
| **Deep search** | `deep_search_service.search_then_answer` | System prompt updated with real capabilities (workspace, DaenaBot Hands); direct answer for computer-control questions states access. |

---

## 5. DaenaBot Awareness (capabilities + policies)

| Element | Backend | Notes |
|---------|---------|--------|
| **Hands offline banner** | GET `/api/v1/system/capabilities` | Shown when `available.hands_gateway` is false; text: "DaenaBot can plan but cannot act (Hands offline)." |
| **Remote Hands warning** | Same | When `remote_hands_warning` is true, banner shows ENABLE_REMOTE_HANDS note. |
| **DaenaBot Awareness panel** (Governance tab) | GET `/api/v1/system/capabilities` | Hands status, Local LLM (provider/model/health), Governance mode; loaded on init and when switching to Governance tab. |
| **Policies** | GET `/api/v1/system/policies` | Governance + tool policy summary (autopilot, risk levels, emergency stop, automation mode). |

- **Capability registry:** `backend/core/capabilities.py` — `build_capabilities()` returns hands_gateway (2s WS test), local_llm (Ollama ping), tool_catalog, governance profile, version; `_remote_hands_warning()` true when Hands URL host is not 127.0.0.1 and ENABLE_REMOTE_HANDS is not set.

---

## 6. Autopilot Sync (single source of truth)

- **Runtime (chat pipeline):** `governance_loop.autopilot` (used by chat.py).
- **Persistence:** `SystemConfig` key `autopilot_enabled` (brain_status).
- **Sync rules:**  
  - GET `/api/v1/brain/autopilot`: return governance_loop.autopilot if available, else DB; persist to DB when read from loop.  
  - POST `/api/v1/brain/autopilot`: set DB + governance_loop.autopilot.  
  - POST `/api/v1/governance/toggle-autopilot`: set governance_loop.autopilot + persist via brain_status._set_system_config.  
- **Frontend:** Topbar and Control Panel both load from GET `/api/v1/brain/autopilot`; toggles call brain POST or governance POST; both backends stay synced.

---

## 7. Crypto Monitor (separate page, synced with backend)

| Element | Backend | Notes |
|---------|---------|--------|
| **Page** | GET `/ui/crypto-monitor` | Renders `crypto_monitor.html` (extends base; left panel = sidebar from base). |
| **Sidebar link** | — | "Crypto" in left panel → `/ui/crypto-monitor`. |
| **Dashboard data** | GET `/api/v1/crypto/dashboard` | Returns `summary` (prices, defi_status, scans_count), `defi`, `scans`, `tools`. |
| **Price** | Env `CRYPTO_SYMBOL`, `CRYPTO_PRICE_USD` | Optional; displayed in Crypto Monitor. |
| **DeFi** | `/api/v1/defi` (status, scans) | Crypto dashboard calls defi_status + list_scans for scans and tools. |

- **Wiring:** Crypto page is separate from Control Panel; same sidebar (base.html + partials/sidebar.html). Frontend fetches `/api/v1/crypto/dashboard` on load and every 60s; backend crypto router uses defi module for scans/health.

---

## 8. Links to Control Panel

- **brain_api.html:** "Open in Control Panel" → `/ui/control-panel` (was `/ui/control-plane#governance`; control-panel is canonical).

---

## 9. Other Key Pages (high-level)

- **dashboard.html:** No Quick Actions; links to Control Panel, Brain, etc.
- **daena_office.html:** Chat UI; pipeline status from backend.
- **founder_panel.html, incident_room.html:** Lockdown, emergency; use security/containment APIs.
- **execution.html, skills.html, proactive.html:** Same API base as Control Panel tabs; some pages may duplicate logic – Control Panel is the single pane for Skills, Execution, Governance, DaenaBot Tools, etc.

When adding new buttons or toggles, wire them to the correct `/api/v1/...` route and, for governance/autopilot, keep the sync rules above.
