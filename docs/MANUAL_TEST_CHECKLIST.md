# Manual Test Checklist

Run these in order when verifying the Daena setup (including DaenaBot hands / execution layer).

## 1. Env (no backend)

From project root:

```bash
python scripts/verify_daenabot_hands_env.py
```

- Expect: "OK (safe default or env): ws://127.0.0.1:18789/ws" and token set True/False.
- If step 3 is SKIP (pydantic not available), that’s fine; use a venv with backend deps for full settings check.

## 2. Backend health

Start the backend (e.g. `scripts\start_backend.bat` or `scripts\start_backend_with_env.bat`), then:

```bash
python scripts/smoke_and_manual_ui.py --base http://127.0.0.1:8000
```

- Expect: step 1 GET /health OK, then dashboard, chat sessions, execution auth-status (4b), system-summary/health.
- Optional: set `EXECUTION_TOKEN` for execution/tools check (step 4).

## 3. Manual UI

With backend running, in the browser:

| Step | URL | Check |
|------|-----|--------|
| 1 | `/ui/dashboard` | Brain status, Quick Actions, Execution section |
| 2 | `/ui/daena-office` | Sessions, send message, streamed reply |
| 3 | `/ui/control-panel` | Tabs: Skills, Execution, Integrations, etc.; Execution tab shows auth-status and (if token set) tools |
| 4 | `/ui/system-monitor` | Backend status visible |
| 5 | Daena Office chat | Ask "What is the structure of this repo?" – reply shows workspace/repo digest |

## 4. Pytest (sanity)

From project root with a venv that has `pydantic`, `pydantic-settings`, `pytest`, `httpx`:

```bash
set PYTHONPATH=%CD%   # Windows; on Linux/Mac: export PYTHONPATH=$PWD
python -m pip install pytest httpx --quiet
python -m pytest tests/sanity -v --tb=short
```

Or use `scripts\run_comprehensive_tests.bat` (installs pytest if needed; backend must be running for some tests).

## Suggestions

- **DaenaBot hands:** Keep `DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws`; do not expose 18789 to LAN.
- **Execution token:** For Control Panel Execution tab (tools list, etc.), set `EXECUTION_TOKEN` in `.env` or use "Save for session" in the Execution auth box; for local dev only you can set `ALLOW_INSECURE_EXECUTION_LOCAL=1` (localhost).
- **Smoke timeout:** If smoke script hangs on step 1, backend is not running; start it first.
