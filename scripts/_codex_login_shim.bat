@echo off
title Codex Login - sign in via browser
echo.
echo  ================================================
echo   CODEX LOGIN - sign in via your default browser
echo  ================================================
echo.
echo  Codex CLI will open your browser. Sign in with
echo  your ChatGPT Plus / Pro account. The CLI prints
echo  a success message when done. Then come back to
echo  Claude Code -- Daena will re-probe automatically.
echo.
echo  Starting in 2 seconds...
echo.
ping -n 3 127.0.0.1 >NUL
codex login
echo.
echo  ================================================
echo   Done. Press any key to close this window.
echo  ================================================
pause >NUL
