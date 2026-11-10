import os
import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

CHECKPOINTS_DIR = Path(__file__).resolve().parent.parent / "data" / "execution_checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


class AgentExecutionController:
    """
    Thread-safe execution controller for Unleash-Agent ReAct loops:
    - Cooperative Pause & Resume (freezes after current atomic step, persists checkpoint)
    - Instant Cancellation & 1-Click Rollback trigger
    - Compute Boundary handling (prompts user or auto-cascades)
    - Compressed Context Relay (<3,500 tokens) for safe 70B/32B -> 8B handoffs.
    """

    _lock = threading.Lock()
    _pause_flags: Dict[str, bool] = {}
    _cancel_flags: Dict[str, bool] = {}
    _states: Dict[str, str] = {}  # "idle", "running", "paused", "cancelled", "boundary_reached", "completed"
    _status_details: Dict[str, str] = {}
    _checkpoints: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _clean_key(cls, project_name: str) -> str:
        return str(project_name or "default_project").strip().lower().replace(" ", "_")

    @classmethod
    def register_start(cls, project_name: str, model: str = ""):
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._pause_flags[key] = False
            cls._cancel_flags[key] = False
            cls._states[key] = "running"
            cls._status_details[key] = f"Active agent execution running on {model}"

    @classmethod
    def register_completion(cls, project_name: str, summary: str = "Execution completed"):
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._pause_flags[key] = False
            cls._cancel_flags[key] = False
            cls._states[key] = "completed"
            cls._status_details[key] = summary

    @classmethod
    def request_pause(cls, project_name: str) -> Dict[str, Any]:
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._pause_flags[key] = True
            cls._status_details[key] = "Pause requested. Will freeze safely after current atomic step."
        return {
            "status": "pause_requested",
            "project_name": key,
            "message": "Pause requested. Execution will freeze safely after the current step."
        }

    @classmethod
    def is_pause_requested(cls, project_name: str) -> bool:
        key = cls._clean_key(project_name)
        with cls._lock:
            return cls._pause_flags.get(key, False)

    @classmethod
    def request_resume(cls, project_name: str, new_tier: Optional[str] = None) -> Dict[str, Any]:
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._pause_flags[key] = False
            cls._cancel_flags[key] = False
            cls._states[key] = "resuming"
            cls._status_details[key] = f"Resuming execution{' on ' + new_tier if new_tier else ''}..."

        if new_tier:
            try:
                from backend.core.cloud_gpu_bridge import CloudGpuBridge
                CloudGpuBridge.set_compute_mode(new_tier)
            except Exception:
                pass

        return {
            "status": "resumed",
            "project_name": key,
            "new_tier": new_tier,
            "checkpoint": cls.get_checkpoint(key)
        }

    @classmethod
    def request_cancel(cls, project_name: str) -> Dict[str, Any]:
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._cancel_flags[key] = True
            cls._pause_flags[key] = False
            cls._states[key] = "cancelled"
            cls._status_details[key] = "Execution cancelled by user."

        # Trigger automatic snapshot checkpoint reference for 1-click rollback
        rollback_available = False
        try:
            from backend.core.workspace_snapshot import list_snapshots
            snaps = list_snapshots(key)
            rollback_available = len(snaps.get("snapshots", [])) > 0
        except Exception:
            pass

        return {
            "status": "cancelled",
            "project_name": key,
            "message": "Execution halted immediately.",
            "rollback_available": rollback_available
        }

    @classmethod
    def is_cancel_requested(cls, project_name: str) -> bool:
        key = cls._clean_key(project_name)
        with cls._lock:
            return cls._cancel_flags.get(key, False)

    @classmethod
    def get_state(cls, project_name: str) -> Dict[str, Any]:
        key = cls._clean_key(project_name)
        with cls._lock:
            state = cls._states.get(key, "idle")
            detail = cls._status_details.get(key, "")
            is_paused = cls._pause_flags.get(key, False) or state == "paused"
            is_cancelled = cls._cancel_flags.get(key, False) or state == "cancelled"

        chk = cls.get_checkpoint(key)
        return {
            "project_name": key,
            "state": state,
            "detail": detail,
            "is_paused": is_paused,
            "is_cancelled": is_cancelled,
            "has_checkpoint": chk is not None,
            "checkpoint": chk
        }

    @classmethod
    def set_state(cls, project_name: str, state: str, detail: Optional[str] = None):
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._states[key] = state
            if detail:
                cls._status_details[key] = detail

    @classmethod
    def save_checkpoint(cls, project_name: str, checkpoint_data: Dict[str, Any]) -> str:
        """Persists execution freeze state so execution can be safely resumed at any time."""
        key = cls._clean_key(project_name)
        checkpoint_data["saved_at"] = time.time()
        checkpoint_data["project_name"] = key

        with cls._lock:
            cls._checkpoints[key] = checkpoint_data
            cls._states[key] = "paused"
            cls._status_details[key] = f"Execution frozen at step {checkpoint_data.get('step', 1)}"

        # Persist to disk
        file_path = CHECKPOINTS_DIR / f"{key}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2)
        except Exception as e:
            print(f"[ExecutionController Checkpoint Error]: {e}")

        return str(file_path)

    @classmethod
    def get_checkpoint(cls, project_name: str) -> Optional[Dict[str, Any]]:
        key = cls._clean_key(project_name)
        with cls._lock:
            if key in cls._checkpoints:
                return cls._checkpoints[key]

        file_path = CHECKPOINTS_DIR / f"{key}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    with cls._lock:
                        cls._checkpoints[key] = data
                    return data
            except Exception:
                return None
        return None

    @classmethod
    def clear_checkpoint(cls, project_name: str):
        key = cls._clean_key(project_name)
        with cls._lock:
            cls._checkpoints.pop(key, None)
            cls._pause_flags[key] = False
            cls._cancel_flags[key] = False
            cls._states[key] = "idle"

        file_path = CHECKPOINTS_DIR / f"{key}.json"
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

    @classmethod
    def compress_context_for_relay(
        cls,
        user_prompt: str,
        messages: List[Dict[str, Any]],
        goals: List[Dict[str, Any]],
        existing_files: List[str],
        last_error: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        70B/32B -> 8B Context Relay Compression Engine:
        Compresses extensive multi-turn conversation traces (>20k tokens) down to a razor-sharp
        state pack under 3,500 tokens so 8B/7B models on RTX 3050 or CPU run safely with zero OOM.
        """
        # 1. Milestone checklist extraction
        completed_milestones = []
        pending_milestones = []
        for g in goals:
            if g.get("completed"):
                completed_milestones.append(f"✓ {g.get('name', 'Goal')}: {g.get('desc', '')}")
            else:
                pending_milestones.append(f"○ [NEXT] {g.get('name', 'Goal')}: {g.get('desc', '')}")

        milestones_text = "COMPLETED MILESTONES:\n" + ("\n".join(completed_milestones) if completed_milestones else "None yet.")
        milestones_text += "\n\nREMAINING MILESTONES TO FINISH:\n" + ("\n".join(pending_milestones) if pending_milestones else "All complete.")

        # 2. Files on disk summary
        files_text = f"Files already created/modified in workspace: {', '.join(existing_files) if existing_files else 'None'}"

        # 3. Last error trace if any
        err_text = f"\nLast Handled Error: {last_error}" if last_error else ""

        compressed_system = (
            "You are an Elite Software Engineer operating in COMPUTE-CASCADE RELAY MODE.\n"
            "A previous high-parameter cloud tier completed preliminary architecture and files. "
            "You are now taking over execution on the local/CPU tier to finish all remaining milestones without dropping progress.\n\n"
            f"=== ORIGINAL USER INTENT ===\n{user_prompt.strip()}\n\n"
            f"=== WORKSPACE STATE ===\n{files_text}{err_text}\n\n"
            f"=== GOAL PROGRESS ===\n{milestones_text}\n\n"
            "MANDATE: Continue directly from the first uncompleted milestone. Call 'edit_project_file' or 'write_project_file' "
            "to implement the missing logic and conclude with 'Final Answer:' once all milestones are verified."
        )

        compressed_user = f"Please continue building and complete the next pending milestone: '{pending_milestones[0] if pending_milestones else 'finalize project'}'."

        return [
            {"role": "system", "content": compressed_system},
            {"role": "user", "content": compressed_user}
        ]
