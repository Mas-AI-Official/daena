# Control Plane Consolidation – Deliverables

## 1. Updated files

### Frontend / UI
- **frontend/templates/control_plane.html** – Unified Control Plane page with separate tabs: Brain & API, Integrations, Skills, Execution, Proactive, **Tasks**, **Runbook**, **Approvals Inbox**, Provider onboarding (each in its own full-height iframe).
- **frontend/templates/partials/sidebar.html** – Replaced 9 control-plane items + System Monitor with one "Control Plane" link; removed Provider onboarding and System Monitor from sidebar.
- **frontend/templates/base.html** – Embed mode: when `?embed=1`, sidebar/topbar/lockdown hidden and main wrapper full width for iframes.
- **frontend/templates/dashboard.html** – System Health panel: Backend Status + API Endpoints (ids: `system-backend-status`, `system-api-count`); Quick Actions updated to Control Plane links.

### Backend
- **backend/routes/ui.py** – `/ui/control-plane`; `_redirect_to_control_plane()`; `/ui/tasks-runbook-approvals` (condensed); skills, execution, proactive, tasks, runbook, approvals, provider-onboarding redirect when not `?embed=1`; `/ui/system-monitor` → `/ui/dashboard`.
- **backend/main.py** – Brain/app-setup redirect to Control Plane. CORS via `get_cors_origins()` (no `*`).
- **backend/config/settings.py** – `disable_auth` default `False` (auth ON).
- **backend/middleware/api_key_guard.py** – Public paths: `/`, `/health`, `/health/`, `/api/v1/health`, docs; no sensitive endpoints public.

### Config / Security
- **.env.example** – `DISABLE_AUTH=0` by default; added `CORS_ORIGINS` comment.
- **config/secrets.example.env** – New file with placeholders only (no real keys).

---

## 2. Sidebar and Control Plane

- Sidebar shows a single **Control Plane** link (replacing Brain & API, App Setup, Skills, Execution, Proactive, Tasks, Runbook, Approvals Inbox, Provider onboarding, System Monitor).
- **Control Plane** (`/ui/control-plane`) loads with tabs; each tab shows one page in a full-height iframe with `?embed=1`. Tasks, Runbook, and Approvals Inbox are separate tabs (not combined).
- Old URLs (e.g. `/ui/brain-settings`, `/ui/skills`, `/ui/tasks`, `/ui/runbook`, `/ui/approvals`) redirect to `/ui/control-plane#&lt;section&gt;` when opened directly (no `embed=1`).

---

## 3. Dashboard System Health

- Dashboard includes a **System Health** card with:
  - **Backend Status** – Filled by `loadSystemStatus()` from `/api/v1/system-summary/summary` or `/health`.
  - **API Endpoints** – Count from the same API when available.
- `/ui/system-monitor` redirects to `/ui/dashboard`.

---

## 4. Aligned files (next steps)

- **frontend/templates/dashboard.html** – Quick Actions: Brain Settings and App Setup → Control Plane (#brain, #app-setup).
- **frontend/templates/runbook.html** – Links to Execution and App Setup → `/ui/control-plane#execution`, `#app-setup`.
- **frontend/templates/app_setup.html** – Open Brain Settings → `/ui/control-plane#brain`; Open Execution → `/ui/control-plane#execution`.
- **scripts/test_frontend_functionality.py** – UI pages list: `/ui/system-monitor` replaced with `/ui/control-plane`.
- **scripts/manual_verification_steps.py** – Step 6: GET `/ui/control-plane` (was `/ui/runbook`).
- **scripts/daena_ui_e2e_flows.py** – Skills, Execution, Proactive, Runbook use `?embed=1` for direct load.
- **backend/config/settings.py** – Added `brain_root` (BRAIN_ROOT) for learned memory, chat history, embeddings.
- **scripts/cleanup_old_upgrade.ps1** – Size report; optional move to BRAIN_ROOT; with `-Confirm` and typing `YES`, deletes `backend\.venv`, `daena_tts`, and **DaenaBrain** (if present and unused).
- **docs/VERIFICATION_CHECKLIST.md** – UI spot checks updated for Control Plane and Dashboard System Health.
- **docs/RUN_TESTS_AND_NEXT_STEPS.md** – Control Plane section added.

---

## 5. Smoke test checklist

- [ ] **Control Plane loads** – Open `/ui/control-plane`; all tabs (Brain & API, Integrations, Skills, Execution, Proactive, Tasks+Runbook+Approvals, Provider onboarding) switch and show content.
- [ ] **Execution logs** – From Control Plane → Execution tab, run a tool (with token); logs show tool runs.
- [ ] **Unauthorized execution blocked** – Call execution API without `X-Execution-Token`; expect 401.
- [ ] **No secrets in repo** – No `.env` or `config/secrets.env` with real keys committed; `.env.example` and `config/secrets.example.env` contain placeholders only.
- [ ] **Auth default** – With no `DISABLE_AUTH`, auth is ON (default from settings).
- [ ] **CORS** – CORS does not use `*`; uses configured origins or localhost list.

---

## 6. Model path (MODELS_ROOT / BRAIN_ROOT)

- **MODELS_ROOT** – Model weights and caches (Ollama, XTTS, Whisper). Default: `D:\Ideas\MODELS_ROOT`.
- **BRAIN_ROOT** – Learned memory, chat history, embeddings, governance logs. Optional; when unset, code may use project `local_brain` or similar.
- **cleanup_old_upgrade.ps1** – Run: `.\scripts\cleanup_old_upgrade.ps1` for size report; `-Confirm` and type `YES` to delete `backend\.venv`, `daena_tts`, and `DaenaBrain` (if present).

---

## 7. Security and follow-up (planned updates applied)

- **Public paths (API key guard)** – `backend/middleware/api_key_guard.py`: `public_paths` restricted to truly public only (`/`, `/api/v1/health`, `/api/v1/rate-limit`, `/dashboard`, `/docs`, `/openapi.json`, `/api/v1/docs`, `/api/v1/openapi.json`, `/api/v1/external/test`). System, config, logs, daena, and monitoring endpoints now require API key (or localhost).
- **Role middleware** – `backend/middleware/role_middleware.py`: `public_paths` already minimal; no change.
- **Deprecated main variants** – `backend/main_fixed.py` and `backend/main_minimal.py` marked deprecated; `if __name__ == "__main__"` exits with message to use `backend.main:app`.
- **.gitignore** – Added `backend/.venv/`, `.venv/`, `.brain-ci/` for venvs and CI brain dir.
- **CI** – `.github/workflows/smoke-and-manual-verification.yml`: `BRAIN_ROOT: ${{ github.workspace }}/.brain-ci` so CI uses a dedicated brain dir.
- **Execution layer safety** – Workspace allowlist enforced in `backend/tools/registry.py` and `backend/tools/executors/repo_scan.py`; audit logging in `backend/tools/audit_log.py` and `registry.py` (every tool run → `logs/tools_audit.jsonl`). See **docs/VERIFICATION_CHECKLIST.md** §8.
