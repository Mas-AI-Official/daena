## Daena AI VP — System Status (2025-12-13)

### 1. What is LIVE

- **One-click launcher**: `START_DAENA.bat` in the project root.
- **Backend**: FastAPI app at `http://127.0.0.1:8000`, health at `/api/v1/health/`.
- **UI**: Core pages served by the backend (no separate frontend server) including:
  - `/ui/dashboard`
  - `/ui/departments`
  - `/ui/agents`
  - `/ui/council-dashboard`, `/ui/council-debate`, `/ui/council-synthesis`
  - `/ui/voice-panel`
  - `/ui/task-timeline`
  - `/ui/health`
- **Daena chat**:
  - `/api/v1/daena/chat` (legacy/simple endpoint for UI)
  - `/api/v1/daena/chat/{session_id}/message` (session-oriented).
- **Agent execution**:
  - `/api/v1/agents/{agent_id}/chat`
  - `/api/v1/agents/{agent_id}/assign_task`
  - Both route through the shared canonical brain and CMP where appropriate.

Smoke tests (`tests/test_go_live_smoke.py`) are wired into `START_DAENA.bat` and run automatically after the backend health check. If they fail, the launcher reports the failure, shows the last log lines, and stays open.

### 2. Local Brain vs External APIs

- **Local brain (canonical)**:
  - Implemented in `backend/daena_brain.py` and orchestrated via `backend.core.brain.store`.
  - All high-level reasoning and routing for Daena + agents goes through `daena_brain.process_message(...)`.
  - Memory/governance implemented via the governance store (`GovernanceState`, queues, approval/commit flow).
  - This is the primary path used in local mode; no external LLM APIs are required to run the system.

- **External APIs (optional, not required for go-live)**:
  - LLM service in `backend.services.llm_service` can use configured providers (e.g. OpenAI, Gemini) when credentials are provided.
  - Human Relay Explorer (`backend/services/human_relay_explorer.py` + `backend/routes/human_relay.py`) supports **manual** copy–paste flows to ChatGPT / Gemini, behind configuration flags.
  - No automatic login, cookie scraping, or UI automation is used; any external messaging is human-driven.

### 3. How Agents Work (Subordinate to the Shared Brain)

- **Single shared brain**:
  - `backend/daena_brain.py` is the canonical, shared brain core.
  - `backend/core/brain/store.py` uses this brain for queries, governance, and memory operations.

- **Daena (VP)**:
  - Exposed via `backend/routes/daena.py` and `/api/v1/daena/*` endpoints.
  - Has cross-department visibility and higher authority:
    - Can orchestrate department/agent work.
    - Can invoke governance flows and memory updates via the governance store.
    - Can synthesize multi-department insights and strategic plans.

- **Agents (specialists)**:
  - Defined in the Sunflower Registry (`backend.utils.sunflower_registry`) and surfaced via `backend/routes/agents.py`.
  - **Do not** carry their own “brain”; they are profiles over the shared brain:
    - Different roles/personas.
    - Different tools/permissions via CMP.
    - Different context/memory scopes.
  - Chat and task flows:
    - `/api/v1/agents/{agent_id}/chat`:
      - Builds context (agent metadata, department, etc.).
      - Calls `daena_brain.process_message(...)` with that context.
      - Optionally dispatches CMP tools for execution (e.g. web scraping) while still reporting through Daena.
    - `/api/v1/agents/{agent_id}/assign_task`:
      - Routes assignment prompts through `daena_brain.process_message(...)` with task context.
      - Uses CMP where tool execution is requested.

### 4. Governance and Brain Write-Protection

- **Read path**:
  - All agents and Daena can **read** from the unified brain via the governance store (`brain_store.query`, `/api/v1/brain/query` routes).

- **Write path (protected)**:
  - New experiences/knowledge follow a structured pipeline:
    1. `propose_experience` → creates a proposal in the governance store (state `PROPOSED`).
    2. Review / scoring / debate steps (`SCOUTED`, `DEBATED`, `SYNTHESIZED`, `APPROVED`, `FORGED`) via governance transitions.
    3. `approve_and_commit` (VP-level action) → final `COMMITTED` state and update of shared memory.
  - API surface (backed by `backend/core/brain/store.py`):
    - `brain_read(...)` conceptually maps to query endpoints and store query methods.
    - `propose_learning(...)` → `/api/v1/brain/propose_experience`.
    - `council_review(...)` → `/api/v1/brain/transition/{proposal_id}` with appropriate states.
    - `commit_learning(...)` (restricted) → `/api/v1/brain/commit/{proposal_id}` (intended for Daena VP / governance layer).
  - Tests in `tests/test_brain_write_protection.py` assert the governance flow and that experiences appear in the queue, transition through states, and end up in committed experiences.

### 5. How to Start the System (One Command)

- **Command (from any shell on Windows)**:

  ```bat
  cd /d D:\Ideas\Daena_old_upgrade_20251213 && START_DAENA.bat
  ```

- What this does:
  1. Enforces `PROJECT_ROOT=D:\Ideas\Daena_old_upgrade_20251213` and `cd` there.
  2. Creates/uses the main venv and runs environment setup via `scripts/setup_env.py`:
     - Upgrades `pip`, `setuptools`, `wheel`.
     - Installs dependencies from `requirements.txt`.
     - Attempts to update `requirements.lock.txt` (non-fatal on permission issues).
  3. Runs `scripts/check_env.py` to verify Python version and key imports.
  4. Runs guard scripts:
     - `scripts/verify_no_truncation.py`
     - `scripts/verify_no_duplicates.py`
     - `scripts/verify_no_duplicate_entrypoints.py` (warning-only).
  5. Starts the backend (`uvicorn backend.main:app --host 127.0.0.1 --port 8000`) in a separate window, logging to `logs/backend_*.log`.
  6. Waits for `/api/v1/health/` to return 200 (up to 120 seconds).
  7. Runs go-live smoke tests via `tests/test_go_live_smoke.py`:
     - UI endpoints (`/ui/...`).
     - Daena chat (`/api/v1/daena/chat`).
     - Agent chat (`/api/v1/agents/{id}/chat`).
  8. Opens browser tabs:
     - `http://127.0.0.1:8000/ui/dashboard`
     - `http://127.0.0.1:8000/ui/health`
     - `http://127.0.0.1:8000/ui/agents`
     - `http://127.0.0.1:8000/ui/strategic-meetings`
  9. Prints a final status summary and then waits forever (the window never auto-closes).

### 6. Known Limitations (2025-12-13)

- Some advanced routes that depend on optional modules or databases may log warnings and be skipped at startup (e.g. routes requiring `backend.models.database`, `cryptography`, or full multi-tenant DB state).
- Human Relay Explorer and external LLM integrations are available but remain **manual** and behind flags; they are not required for core local operation.
- Voice/audio features are disabled by default unless the audio environment and dependencies are installed.
- Governance/security/auth are in “local dev mode” by default (`DISABLE_AUTH=1`) for easier UI access; production hardening (auth, secrets, reverse proxy, TLS, etc.) is still required for deployment beyond localhost.

### 7. Truncation / File-Integrity Guarantees

- `scripts/verify_no_truncation.py` runs automatically in the launcher **before** the backend is started.
- If any `.py` file contains known truncation markers or merge-conflict remnants, the launcher:
  - Prints the offending files.
  - Fails fast with a clear message.
  - Keeps the window open so the issue is visible.

This guardrail, plus the policy of patch-style edits only, protects core files (especially large modules like `backend/main.py`, `backend/daena_brain.py`, and services) from silent truncation. 









