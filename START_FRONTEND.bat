@echo off
title STARTING DAENA FRONTEND
cd /d "%~dp0\frontend"
npm run dev -- --port 5173
pause
