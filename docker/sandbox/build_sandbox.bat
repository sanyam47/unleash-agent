@echo off
echo ========================================================
echo Building Cyber Sandbox Linux Container: cyber-sandbox:latest
echo ========================================================

if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
    set "PATH=C:\Program Files\Docker\Docker\resources\bin;%PATH%"
)

where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo Please install Docker Desktop and start the daemon first.
    pause
    exit /b 1
)

docker build -t cyber-sandbox:latest -f "%~dp0Dockerfile" "%~dp0"
if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] cyber-sandbox:latest built successfully!
    echo Pre-installed: pwntools, scapy, cryptography, pycryptodome, impacket.
) else (
    echo.
    echo [ERROR] Docker build failed.
)
pause
