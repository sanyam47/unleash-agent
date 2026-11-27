@echo off
setlocal enabledelayedexpansion
title Unleash-Agent Studio (Air-Gapped Autonomous Runtime)
color 0A

echo =====================================================================
echo    __  __      __                __       ___                    __ 
echo   / / / /___  / /__  ____ ______/ /_     /   ^| ____ _____  ____  / /_
echo  / / / / __ \/ / _ \/ __ `/ ___/ __ \   / /^| ^|/ __ `/ _ \/ __ \/ __/
echo / /_/ / / / / /  __/ /_/ (__  ) / / /  / ___ / /_/ /  __/ / / / /_  
echo \____/_/ /_/_/\___/\__,_/____/_/ /_/  /_/  ^|_\__, /\___/_/ /_/\__/   
echo                                             /____/                  
echo       THE SECURE, AIR-GAPPED AUTONOMOUS AGENT RUNTIME
echo =====================================================================
echo.

:: 1. Set working directory & PYTHONPATH
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

:: 2. Pre-flight Python Check
echo [*] Checking Python runtime environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.10+ from python.org and check "Add to PATH".
    pause
    exit /b 1
)

:: 3. Pre-flight Ollama Engine Check
echo [*] Auditing local Ollama LLM runtime...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Ollama background daemon is active.
) else (
    echo [*] Launching Ollama daemon in background...
    start /B "" ollama serve >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: 4. Clean Stale Port 8001
echo [*] Verifying port 8001 availability...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
    echo [*] Freeing port 8001 (terminating zombie PID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

:: 5. Arm Floating Gyro Sphere Hotkey in Standby (Ctrl+Shift+Space to show/hide)
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start /B "" pythonw backend\scripts\jarvis_desktop_hud.py --hidden
) else (
    start /B "" python backend\scripts\jarvis_desktop_hud.py --hidden
)

:: 6. Launch Browser in background
echo [*] Launching Unleash-Agent Studio UI at http://localhost:8001 ...
start "" http://localhost:8001

:: 7. Launch FastAPI Server
echo [*] Booting Air-Gapped Executive API & Sensory Telemetry Engine...
echo =====================================================================
python -m uvicorn backend.api.main:app --port 8001 --reload

pause
