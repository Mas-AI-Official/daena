# 🚀 Daena AI VP - Complete Setup Guide

## ✅ **ISSUES FIXED**

### **🔧 Permission Issues:**
- **Clean environment setup** - Removes corrupted installations
- **No-cache installation** - Avoids permission conflicts
- **Separate environments** - Main and audio isolated
- **Optimized requirements** - Only essential packages

### **🚫 Port Conflicts:**
- **Port 8000 detection** - Checks for existing processes
- **Automatic cleanup** - Kills conflicting processes
- **Manual override** - User choice for process management
- **Quick fix script** - Immediate resolution

### **🎤 Voice Service Issues:**
- **Missing packages added** - SpeechRecognition and pyttsx3
- **Automatic installation** - Installs during launch
- **Voice capabilities** - Speech recognition and TTS working

### **⚡ Performance Issues:**
- **One-time installation** - Environments set up once
- **Fast launch** - No repeated installations
- **Environment validation** - Tests before launch
- **Error handling** - Graceful failure recovery

## 🎯 **SETUP PROCESS**

### **Step 1: Environment Setup (One-time)**
```bash
# Run this first to set up both environments
SETUP_ENVIRONMENTS.bat
```

**What this does:**
- ✅ Creates fresh virtual environments
- ✅ Installs all dependencies cleanly
- ✅ Sets up file structure
- ✅ Avoids permission issues
- ✅ Separates main and audio environments

### **Step 2: Launch Daena (Every time)**
```bash
# Use the optimized launch script
LAUNCH_DAENA_OPTIMIZED.bat
```

**What this does:**
- ✅ Checks environments exist
- ✅ Validates environment health
- ✅ Handles port conflicts
- ✅ Installs missing voice packages
- ✅ Starts backend server
- ✅ Opens dashboard automatically

### **Step 3: Quick Fix (If needed)**
```bash
# Use this for immediate fixes
QUICK_FIX.bat
```

**What this does:**
- ✅ Kills existing processes
- ✅ Installs missing packages
- ✅ Resolves port conflicts
- ✅ Starts Daena immediately

## 🛠️ **ENVIRONMENT STRUCTURE**

### **📁 Main Environment (`venv_daena_main_py310`):**
```
backend/requirements.txt
├── fastapi==0.104.1          # Web framework
├── uvicorn[standard]==0.24.0  # ASGI server
├── sqlalchemy==2.0.23         # Database ORM
├── pydantic==2.5.0           # Data validation
├── openai==1.12.0            # OpenAI integration
├── google-generativeai==0.3.2 # Google AI
├── anthropic==0.8.0          # Anthropic Claude
├── langchain==0.0.350        # LangChain framework
├── aiofiles==23.2.1          # Async file handling
├── psutil==5.9.6             # System monitoring
├── SpeechRecognition==3.10.0  # Speech recognition
├── pyttsx3==2.90             # Text-to-speech
└── ... (other dependencies)
```

### **📁 Audio Environment (`venv_daena_audio`):**
```
audio/requirements.txt
├── pyaudio==0.2.11           # Audio I/O
├── speechrecognition==3.10.0  # Speech recognition
├── pyttsx3==2.90             # Text-to-speech
├── torch==2.1.0              # PyTorch ML
├── librosa==0.10.1           # Audio processing
├── webrtcvad==2.0.10         # Voice activity detection
├── deepgram-sdk==2.12.0      # Deepgram integration
└── ... (other audio dependencies)
```

## 🚀 **LAUNCH OPTIONS**

### **1. Optimized Launch (Recommended)**
```bash
LAUNCH_DAENA_OPTIMIZED.bat
```
**Features:**
- ✅ Environment validation
- ✅ Port conflict handling
- ✅ Voice package installation
- ✅ Fast startup
- ✅ Error recovery
- ✅ Automatic dashboard opening

### **2. Quick Fix (Immediate)**
```bash
QUICK_FIX.bat
```
**Features:**
- ✅ Kills existing processes
- ✅ Installs missing packages
- ✅ Resolves port conflicts
- ✅ Immediate startup

### **3. Port Conflict Fix**
```bash
FIX_PORT_CONFLICT.bat
```
**Features:**
- ✅ Detects port conflicts
- ✅ Shows process details
- ✅ Kills conflicting processes
- ✅ Manual control

### **4. Simple Launch (Quick)**
```bash
LAUNCH_DAENA_SIMPLE.bat
```
**Features:**
- ✅ Minimal checks
- ✅ Fast startup
- ✅ Basic functionality
- ✅ No complex setup

