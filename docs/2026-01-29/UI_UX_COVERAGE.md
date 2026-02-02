# UI/UX & Dashboard Coverage of Backend Workflows

## Purpose

Ensure every major backend workflow has a reachable, working UI page or dashboard so operators and founders can use the system without calling APIs directly.

## Sidebar (main nav)

All links use the sidebar in `frontend/templates/partials/sidebar.html` (included by `base.html`). Current entries:

| Label           | Path               | Backend / Notes                    |
|----------------|--------------------|------------------------------------|
| Dashboard      | `/ui/dashboard`    | Brain status, execution layer, quick actions |
| Daena Office   | `/ui/daena-office` | Chat, daena router                 |
| Projects       | `/ui/projects`     | projects_router                    |
| Councils       | `/ui/councils`     | councils_router, council_router    |
| Workspace      | `/ui/workspace`    | workspace_router                   |
| Analytics      | `/ui/analytics`    | analytics_router                   |
| Agents         | `/ui/agents`       | agent activity, categories        |
| Brain & API    | `/ui/brain-settings` | brain_status, LLM/Ollama          |
| App Setup      | `/ui/app-setup`    | Core services config (Moltbot-style) |
| Founder        | `/ui/founder-panel`| founder_api_router, emergency      |
| Connections    | `/ui/connections`  | connections_router (integrations)  |
| Incident Room  | `/incident-room`   | Decoy hits, lockdown/unlock        |
| QA Guardian    | `/api/v1/qa/ui`    | qa_guardian_router                 |
| System Monitor | `/ui/system-monitor` | system_monitor template, monitoring |

## Dashboard quick actions

The main dashboard (`/ui/dashboard`) includes:

- **Ask Daena** → `/ui/daena-office`
- **View Agents** → `/ui/agents`
- **Projects** → `/ui/projects`
- **Analytics** → `/ui/analytics`
- **Brain Settings** → `/ui/brain-settings`
- **App Setup** → `/ui/app-setup`
- **Founder Panel** → `/ui/founder-panel`
- **Connections** → `/ui/connections`
- **Incident Room** → `/incident-room`
- **QA Guardian** → `/api/v1/qa/ui`

Plus: **Execution Layer** panel (tools, run, logs, token) and **Brain status** card (from `/api/v1/brain/status`).

## Backend → UI mapping (key workflows)

| Backend area           | API prefix / routes           | UI page(s)                          |
|------------------------|-------------------------------|------------------------------------|
| Brain / Ollama         | `/api/v1/brain/*`             | `/ui/brain-settings`, dashboard card |
| Voice                  | `/api/v1/voice/*`             | Dashboard top bar, app_setup, voice widgets |
| Execution layer        | `/api/v1/execution/*`         | Dashboard “Execution Layer” panel  |
| Connections            | `/api/v1/connections/*`        | `/ui/connections`                  |
| Founder / emergency    | `/api/v1/founder-panel/*`     | `/ui/founder-panel`, Incident Room  |
| Deception / security   | `/api/v1/_decoy/*`            | `/incident-room`                   |
| QA Guardian            | `/api/v1/qa/*`                | `/api/v1/qa/ui` (dashboard)        |
| Councils                | councils, council_router      | `/ui/councils`, council_dashboard  |
| Agents                  | agent_activity, categories   | `/ui/agents`, agent_detail, agent_config |
| Projects                | projects_router               | `/ui/projects`                     |
| Workspace               | workspace_router              | `/ui/workspace`                    |
| Analytics               | analytics_router              | `/ui/analytics`                    |
| System / monitoring     | system_summary, monitoring    | `/ui/system-monitor`               |
| Chat / Daena            | daena_router, chat_history   | `/ui/daena-office`                 |

## Other UI routes (no sidebar link)

Reachable from in-app links or direct URL:

- `/ui/departments`, `/ui/department/{slug}` – departments
- `/ui/enhanced-dashboard`, `/ui/health` – health/enhanced dashboard
- `/ui/command-center` – daena_command_center
- `/ui/operator` – operator tools
- `/cmp-canvas`, `/control-center`, `/voice-diagnostics` – CMP / control / voice (cmp_canvas_router)
- `/ui/decisions`, `/ui/decisions/{id}` – if routes exist
- `/ui/strategic-room`, `/ui/strategic-meetings`, `/ui/conference-room`, `/ui/council-debate`, `/ui/council-synthesis` – meetings/council

## Consistency checks

- **App Setup** “Open Connections” → `/ui/connections` (correct).
- **Dashboard** “Open Dashboard → Execution” → `/ui/dashboard#execution-layer` (correct).
- **Incident Room** links to QA Guardian (`/api/v1/qa/ui`) and CMP Canvas (`/cmp-canvas`).
- **QA Guardian** dashboard header links to **Incident Room** (`/incident-room`).

## Recommendations

1. **Auth**: In production, protect `/ui/founder-panel`, `/incident-room`, `/api/v1/qa/ui`, and `/api/v1/_decoy/hits` with auth.
2. **Errors**: Use global `handleApiError` (base.html) where frontend calls backend so errors show consistently.
3. **Mobile**: Sidebar and dashboard are responsive; test key flows on small screens.
