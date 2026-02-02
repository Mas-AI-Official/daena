# UPGRADE_REPORT (NEW → OLD, no-auth + HTMX-only)

**Date**: 2025-12-13  
**NEW repo (mined)**: `D:\Ideas\Daena\` (branch: `upgrade/mine-backend-from-new-into-old-20251213`)  
**OLD baseline (upgraded worktree)**: `D:\Ideas\Daena_old_upgrade_20251213\` (branch: `old/upgrade-target-20251213`)  

## Goals met (so far)

- **No-auth local mode**: `DISABLE_AUTH=1` (default) bypasses auth middleware + role middleware + `get_current_user()`.
- **HTMX/HTML UI only**: added `/ui/*` pages (no React/Node).
- **Key UI pages implemented**:
  - `/ui/dashboard`
  - `/ui/departments`
  - `/ui/agents`
  - `/ui/council`
  - `/ui/memory`
  - `/ui/health`
- **Local LLM-first**: added Ollama client + fallback path so the backend can answer without paid keys when Ollama is running.
- **Stability fix**: sunflower adjacency guard now **clamps/casts** invalid indices instead of raising (`Index k must be between ...` crash removed).
- **Seed/maintenance**: added `backend/maintenance/activate_all_agents.py`.
- **Windows launchers updated**: open `/ui/dashboard` and default `DISABLE_AUTH=1`.

## What we mined from NEW (since 2025-12-01)

High-signal backend improvements mined include:
- `DISABLE_AUTH` behavior + dev founder (`DevUser`)
- HTMX `/ui/*` route wiring (legacy UI compatibility)
- Local Ollama integration (`local_llm_ollama.py`) and local-first model selection
- Sunflower adjacency guard
- One-off maintenance script to activate agents

See: `D:\Ideas\Daena\docs\upgrade\UPGRADE_CANDIDATES.md` and `UPGRADE_PLAN.md`.

## What we ported into OLD (files changed)

### Auth removal / no-auth mode

- `config/settings.py`
  - Adds `disable_auth` and `dev_founder_name` (runtime settings used by `backend/main.py`)
- `backend/services/auth_service.py`
  - Converted to **NO-AUTH baseline** (no JWT/bcrypt); always returns Dev Founder when `DISABLE_AUTH=1`
- `backend/middleware/auth_middleware.py`
  - Bypasses all auth checks when `DISABLE_AUTH=1`
- `backend/middleware/role_middleware.py`
  - Bypasses role checks when `DISABLE_AUTH=1`

### UI (/ui/*) routes

- `backend/routes/ui.py` (NEW)
  - Adds required `/ui/*` pages using existing `frontend/templates`
- `frontend/templates/ui_departments.html` (NEW)
  - Wraps `departments.html` fragment in `layout.html`
- `frontend/templates/layout.html`
  - Adds `id="main"` for HTMX target, and removes forced `/login` redirect in no-auth mode
- `frontend/templates/partials/navbar.html`
  - Removes login-centric actions in no-auth mode; “Founder (DEV)” badge and no `/login` redirect on logout

### Local LLM (Ollama-first)

- `backend/services/local_llm_ollama.py` (NEW)
- `backend/services/model_registry.py` (NEW, safe variant)
- `backend/services/llm_service.py`
  - If no cloud providers configured, tries Ollama before falling back

### Stability + maintenance

- `backend/utils/sunflower.py`
  - `get_neighbor_indices()` now casts/clamps invalid `k` and returns `[]` safely
- `backend/maintenance/activate_all_agents.py` (NEW)

### Launch scripts

- `START_DAENA.bat`
  - Defaults `DISABLE_AUTH=1`
  - Opens `http://localhost:8000/ui/dashboard`
- `LAUNCH_DAENA_COMPLETE.bat`
  - Defaults `DISABLE_AUTH=1`
  - Opens `/ui/dashboard` and `/ui/health`
  - Prefers `py -3.10` if available (to avoid Python-version incompatibilities)

## Commits applied (OLD upgrade branch)

- `ce3c293` — feat(no-auth): add DISABLE_AUTH dev founder, /ui routes, and remove login gating  
- `98468e4` — feat(local-llm): add Ollama local LLM fallback + safe model registry  
- `3c64c4c` — fix(sunflower): guard invalid adjacency indices + add activate_all_agents maintenance  
- `be193a2` — chore(launch): default DISABLE_AUTH=1, add /ui dashboard opens, prefer py -3.10  

## How to run locally (Windows)

From `D:\Ideas\Daena_old_upgrade_20251213\`:

1. Run:
   - `START_DAENA.bat` (recommended)
2. Browser should open:
   - `http://127.0.0.1:8000/ui/dashboard`

### Optional: Ollama local model

Set env vars (or add to `.env`):
```env
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LOCAL_MODEL=qwen2.5:7b-instruct
FALLBACK_LOCAL_MODEL=llama3.2:3b-instruct
TRAINED_DAENA_MODEL=daena-brain
```

## Tests

Added a minimal smoke test:
- `tests/test_no_auth_ui.py`
  - Verifies `/ui/*` pages return 200 and `/api/v1/agents` + `/api/v1/departments` do not 401 under `DISABLE_AUTH=1`.

## Known gaps / follow-ups

- **Python version**: some optional dependencies in older pinned stacks may not support Python ≥ 3.13.
  - The launcher now prefers **Python 3.10** via `py -3.10` when available.
- **Final “replace NEW with upgraded OLD”** (Step 7) and dedupe pass (Step 8) still pending.






