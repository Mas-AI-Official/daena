@echo off
REM Finishes the Claude Opus 4.7 + xhigh-effort config upgrade.
REM Run this AFTER closing all Claude Code sessions (the live file is
REM locked while Claude Code is running).
echo.
echo Claude Code Opus 4.7 + xhigh effort upgrade
echo --------------------------------------------
echo Closing Claude Code releases the file lock. If any Claude Code
echo window is still open, close it now and re-run this script.
echo.
if exist "C:\Users\masou\.claude\settings.json.new" (
    move /Y "C:\Users\masou\.claude\settings.json.new" "C:\Users\masou\.claude\settings.json"
    if %ERRORLEVEL%==0 (
        echo OK -- settings.json updated.
        echo Backup is at C:\Users\masou\.claude\settings.json.bak-4-7-upgrade
    ) else (
        echo FAILED -- settings.json is still locked. Close Claude Code and retry.
    )
) else (
    echo Nothing to apply; settings.json.new not found.
)
pause
