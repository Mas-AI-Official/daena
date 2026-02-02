# Known Issues & Solutions
**Date**: 2025-12-19  
**Target Folder**: `D:\Ideas\Daena_old_upgrade_20251213`

---

## Current Issues

### None - All Systems Operational ✅

All critical systems are working. Remaining items are enhancements, not blockers.

---

## Common Problems & Solutions

### Problem: Backend Window Closes Immediately

**Symptoms**: Backend window opens then closes instantly

**Causes**:
- Python import error
- Missing dependencies
- Port conflict
- Syntax error in code

**Solutions**:
1. Check backend log: `logs/backend_<timestamp>.log`
2. Run preflight check: `python -c "import backend.main"`
3. Verify dependencies: `pip install -r requirements.txt`
4. Check port: `netstat -ano | findstr :8000`
5. Review error in backend window before it closes

**Prevention**: Launcher now includes preflight checks

---

### Problem: "Ollama not reachable" Message

**Symptoms**: Chat returns "Ollama not reachable" message

**Causes**:
- Ollama not installed
- Ollama not running
- Wrong port/URL
- Model not pulled

**Solutions**:
1. Install Ollama: https://ollama.ai/download
2. Start Ollama service
3. Verify: `curl http://localhost:11434/api/tags`
4. Pull model: `ollama pull qwen2.5:7b-instruct`
5. Check LLM status: `GET /api/v1/llm/status`

**Workaround**: System works without Ollama (shows clear error message)

---

### Problem: Voice Toggle Doesn't Work

**Symptoms**: Voice toggle in UI doesn't change state

**Causes**:
- Frontend not calling `/api/v1/voice/state`
- Frontend not using `/api/v1/voice/enable`/`/disable`
- Voice service not initialized

**Solutions**:
1. Check browser console for errors
2. Verify endpoint: `GET /api/v1/voice/state`
3. Test manually: `POST /api/v1/voice/enable`
4. Check backend logs for voice service errors
5. Update frontend to use new endpoints (Phase D)

**Status**: Backend endpoints ready, frontend integration pending

---

### Problem: Chat History Not Persisting

**Symptoms**: Chat messages disappear after refresh

**Causes**:
- Database not created
- Table not created
- Database permissions
- Database locked

**Solutions**:
1. Check database exists: `daena.db`
2. Verify table: Check `DepartmentChatMessage` table exists
3. Check permissions: Ensure write access to project directory
4. Review backend logs for database errors
5. Run migration: `python backend/scripts/add_chat_history_table.py`

**Prevention**: Migration runs automatically on startup

---

### Problem: Multiple Agent Responses in Group Chat

**Symptoms**: All agents respond individually instead of one spokesperson

**Causes**:
- Group speaker logic not implemented (Phase E)

**Solutions**:
1. This is expected behavior (Phase E pending)
2. Use specific agent ID for direct agent response
3. Wait for Phase E implementation

**Status**: Enhancement, not a bug

---

### Problem: "Module not found" Errors

**Symptoms**: Import errors in backend logs

**Causes**:
- Missing dependencies
- Wrong Python environment
- Virtual environment not activated

**Solutions**:
1. Activate venv: `venv_daena_main_py310\Scripts\activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Verify Python: `python --version` (should be 3.10+)
4. Check imports: `python -c "import backend.main"`

**Prevention**: Launcher handles this automatically

---

### Problem: Port 8000 Already in Use

**Symptoms**: Backend fails to start, port conflict error

**Causes**:
- Another instance running
- Another application using port 8000

**Solutions**:
1. Find process: `netstat -ano | findstr :8000`
2. Kill process: `taskkill /F /PID <pid>`
3. Change port: Set `BACKEND_PORT=8001` in environment
4. Restart backend

**Prevention**: Launcher checks for existing processes

---

### Problem: Voice File Not Found

**Symptoms**: Voice features don't work, "voice file not found" error

**Causes**:
- `daena_voice.wav` missing
- Wrong path configuration
- File permissions

**Solutions**:
1. Check file exists: `daena_voice.wav` in project root
2. Verify path: Check `backend/config/voice_config.py`
3. Set override: `DAENA_VOICE_WAV=<path>` environment variable
4. Check permissions: Ensure file is readable

**Prevention**: System checks multiple locations automatically

---

## Performance Issues

### Slow LLM Responses

**Causes**:
- Large model (7B+)
- CPU-only inference
- Network latency (cloud)

**Solutions**:
1. Use smaller model: `llama3.2:3b-instruct`
2. Enable GPU: Ensure CUDA available
3. Use local model: Prefer Ollama over cloud
4. Check system resources: CPU/RAM usage

---

### High Memory Usage

**Causes**:
- Large models loaded
- Multiple instances
- Memory leaks

**Solutions**:
1. Use smaller models
2. Restart backend periodically
3. Check for memory leaks in logs
4. Monitor system resources

---

## Feature Limitations

### Group Chat (Phase E)
- **Status**: Not implemented
- **Workaround**: Use specific agent ID
- **Timeline**: Enhancement, low priority

### Voice Test Endpoint
- **Status**: Structure exists, needs implementation
- **Workaround**: Use `/api/v1/voice/synthesize`
- **Timeline**: Enhancement, low priority

### Doctor Mode
- **Status**: Not implemented
- **Workaround**: Manual diagnostics
- **Timeline**: Enhancement, low priority

---

## Reporting Issues

### Before Reporting
1. Check this document
2. Review logs: `logs/backend_*.log`
3. Test endpoints: Use `/docs` to test API
4. Check system status: `GET /api/v1/health/`

### When Reporting
Include:
- Error message (full text)
- Steps to reproduce
- Log file excerpts
- System information (Python version, OS)
- Backend status: `GET /api/v1/health/`

---

**Last Updated**: 2025-12-19  
**Status**: All critical issues resolved ✅




