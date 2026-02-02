# 🚀 Daena AI VP - Simple Launch Guide

## 📁 **AVAILABLE SCRIPTS**

### **1. `ACTIVATE_ENVIRONMENTS.bat`**
**Purpose:** Activates both environments and installs dependencies
```bash
ACTIVATE_ENVIRONMENTS.bat
```
**What it does:**
- ✅ Activates main environment (`venv_daena_main_py310`)
- ✅ Activates audio environment (`venv_daena_audio`)
- ✅ Installs dependencies from `backend/requirements.txt`
- ✅ Installs dependencies from `audio/requirements.txt`
- ✅ Tests both environments

### **2. `START_DAENA_SIMPLE.bat`**
**Purpose:** Simple launch of Daena AI VP
```bash
START_DAENA_SIMPLE.bat
```
**What it does:**
- ✅ Activates main environment
- ✅ Checks and resolves port 8000 conflicts
- ✅ Starts backend server
- ✅ Opens dashboard automatically

### **3. `SETUP_ENVIRONMENTS.bat`**
**Purpose:** One-time setup of both environments
```bash
SETUP_ENVIRONMENTS.bat
```
**What it does:**
- ✅ Creates fresh virtual environments
- ✅ Installs all dependencies cleanly
- ✅ Sets up file structure
- ✅ Avoids permission issues

## 🎯 **HOW TO USE**

### **First Time Setup:**
```bash
# 1. Set up environments (one-time only)
SETUP_ENVIRONMENTS.bat

# 2. Activate environments and install dependencies
ACTIVATE_ENVIRONMENTS.bat

# 3. Launch Daena
START_DAENA_SIMPLE.bat
```

### **Regular Usage:**
```bash
# Just activate and launch
ACTIVATE_ENVIRONMENTS.bat
START_DAENA_SIMPLE.bat
```

### **Manual Launch:**
```bash
# Activate environment manually
call venv_daena_main_py310\Scripts\activate.bat

# Start backend
python backend/main.py
```

## 🛠️ **ENVIRONMENT STRUCTURE**

### **Main Environment (`venv_daena_main_py310`):**
- **Web Framework:** FastAPI, Uvicorn
- **Database:** SQLAlchemy, Alembic
- **AI/LLM:** OpenAI, Google AI, Anthropic, LangChain
- **Voice:** SpeechRecognition, pyttsx3, ElevenLabs
- **Monitoring:** Prometheus, psutil
- **Security:** bcrypt, cryptography
- **Utilities:** aiofiles, requests, httpx

### **Audio Environment (`venv_daena_audio`):**
- **Audio Processing:** PyAudio, sounddevice, librosa
- **Machine Learning:** PyTorch, torchaudio
- **Audio Files:** pydub, wave, scipy, numpy, soundfile
- **Voice Detection:** webrtcvad, deepgram-sdk
- **Networking:** requests, websockets

## 🔧 **TROUBLESHOOTING**

### **❌ "Environment not found":**
```bash
# Solution: Run setup first
SETUP_ENVIRONMENTS.bat
ACTIVATE_ENVIRONMENTS.bat
```

### **❌ "Port 8000 already in use":**
```bash
# Solution: Use simple start (handles automatically)
START_DAENA_SIMPLE.bat
```

### **❌ "Permission denied":**
```bash
# Solution: Run as administrator or use setup
SETUP_ENVIRONMENTS.bat
```

### **❌ "Package not found":**
```bash
# Solution: Reinstall dependencies
ACTIVATE_ENVIRONMENTS.bat
```

## 📋 **COMMAND REFERENCE**

### **🔄 Environment Commands:**
```bash
# Setup (first time)
SETUP_ENVIRONMENTS.bat

# Activate and install
ACTIVATE_ENVIRONMENTS.bat

# Test environments
call venv_daena_main_py310\Scripts\activate.bat
python -c "import fastapi; print('Main OK')"

call venv_daena_audio\Scripts\activate.bat
python -c "import torch; print('Audio OK')"
```

### **🚀 Launch Commands:**
```bash
# Simple launch
START_DAENA_SIMPLE.bat

# Manual launch
call venv_daena_main_py310\Scripts\activate.bat
python backend/main.py
```

### **🧹 Cleanup Commands:**
```bash
# Kill backend process
taskkill /f /im python.exe

# Kill processes using port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000"') do taskkill /f /pid %%a
```

## ✅ **SUCCESS INDICATORS**

### **✅ Environment Setup Success:**
- Both environments created
- All packages installed
- No permission errors
- Voice packages working

### **✅ Launch Success:**
- Backend starts without errors
- Port 8000 available
- Dashboard opens automatically
- All features working

### **✅ System Running:**
- Backend responding on port 8000
- Dashboard accessible
- Chat persistence working
- Voice services available

## 🎯 **NEXT STEPS**

1. **First time setup:**
   ```bash
   SETUP_ENVIRONMENTS.bat
   ACTIVATE_ENVIRONMENTS.bat
   START_DAENA_SIMPLE.bat
   ```

2. **Regular usage:**
   ```bash
   ACTIVATE_ENVIRONMENTS.bat
   START_DAENA_SIMPLE.bat
   ```

3. **Access Daena:**
   - Dashboard: `http://localhost:8000/dashboard`
   - Analytics: `http://localhost:8000/analytics`
   - API Docs: `http://localhost:8000/docs`

---

**🎯 Your Daena AI VP system is now streamlined with simple, reliable launch scripts!** 