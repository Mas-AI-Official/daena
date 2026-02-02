# Local LLM Setup with Ollama

## Quick Start

### 1. Install Ollama
Download from https://ollama.com/download/windows and install.

### 2. Set Model Storage to D: Drive
```powershell
# Set environment variable
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\ollama", "User")

# Restart Ollama service (Admin PowerShell)
Restart-Service Ollama
```

### 3. Pull Models
```bash
ollama pull qwen2.5:7b-instruct
ollama pull llama3.2:3b-instruct
```

### 4. Configure Daena .env
Add to your `.env` file:
```env
# Local LLM (Ollama)
LOCAL_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LOCAL_MODEL=qwen2.5:7b-instruct
FALLBACK_LOCAL_MODEL=llama3.2:3b-instruct

# Cloud APIs (leave empty if not using)
OPENAI_API_KEY=
AZURE_OPENAI_API_KEY=
```

### 5. Verify
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test in Daena
# The dashboard will automatically use local Ollama when cloud keys are missing
```

## Model Recommendations

- **Primary (7B)**: `qwen2.5:7b-instruct` - Good reasoning, needs 8-12GB VRAM
- **Fallback (3B)**: `llama3.2:3b-instruct` - Small, fast, needs 4-6GB VRAM

## How It Works

1. Daena checks for cloud API keys first
2. If no cloud keys found, checks for Ollama
3. If Ollama available, uses local model
4. Falls back to error message if nothing available

## Files Changed

- `backend/services/local_llm_ollama.py` - NEW: Ollama client
- `backend/services/model_registry.py` - UPDATED: Auto-detects Ollama
- `backend/routes/workflows.py` - FIXED: Better error messages


