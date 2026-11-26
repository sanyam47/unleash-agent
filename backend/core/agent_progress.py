"""
Thread-safe in-memory progress tracker for real-time agentic execution.
Powers the live Antigravity progress pills in the UI (scouting, coding, styling, acceptance gate).
"""

import time
from typing import Dict, Any, Optional, List

_PROJECT_PROGRESS: Dict[str, Dict[str, Any]] = {}


def _append_event(
    existing: Dict[str, Any],
    phase: str,
    headline: str,
    detail: str = "",
    step: int = 1,
    file_path: Optional[str] = None,
    tool: Optional[str] = None,
) -> tuple[int, List[Dict[str, Any]]]:
    """Appends a live progress event to the project's bounded ring buffer."""
    seq = int(existing.get("seq", 0)) + 1
    events: List[Dict[str, Any]] = list(existing.get("events", []))
    start_time = existing.get("start_time", time.time())
    entry = {
        "seq": seq,
        "ts": round(time.time() - start_time, 1),
        "step": step,
        "phase": phase,
        "headline": str(headline)[:140],
        "detail": str(detail or "")[:180],
        "file": file_path,
        "tool": tool,
    }
    events.append(entry)
    if len(events) > 40:
        events = events[-40:]
    return seq, events


def reset_project_progress(project_name: str) -> None:
    """Clears stale progress & event history before a new agent turn starts."""
    clean = str(project_name).strip()
    _PROJECT_PROGRESS.pop(clean, None)


def set_project_plan(project_name: str, steps: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Stores the agent's live dynamic checklist steps for UI streaming."""
    clean = str(project_name).strip()
    existing = _PROJECT_PROGRESS.get(clean, {})
    start_time = existing.get("start_time", time.time())

    normalized: List[Dict[str, str]] = []
    valid_statuses = {"pending", "in_progress", "done", "skipped", "failed"}
    for idx, st in enumerate(steps[:12]):
        if isinstance(st, dict):
            title = str(st.get("title") or st.get("step") or f"Step {idx + 1}").strip()[:80]
            status = str(st.get("status") or "pending").strip().lower()
            if status not in valid_statuses:
                status = "pending"
            normalized.append({"title": title, "status": status})
        elif isinstance(st, str) and st.strip():
            normalized.append({"title": st.strip()[:80], "status": "pending"})

    active_titles = [s["title"] for s in normalized if s["status"] == "in_progress"]
    done_cnt = sum(1 for s in normalized if s["status"] == "done")
    headline = existing.get("headline", "Executing plan...")
    if active_titles:
        headline = f"[{done_cnt}/{len(normalized)}] {active_titles[0]}"

    seq, events = _append_event(
        existing,
        phase=existing.get("phase", "planning"),
        headline=headline,
        detail=f"Plan updated ({done_cnt}/{len(normalized)} done)",
        step=existing.get("step", 1),
        file_path=existing.get("file"),
        tool="update_plan",
    )

    existing.update({
        "project_name": clean,
        "phase": existing.get("phase", "planning"),
        "headline": headline,
        "detail": existing.get("detail", ""),
        "step": existing.get("step", 1),
        "file": existing.get("file"),
        "plan_steps": normalized,
        "seq": seq,
        "events": events,
        "start_time": start_time,
        "elapsed_sec": round(time.time() - start_time, 1),
        "updated_at": time.time(),
    })
    _PROJECT_PROGRESS[clean] = existing
    return normalized


def set_project_progress(
    project_name: str,
    phase: str,
    headline: str,
    detail: str = "",
    step: int = 1,
    file_path: Optional[str] = None,
    tool: Optional[str] = None,
) -> None:
    """Updates the live progress state of an active project workspace."""
    clean = str(project_name).strip()
    existing = _PROJECT_PROGRESS.get(clean, {})
    start_time = existing.get("start_time", time.time())
    if "start_time" not in existing:
        existing["start_time"] = start_time

    seq, events = _append_event(
        existing,
        phase=phase,
        headline=headline,
        detail=detail,
        step=step,
        file_path=file_path,
        tool=tool,
    )

    _PROJECT_PROGRESS[clean] = {
        "project_name": clean,
        "phase": phase,          # scouting | planning | analyzing | coding | styling | scripting | validating | self_repairing | completed
        "headline": headline,
        "detail": detail,
        "step": step,
        "file": file_path,
        "tool": tool,
        "plan_steps": existing.get("plan_steps", []),
        "seq": seq,
        "events": events,
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
            "plan_steps": [],
            "seq": 0,
            "events": [],
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
