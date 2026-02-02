## Docs takeaways → applied upgrades (no-auth, HTMX-only)

This repo has a lot of narrative docs. I mined them for **runtime-impacting** takeaways that match the current constraints:
- **No React/Node**
- **No login/auth gating (DISABLE_AUTH=1)**
- **Local-first (no cloud calls unless explicitly enabled)**

## Applied improvements

### 1) “Real-time knowledge” baseline is enforced
- Startup no longer crashes on logging context (`trace_id`) or Windows console encoding.
- Optional providers (Gemini / voice cloning) are now **non-fatal** when their deps aren’t installed.

### 2) Enterprise-DNA is now actually enabled
Docs talk heavily about Enterprise-DNA; previously the route could not load due to missing models/auth import.
- Added `backend/models/enterprise_dna.py`
- Removed the dead auth import from `backend/routes/enterprise_dna.py`
- Result: `backend/routes/enterprise_dna.py` registers successfully and can be used in no-auth mode.

### 3) Council governance remains local-safe
Council is available through the existing “V2/status/rounds” routes without forcing cloud LLM usage.
- `backend/services/council_service.py` now treats OpenAI as **optional** and only uses it when `ENABLE_CLOUD_LLM=1`.

### 4) UI routing + navigation are unified under `/ui/*`
Many templates hardlinked to `/`, `/daena-office`, `/council-dashboard`, etc. This caused broken flows when using `/ui/*`.
- Added `/ui/*` aliases in `backend/routes/ui.py` (daena office, founder panel, strategic room, command center, etc.)
- Updated `frontend/templates/partials/navbar.html` to use `/ui/*`
- Updated common standalone templates to link back to `/ui/dashboard`

### 5) Two-environment model supported in launcher (base vs audio)
Docs and logs show you want “whole system” and “audio-only” separation. We implemented the practical version:
- `LAUNCH_DAENA_COMPLETE.bat` supports:
  - `ENABLE_AUDIO=1` → additionally installs `requirements-audio.txt`
  - `ENABLE_CLOUD_LLM=1` → loads `.env_azure_openai`
- Added `config/local.env.example` and the launcher prefers `config/local.env` for safe local dev.

## Remaining high-impact opportunities (not yet implemented)
- Consolidate the many legacy `models.*` imports (some routers still fail safe-import due to missing legacy modules).
- Add a dedicated “NBMF / Memory” UI page that surfaces `/api/v1/monitoring/memory*` endpoints in a cleaner dashboard.
- Replace remaining cloud-default prompt paths with model-registry + Ollama-first routing everywhere (some legacy services still assume OpenAI).











