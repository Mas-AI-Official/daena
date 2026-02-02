# UPGRADE_PLAN (NEW → OLD, no-auth + HTMX-only)

**Target**: Port selected backend upgrades from `D:\Ideas\Daena\` (NEW) into `D:\Ideas\Daena_old\` (OLD) without:
- auth/login/session/JWT/OAuth at runtime
- React/Next/Node tooling
- cloud-provider calls by default (local-first, keys required to enable cloud)

**Primary acceptance**:
- `DISABLE_AUTH=1` opens dashboard directly
- `/ui/dashboard`, `/ui/departments`, `/ui/agents`, `/ui/council`, `/ui/memory`, `/ui/health` render
- `/api/*` endpoints work without tokens when `DISABLE_AUTH=1`

---

## Bucket A) Models & Migrations (only if required by kept routes)

**Plan**
- Audit OLD DB models/migrations vs NEW usage for:
  - Agents (`is_active` field must exist and be respected)
  - Departments (canonical slugs)
  - Any council governance tables if we keep council APIs that persist
- Add Alembic migrations only when a kept route/service truly depends on it.

**Keep / port**
- Minimal `Agent.is_active` (required by maintenance + UI visibility).
- Council structure validation is config-only (`backend/config/council_config.py`) and does not require DB changes by itself.

**Avoid**
- Auth tables or login sessions.

---

## Bucket B) Services (brain/routing/adapters/state)

**Keep / port**
- **Local LLM (Ollama-first)**
  - `backend/services/local_llm_ollama.py`
  - `backend/services/model_registry.py` (local registered when no cloud keys)
  - Ensure any cloud providers remain **opt-in** (only if keys exist).
- **Routing**
  - `backend/services/router.py`
  - `backend/services/router_ranker.py` (keep `scikit-learn` optional)
  - (If used) `backend/services/router_learning.py` behind a feature flag / safe import
- **Adapters**
  - `backend/services/adapters.py` (keep `peft` optional; simulated mode must boot)
- **Stability**
  - `backend/utils/sunflower.py` adjacency guard (cast/clamp/safe-empty)
  - `backend/services/agent_state_persistence.py` (safe local persistence)

**Drop / quarantine**
- Any service that requires paid cloud keys by default (keep code paths disabled unless keys exist).

---

## Bucket C) API Routers (no-auth)

**Keep / port**
- **Core data APIs for HTMX pages**
  - `backend/routes/internal/agents.py` → `/api/v1/agents`
  - `backend/routes/internal/departments.py` → `/api/v1/departments`
- **Legacy UI compatibility**
  - `backend/routes/internal/daena.py` → `/api/v1/daena/chat` + `/api/v1/daena/voice`
  - `backend/routes/voice.py` → `/api/v1/voice/*`
- **Health**
  - `backend/routes/shared/health.py` but modify so health endpoints are accessible when `DISABLE_AUTH=1`
    - Specifically: bypass `verify_monitoring_auth` dependency in no-auth mode.

**Auth bypass strategy (required)**
- Add/port `get_current_user()` that returns a Dev Founder when `DISABLE_AUTH=1`.
- Remove JWT/login dependency from kept routers.

**Drop / quarantine**
- `backend/routes/auth.py`, `backend/routes/sso.py`, anything login/session/JWT-centric.

---

## Bucket D) Seeders & Maintenance

**Keep / port**
- `backend/maintenance/activate_all_agents.py`
- Any seeder logic required to guarantee agents exist and are `is_active=True`.

---

## Bucket E) Settings / Config / Launchers

**Keep / port**
- Settings:
  - `DISABLE_AUTH=1` default for local
  - Ollama envs (`OLLAMA_BASE_URL`, `DEFAULT_LOCAL_MODEL`, `FALLBACK_LOCAL_MODEL`, `TRAINED_DAENA_MODEL`)
- Launchers:
  - Update OLD batch launchers to:
    - set `DISABLE_AUTH=1` by default
    - start uvicorn
    - open `http://127.0.0.1:8000/ui/dashboard`

**Drop / quarantine**
- Any launcher logic that opens `/login`.

---

## Bucket F) Frontend (HTML/HTMX only)

**Keep / port**
- `/ui/*` routes that render templates with no login gates
- Templates and static assets needed for:
  - `/ui/dashboard`
  - `/ui/departments`
  - `/ui/agents`
  - `/ui/council`
  - `/ui/memory`
  - `/ui/health`

---

## Implementation order (dependency-first)

1. **E (Settings) + no-auth shim**
2. **F (UI routes/templates/static) wiring + mounts**
3. **B (Local LLM + model registry)**
4. **B (Sunflower guard + agent state persistence)**
5. **C (Agents/Departments/Daena/Voice routes)**
6. **D (Seeders + activate_all_agents)**
7. **C (Health endpoints no-auth behavior)**
8. Tests + launch smoke on OLD






