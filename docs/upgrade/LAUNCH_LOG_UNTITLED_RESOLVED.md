## Summary
`Untitled` was a raw startup log capture from a failed local run. It is now **archived** and the underlying issues are **fixed**, so `/ui/dashboard` and `/ui/health` load normally.

## What was failing (root causes)
- **Logging formatter crash**: dev formatter required `%(trace_id)s`, but most logs didn’t provide it.
- **Windows console UnicodeEncodeError**: emoji/unicode log messages crashed on cp1252 consoles.
- **Optional provider crash**: Gemini (`google.generativeai` / `genai`) referenced when not installed.
- **Optional voice crash**: voice cloning imported `aiohttp` at import-time; missing dependency broke boot.
- **Missing module**: `models.chat_history` was imported but didn’t exist.
- **Monitoring route crash**: `backend/routes/monitoring.py` used `logging` without importing it.

## Fixes implemented
- **`backend/config/logging_config.py`**
  - Adds a filter that injects default `trace_id` / `request_id`.
  - Avoids auto-running logging setup at import-time.
  - Adds UTF-8 stdout safety to prevent UnicodeEncodeError on Windows.
- **`backend/services/llm_service.py` + `backend/config/settings.py`**
  - Makes cloud providers **opt-in** via `ENABLE_CLOUD_LLM=1`.
  - Guards Gemini usage when the library isn’t installed.
- **`backend/services/voice_service.py` + `backend/services/voice_cloning.py`**
  - Fixes `logger` initialization order.
  - Makes voice cloning safe when `aiohttp` is missing (disabled instead of crashing).
  - `requirements-audio.txt` includes `aiohttp` for the audio environment.
- **`backend/models/chat_history.py`**
  - Adds a minimal chat history manager used by `/api/v1/chat-history/*`.
- **`backend/routes/monitoring.py`**
  - Adds missing `import logging`.

## Verified (local)
- `/ui/dashboard` → **200**
- `/ui/health` → **200**
- `/api/v1/health/` → **200**











