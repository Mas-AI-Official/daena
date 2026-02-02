# UPGRADE_CANDIDATES (mine NEW since 2025-12-01)

**Repo**: `D:\Ideas\Daena\` (NEW, working branch: `upgrade/mine-backend-from-new-into-old-20251213`)  
**Mining window**: `git log --since=2025-12-01`  
**Goal**: Identify **legit backend improvements** to port into `D:\Ideas\Daena_old\` (OLD) while enforcing:

- **No React/Next/Node** (HTMX/HTML only)
- **No auth/login/session/JWT** at runtime (local dev must work with `DISABLE_AUTH=1`)
- **No cloud-only default paths** (local Ollama-first; cloud providers opt-in via keys)

---

## Scope & filters used

### Included code roots (backend-ish)
- `backend/**`
- `app/**` (python)
- `db/**` (models/migrations)
- `core/**`, `services/**`, `routes/**`, `utils/**`, `scripts/**`

### Excluded by policy (will be dropped or quarantined)
- Anything React/Node/Next (`package.json`, `node_modules`, `tsconfig`, etc.)
- Auth/login/session/JWT/OAuth routes/middleware/templates **as features**
- Cloud-only paths that are enabled by default without keys
- CI-only files unrelated to runtime

---

## High-signal mined improvements (candidates)

### A) Settings / No-auth bootstrap (KEEP, but strip real auth)

- **`backend/config/settings.py`** (commit: `35ebdb8`)
  - **What changed**: Adds `DISABLE_AUTH` flag (parsed robustly) and `dev_founder_name` for local dev; keeps other settings.
  - **Why keep**: Required to enforce “no-auth dashboard + APIs” policy safely via one switch.
  - **Doc justification**:
    - From `docs/12-12-2025/DISABLE_AUTH_IMPLEMENTATION.md`: “Bypass all authentication for local development when `DISABLE_AUTH=1`” and “`get_current_user()` returns mock founder user immediately, no token required”.

- **`backend/security/dev_user.py`** (commit: `35ebdb8`)
  - **What changed**: `DevUser` (Founder/Admin) object for local development.
  - **Why keep**: Enables routes to have a consistent “current user” object without implementing auth.

- **`backend/services/auth_service.py`** (commit: `35ebdb8`)
  - **What changed**: `get_current_user()` / `get_current_user_optional()` short-circuit to `DevUser` when `settings.disable_auth` is true.
  - **Why keep**: We will **port only** the `DISABLE_AUTH` bypass + `get_current_user` shape; we will **not port** JWT/login flows.
  - **Doc justification**:
    - From `docs/12-12-2025/DISABLE_AUTH_IMPLEMENTATION.md`: “Modified `get_current_user()` to return mock user when `DISABLE_AUTH=1`”.

**Dependencies**
- `pydantic-settings`, `python-dotenv` (settings)

---

### B) HTMX/HTML UI wiring + stability (KEEP)

- **`backend/ui/routes_ui.py`** (commits: `9994957`, `35ebdb8`, `7cd71aa`, `1f4242f`, `859d67a`)
  - **What changed**: Restores/rewires legacy UI under `/ui/*`, removes login gating, fixes HTMX swapping selectors, fixes API base URL assumptions.
  - **Why keep**: The final system must be **HTMX+HTML only** and the required pages must work.
  - **Doc justification**:
    - From `docs/12-12-2025/DASHBOARD_FIXES_SUMMARY.md`:
      - “Added HTMX attributes to all sidebar links … `hx-get` … `hx-target="#main"` …”
      - “Changed to dynamic `get_api_base(request)`”
      - “Changed all `hx-target="main"` → `hx-target="#main"`”

- **`backend/ui/templates/**` + `backend/ui/static/**`** (commits: `859d67a`, `52fa7e0`, `7cd71aa`, `51e6069`)
  - **What changed**: Restored classic UI templates + static assets; fixed legacy path/selector mismatches; quarantined login template.
  - **Why keep**: These assets back the required `/ui/*` pages.

**Dependencies**
- `jinja2`, `fastapi`, `starlette`, HTMX (client-side)

---

### C) Sunflower stability guard (KEEP)

- **`backend/utils/sunflower.py`** (commits: `45194be`, `35ebdb8`)
  - **What changed**: Adds robust guardrails around `k` handling (casts non-ints; clamps ranges; returns safe empty list).
  - **Why keep**: Directly matches the “Sunflower adjacency guard” priority (prevents crash loops from invalid indices).

---

### D) Local LLM (Ollama-first) fallback (KEEP)

- **`backend/services/local_llm_ollama.py`** (commit: `85df37f`)
  - **What changed**: Local Ollama client (`/api/chat`), model auto-selection with priority (trained > default > fallback).
  - **Why keep**: Enforces “local-first” and avoids paid-key defaults.
  - **Doc justification**:
    - From `docs/12-11-2025/LOCAL_LLM_SETUP.md`:
      - “The dashboard will automatically use local Ollama when cloud keys are missing”
      - “Priority: trained model > default model > fallback”

- **`backend/services/model_registry.py`** (commit: `85df37f`)
  - **What changed**: Registers cloud models only if keys exist; registers local Ollama when no cloud keys (or as fallback).
  - **Why keep**: Centralizes provider selection and avoids accidental external calls.
  - **Doc justification**:
    - From `docs/12-11-2025/TRAINING_AND_BACKEND_SETUP.md`:
      - “Backend checks for trained model (`daena-brain`) on startup”
      - “Priority: Trained model > Default model > Fallback”

**Dependencies**
- `httpx` (async client)

---

### D2) Brain routing / orchestration primitives (KEEP, but keep optional deps optional)

- **`backend/config/council_config.py`** (changed since 2025-12-01)
  - **What changed**: Canonical “single source of truth” for the **8 departments × 6 agents** structure, plus **Council-as-governance-layer** (not a department).
  - **Why keep**: Stabilizes seeders + health checks + UI expectations (“Council is NOT a department”) and prevents silent drift.

- **`backend/services/router.py` + `backend/routes/router.py`** (changed since 2025-12-01)
  - **What changed**: A “unified meta-router” that can:
    - classify tasks (`TaskType`, `RiskLevel`)
    - prefer local execution when possible
    - escalate to council governance for higher-risk decisions
    - run **canary checks** (PII redaction, cost checks) if enabled by config
  - **Why keep**: This directly aligns with “routing, consensus/compare logic, council governance (allow disabling)”.
  - **Porting note**: Ensure all cloud-provider calls remain **opt-in** (keys required) and local remains default.

- **`backend/services/router_ranker.py`** (changed since 2025-12-01)
  - **What changed**: Ranks multiple candidate responses; uses **rule-based** scoring by default and optionally uses `scikit-learn` if installed.
  - **Why keep**: Improves stability/quality without hard dependency on heavy ML libs.
  - **Dependencies**: `scikit-learn` **optional** (should not be required to boot).

- **`backend/services/adapters.py` + `backend/routes/adapters.py`** (changed since 2025-12-01)
  - **What changed**: Adapter service for LoRA skill adapters:
    - LRU cache (max loaded)
    - reference counting
    - simulated mode when `peft` is missing
  - **Why keep**: Matches “model adapters, training/inference services, agent specialization”.
  - **Dependencies**: `peft` **optional** (should not be required to boot).

- **`backend/services/agent_state_persistence.py`**
  - **What changed**: Persist agent state to disk (`data/agent_states/*.json`) so restarts don’t lose progress/context.
  - **Why keep**: Stability + recovery; no external dependencies.

---

### E) Legacy UI compatibility endpoints (KEEP)

- **`backend/routes/internal/daena.py`** (commit: `4e6ff54`)
  - **What changed**: Adds convenience endpoints:
    - `POST /api/v1/daena/chat` (accepts `{message|text|content}`)
    - `POST /api/v1/daena/voice`
  - **Why keep**: Prevents UI regressions by supporting legacy request shapes and fields.

- **`backend/routes/voice.py`** (commit: `ff00b05`)
  - **What changed**: Exposes `/api/v1/voice/*` endpoints expected by legacy UI.
  - **Why keep**: Required for `/ui/*` pages that reference voice assets/endpoints.

---

### F) Maintenance / seed hygiene (KEEP)

- **`backend/maintenance/activate_all_agents.py`** (commit: `35ebdb8`)
  - **What changed**: One-shot script to mark all `Agent.is_active=True`.
  - **Why keep**: Matches priority list; unblocks UIs that filter by active agents.

---

## “Drop / quarantine” candidates (per policy)

These may exist in git history since 2025-12-01 but will **not** be ported as features:

- **JWT/login/auth routes & middleware**: keep only the `DISABLE_AUTH` short-circuit behavior needed to avoid 401s locally.
- **SSO / Vibe embedding** (`backend/routes/sso.py`, etc.): auth-adjacent; keep disabled/off by default in OLD.
- **Monitoring auth enforcement**: will be adjusted so `/ui/health` works without credentials when `DISABLE_AUTH=1`.

---

## Requirements / env knobs discovered (to port to OLD)

- **No-auth**
  - `DISABLE_AUTH=1` (default for local)
  - `DEV_FOUNDER_NAME=Masoud` (optional)
- **Local LLM (Ollama)**
  - `LOCAL_LLM_PROVIDER=ollama`
  - `OLLAMA_BASE_URL=http://localhost:11434`
  - `TRAINED_DAENA_MODEL=daena-brain` (optional)
  - `DEFAULT_LOCAL_MODEL=qwen2.5:7b-instruct`
  - `FALLBACK_LOCAL_MODEL=llama3.2:3b-instruct`
  - `OLLAMA_TIMEOUT=120` (optional)