### **5. Full Setup (First time)**
```bash
SETUP_ENVIRONMENTS.bat
```
**Features:**
- ✅ Complete environment setup
- ✅ Clean installations
- ✅ Both environments
- ✅ File structure creation

## 🔧 **TROUBLESHOOTING**

### **❌ "Access is denied" errors:**
```bash
# Solution: Run environment setup
SETUP_ENVIRONMENTS.bat
```

### **❌ "Port 8000 already in use":**
```bash
# Solution 1: Use optimized launch
LAUNCH_DAENA_OPTIMIZED.bat

# Solution 2: Quick fix
QUICK_FIX.bat

# Solution 3: Manual fix
FIX_PORT_CONFLICT.bat
```

### **❌ "Speech recognition not available":**
```bash
# Solution: Use optimized launch (installs automatically)
LAUNCH_DAENA_OPTIMIZED.bat

# Or manual installation
call venv_daena_main_py310\Scripts\activate.bat
pip install SpeechRecognition pyttsx3
```

### **❌ "Environment not found":**
```bash
# Solution: Run setup first
SETUP_ENVIRONMENTS.bat
# Then launch
LAUNCH_DAENA_OPTIMIZED.bat
```

### **❌ "RuntimeError: no running event loop":**
```bash
# Solution: Fixed in chat persistence
# Use optimized launch script
LAUNCH_DAENA_OPTIMIZED.bat
```

## 📊 **PERFORMANCE BENEFITS**

### **⚡ Speed Improvements:**
- **One-time setup** - Environments created once
- **Fast launch** - No repeated installations
- **Cached environments** - Reuse existing setups
- **Optimized dependencies** - Only essential packages

### **🛡️ Reliability Improvements:**
- **Environment validation** - Tests before launch
- **Port conflict handling** - Automatic resolution
- **Voice package management** - Automatic installation
- **Error recovery** - Graceful failure handling
- **Clean installations** - No corrupted packages

### **🎯 User Experience:**
- **Simple commands** - Easy to remember
- **Clear feedback** - Progress indicators
- **Automatic recovery** - Self-healing setup
- **Fast startup** - Quick access to Daena
- **Voice capabilities** - Speech recognition and TTS

## 📋 **COMMAND REFERENCE**

### **🔄 Setup Commands:**
```bash
# First time setup
SETUP_ENVIRONMENTS.bat

# Test environments
call venv_daena_main_py310\Scripts\activate.bat
python -c "import fastapi; print('Main OK')"

call venv_daena_audio\Scripts\activate.bat
python -c "import torch; print('Audio OK')"
```

### **🚀 Launch Commands:**
```bash
# Recommended launch
LAUNCH_DAENA_OPTIMIZED.bat

# Quick fix for immediate issues
QUICK_FIX.bat

# Port conflict resolution
FIX_PORT_CONFLICT.bat

# Simple launch
LAUNCH_DAENA_SIMPLE.bat

# Manual launch
call venv_daena_main_py310\Scripts\activate.bat
python backend/main.py
```

### **🧹 Cleanup Commands:**
```bash
# Clean environments
rmdir /s /q venv_daena_main_py310
rmdir /s /q venv_daena_audio

# Kill backend process
taskkill /f /im python.exe

# Kill processes using port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000"') do taskkill /f /pid %%a
```

## 🎯 **SUCCESS INDICATORS**

### **✅ Environment Setup Success:**
- Both environments created
- All packages installed
- No permission errors
- File structure created
- Voice packages available

### **✅ Launch Success:**
- Backend starts without errors
- Port 8000 available
- Dashboard opens automatically
- Chat persistence working
- Voice services available

### **✅ System Running:**
- Backend responding on port 8000
- Dashboard accessible
- Analytics working
- Chat persistence active
- Speech recognition working
- Text-to-speech working

## 🚀 **NEXT STEPS**

1. **Run environment setup** (first time only):
   ```bash
   SETUP_ENVIRONMENTS.bat
   ```

2. **Launch Daena** (every time):
   ```bash
   LAUNCH_DAENA_OPTIMIZED.bat
   ```

3. **Quick fix** (if issues occur):
   ```bash
   QUICK_FIX.bat
   ```

4. **Access Daena**:
   - Dashboard: `http://localhost:8000/dashboard`
   - Analytics: `http://localhost:8000/analytics`
   - API Docs: `http://localhost:8000/docs`

5. **Test features**:
   - Chat with Daena (auto-saves)
   - View analytics dashboard
   - Manage departments and agents
   - Monitor API usage
   - Use voice features (speech recognition and TTS)

---

**🎯 Your Daena AI VP system is now optimized for fast, reliable launches with proper environment management, voice capabilities, and automatic conflict resolution!** 