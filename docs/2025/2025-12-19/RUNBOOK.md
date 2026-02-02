# Daena System Runbook
**Date**: 2025-12-19  
**Target Folder**: `D:\Ideas\Daena_old_upgrade_20251213`

---

## Quick Start

### One-Command Launch
```batch
START_DAENA.bat
```

This single command will:
1. Verify environment
2. Install dependencies (if needed)
3. Start backend server
4. Wait for health check
5. Open dashboard in browser
6. Keep window open for monitoring

---

## Startup Sequence

### 1. Environment Setup
- **Python**: 3.10+ required (venv: `venv_daena_main_py310`)
- **Dependencies**: Auto-installed from `requirements.txt`
- **Database**: SQLite at `daena.db` (auto-created)

### 2. Backend Launch
- **Server**: Uvicorn on `http://127.0.0.1:8000`
- **Entrypoint**: `backend.main:app`
- **Logs**: `logs/backend_<timestamp>.log`
- **Window**: Separate window for backend output

### 3. Health Verification
- **Endpoint**: `http://127.0.0.1:8000/docs`
- **Timeout**: 30 seconds
- **Retry**: Every 1 second
- **Failure**: Shows last 200 lines of backend log

### 4. Browser Launch
- **Dashboard**: `http://127.0.0.1:8000/ui/dashboard`
- **API Docs**: `http://127.0.0.1:8000/docs`
- **Health**: `http://127.0.0.1:8000/api/v1/health/`

---

## Ports & Endpoints

### Backend Server
- **Port**: `8000`
- **Host**: `127.0.0.1` (localhost only)
- **Protocol**: HTTP

### Key Endpoints
- **Health**: `GET /api/v1/health/`
- **LLM Status**: `GET /api/v1/llm/status`
- **Voice State**: `GET /api/v1/voice/state`
- **Daena Chat**: `POST /api/v1/daena/chat`
- **Department Chat**: `POST /api/v1/departments/{id}/chat`
- **API Docs**: `GET /docs`

---

## Environment Variables

### Local-First Configuration
```env
# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LOCAL_MODEL=qwen2.5:7b-instruct
TRAINED_DAENA_MODEL=daena-brain

# Cloud LLM (opt-in)
ENABLE_CLOUD_LLM=false
OPENAI_API_KEY=
AZURE_OPENAI_API_KEY=

# Voice Configuration
DAENA_VOICE_WAV=daena_voice.wav
VOICE_ENGINE=xtts  # xtts | elevenlabs | system

# Server Configuration
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DEBUG=true
```

### Optional Variables
```env
# Authentication (disabled by default)
DISABLE_AUTH=1

# Audio Features
ENABLE_AUDIO=0

# Logging
LOG_LEVEL=INFO
```

---

## File Locations

### Project Structure
```
D:\Ideas\Daena_old_upgrade_20251213\
├── backend/              # Backend Python code
├── frontend/             # Frontend templates & static files
├── logs/                 # Log files (auto-created)
├── scripts/              # Utility scripts
├── docs/                 # Documentation
├── daena.db              # SQLite database
├── daena_voice.wav       # Daena voice file
├── requirements.txt      # Python dependencies
└── START_DAENA.bat       # Main launcher
```

### Important Files
- **Launcher**: `START_DAENA.bat`
- **Backend Entry**: `backend/main.py`
- **Database**: `daena.db`
- **Voice File**: `daena_voice.wav`
- **Logs**: `logs/backend_<timestamp>.log`

---

## Stopping the System

### Graceful Shutdown
1. **Backend Window**: Press `Ctrl+C` in backend window
2. **Launcher Window**: Close window or press `Ctrl+C`
3. **Browser**: Close tabs manually

### Force Stop
```batch
taskkill /F /IM python.exe
```

---

## Troubleshooting

### Backend Won't Start
1. Check Python version: `python --version` (need 3.10+)
2. Check dependencies: `pip install -r requirements.txt`
3. Check port: Ensure port 8000 is not in use
4. Check logs: `logs/backend_<timestamp>.log`

### Dashboard Won't Load
1. Verify backend is running: `http://127.0.0.1:8000/docs`
2. Check browser console for errors
3. Verify frontend files exist: `frontend/templates/`, `frontend/static/`

### LLM Not Working
1. Check Ollama: `curl http://localhost:11434/api/tags`
2. Check LLM status: `GET /api/v1/llm/status`
3. Verify model: `ollama list` should show model
4. Start Ollama if not running

### Voice Not Working
1. Check voice state: `GET /api/v1/voice/state`
2. Verify voice file: `daena_voice.wav` should exist
3. Check voice service logs in backend output
4. Verify TTS dependencies if using XTTS

### Chat History Not Persisting
1. Check database: `daena.db` should exist
2. Verify table: `DepartmentChatMessage` table should exist
3. Check database permissions
4. Review backend logs for database errors

---

## Maintenance

### Daily
- Check logs for errors: `logs/backend_*.log`
- Verify health endpoint: `GET /api/v1/health/`
- Test core functionality: Daena chat, department chat

### Weekly
- Review database size: `daena.db`
- Clean old logs: `logs/` directory
- Update dependencies: `pip install -r requirements.txt --upgrade`

### Monthly
- Backup database: Copy `daena.db`
- Review system performance
- Update documentation

---

## Support & Resources

### Documentation
- **Status**: `docs/2025-12-19/GO_LIVE_STATUS.md`
- **Issues**: `docs/2025-12-19/KNOWN_ISSUES.md`
- **Implementation**: `docs/2025-12-19/PHASE_IMPLEMENTATION_STATUS.md`

### Logs
- **Backend**: `logs/backend_<timestamp>.log`
- **Launcher**: `logs/launch_<timestamp>.log`
- **Smoke Tests**: `logs/smoke_<timestamp>.log`

### API Documentation
- **Interactive**: `http://127.0.0.1:8000/docs`
- **OpenAPI**: `http://127.0.0.1:8000/openapi.json`

---

**Last Updated**: 2025-12-19




