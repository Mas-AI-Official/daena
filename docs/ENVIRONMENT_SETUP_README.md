# Daena AI VP System - Environment Setup Guide

## 🚀 Quick Start

To get Daena running with the correct Python 3.10 environment on Drive D:

1. **Run Environment Setup**: `setup_environments.bat`
2. **Test Environments**: `test_environments.py`
3. **Launch Daena**: `LAUNCH_DAENA_COMPLETE.bat`

## 🔧 Environment Setup Process

### Step 1: Setup Environments (`setup_environments.bat`)

This script will:
- ✅ Check if Drive D is available
- ✅ Create/update both main and voice environments
- ✅ Configure Python 3.10 paths correctly
- ✅ Install all necessary dependencies
- ✅ Test both environments

**Run this first if you're having environment issues!**

### Step 2: Test Environments (`test_environments.py`)

This script will:
- ✅ Verify both environments are working
- ✅ Check Python versions (should be 3.10.x)
- ✅ Test key packages (FastAPI, Uvicorn, SQLAlchemy)
- ✅ Test voice packages (PyAudio, SpeechRecognition, pyttsx3)
- ✅ Provide detailed status report

### Step 3: Launch Daena (`LAUNCH_DAENA_COMPLETE.bat`)

This script will:
- ✅ Activate both environments correctly
- ✅ Kill any conflicting Python processes
- ✅ Start the Daena server
- ✅ Test all API endpoints
- ✅ Open the web interface
- ✅ Provide comprehensive status

## 🐍 Python Environment Details

### Main Environment: `venv_daena_main_py310`
- **Purpose**: Core Daena system, FastAPI, database
- **Python Version**: 3.10.x
- **Key Packages**: FastAPI, Uvicorn, SQLAlchemy, httpx, watchdog
- **Location**: `D:\Ideas\Daena\venv_daena_main_py310\`

### Voice Environment: `venv_daena_voice_py310`
- **Purpose**: Voice processing, TTS, STT
- **Python Version**: 3.10.x
- **Key Packages**: PyAudio, SpeechRecognition, pyttsx3, sounddevice
- **Location**: `D:\Ideas\Daena\venv_daena_voice_py310\`

## 🚨 Common Issues & Solutions

### Issue: "Python 3.13 is being used instead of 3.10"
**Solution**: Run `setup_environments.bat` to fix environment paths

### Issue: "Port 8000 is already in use"
**Solution**: The launch script automatically kills conflicting processes

### Issue: "Voice endpoints returning 404"
**Solution**: Ensure both environments are activated and voice packages installed

### Issue: "File monitor errors"
**Solution**: Fixed in latest backend code - should work automatically

## 🔍 Verification Commands

### Check Python Version
```bash
# In main environment
venv_daena_main_py310\Scripts\activate.bat
python --version

# In voice environment  
venv_daena_voice_py310\Scripts\activate.bat
python --version
```

### Check Installed Packages
```bash
# In main environment
pip list | findstr fastapi
pip list | findstr uvicorn

# In voice environment
pip list | findstr pyaudio
pip list | findstr speechrecognition
```

### Test Environment Activation
```bash
# Test main environment
venv_daena_main_py310\Scripts\activate.bat && python -c "import sys; print(sys.executable)"

# Test voice environment
venv_daena_voice_py310\Scripts\activate.bat && python -c "import sys; print(sys.executable)"
```

## 📁 File Structure

```
D:\Ideas\Daena\
├── setup_environments.bat          # Environment setup script
├── test_environments.py            # Environment test script
├── LAUNCH_DAENA_COMPLETE.bat      # Main launch script
├── venv_daena_main_py310\         # Main Python environment
├── venv_daena_voice_py310\        # Voice Python environment
├── backend\                        # Backend code
├── frontend\                       # Frontend code
└── Voice\                          # Voice-related files
```

## 🎯 Expected Behavior

After running all scripts correctly:

1. **Dashboard**: Shows 48 agents across 8 departments
2. **Voice System**: All voice endpoints work (activate, deactivate, talk-mode)
3. **API**: All endpoints respond correctly
4. **Environment**: Python 3.10.x from Drive D
5. **Port**: Server runs on http://localhost:8000

## 🔧 Troubleshooting

### If environments still point to C: drive:
1. Delete both `venv_daena_main_py310` and `venv_daena_voice_py310` folders
2. Run `setup_environments.bat` again
3. This will recreate environments with correct paths

### If packages are missing:
1. Activate the environment: `venv_daena_main_py310\Scripts\activate.bat`
2. Install packages: `pip install -r requirements.txt`
3. For voice: `pip install pyaudio speechrecognition pyttsx3`

### If server won't start:
1. Check if port 8000 is free: `netstat -an | findstr :8000`
2. Kill conflicting processes: `taskkill /f /im python.exe`
3. Run launch script again

## 📞 Support

If you continue to have issues:

1. Run `test_environments.py` and check the output
2. Check the console output from the launch script
3. Verify both environments are pointing to Drive D
4. Ensure Python 3.10 is installed and accessible

## 🎉 Success Indicators

You'll know everything is working when:

- ✅ Both environments show Python 3.10.x
- ✅ All packages install without errors
- ✅ Server starts on port 8000
- ✅ Dashboard shows 48 agents
- ✅ Voice endpoints respond correctly
- ✅ No "Python 3.13" errors in logs

---

**Remember**: Always run `setup_environments.bat` first if you're having environment issues! 