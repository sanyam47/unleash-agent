"""
FastAPI Router for Jarvis Autonomous Background Daemon & Policy Governance.
Provides endpoints for asynchronous background workers and project-level security policies.
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from backend.core.task_daemon import (
    spawn_daemon_task, get_task_status, list_active_tasks,
    list_all_tasks, pause_task, resume_task, cancel_task,
    get_proactive_alerts, get_watchdog_status, configure_watchdog,
    proactive_watchdog_tick
)
from backend.core.desktop_perception import get_ambient_desktop_context
from backend.core.habit_miner import synthesize_user_habits, get_current_habit_summary
from backend.core.permission_controller import LocalPermissionController

router = APIRouter(prefix="/api/daemon", tags=["Autonomous Daemon & Policy"])


def _resolve_hud_python_executable() -> str:
    """Resolves a silent windowless Windows Python executable (`pythonw.exe`) that has voice/GUI deps."""
    import sys
    import shutil
    from pathlib import Path

    exe = Path(sys.executable)
    if os.name == "nt":
        # Prefer global pythonw when current interpreter is a stripped venv lacking speech_recognition/pyaudio
        try:
            __import__("speech_recognition")
            __import__("pyaudio")
            has_voice_deps = True
        except ImportError:
            has_voice_deps = False

        if has_voice_deps:
            candidate_w = exe.with_name("pythonw.exe")
            if candidate_w.exists():
                return str(candidate_w)

        sys_pythonw = shutil.which("pythonw")
        if sys_pythonw and "windowsapps" not in sys_pythonw.lower():
            return sys_pythonw
        candidate_w = exe.with_name("pythonw.exe")
        if candidate_w.exists():
            return str(candidate_w)
    return str(exe)


def _hud_ipc_send(cmd: str) -> Optional[Dict[str, Any]]:
    """Sends a sub-millisecond loopback command to the live Gyro Sphere HUD across Window Stations."""
    import json
    import socket
    port = int(os.getenv("UNLEASH_HUD_IPC_PORT", "48001"))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.08) as sock:
            sock.settimeout(0.12)
            sock.sendall((cmd.strip().upper() + "\n").encode("utf-8"))
            raw = sock.recv(512).decode("utf-8", errors="ignore").strip()
            return json.loads(raw) if raw else {"status": "ok"}
    except Exception:
        return None


@router.get("/hud/state")
def get_hud_state_endpoint() -> Dict[str, Any]:
    """Single lightweight (<1ms) state snapshot for the Floating Gyroscopic Sphere HUD."""
    mic_active = False
    try:
        from backend.core.voice_pilot import load_voice_config
        mic_active = bool(load_voice_config().get("wake_word_enabled", False))
    except Exception:
        pass

    duplex: Dict[str, Any] = {
        "is_listening": False,
        "is_speaking": False,
        "duplex_state": "IDLE",
        "speech_energy": 0.0,
    }
    try:
        from backend.core.wake_word_listener import get_duplex_listener_status
        duplex = get_duplex_listener_status()
    except Exception:
        try:
            from backend.core.voice_pilot import get_duplex_state
            duplex = get_duplex_state()
        except Exception:
            pass

    active_tasks = list_active_tasks()
    top_task = active_tasks[0] if active_tasks else None
    ipc_stat = _hud_ipc_send("STATUS")
    hud_running = bool(ipc_stat and ipc_stat.get("running"))
    if not hud_running and os.name == "nt":
        try:
            import ctypes
            hud_running = bool(ctypes.windll.user32.FindWindowW("UnleashGyroSphereHUDWindow", "Unleash Gyro Sphere HUD"))
        except Exception:
            pass
    return {
        "status": "success",
        "hud_running": hud_running,
        "hud_visible": bool(ipc_stat.get("visible", False)) if ipc_stat else False,
        "mic_active": mic_active,
        "is_listening": bool(duplex.get("is_listening", False)),
        "is_speaking": bool(duplex.get("is_speaking", False)),
        "duplex_state": duplex.get("duplex_state", "IDLE"),
        "speech_energy": float(duplex.get("speech_energy", 0.0) or 0.0),
        "mic_energy": float(duplex.get("mic_energy", 0.0) or 0.0),
        "active_tasks_count": len(active_tasks),
        "top_task_progress": float(top_task.get("progress", 0.0)) if top_task else 0.0,
        "top_task_title": str(top_task.get("title", "")) if top_task else "",
    }


@router.post("/hud/toggle")
def toggle_desktop_hud_endpoint() -> Dict[str, Any]:
    """Toggles visibility of the live Windows Gyro Sphere if running, without duplicating windows."""
    ipc_res = _hud_ipc_send("TOGGLE")
    if ipc_res:
        return {"status": "success", "hud_running": True, "visible": bool(ipc_res.get("visible", False))}
    if os.name == "nt":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW("UnleashGyroSphereHUDWindow", "Unleash Gyro Sphere HUD")
            if hwnd:
                is_vis = bool(user32.IsWindowVisible(hwnd))
                user32.PostMessageW(hwnd, 0x8002 if is_vis else 0x8001, 0, 0)
                return {"status": "success", "hud_running": True, "visible": not is_vis}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return {"status": "success", "hud_running": False, "visible": False}


@router.post("/hud/quit")
def quit_desktop_hud_endpoint() -> Dict[str, Any]:
    """Terminates the running Windows Gyro Sphere HUD process cleanly."""
    ipc_res = _hud_ipc_send("QUIT")
    if ipc_res:
        return {"status": "success", "hud_running": False, "message": "Gyro Sphere process stopped cleanly."}
    if os.name == "nt":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW("UnleashGyroSphereHUDWindow", "Unleash Gyro Sphere HUD")
            if hwnd:
                user32.PostMessageW(hwnd, 0x8003, 0, 0)  # WM_USER_QUIT
                return {"status": "success", "hud_running": False, "message": "Gyro Sphere process stopped."}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return {"status": "success", "hud_running": False, "message": "Gyro Sphere was not running."}


def cleanup_all_runtime_processes() -> None:
    """Stops mic listener, audio, Gyro Sphere HUD, Ollama, and Docker/WSL2 cleanly."""
    import subprocess
    try:
        from backend.core.wake_word_listener import stop_native_wake_word_daemon
        stop_native_wake_word_daemon()
    except Exception:
        pass
    try:
        from backend.core.voice_pilot import stop_speaking
        stop_speaking()
    except Exception:
        pass
    try:
        quit_desktop_hud_endpoint()
    except Exception:
        pass

    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
        docker_was_active = False
        for proc_name in ("ollama.exe", "Docker Desktop.exe", "com.docker.backend.exe", "docker-agent.exe"):
            try:
                res = subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    check=False,
                    timeout=3.0,
                )
                if res.returncode == 0 and "docker" in proc_name.lower():
                    docker_was_active = True
            except Exception:
                pass
        if docker_was_active:
            try:
                subprocess.run(
                    ["wsl", "--shutdown"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    check=False,
                    timeout=5.0,
                )
            except Exception:
                pass


@router.post("/app/shutdown")
def shutdown_unleash_app_endpoint() -> Dict[str, Any]:
    """Cleanly shuts down Gyro Sphere, mic daemon, Ollama, Docker/WSL2, and Unleash backend."""
    import threading
    cleanup_all_runtime_processes()

    def _delayed_exit():
        os._exit(0)

    threading.Timer(0.25, _delayed_exit).start()
    return {"status": "success", "message": "Unleash Agent, Sphere, Ollama, and Docker shut down cleanly."}


@router.post("/hud/launch")
def launch_desktop_hud_endpoint() -> Dict[str, Any]:
    """Launches the floating Gyroscopic Sphere HUD overlay widget on Windows."""
    import subprocess
    from pathlib import Path

    if _hud_ipc_send("SHOW"):
        return {"status": "success", "hud_running": True, "message": "Existing Gyro Sphere surfaced on Windows display."}

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "jarvis_desktop_hud.py"
    try:
        creation_flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
        hud_python = _resolve_hud_python_executable()
        proc = subprocess.Popen(
            [hud_python, str(script_path), "--visible"],
            creationflags=creation_flags,
        )
        return {"status": "success", "pid": proc.pid, "message": "Floating Gyroscopic Sphere launched on Windows display."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class HudStartupRequest(BaseModel):
    enabled: bool = Field(..., description="Whether to register the Floating Gyro Sphere in Windows Startup")


def _get_hud_startup_shortcut_path() -> "Path":
    from pathlib import Path
    appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "UnleashGyroSphere.lnk"


def _set_hud_startup_enabled(enabled: bool, spawn_if_missing: bool = True) -> Dict[str, Any]:
    from pathlib import Path
    shortcut_path = _get_hud_startup_shortcut_path()
    project_root = Path(__file__).resolve().parent.parent.parent
    script_path = project_root / "backend" / "scripts" / "jarvis_desktop_hud.py"

    if enabled:
        if os.name != "nt":
            return {"status": "error", "enabled": False, "error": "Windows Startup shortcuts are only supported on Windows."}
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        hud_python = _resolve_hud_python_executable()
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = hud_python
        shortcut.Arguments = f'"{script_path}" --hidden'
        shortcut.WorkingDirectory = str(project_root)
        shortcut.Description = "Unleash-Agent Floating Gyro Sphere (Ctrl+Shift+Space)"
        shortcut.WindowStyle = 7  # Minimized/hidden
        shortcut.Save()

        if spawn_if_missing:
            try:
                import ctypes
                import subprocess
                hwnd = ctypes.windll.user32.FindWindowW("UnleashGyroSphereHUDWindow", "Unleash Gyro Sphere HUD")
                if not hwnd:
                    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                    subprocess.Popen([hud_python, str(script_path), "--hidden"], creationflags=flags)
            except Exception:
                pass
        return {
            "status": "success",
            "enabled": True,
            "shortcut_path": str(shortcut_path),
            "message": "Gyro Sphere armed for Windows Startup (Ctrl+Shift+Space ready).",
        }
    else:
        if shortcut_path.exists():
            shortcut_path.unlink()
        return {
            "status": "success",
            "enabled": False,
            "shortcut_path": str(shortcut_path),
            "message": "Removed Gyro Sphere from Windows Startup.",
        }


@router.get("/hud/startup")
def get_hud_startup_endpoint() -> Dict[str, Any]:
    """Checks whether the Floating Gyro Sphere is registered to start on Windows login."""
    shortcut_path = _get_hud_startup_shortcut_path()
    return {
        "status": "success",
        "enabled": shortcut_path.exists(),
        "shortcut_path": str(shortcut_path),
    }


@router.post("/hud/startup")
def set_hud_startup_endpoint(req: HudStartupRequest) -> Dict[str, Any]:
    """Enables or disables Windows Startup auto-arm for the Floating Gyro Sphere."""
    try:
        return _set_hud_startup_enabled(req.enabled)
    except Exception as e:
        return {"status": "error", "enabled": False, "error": str(e)}


@router.post("/wakeword/start")
def start_wakeword_listener_endpoint() -> Dict[str, Any]:
    """Starts the native OS-level background wake-word engine across Windows."""
    try:
        from backend.core.wake_word_listener import start_native_wake_word_daemon
        start_native_wake_word_daemon(in_background=True)
        return {"status": "success", "message": "Native OS Wake-Word daemon started. Listening for 'Hey Jarvis'..."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/wakeword/stop")
def stop_wakeword_listener_endpoint() -> Dict[str, Any]:
    """Stops the native OS-level background wake-word engine."""
    try:
        from backend.core.wake_word_listener import stop_native_wake_word_daemon
        stop_native_wake_word_daemon()
        return {"status": "success", "message": "Native OS Wake-Word daemon stopped."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/habits")
def get_user_habits_endpoint() -> Dict[str, Any]:
    """Returns mined user behavior habits and profile summary."""
    return synthesize_user_habits()


@router.get("/perception")
def get_desktop_perception_endpoint() -> Dict[str, Any]:
    """Returns ambient perception of the user's active desktop, dev stack, and top applications."""
    return get_ambient_desktop_context()


