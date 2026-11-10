import json
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "local_permissions_config.json"

DEFAULT_CONFIG = {
    "mode": "default",  # "review", "default", "auto", "turbo"
    "auto_approve_readonly": True,
    "last_updated": 0
}

class LocalPermissionController:
    """
    Antigravity-Style Local Permissions Controller:
    - Request Review: Every command requires approval.
    - Default (Recommended): Ask before sensitive operations (overwrites, deletions, terminal shell).
    - Auto: Automatically decide if commands run based on AST and blast radius.
    - Turbo: Run all commands without restrictions.
    """
    CONFIG_FILE = CONFIG_FILE
    _lock = threading.RLock()
    _config: Optional[Dict[str, Any]] = None

    @classmethod
    def load_config(cls, force_reload: bool = False) -> Dict[str, Any]:
        with cls._lock:
            if cls._config is not None and not force_reload:
                return cls._config

            if not CONFIG_FILE.exists():
                cls._save_unlocked(DEFAULT_CONFIG)
                cls._config = dict(DEFAULT_CONFIG)
                return cls._config

            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cls._config = {**DEFAULT_CONFIG, **data}
                    return cls._config
            except Exception:
                cls._config = dict(DEFAULT_CONFIG)
                return cls._config

    @classmethod
    def _save_unlocked(cls, data: Dict[str, Any]):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[LocalPermissionController Save Error]: {e}")

    @classmethod
    def get_mode(cls, force_reload: bool = False) -> str:
        cfg = cls.load_config(force_reload=force_reload)
        return cfg.get("mode", "default")

    @classmethod
    def set_mode(cls, mode: str) -> Dict[str, Any]:
        clean_mode = str(mode or "").strip().lower()
        if clean_mode not in ("review", "default", "auto", "turbo"):
            raise ValueError(f"Unknown permission mode '{mode}'. Choose 'review', 'default', 'auto', or 'turbo'.")

        with cls._lock:
            cfg = cls.load_config()
            cfg["mode"] = clean_mode
            cls._save_unlocked(cfg)
            cls._config = dict(cfg)

        return {
            "status": "success",
            "mode": clean_mode,
            "mode_display": cls.get_mode_display(clean_mode)
        }

    @classmethod
    def get_mode_display(cls, mode: Optional[str] = None) -> Dict[str, str]:
        m = (mode or cls.get_mode()).lower()
        modes_meta = {
            "review": {
                "id": "review",
                "name": "Request Review",
                "badge": "Strict",
                "description": "Every command requires approval."
            },
            "default": {
                "id": "default",
                "name": "Default",
                "badge": "Recommended",
                "description": "Ask before sensitive operations."
            },
            "auto": {
                "id": "auto",
                "name": "Auto",
                "badge": "Intelligent",
                "description": "Automatically decide if commands run."
            },
            "turbo": {
                "id": "turbo",
                "name": "Turbo",
                "badge": "Full Autonomy",
                "description": "Run all commands without restrictions."
            }
        }
        return modes_meta.get(m, modes_meta["default"])

    @classmethod
    def evaluate_action(
        cls,
        project_name: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        existing_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a tool execution against the active permission mode.
        Returns whether approval is required and details for human confirmation.
        """
        existing_files = existing_files or []
        mode = cls.get_mode()

        # 1. Turbo mode runs all commands without restrictions
        if mode == "turbo":
            return {
                "mode": "turbo",
                "requires_approval": False,
                "risk_level": "low",
                "action_title": f"Execute {tool_name}",
                "action_desc": "Turbo mode: running without restrictions.",
                "target": ""
            }

        # Determine target and sensitivity
        target = ""
        is_sensitive = False
        risk_level = "low"
        reason = ""

        # Analyze tool type
        if tool_name in ("write_project_file", "edit_project_file", "append_project_file", "write_file", "edit_file", "append_file"):
            target = tool_args.get("file_path") or tool_args.get("path") or ""
            # If target already exists on disk, it's an overwrite/edit of existing work
            is_overwrite = target in existing_files
            if is_overwrite or tool_name in ("edit_project_file", "edit_file"):
                is_sensitive = True
                risk_level = "medium"
                reason = f"Modifies existing workspace file '{target}'."
            else:
                # Creating brand new file in project
                risk_level = "low"
                reason = f"Creates new workspace file '{target}'."

        elif tool_name in ("run_terminal_command", "terminal_run_command", "run_command", "execute_command", "run_in_sandbox", "bash", "sh"):
            cmd = tool_args.get("command") or tool_args.get("cmd") or ""
            target = cmd[:60]
            is_sensitive = True
            # Check for destructive commands and PowerShell cmdlets
            destructive_patterns = [
                "rm ", "rmdir", "del ", "erase", "format ", "git reset", "git clean", 
                "drop ", "sudo ", "remove-item", "clear-content", "rd /", "deltree"
            ]
            cmd_lower = cmd.lower()
            if any(pat in cmd_lower for pat in destructive_patterns):
                risk_level = "high"
                reason = f"High-risk command execution: '{cmd[:50]}...'"
            else:
                risk_level = "medium"
                reason = f"Executes terminal command: '{cmd[:50]}...'"

        elif tool_name in ("delete_project_file", "unlink_file", "remove_file", "delete_file"):
            target = tool_args.get("file_path") or tool_args.get("path") or ""
            is_sensitive = True
            risk_level = "high"
            reason = f"Deletes file '{target}' from workspace."

        else:
            # Pure read/inspection tools (read_project_file, search_docs, list_files)
            target = str(tool_args.get("path") or tool_args.get("query") or "")
            is_sensitive = False
            risk_level = "low"
            reason = f"Read-only operation: {tool_name}"

        # 2. Evaluate based on Mode
        if mode == "review":
            # Strict mode: every action with side-effects requires approval
            requires_approval = is_sensitive or (tool_name in ("write_project_file", "edit_project_file"))
        elif mode == "default":
            # Default mode: ask before sensitive operations (overwriting existing files, shell commands, deletions)
            requires_approval = is_sensitive
        elif mode == "auto":
            # Auto mode: only prompt on high-risk operations (destructive commands or deletions)
            requires_approval = (risk_level == "high")
        else:
            requires_approval = False

        return {
            "mode": mode,
            "requires_approval": requires_approval,
            "risk_level": risk_level,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "action_title": f"{'Modify' if 'edit' in tool_name or is_sensitive else 'Run'} {tool_name}",
            "action_desc": reason,
            "reason": reason,
            "target": target
        }
