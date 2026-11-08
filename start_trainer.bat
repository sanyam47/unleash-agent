@echo off
title AI Trainer & Local LLM Studio
echo =======================================================
echo   Starting AI Trainer & Local Ollama Engine
echo =======================================================
echo.

:: Start Ollama in background if not already running
echo [*] Checking Ollama service...
start /B "" ollama serve > nul 2>&1

:: Start FastAPI Backend
echo [*] Starting FastAPI Web Server on http://localhost:8001 ...
start "" http://localhost:8001
python -m uvicorn backend.api.main:app --reload --port 8001

pause
