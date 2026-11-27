@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw backend\scripts\jarvis_desktop_hud.py --visible
) else (
    start /B "" python backend\scripts\jarvis_desktop_hud.py --visible
)
