"""
Windowless Unleash-Agent Desktop Launcher (`pythonw.exe`).

Starts the Unleash-Agent backend on port 8001 (no console window), arms the
system-wide Floating Gyro Sphere hotkey (`Ctrl+Shift+Space`) in standby,
and opens http://127.0.0.1:8001 in the user's browser cleanly.
"""

from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_PORT = 8001
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"


def _is_port_open(host: str = "127.0.0.1", port: int = BACKEND_PORT, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_python_executables() -> tuple[str, str]:
    """Returns `(python_console_exe, pythonw_gui_exe)` preferring the global Python install."""
    exe = Path(sys.executable)
    if os.name != "nt":
        return str(exe), str(exe)

    sys_py = shutil.which("python")
    sys_pyw = shutil.which("pythonw")
    py_console = sys_py if (sys_py and "windowsapps" not in sys_py.lower()) else str(exe.with_name("python.exe"))
    py_gui = sys_pyw if (sys_pyw and "windowsapps" not in sys_pyw.lower()) else str(exe.with_name("pythonw.exe"))
    if not Path(py_console).exists():
        py_console = str(exe)
    if not Path(py_gui).exists():
        py_gui = py_console
    return py_console, py_gui


def ensure_backend_running() -> bool:
    """Starts FastAPI backend cleanly on port 8001 without opening a console window."""
    if _is_port_open("127.0.0.1", BACKEND_PORT):
        return True

    py_console, py_gui = _resolve_python_executables()
    log_dir = PROJECT_ROOT / "backend" / "data" / "voice_profiles"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "studio_server.log"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0

    with open(log_path, "ab") as log_f:
        subprocess.Popen(
            [py_console, "-m", "uvicorn", "backend.api.main:app", "--port", str(BACKEND_PORT)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=log_f,
            creationflags=flags,
        )

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if _is_port_open("127.0.0.1", BACKEND_PORT):
            return True
        time.sleep(0.2)
    return False


def ensure_gyro_sphere_armed(start_visible: bool = False) -> bool:
    """Ensures the OS-wide Floating Gyro Sphere HUD is running in this Windows session."""
    if os.name == "nt":
        try:
            hwnd = ctypes.windll.user32.FindWindowW("UnleashGyroSphereHUDWindow", "Unleash Gyro Sphere HUD")
            if hwnd:
                if start_visible:
                    ctypes.windll.user32.PostMessageW(hwnd, 0x8001, 0, 0)  # WM_USER_SHOW
                return True
        except Exception:
            pass

    _, py_gui = _resolve_python_executables()
    hud_script = PROJECT_ROOT / "backend" / "scripts" / "jarvis_desktop_hud.py"
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    arg = "--visible" if start_visible else "--hidden"
    subprocess.Popen(
        [py_gui, str(hud_script), arg],
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    return True


def install_desktop_shortcuts() -> dict:
    """Registers Desktop & Start Menu `Unleash Agent` shortcuts using the official Unleash logo."""
    if os.name != "nt":
        return {"status": "error", "error": "Desktop shortcuts only supported on Windows."}

    import win32com.client

    official_ico = PROJECT_ROOT / "frontend" / "assets" / "favicon.ico"
    fallback_ico = PROJECT_ROOT / "backend" / "data" / "voice_profiles" / "unleash_gyro.ico"
    ico_path = official_ico if official_ico.exists() else fallback_ico

    _, py_gui = _resolve_python_executables()
    shell = win32com.client.Dispatch("WScript.Shell")
    created = []
    for folder in (shell.SpecialFolders("Desktop"), shell.SpecialFolders("Programs")):
        lnk_path = Path(folder) / "Unleash Agent.lnk"
        sc = shell.CreateShortcut(str(lnk_path))
        sc.TargetPath = py_gui
        sc.Arguments = f'"{Path(__file__).resolve()}"'
        sc.WorkingDirectory = str(PROJECT_ROOT)
        sc.IconLocation = str(ico_path)
        sc.Description = "Unleash-Agent Studio & Floating Gyro Sphere (Ctrl+Shift+Space)"
        sc.WindowStyle = 7
        sc.Save()
        created.append(str(lnk_path))
    return {"status": "success", "icon": str(ico_path), "shortcuts": created}


def launch_all(open_browser: bool = False, show_sphere: bool = True):
    ensure_gyro_sphere_armed(start_visible=show_sphere)
    ensure_backend_running()
    if open_browser:
        webbrowser.open(BACKEND_URL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Silent desktop launcher for Unleash-Agent & Floating Gyro Sphere")
    parser.add_argument("--browser", action="store_true", help="Also open Unleash Studio in browser")
    parser.add_argument("--hidden", action="store_true", help="Keep Gyro Sphere hidden in hotkey standby on launch")
    parser.add_argument("--install-shortcut", action="store_true", help="Install Desktop and Start Menu Unleash Agent shortcuts")
    args = parser.parse_args()
    if args.install_shortcut:
        print(install_desktop_shortcuts())
    else:
        launch_all(open_browser=args.browser, show_sphere=not args.hidden)
