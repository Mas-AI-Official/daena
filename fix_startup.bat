@echo off
echo ============================================
echo    DAENA STARTUP FIX - AGGRESSIVE MODE
echo ============================================
echo.

echo [1/4] Killing all Python processes...
taskkill /F /IM python.exe /T 2>nul
if %errorlevel%==0 (
    echo [OK] Python processes stopped
    timeout /t 2 /nobreak >nul
) else (
    echo [INFO] No Python processes running
)

echo.
echo [2/4] Unlocking database (forceful)...
REM Wait for file handles to release
timeout /t 1 /nobreak >nul

REM Try multiple times with delay
set RETRY=0
:DELETE_WAL
if exist daena.db-wal (
    del /F /Q daena.db-wal 2>nul
    if %errorlevel%==0 (
        echo [OK] daena.db-wal deleted
    ) else (
        set /a RETRY+=1
        if %RETRY% LSS 3 (
            echo [RETRY] Attempt %RETRY%/3 - waiting 2s...
            timeout /t 2 /nobreak >nul
            goto DELETE_WAL
        ) else (
            echo [WARN] Could not delete daena.db-wal (file locked)
        )
    )
) else (
    echo [OK] daena.db-wal not present
)

set RETRY=0
:DELETE_SHM
if exist daena.db-shm (
    del /F /Q daena.db-shm 2>nul
    if %errorlevel%==0 (
        echo [OK] daena.db-shm deleted
    ) else (
        set /a RETRY+=1
        if %RETRY% LSS 3 (
            echo [RETRY] Attempt %RETRY%/3 - waiting 2s...
            timeout /t 2 /nobreak >nul
            goto DELETE_SHM
        ) else (
            echo [WARN] Could not delete daena.db-shm (file locked)
        )
    )
) else (
    echo [OK] daena.db-shm not present
)

echo.
echo [3/4] Setting database permissions...
if exist "daena.db" (
    echo   - Removing read-only attribute...
    attrib -R "daena.db" /S
    echo   - Granting full permissions...
    icacls "daena.db" /grant:r "Everyone":(F) /T /C /Q >nul 2>&1
    icacls "daena.db" /grant:r "%USERNAME%":(F) /T /C /Q >nul 2>&1
)

if exist "logs" (
    attrib -R "logs" /S /D
    icacls "logs" /grant:r "Everyone":(F) /T /C /Q >nul 2>&1
)

echo.
echo [3/4] Checking Audio Service dependencies...
if exist venv_daena_audio_py310\Scripts\pip.exe (
    echo [INFO] Installing faster-whisper and TTS...
    venv_daena_audio_py310\Scripts\pip install faster-whisper TTS --quiet --disable-pip-version-check
    if %errorlevel%==0 (
        echo [OK] Audio dependencies installed
    ) else (
        echo [WARN] Audio dependencies installation had issues
    )
) else (
    echo [ERROR] Audio venv not found!
)

echo.
echo [4/4] Finalizing...
echo [OK] Startup fixes complete!
echo.
echo ============================================
echo    Ready to launch Daena
echo ============================================
timeout /t 2 /nobreak >nul
