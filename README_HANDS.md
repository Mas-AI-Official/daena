# DaenaBot "Hands" (OpenClaw Gateway)

DaenaBot uses a **hands** service (OpenClaw Gateway) to run tools (browser, filesystem, terminal) under governance. This document describes safe local-only setup.

## What they mean

- **DAENABOT_DISPLAY_NAME** — (Optional) UI label for the bot (e.g. `DaenaBot` or `DanBot`). Control Panel tab and tools panel use this; default is `DaenaBot`.
- **DAENABOT_HANDS_URL** — WebSocket URL where the hands service (OpenClaw Gateway) is running.
- **DAENABOT_HANDS_TOKEN** — Secret token DaenaBot uses to authenticate to that gateway.

**Safe default (local-only):**

```env
DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws
DAENABOT_HANDS_TOKEN=put_the_gateway_token_here
```

## Security

- **Bind to 127.0.0.1 only.** Do not expose port 18789 to LAN or internet.
- **Good:** `ws://127.0.0.1:18789/ws` (localhost only).
- **Risky:** `0.0.0.0` or any LAN IP exposes the gateway; use only behind a proper access layer if needed.
- Copy the gateway token from the OpenClaw config/wizard and paste it into `.env`. Do not commit `.env`.

## Backward compatibility

If you still use the old env names, they still work:

- `OPENCLAW_GATEWAY_URL` → used when `DAENABOT_HANDS_URL` is not set.
- `OPENCLAW_GATEWAY_TOKEN` → used when `DAENABOT_HANDS_TOKEN` is not set.

`DAENABOT_HANDS_*` take precedence.

## How to run locally

1. Run the OpenClaw Gateway separately (e.g. on port 18789, bound to 127.0.0.1).
2. Copy the gateway token from its config or wizard.
3. In this repo’s `.env` set:
   - `DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws`
   - `DAENABOT_HANDS_TOKEN=<paste_the_token>`
4. Start Daena; it will connect to the gateway with the token.

## Quick local test

1. **Env only (no backend):**  
   From project root:
   ```bash
   python scripts/verify_daenabot_hands_env.py
   ```
   Checks `DAENABOT_HANDS_URL` / `OPENCLAW_GATEWAY_URL` and token env; safe default is `ws://127.0.0.1:18789/ws`.

2. **With backend:**  
   Set `DAENABOT_HANDS_URL` and `DAENABOT_HANDS_TOKEN` in `.env`, start the backend, then open Control Panel → DaenaBot Tools (or the tools status endpoint). Connection status should show **connected/authenticated** when the gateway is running and the token matches.

3. **Smoke (backend must be running):**  
   ```bash
   python scripts/smoke_and_manual_ui.py --base http://127.0.0.1:8000
   ```
   Optional: set `EXECUTION_TOKEN` for execution-layer checks.

4. **Pytest (sanity):**  
   From project root with a venv that has `pydantic`, `pydantic-settings`, `pytest`, `httpx`:
   ```bash
   set PYTHONPATH=%CD%   # or export PYTHONPATH=$PWD
   python -m pytest tests/sanity -v --tb=short
   ```
   Or use `scripts\run_comprehensive_tests.bat` (prefers `venv_daena_main_py310` then `venv_daena_audio_py310`, installs pytest if needed).
