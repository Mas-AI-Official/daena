@echo off
REM ============================================================
REM DAENA VOICE SYSTEM - QUICK START GUIDE
REM ============================================================

echo.
echo ========================================
echo   DAENA VOICE SYSTEM - QUICK START
echo ========================================
echo.

REM Check if backend is running
echo [1/4] Checking Backend Service...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel%==0 (
    echo   ✅ Backend is running on port 8000
) else (
    echo   ❌ Backend is NOT running
    echo   📝 Run START_DAENA.bat first!
    pause
    exit /b 1
)
echo.

REM Check if audio service is running
echo [2/4] Checking Audio Service...
curl -s http://127.0.0.1:5001/health >nul 2>&1
if %errorlevel%==0 (
    echo   ✅ Audio service is running on port 5001
) else (
    echo   ⚠️  Audio service is NOT running
    echo   📝 Starting audio service now...
    echo.
    
    REM Check if audio venv exists
    if not exist "venv_daena_audio_py310\Scripts\python.exe" (
        echo   ❌ Audio environment not found!
        echo   📝 Creating audio environment...
        python -m venv venv_daena_audio_py310
        echo   📝 Installing audio dependencies...
        venv_daena_audio_py310\Scripts\pip.exe install -q -r requirements-audio.txt
    )
    
    REM Start audio service in background
    start "DAENA - AUDIO" cmd /k "cd /d %cd% && call venv_daena_audio_py310\Scripts\activate.bat && python -m uvicorn audio.audio_service.main:app --host 127.0.0.1 --port 5001"
    
    echo   ⏳ Waiting for audio service to start...
    timeout /t 5 /nobreak >nul
    
    curl -s http://127.0.0.1:5001/health >nul 2>&1
    if %errorlevel%==0 (
        echo   ✅ Audio service started successfully
    ) else (
        echo   ❌ Failed to start audio service
        echo   📝 Check the DAENA - AUDIO window for errors
        pause
        exit /b 1
    )
)
echo.

REM Check voice sample file
echo [3/4] Checking Voice Sample...
if exist "daena_voice.wav" (
    echo   ✅ daena_voice.wav found (main directory)
) else if exist "Voice\daena_voice.wav" (
    echo   ✅ daena_voice.wav found (Voice directory)
) else (
    echo   ⚠️  daena_voice.wav not found!
    echo   📝 Voice cloning won't work without this file
    echo   💡 Add a WAV recording of Daena's voice to the project root
)
echo.

REM Open dashboard
echo [4/4] Opening Daena Office...
start "" "http://127.0.0.1:8000/ui/daena-office"
timeout /t 2 /nobreak >nul
echo   ✅ Dashboard opened in browser
echo.

echo ========================================
echo   VOICE SYSTEM STATUS: READY
echo ========================================
echo.
echo 📝 HOW TO USE VOICE:
echo.
echo   1. Look for the microphone icon in the top-right navbar
echo   2. Click it to enable voice mode
echo   3. Allow microphone access when browser prompts
echo   4. Speak your message - it will transcribe automatically
echo   5. Hear Daena's voice response
echo.
echo 🎙️  VOICE FEATURES:
echo.
echo   ✅ Speech-to-Text (your voice → text)
echo   ✅ Text-to-Speech (Daena's voice response)
echo   ✅ Auto-interrupt when you type/speak
echo   ✅ Works in background (minimized window)
echo   ✅ Navbar toggle (easy on/off)
echo.
echo 🔧 TROUBLESHOOTING:
echo.
echo   - Voice not working? Check browser console (F12)
echo   - Audio service offline? Run this script again
echo   - No microphone access? Check browser permissions
echo.
echo ========================================
echo   Press any key to open documentation...
echo ========================================
pause >nul

REM Open voice documentation
if exist "docs\VOICE_SYSTEM_SETUP.md" (
    notepad "docs\VOICE_SYSTEM_SETUP.md"
) else (
    echo Documentation not found. Check docs/VOICE_SYSTEM_SETUP.md
)