@router.get("/alerts")
def get_proactive_alerts_endpoint(limit: int = 10) -> Dict[str, Any]:
    """Returns recent proactive alerts issued autonomously by the watchdog."""
    alerts = get_proactive_alerts(limit=limit)
    return {"status": "success", "count": len(alerts), "alerts": alerts}


@router.get("/watchdog/status")
def get_watchdog_status_endpoint() -> Dict[str, Any]:
    """Returns real-time status of the proactive ambient watchdog daemon."""
    return get_watchdog_status()


@router.post("/watchdog/configure")
def configure_watchdog_endpoint(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates watchdog monitoring thresholds (RAM %, GPU temp, battery, interval)."""
    return configure_watchdog(updates)


@router.post("/watchdog/tick")
def trigger_watchdog_tick_endpoint() -> Dict[str, Any]:
    """Manually triggers an immediate proactive watchdog tick evaluation."""
    return proactive_watchdog_tick()


class SpawnTaskRequest(BaseModel):
    title: str = Field(..., description="Title or goal of the background task")
    description: Optional[str] = Field(default="", description="Detailed instructions")
    steps: Optional[List[str]] = Field(default=None, description="Optional custom step plan")
    project_name: Optional[str] = Field(default="default_project", description="Target workspace project")


class PolicyRequest(BaseModel):
    project_name: str = Field(..., description="Project name")
    policy_key: str = Field(default="require_approval", description="Policy rule key (e.g. require_approval, ask_every_time)")
    value: bool = Field(default=True, description="Boolean flag")


@router.get("/tasks")
def get_tasks_endpoint(limit: int = 25) -> Dict[str, Any]:
    """Lists all recent background daemon tasks."""
    return {"status": "success", "tasks": list_all_tasks(limit=limit)}


@router.get("/tasks/active")
def get_active_tasks_endpoint() -> Dict[str, Any]:
    """Lists currently queued, running, or paused daemon tasks."""
    actives = list_active_tasks()
    return {"status": "success", "count": len(actives), "tasks": actives}


@router.post("/tasks")
def spawn_task_endpoint(req: SpawnTaskRequest) -> Dict[str, Any]:
    """Spawns an asynchronous background daemon worker."""
    res = spawn_daemon_task(
        title=req.title,
        description=req.description or req.title,
        steps=req.steps,
        project_name=req.project_name or "default_project"
    )
    return res


@router.get("/tasks/{task_id}")
def get_task_status_endpoint(task_id: str) -> Dict[str, Any]:
    """Gets real-time telemetry and logs for a specific daemon task."""
    status = get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Daemon task '{task_id}' not found.")
    return {"status": "success", "task": status}


@router.post("/tasks/{task_id}/pause")
def pause_task_endpoint(task_id: str) -> Dict[str, Any]:
    """Pauses an ongoing daemon task."""
    return pause_task(task_id)


@router.post("/tasks/{task_id}/resume")
def resume_task_endpoint(task_id: str) -> Dict[str, Any]:
    """Resumes a paused daemon task."""
    return resume_task(task_id)


@router.post("/tasks/{task_id}/cancel")
def cancel_task_endpoint(task_id: str) -> Dict[str, Any]:
    """Cancels a daemon task."""
    return cancel_task(task_id)


@router.post("/tasks/cancel_all")
def cancel_all_tasks_endpoint() -> Dict[str, Any]:
    """Cancels all active daemon tasks."""
    actives = list_active_tasks()
    for t in actives:
        cancel_task(t["task_id"])
    return {"status": "success", "cancelled_count": len(actives)}


@router.get("/policy/{project_name}")
def get_policy_endpoint(project_name: str) -> Dict[str, Any]:
    """Gets project-specific governance policies."""
    policies = LocalPermissionController.get_project_policy(project_name)
    return {"status": "success", "project_name": project_name, "policies": policies}


@router.post("/policy")
def set_policy_endpoint(req: PolicyRequest) -> Dict[str, Any]:
    """Sets a project-specific governance policy rule."""
    res = LocalPermissionController.set_project_policy(req.project_name, req.policy_key, req.value)
    return res


@router.delete("/policy/{project_name}")
def clear_policy_endpoint(project_name: str, policy_key: Optional[str] = None) -> Dict[str, Any]:
    """Clears project-specific governance policies."""
    res = LocalPermissionController.clear_project_policy(project_name, policy_key)
    return res
