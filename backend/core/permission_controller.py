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

SENSITIVE_FILES_PATTERN = {
    ".env", ".env.local", ".env.production", "secrets.json", "credentials.json",
    "id_rsa", "id_ed25519", "private_key.pem", ".npmrc", ".pypirc"
}


class LocalPermissionController:
    """
    Antigravity Risk-Tiered Human-in-the-Loop (HITL) Permissions Controller:
    - Request Review: Every command requires approval (Strict).
    - Default (Recommended): Ask before high-risk operations (package install, file deletion,
      Docker-offline host fallback, secret edits). Auto-approve harmless read-only & air-gapped tasks.
    - Auto: Automatically decide if commands run based on risk level and blast radius.
    - Turbo: Run without human prompts (underlying container sandbox still enforces capabilities & air-gap).
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
    def get_project_policy(cls, project_name: str) -> Dict[str, Any]:
        """Retrieves persistent governance policies for a specific project."""
        cfg = cls.load_config()
        policies = cfg.get("project_policies", {})
        clean_proj = str(project_name or "").strip()
        return policies.get(clean_proj, {})

    @classmethod
    def set_project_policy(cls, project_name: str, policy_key: str, value: Any = True) -> Dict[str, Any]:
        """Sets a project-specific governance rule (e.g. require_approval=True)."""
        clean_proj = str(project_name or "default_project").strip()
        with cls._lock:
            cfg = cls.load_config()
            if "project_policies" not in cfg:
                cfg["project_policies"] = {}
            if clean_proj not in cfg["project_policies"]:
                cfg["project_policies"][clean_proj] = {}
            cfg["project_policies"][clean_proj][policy_key] = value
            cls._save_unlocked(cfg)
            cls._config = dict(cfg)
        return {
            "status": "success",
            "project_name": clean_proj,
            "policy_key": policy_key,
            "value": value,
            "all_policies": cfg["project_policies"][clean_proj]
        }

    @classmethod
    def clear_project_policy(cls, project_name: str, policy_key: Optional[str] = None) -> Dict[str, Any]:
        """Clears project-specific governance rules."""
        clean_proj = str(project_name or "default_project").strip()
        with cls._lock:
            cfg = cls.load_config()
            policies = cfg.get("project_policies", {})
            if clean_proj in policies:
                if policy_key:
                    policies[clean_proj].pop(policy_key, None)
                else:
                    policies.pop(clean_proj, None)
                cfg["project_policies"] = policies
                cls._save_unlocked(cfg)
                cls._config = dict(cfg)
        return {"status": "success", "cleared_project": clean_proj, "policy_key": policy_key}

    @classmethod
    def get_mode_display(cls, mode: Optional[str] = None) -> Dict[str, str]:
        m = (mode or cls.get_mode()).lower()
        modes_meta = {
            "review": {
                "id": "review",
                "name": "Request Review",
                "badge": "Strict",
                "description": "Every command requires human approval before execution."
            },
            "default": {
                "id": "default",
                "name": "Default",
                "badge": "Recommended",
                "description": "Ask before sensitive actions (packages, deletions, host fallback). Auto-approves safe code."
            },
            "auto": {
                "id": "auto",
                "name": "Auto",
                "badge": "Intelligent",
                "description": "Automatically decide if commands run based on risk level and blast radius."
            },
            "turbo": {
                "id": "turbo",
                "name": "Turbo",
                "badge": "Full Autonomy",
                "description": "Run without HITL prompts (sandbox container still drops caps & air-gaps code)."
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
        Evaluates a tool execution against the active permission mode and security zones.
        Returns whether human approval is required and details for confirmation.
        """
        existing_files = existing_files or []
        mode = cls.get_mode()

        # 0. Check Project Governance Policies (Overrides even Turbo Mode!)
        proj_policy = cls.get_project_policy(project_name)
        if proj_policy.get("require_approval", False) or proj_policy.get("ask_every_time", False):
            target_desc = str(tool_args.get("command") or tool_args.get("cmd") or tool_args.get("path") or tool_args.get("file_path") or "")[:80]
            return {
                "mode": mode,
                "requires_approval": True,
                "risk_level": "policy_enforced",
                "action_title": f"🛡️ Policy Enforced: {tool_name}",
                "action_desc": f"Project Governance Active: You instructed Jarvis to always request approval before executing actions in project '{project_name}'.",
                "target": target_desc
            }

        # 0.5. Check Pre-Flight Discretion Inspector for Shady/Suspicious Patterns
        try:
            from backend.core.preflight_inspector import inspect_command_safety, inspect_url_safety
            cmd_candidate = tool_args.get("command") or tool_args.get("cmd") or ""
            if cmd_candidate:
                preflight = inspect_command_safety(str(cmd_candidate))
                if preflight.get("is_suspicious"):
                    alt_note = f" (Suggested alternative: '{preflight.get('suggested_alternative')}')" if preflight.get("suggested_alternative") else ""
                    return {
                        "mode": mode,
                        "requires_approval": True,
                        "risk_level": "suspicious_advisory",
                        "action_title": "⚠️ Security Advisory: Suspicious Directive",
                        "action_desc": f"Jarvis Discretion Warning: {preflight.get('reason')}{alt_note}",
                        "target": str(cmd_candidate)[:80],
                        "recommendation": preflight.get("recommendation")
                    }

            url_candidate = tool_args.get("url") or ""
            if url_candidate:
                preflight_url = inspect_url_safety(str(url_candidate))
                if preflight_url.get("is_suspicious"):
                    return {
                        "mode": mode,
                        "requires_approval": True,
                        "risk_level": "suspicious_advisory",
                        "action_title": "⚠️ Security Advisory: Suspicious Network Target",
                        "action_desc": f"Jarvis Discretion Warning: {preflight_url.get('reason')}",
                        "target": str(url_candidate)[:80],
                        "recommendation": preflight_url.get("recommendation")
                    }
        except Exception:
            pass

        # 1. Turbo mode runs all safe commands without human prompts
        # (Downstream container sandbox still drops capabilities and air-gaps code)
        if mode == "turbo":
            return {
                "mode": "turbo",
                "requires_approval": False,
                "risk_level": "low",
                "action_title": f"Execute {tool_name}",
                "action_desc": "Turbo mode: running without human-in-the-loop prompts.",
                "target": ""
            }

        target = ""
        is_sensitive = False
        risk_level = "low"
        action_title = f"Run {tool_name}"
        reason = ""

        # =====================================================================
        # A. TERMINAL / SHELL COMMANDS (Integrated with 3-Zone Sandbox)
        # =====================================================================
        if tool_name in ("run_terminal_command", "terminal_run_command", "run_command", "execute_command", "run_in_sandbox", "bash", "sh"):
            cmd = tool_args.get("command") or tool_args.get("cmd") or ""
            target = cmd[:80]

            from backend.core.container_runner import classify_command_security_zone, SecurityZone, is_docker_running
            zone, zone_reason, meta = classify_command_security_zone(cmd)

            if zone == SecurityZone.BLOCKED:
                is_sensitive = True
                risk_level = "critical"
                action_title = "Blocked System Command"
                reason = f"Security Violation: {zone_reason}"

            elif zone == SecurityZone.LOCAL_SAFE:
                # Harmless offline inspection: py_compile, ast, git status/diff
                # Zero prompt fatigue: auto-approved in default & auto modes
                is_sensitive = False
                risk_level = "low"
                action_title = "Local Verification Check"
                reason = f"Safe offline developer inspection: '{cmd[:60]}' (Zone 1: Local Safe)."

            elif zone == SecurityZone.CONTROLLED_EGRESS:
                # Package managers: pip install, npm install, yarn add, cargo add
                pkg_mgr = meta.get("package_manager", "package manager")
                is_sensitive = True
                risk_level = "high"
                action_title = f"Install Dependency ({pkg_mgr.upper()})"
                
                # Perform live pre-flight package verification & typosquat check
                try:
                    from backend.core.package_verifier import audit_command_packages
                    audits = audit_command_packages(cmd)
                    badges = [a.get("badge") for a in audits if a.get("badge")]
                    warnings = [a.get("typo_warning") for a in audits if a.get("typo_warning")]

                    if warnings:
                        risk_level = "critical"
                        action_title = "⚠️ High-Risk Dependency Alert"
                        reason = f"Security Warning: {'; '.join(warnings)}. (Command: '{cmd}')"
                    elif any(a.get("is_new") for a in audits):
                        risk_level = "high"
                        action_title = "⚠️ Zero-Day / New Package"
                        reason = f"New Package Alert: Released <30 days ago. Requires human approval. (Command: '{cmd}')"
                    else:
                        badge_str = f" [{', '.join(badges)}]" if badges else ""
                        reason = (
                            f"Agent requests to install external dependency: '{cmd}'{badge_str}. "
                            "Requires human approval before downloading packages into the hardened container."
                        )
                except Exception:
                    reason = (
                        f"Agent requests to install external dependency: '{cmd}'. "
                        "Requires human approval before downloading packages into the hardened container."
                    )

            elif zone == SecurityZone.QUARANTINE_AIRGAP:
                docker_on = is_docker_running()
                if docker_on:
                    # In Docker, it's strictly air-gapped (--network none, cap-drop=ALL, read-only deps)
                    is_sensitive = False
                    risk_level = "medium"
                    action_title = "Run Air-Gapped Code / Test"
                    reason = f"Air-gapped execution in isolated container (--network none): '{cmd[:60]}'."
                else:
                    # Docker is offline: would execute on host!
                    is_sensitive = True
                    risk_level = "high"
                    action_title = "Run Script on Host (Docker Offline)"
                    reason = (
                        f"Docker is offline. Running script '{cmd[:60]}' directly on host machine "
                        "requires explicit user approval."
                    )

        # =====================================================================
        # B. FILE DELETIONS (High Risk)
        # =====================================================================
        elif tool_name in ("delete_project_file", "unlink_file", "remove_file", "delete_file"):
            target = tool_args.get("file_path") or tool_args.get("path") or ""
            is_sensitive = True
            risk_level = "high"
            action_title = "Delete Workspace File"
            reason = f"Permanently deletes file '{target}' from project workspace."

        # =====================================================================
        # C. FILE WRITING & EDITING
        # =====================================================================
        elif tool_name in ("write_project_file", "edit_project_file", "append_project_file", "write_file", "edit_file", "append_file"):
            target = tool_args.get("file_path") or tool_args.get("path") or ""
            filename_only = Path(target).name.lower()

            # Check for sensitive credentials, keys, and environment files
            if filename_only in SENSITIVE_FILES_PATTERN or any(s in filename_only for s in ("secret", "token", "password", "credential")):
                is_sensitive = True
                risk_level = "high"
                action_title = "Modify Sensitive File"
                reason = f"Modifies sensitive environment/credential file '{target}'."
            else:
                # Normal code files in project workspace: autonomous editing permitted
                is_sensitive = False
                risk_level = "low"
                action_title = f"{'Edit' if 'edit' in tool_name else 'Write'} Code File"
                reason = f"{'Modifies' if target in existing_files else 'Creates'} project file '{target}'."

        # =====================================================================
        # D. JARVIS OS EXECUTIVE ACTIONS (Windows Host Gateway)
        # =====================================================================
        elif tool_name in ("launch_application", "launch_app", "open_app", "start_app"):
            app_n = tool_args.get("app_name") or tool_args.get("name") or "Application"
            target = str(app_n)
            is_sensitive = False
            risk_level = "low"
            action_title = f"Launch {app_n}"
            reason = f"Opens desktop application or protocol handler '{app_n}' on Windows."

        elif tool_name in ("open_browser_url", "open_url", "browse_url", "open_browser", "browse"):
            target = str(tool_args.get("url") or "")
            is_sensitive = False
            risk_level = "low"
            action_title = "Open Web Browser"
            reason = f"Navigates default web browser to '{target}'."

        elif tool_name in ("system_control", "os_control", "sys_control", "hardware_telemetry"):
            act = str(tool_args.get("action") or "telemetry")
            target = act
            is_sensitive = False
            risk_level = "low"
            action_title = f"System Control ({act})"
            reason = f"Performs system telemetry/control action: '{act}'."

        elif tool_name in ("send_desktop_notification", "notify_user", "desktop_notification", "toast_notification", "notify"):
            title = str(tool_args.get("title") or "Notification")
            target = title
            is_sensitive = False
            risk_level = "low"
            action_title = "Desktop Notification"
            reason = f"Displays toast alert: '{title}'."

        elif tool_name in (
            "browser_navigate", "browser_click", "browser_type", "browser_extract",
            "browser_screenshot", "browser_scroll", "browser_search_and_read", "browser_close",
            "web_navigate", "web_click", "web_type", "web_extract", "web_screenshot", "web_scroll"
        ):
            target = str(tool_args.get("url") or tool_args.get("query") or tool_args.get("selector") or "")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Web Pilot ({tool_name})"
            reason = f"Autonomous browser action: '{tool_name}' on target '{target}'."

        elif tool_name in (
            "capture_desktop_screen", "capture_screen", "capture_desktop", "take_desktop_screenshot",
            "list_open_windows", "get_open_windows", "list_windows",
            "focus_window", "activate_window", "switch_to_window",
            "analyze_screen_vision", "screen_vision", "inspect_screen"
        ):
            target = str(tool_args.get("title") or tool_args.get("prompt") or tool_args.get("filename") or "")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Jarvis Vision ({tool_name})"
            reason = f"Perceptual vision and window inspection: '{tool_name}' ({target})."

        elif tool_name in (
            "desktop_click", "mouse_click", "click_desktop",
            "desktop_type", "keyboard_type", "type_desktop",
            "desktop_hotkey", "press_hotkey", "send_hotkey", "keyboard_shortcut",
            "desktop_move", "mouse_move", "move_cursor",
            "desktop_scroll", "scroll_desktop",
            "desktop_cursor_pos", "get_cursor_position", "cursor_position"
        ):
            target = str(tool_args.get("text") or tool_args.get("keys") or f"({tool_args.get('x')}, {tool_args.get('y')})")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Desktop Control ({tool_name})"
            reason = f"Desktop GUI input action: '{tool_name}' ({target})."

        elif tool_name in ("speak_aloud", "speak", "say_aloud", "talk", "set_voice_mode", "switch_voice_mode", "get_voice_mode", "voice_status", "configure_wake_word", "set_wake_word", "update_wake_word"):
            target = str(tool_args.get("text") or tool_args.get("mode") or tool_args.get("wake_words") or "")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Jarvis Voice ({tool_name})"
            reason = f"Speech audio output or voice mode switch: '{tool_name}' ({target})."

        elif tool_name in ("remember_fact", "remember", "memorize_fact", "recall_memory", "recall", "search_memory", "forget_memory", "forget", "multi_hop_query", "find_entity_path", "consolidate_memory"):
            target = str(tool_args.get("content") or tool_args.get("query") or tool_args.get("fact") or "")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Jarvis Cognitive Memory ({tool_name})"
            reason = f"Personal knowledge graph operation: '{tool_name}' ({target})."

        elif tool_name in ("start_background_task", "check_background_tasks", "control_background_task", "set_project_permission_policy", "inspect_preflight_safety"):
            target = str(tool_args.get("title") or tool_args.get("task_id") or tool_args.get("target") or "")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Autonomous Executive ({tool_name})"
            reason = f"Background daemon worker or governance management: '{tool_name}' ({target})."

        elif tool_name in ("send_email", "bulk_send_emails", "send_whatsapp_message"):
            target = str(tool_args.get("to") or tool_args.get("recipient") or "")[:80]
            is_sensitive = True
            risk_level = "high"
            action_title = "External Message / Email Dispatch"
            reason = f"Sends external communication ({tool_name}) to '{target}'. Dry-run confirmation required."

        elif tool_name in ("configure_email_credentials", "configure_email_vault", "store_secret"):
            target = str(tool_args.get("email_address") or tool_args.get("service_name") or "vault")[:80]
            is_sensitive = True
            risk_level = "medium"
            action_title = "Modify Encrypted Credential Vault"
            reason = f"Updates encrypted credentials in vault ({target})."

        elif tool_name in ("read_emails", "check_emails", "fetch_emails", "find_files", "read_document", "read_pdf"):
            target = str(tool_args.get("file_path") or tool_args.get("dir_path") or tool_args.get("folder") or tool_args.get("query") or "")[:80]
            is_sensitive = False
            risk_level = "low"
            action_title = f"Read / Discover ({tool_name})"
            reason = f"Read-only document, folder, or inbox inspection: '{tool_name}' ({target})."

        elif tool_name in ("run_host_cli", "host_cli", "run_host_command", "execute_host_command"):
            cmd = tool_args.get("command") or tool_args.get("cmd") or ""
            target = cmd[:80]
            from backend.core.container_runner import BLOCKED_COMMANDS
            import re
            is_blocked = any(re.search(pat, cmd.lower()) for pat in BLOCKED_COMMANDS)
            if is_blocked:
                is_sensitive = True
                risk_level = "critical"
                action_title = "⚠️ Blocked Host Command"
                reason = f"Host command matches restricted destructive pattern: '{cmd[:60]}'."
            else:
                is_sensitive = True
                risk_level = "high"
                action_title = "Execute Host Command"
                reason = f"Runs command directly on Windows host: '{cmd[:60]}'."

        # =====================================================================
        # E. READ-ONLY INSPECTION TOOLS
        # =====================================================================
        else:
            target = str(tool_args.get("path") or tool_args.get("query") or "")
            is_sensitive = False
            risk_level = "low"
            action_title = f"Query {tool_name}"
            reason = f"Read-only workspace inspection: {tool_name}"

        # =====================================================================
        # EVALUATE HUMAN APPROVAL REQUIREMENT BY MODE
        # =====================================================================
        if mode == "review":
            # Strict mode: every action with side-effects requires human approval
            requires_approval = is_sensitive or (tool_name in ("write_project_file", "edit_project_file", "run_terminal_command"))
        elif mode == "default":
            # Default (Recommended): ask on high-risk operations (package install, deletions, host fallback, secret edits)
            requires_approval = is_sensitive
        elif mode == "auto":
            # Auto mode: only prompt on high/critical risk
            requires_approval = (risk_level in ("high", "critical"))
        else:
            requires_approval = False

        return {
            "mode": mode,
            "requires_approval": requires_approval,
            "risk_level": risk_level,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "action_title": action_title,
            "action_desc": reason,
            "reason": reason,
            "target": target
        }
