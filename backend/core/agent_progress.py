"""
Thread-safe in-memory progress tracker for real-time agentic execution.
Powers the live Antigravity progress pills in the UI (scouting, coding, styling, acceptance gate).
"""

import time
from typing import Dict, Any, Optional

_PROJECT_PROGRESS: Dict[str, Dict[str, Any]] = {}

def set_project_progress(
    project_name: str,
    phase: str,
    headline: str,
    detail: str = "",
    step: int = 1,
    file_path: Optional[str] = None
) -> None:
    """Updates the live progress state of an active project workspace."""
    clean = str(project_name).strip()
    existing = _PROJECT_PROGRESS.get(clean, {})
    start_time = existing.get("start_time", time.time())

    _PROJECT_PROGRESS[clean] = {
        "project_name": clean,
        "phase": phase,          # scouting | analyzing | coding | styling | scripting | validating | self_repairing | completed
        "headline": headline,
        "detail": detail,
        "step": step,
        "file": file_path,
        "start_time": start_time,
        "elapsed_sec": round(time.time() - start_time, 1),
        "updated_at": time.time()
    }


def get_project_progress(project_name: str) -> Dict[str, Any]:
    """Retrieves the current progress state of a project workspace."""
    clean = str(project_name).strip()
    data = _PROJECT_PROGRESS.get(clean)
    if not data:
        return {
            "project_name": clean,
            "phase": "idle",
            "headline": "Preparing agent environment...",
            "detail": "Initializing inference session",
            "step": 0,
            "file": None,
            "elapsed_sec": 0.0
        }

    # Update elapsed seconds
    data["elapsed_sec"] = round(time.time() - data.get("start_time", time.time()), 1)
    return data


def clear_project_progress(project_name: str) -> None:
    """Cleans up progress tracking when task finishes."""
    clean = str(project_name).strip()
    if clean in _PROJECT_PROGRESS:
        _PROJECT_PROGRESS[clean]["phase"] = "completed"
        _PROJECT_PROGRESS[clean]["headline"] = "Task completed successfully"
