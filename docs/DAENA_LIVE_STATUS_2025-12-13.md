## Daena Live Status — 2025-12-13

### Definition of "LIVE"

Daena is considered **LIVE (local brain)** when all of the following hold:

- `START_DAENA.bat` runs from `D:\Ideas\Daena_old_upgrade_20251213` without auto-closing.
- Backend starts and `/api/v1/health/` returns 200.
- UI dashboard loads at `/ui/dashboard`.
- `/api/v1/daena/chat` responds using the canonical `daena_brain` path.
- `/api/v1/agents/{id}/chat` and `/assign_task` execute real logic via the same brain + CMP.
- No source files contain truncation markers.
- Go-live smoke tests pass end-to-end.

### Local Brain (Canonical) vs External APIs

- **Canonical brain**: `backend/daena_brain.py` + `backend/core/brain/store.py`.
  - All high-level reasoning for Daena and agents uses `daena_brain.process_message(...)`.
  - Memory/governance flows are mediated through the governance store (queue + states).
- **External APIs**: optional LLM providers wired through `backend/services/llm_service` or manual Human Relay Explorer.
  - No external provider is required to run Daena locally.
  - Human Relay Explorer remains manual copy–paste and is behind flags.

### Agent Permissions and Governance Flow

- Agents:
  - Share the same brain core (no independent brains).
  - Can **read** from the brain via query endpoints.
  - Cannot directly commit new knowledge to the shared memory store.
- Daena VP + governance:
  - Receives proposals via `/api/v1/brain/propose_experience`.
  - Applies review / debate / synthesis states via `/api/v1/brain/transition/{proposal_id}`.
  - Commits approved experiences via `/api/v1/brain/commit/{proposal_id}` (VP-only path).
  - Tests in `tests/test_brain_write_protection.py` validate that proposals flow through this pipeline and end in the committed set.

### How to Start the System

- **One canonical launcher**:

  ```bat
  cd /d D:\Ideas\Daena_old_upgrade_20251213 && START_DAENA.bat
  ```

- The launcher:
  - Enforces project root and creates `logs\`.
  - Uses the main venv via `scripts/setup_env.py` (pip upgrade + `requirements.txt` install + lockfile best-effort).
  - Runs `scripts/check_env.py` for import and version sanity.
  - Runs truncation + duplicate guards (including `verify_no_truncation.py`), failing fast if any issue is found.
  - Starts backend (`uvicorn backend.main:app ...`) and waits for `/api/v1/health/`.
  - Executes go-live smoke tests (`tests/test_go_live_smoke.py`) which hit:
    - Key UI pages under `/ui/*`.
    - `/api/v1/daena/chat`.
    - `/api/v1/agents/{id}/chat` for at least one real agent.
  - Opens dashboard and related pages in the browser.
  - Prints a final status summary and then loops forever so the window never closes silently.

### Truncation and File-Integrity Guarantees

- `scripts/verify_no_truncation.py` now scans:
  - `*.py`
  - `*.html`
  - `*.js`
  for known truncation phrases and merge markers.
- A backend wrapper `backend/scripts/verify_no_truncation.py` delegates to the root script, so tools expecting either path are satisfied.
- `START_DAENA.bat` runs this guard before starting the backend; any failure:
  - Shows the offending files.
  - Prevents startup.
  - Keeps the window open for inspection.

### Current Status Checklist

- **No truncated files**: Guard in place and run by launcher; code search confirms no source file contains the known truncation markers.
- **Launcher stable**: `START_DAENA.bat` never exits without either a visible error + pause or the infinite wait loop.
- **Daena responds**: `/api/v1/daena/chat` wired through `daena_brain`, validated by smoke tests.
- **Agents execute**: `/api/v1/agents/{id}/chat` and `/assign_task` route through `daena_brain` with CMP hooks; agent chat is validated in smoke tests.
- **System live with local brain**: All core flows (dashboard, Daena chat, agent chat) operate without external LLM APIs, backed by the local canonical brain and governance store.









