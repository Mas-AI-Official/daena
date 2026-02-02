# Daena AI VP - Runbook
**Date:** 2025-01-23
**Purpose:** Step-by-step guide to start and operate the system

## Prerequisites

1. **Python 3.10+** installed
2. **Ollama** (optional, for AI brain) - Download from https://ollama.ai
3. **Windows** (batch scripts are Windows-specific)

## Quick Start

### Option 1: One-Click Launcher (Recommended)
```cmd
START_DAENA.bat
```
This will:
- Set up environment
- Install dependencies
- Start backend
- Open browser tabs

### Option 2: Manual Start

#### Step 1: Start Ollama (Optional)
```cmd
scripts\START_OLLAMA.bat
```
Or manually:
```cmd
ollama serve
```

#### Step 2: Start Backend
```cmd
scripts\simple_start_backend.bat
```
Or manually:
```cmd
cd D:\Ideas\Daena_old_upgrade_20251213
venv_daena_main_py310\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

#### Step 3: Start Audio Environment (Optional)
```cmd
scripts\START_AUDIO_ENV.bat
```

## Verification

### Check Backend Health
```cmd
curl http://127.0.0.1:8000/api/v1/health/
```
Or in browser: http://127.0.0.1:8000/api/v1/health/

### Check Ollama (if using)
```cmd
curl http://127.0.0.1:11434/api/tags
```

### Access Points

- **Dashboard:** http://127.0.0.1:8000/ui/dashboard
- **API Docs:** http://127.0.0.1:8000/docs
- **Health Check:** http://127.0.0.1:8000/api/v1/health/

## Troubleshooting

### Backend Won't Start

1. **Check Python:**
   ```cmd
   venv_daena_main_py310\Scripts\python.exe --version
   ```
   Should show Python 3.10.x

2. **Check Dependencies:**
   ```cmd
   venv_daena_main_py310\Scripts\python.exe -c "import fastapi, uvicorn; print('OK')"
   ```

3. **Check Database:**
   ```cmd
   dir daena.db
   ```
   Should exist and have content

4. **Check Port 8000:**
   ```cmd
   netstat -an | findstr :8000
   ```
   Should be empty (port not in use)

### Backend Starts But Tests Fail

1. **Check Backend Logs:**
   - Look in `logs\backend_*.log`
   - Check for import errors or database issues

2. **Verify Database:**
   ```cmd
   python -c "from backend.database import SessionLocal; db = SessionLocal(); print('DB OK')"
   ```

3. **Check Council Seeding:**
   ```cmd
   curl http://127.0.0.1:8000/api/v1/council/list
   ```
   Should return at least 2 councils

### Ollama Not Working

1. **Check Ollama Status:**
   ```cmd
   curl http://127.0.0.1:11434/api/tags
   ```

2. **Start Ollama:**
   ```cmd
   ollama serve
   ```

3. **Pull Model (if needed):**
   ```cmd
   ollama pull qwen2.5:7b-instruct
   ```

## Environment Variables

Optional environment variables:

- `DAENA_VOICE_WAV` - Path to daena_voice.wav file
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://127.0.0.1:11434)
- `ENABLE_CLOUD_LLM` - Enable cloud LLM providers (default: false)

## Stopping Services

1. **Backend:** Press CTRL+C in backend window
2. **Ollama:** Press CTRL+C in Ollama window
3. **Audio Env:** Close the window

## Database Management

### Reset Database (Development Only)
```cmd
python -c "from backend.database import create_tables; create_tables(); print('Tables recreated')"
```

### Backup Database
```cmd
copy daena.db daena.db.backup
```

### View Database
Use SQLite browser or:
```cmd
python -c "from backend.database import SessionLocal; db = SessionLocal(); from backend.database import ChatSession; print(f'Sessions: {db.query(ChatSession).count()}')"
```

## Common Commands

### Run Tests
```cmd
python scripts/comprehensive_test_all_phases.py
```

### Check System Status
```cmd
curl http://127.0.0.1:8000/api/v1/system/status
```

### List All Agents
```cmd
curl http://127.0.0.1:8000/api/v1/agents/
```

### List All Departments
```cmd
curl http://127.0.0.1:8000/api/v1/departments/
```

### List Councils
```cmd
curl http://127.0.0.1:8000/api/v1/council/list
```

## Support

If issues persist:
1. Check `logs\` directory for error logs
2. Review `report bug.txt` for known issues
3. Verify all prerequisites are met
4. Check that no other services are using port 8000


