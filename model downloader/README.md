# Model Downloader

Downloads Ollama LLM models (including **deepseek-r1:14b**, deepseek-r1:7b, qwen2.5, etc.) and LTX video models.

## Configuration

- **MODELS_ROOT**: Default `D:\Ideas\MODELS_ROOT`. Override with env:
  - `MODELS_ROOT` or `DAENA_MODELS_ROOT` (e.g. `set MODELS_ROOT=D:\Ideas\MODELS_ROOT`)
- Ollama models are stored under `MODELS_ROOT/ollama`.
- LTX models under `MODELS_ROOT/ltx`.

## Models included

- **deepseek-r1:14b** — Reasoning
- **deepseek-r1:7b** — Fallback reasoning
- qwen2.5:14b-instruct, qwen2.5:7b-instruct
- nomic-embed-text, bge-m3, llama3.1:8b

## Run

1. Ensure Ollama is installed and (optionally) set `OLLAMA_MODELS` to `MODELS_ROOT/ollama` so pulls go there.
2. From project root:
   ```bat
   python "model downloader\download_models.py"
   ```
   Or with custom root:
   ```bat
   set MODELS_ROOT=D:\Ideas\MODELS_ROOT
   python "model downloader\download_models.py"
   ```

After pulling, **deepseek-r1:14b** and others will appear in Control Plane → Brain & API (from Ollama `api/tags`).
