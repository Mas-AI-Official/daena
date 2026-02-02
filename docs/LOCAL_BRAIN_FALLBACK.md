# Local Brain Fallback (Daena Brain = Local Ollama)

When primary Ollama (port 11434) is down, Daena can use a **local brain fallback**: the same Ollama binary runs on port **11435** with `OLLAMA_MODELS=MODELS_ROOT/ollama`, so the system never fails for lack of Ollama.

## How it works

1. **Primary**: Backend uses `OLLAMA_BASE_URL` (default `http://localhost:11434`). If that responds, all brain and chat traffic goes there.
2. **Fallback**: If primary is unreachable, the backend:
   - Tries fallback URL `http://127.0.0.1:11435`.
   - If that is also down, starts a **Daena-managed** `ollama serve` with:
     - `OLLAMA_HOST=127.0.0.1:11435`
     - `OLLAMA_MODELS=MODELS_ROOT/ollama`
     - `OLLAMA_NUM_GPU=1` and `OLLAMA_GPU_OVERHEAD=10` to reduce GPU OOM.
   - Then retries requests to the fallback URL.

So **daena brain** is just Ollama on a second port using MODELS_ROOT; when you upgrade Ollama, both primary and fallback use the new binary.

## Configuration

| Env / setting | Default | Description |
|---------------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Primary Ollama URL. |
| `OLLAMA_FALLBACK_PORT` | `11435` | Port for Daena-managed fallback. |
| `OLLAMA_USE_LOCAL_BRAIN_FALLBACK` | `true` | If `false`, no fallback; only primary is used. |
| `MODELS_ROOT` | `D:/Ideas/MODELS_ROOT` | Root for models; fallback uses `MODELS_ROOT/ollama`. |
| `OLLAMA_MODELS` | (from MODELS_ROOT) | Override models path for both primary and fallback. |

## GPU / CUDA (efficient, avoid crashes)

- **OLLAMA_NUM_GPU=1** – Use one GPU so multi-model loads don’t OOM.
- **OLLAMA_GPU_OVERHEAD=10** – Reserve ~10% VRAM for system (default in fallback).
- **CUDA_VISIBLE_DEVICES** – Optional; e.g. `CUDA_VISIBLE_DEVICES=0` to pin to one GPU.

Set these in:

- `START_DAENA.bat` – before starting Ollama (already sets `OLLAMA_NUM_GPU`, `OLLAMA_GPU_OVERHEAD`).
- `scripts/START_OLLAMA.bat` – when starting Ollama manually (same vars + `OLLAMA_MODELS=%MODELS_ROOT%\ollama`).

## Manual “local Ollama” (same as Daena brain)

To run Ollama yourself with the same layout and GPU settings:

```bat
set MODELS_ROOT=D:\Ideas\MODELS_ROOT
set OLLAMA_MODELS=%MODELS_ROOT%\ollama
set OLLAMA_NUM_GPU=1
set OLLAMA_GPU_OVERHEAD=10
ollama serve
```

Or run `scripts\START_OLLAMA.bat`; it sets these and starts Ollama on 11434.

## Code

- **Backend**: `backend/services/local_brain_manager.py` – starts fallback process, `try_primary_then_fallback()`.
- **LLM**: `backend/services/local_llm_ollama.py` – uses `get_ollama_base_url()` (primary or fallback) for `chat` and `generate_stream`.
- **Brain status**: `backend/routes/brain_status.py` – `/api/v1/brain/status` uses primary or fallback; response may include `using_fallback: true`.
