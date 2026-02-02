# Local Brain Setup Guide

## Overview
All LLM models and brain storage are now configured to use the `local_brain` directory.

## Directory Structure
```
D:\Ideas\Daena_old_upgrade_20251213\
├── local_brain\
│   ├── models\          # Ollama models (blobs, manifests)
│   ├── brain_store\     # Brain storage (governance queue, committed experiences)
│   ├── adapters\        # Model adapters
│   └── blobs\           # Model blobs
```

## Configuration

### Environment Variables
Set in `.env` file:
```
OLLAMA_MODELS=D:\Ideas\Daena_old_upgrade_20251213\local_brain
OLLAMA_BASE_URL=http://localhost:11434
TRAINED_DAENA_MODEL=daena-brain
DEFAULT_LOCAL_MODEL=qwen2.5:7b-instruct
```

### Settings
- `backend/config/settings.py`: Default path set to `local_brain`
- `backend/services/local_llm_ollama.py`: Uses `settings.ollama_models_path`
- `backend/core/brain/store.py`: Uses `local_brain/brain_store`

## Ollama Configuration

### Option 1: Environment Variable (Recommended)
Set `OLLAMA_MODELS` environment variable before starting Ollama:
```powershell
$env:OLLAMA_MODELS = "D:\Ideas\Daena_old_upgrade_20251213\local_brain"
ollama serve
```

### Option 2: System Environment Variable
Add to System Environment Variables:
- Variable: `OLLAMA_MODELS`
- Value: `D:\Ideas\Daena_old_upgrade_20251213\local_brain`

### Option 3: Restart Ollama Service
If Ollama is running as a service:
1. Stop Ollama service
2. Set `OLLAMA_MODELS` environment variable
3. Start Ollama service

## Verification

### Check Models Location
```powershell
cd D:\Ideas\Daena_old_upgrade_20251213
$env:OLLAMA_MODELS = "D:\Ideas\Daena_old_upgrade_20251213\local_brain"
ollama list
```

### Check Backend Configuration
```powershell
python -c "from backend.config.settings import settings; print(f'OLLAMA_MODELS: {settings.ollama_models_path}')"
```

## Models Available
Based on `local_brain/models/manifests/`:
- `qwen2.5:7b-instruct`
- `qwen2.5:14b-instruct`
- `qwen2.5:14b`
- `llama3.2:3b`

## Troubleshooting

### Models Not Found
1. Verify `OLLAMA_MODELS` is set correctly
2. Restart Ollama service
3. Check `local_brain/models/blobs/` contains model files
4. Verify Ollama can access the path (permissions)

### Backend Can't Find Models
1. Check `.env` file has `OLLAMA_MODELS` set
2. Restart backend after setting environment variable
3. Check backend logs for Ollama path configuration




