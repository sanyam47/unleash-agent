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


@router.post("/hud/launch")
def launch_desktop_hud_endpoint() -> Dict[str, Any]:
    """Launches the floating desktop HUD overlay widget on Windows."""
    import subprocess
    import sys
    from pathlib import Path
    
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "jarvis_desktop_hud.py"
    try:
        # Use pythonw if available or DETACHED_PROCESS + CREATE_NO_WINDOW so no black terminal pops up
        creation_flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            creationflags=creation_flags
        )
        return {"status": "success", "pid": proc.pid, "message": "Desktop HUD launched on your Windows display."}
    except Exception as e:
        return {"status": "error", "error": str(e)}


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
