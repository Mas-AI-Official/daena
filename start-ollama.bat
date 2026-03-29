@echo off
setlocal enabledelayedexpansion
title Daena Ollama
color 0D

:: ============================================================
:: Daena Ollama Launcher
:: Starts Ollama serve if not already running
:: ============================================================

echo.
echo  ============================================
echo   DAENA OLLAMA
echo  ============================================
echo.

:: Check if Ollama is installed
where ollama >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Ollama not found in PATH.
    echo          Install from https://ollama.com/download
    pause
    exit /b 1
)

:: Check if Ollama is already running
curl -s http://localhost:11434/api/tags >nul 2>nul
if not errorlevel 1 (
    echo  [OK] Ollama is already running on port 11434.
    echo.
    echo  Listing available models...
    ollama list
    echo.
    echo  No action needed. Close this window or press any key.
    pause
    exit /b 0
)

:: Check if default model is pulled
echo  [1/2] Checking for default model (llama3.1:8b)...
ollama list 2>nul | findstr /i "llama3.1" >nul 2>nul
if errorlevel 1 (
    echo  [WARN] llama3.1:8b not found. Pulling now (this may take a while)...
    ollama pull llama3.1:8b
    if errorlevel 1 (
        echo  [ERROR] Failed to pull llama3.1:8b.
        echo          Check your internet connection and try again.
        pause
        exit /b 1
    )
    echo  [OK] llama3.1:8b pulled successfully.
) else (
    echo  [OK] llama3.1 model found.
)

:: Start Ollama serve
echo  [2/2] Starting Ollama serve on http://localhost:11434 ...
echo.
echo  API:     http://localhost:11434
echo  Models:  ollama list
echo  ============================================
echo.

ollama serve

pause
