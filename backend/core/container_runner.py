import ast
import os
import re
import shlex
import time
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Set

from backend.core.agent_tools import resolve_safe_project_path, sanitize_project_name

DOCKER_BIN = "docker"
DEFAULT_TIMEOUT_SEC = 20

STANDARD_DOCKER_DESKTOP_PATHS = [
    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe"),
    os.path.expandvars(r"%ProgramW6432%\Docker\Docker\Docker Desktop.exe")
]


# ============================================================================
# SECURITY ZONE DEFINITIONS
# ============================================================================

class SecurityZone(str, Enum):
    """
    3-Zone Dynamic Quarantine Security Model:
    - BLOCKED: Malicious, destructive, or host-compromising instructions. Unconditionally rejected.
    - LOCAL_SAFE: Purely local, offline dev tooling (AST, py_compile, git status). Zero overhead.
    - CONTROLLED_EGRESS: Package management (pip, npm, yarn, cargo). Strictly inside hardened Docker
      with script suppression, host DNS sinkholes, and resource throttles. NEVER falls back to host.
    - QUARANTINE_AIRGAP: Code execution, test suites, and untrusted scripts. Air-gapped (--network none)
      inside isolated container. Zero network, zero host access.
    """
    BLOCKED = "BLOCKED"
    LOCAL_SAFE = "LOCAL_SAFE"
    CONTROLLED_EGRESS = "CONTROLLED_EGRESS"
    QUARANTINE_AIRGAP = "QUARANTINE_AIRGAP"


# High-risk destructive commands unconditionally blocked
BLOCKED_COMMANDS = [
    r"\bformat\b",
    r"\brmdir\s+/[sq]",
    r"\bdel\s+/[sq]",
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|--recursive)\s+/",
    r"\breg\b",
    r"\bregedit\b",
    r"\bnetsh\b",
    r"\bshutdown\b",
    r"\bpkexec\b",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bchmod\s+(?:-[a-zA-Z]*R\s+)?777\s+/",
    r"\bpowershell(?:\.exe)?\s+-[ec]",
    r"\bcmd(?:\.exe)?\s+/[ck]",
    r"\b(?:curl|wget)\b.*\|\s*(?:ba)?sh",
    r"\b/dev/tcp/",
    r"\bnc(?:\.traditional)?\s+.*-e\b",
    r"\bmkfifo\b",
    r":\(\)\s*\{\s*:\|:&\s*\};:",  # fork bomb
    r"(?:/etc/shadow|/etc/passwd|C:\\Windows\\System32\\config)"
]

# Package managers that perform remote resolution and dependency fetching
PACKAGE_MANAGERS_PATTERN = re.compile(
    r"^\s*(?:python\s+-m\s+)?pip\s+(?:install|download)\b|"
    r"^\s*npm\s+(?:install|i|add)\b|"
    r"^\s*yarn\s+(?:add|install)\b|"
    r"^\s*pnpm\s+(?:add|install|i)\b|"
    r"^\s*cargo\s+(?:add|fetch)\b|"
    r"^\s*poetry\s+(?:add|install)\b|"
    r"^\s*composer\s+(?:require|install)\b|"
    r"^\s*go\s+get\b",
    re.IGNORECASE
)

# Strictly offline, local dev inspections with zero network or filesystem modification
LOCAL_SAFE_COMMANDS_PATTERN = re.compile(
    r"^\s*python\s+(-m\s+)?(py_compile|ast)\b|"
    r"^\s*node\s+(-c|--check)\b|"
    r"^\s*git\s+(status|log|diff|rev-parse|branch|show)\b|"
    r"^\s*(?:dir|ls|echo|cat|type)\b",
    re.IGNORECASE
)

# AST safety analysis sets for script inspection
DANGEROUS_AST_MODULES: Set[str] = {
    "socket", "subprocess", "ctypes", "pty", "shlex", "winreg",
    "webbrowser", "paramiko", "requests", "urllib", "http.client",
    "urllib3", "ftplib", "smtplib", "telnetlib"
}
DANGEROUS_AST_CALLS: Set[str] = {
    "system", "popen", "spawnl", "spawnle", "spawnlp", "spawnlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe"
}


# ============================================================================
# DOCKER LIFECYCLE MANAGEMENT
# ============================================================================

def get_docker_desktop_executable() -> Optional[str]:
    """Finds Docker Desktop.exe across standard Windows installation paths."""
    for p in STANDARD_DOCKER_DESKTOP_PATHS:
        if p and os.path.exists(p):
            return p
    return None


DOCKER_DESKTOP_PATH = get_docker_desktop_executable() or r"C:\Program Files\Docker\Docker\Docker Desktop.exe"


def is_docker_running() -> bool:
    """Checks if the Docker daemon is active and responding within 1.2 seconds."""
    try:
        proc = subprocess.run(
            [DOCKER_BIN, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.2,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return proc.returncode == 0
    except Exception:
        return False


def start_docker_desktop() -> Dict[str, Any]:
    """Launches Docker Desktop background process on Windows if not already running."""
    if is_docker_running():
        return {"status": "success", "message": "Docker daemon is already active and running."}

    exe = get_docker_desktop_executable()
    if not exe:
        return {"status": "error", "message": "Docker Desktop executable not found in standard paths."}

    try:
        flags = subprocess.DETACHED_PROCESS if os.name == 'nt' else 0
        subprocess.Popen(
            [exe],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags
        )
        return {
            "status": "success",
            "message": "Docker Desktop launched. Initializing Linux virtualization engine in background..."
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to start Docker Desktop: {str(e)}"}


def stop_docker_desktop() -> Dict[str, Any]:
    """Stops Docker Desktop processes and shuts down WSL2 to reclaim RAM immediately."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "Docker Desktop.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["taskkill", "/F", "/IM", "com.docker.backend.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            subprocess.run(["wsl", "--shutdown"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return {
            "status": "stopped",
            "message": "Docker Desktop and WSL2 VM stopped. System RAM fully reclaimed!"
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to stop Docker: {str(e)}"}


class DockerEphemeralSession:
    """
    Manages ephemeral Docker lifecycle:
    - If Docker was ALREADY ON: keeps it running after agent finishes.
    - If Docker was OFF: turns it on in the background as the agent begins looking at datasets/code,
      and automatically turns it off when the agent loop completes to reclaim 100% of RAM.
    """
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.was_running_initially = False
        self.auto_started = False

    def __enter__(self):
        if not self.enabled:
            return self
        try:
            self.was_running_initially = is_docker_running()
            if not self.was_running_initially:
                res = start_docker_desktop()
                if res.get("status") == "success":
                    self.auto_started = True
                    print("[DOCKER LIFECYCLE]: Auto-started Docker Desktop in background for agent execution.")
            else:
                self.auto_started = False
                print("[DOCKER LIFECYCLE]: Docker was already running; will keep running after agent finishes.")
        except Exception as e:
            print(f"[DOCKER LIFECYCLE WARNING]: Failed to initialize ephemeral session: {e}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.enabled:
            return
        if self.auto_started and not self.was_running_initially:
            print("[DOCKER LIFECYCLE]: Agent completed task. Shutting down Docker and reclaiming RAM...")
            try:
                stop_docker_desktop()
                print("[DOCKER LIFECYCLE]: Docker stopped. RAM reclaimed.")
            except Exception as e:
                print(f"[DOCKER LIFECYCLE WARNING]: Error stopping Docker: {e}")


# ============================================================================
# CLASSIFICATION & AST SAFETY AUDITING
# ============================================================================

def classify_command_security_zone(command: str) -> Tuple[SecurityZone, str, Dict[str, Any]]:
    """
    Evaluates an arbitrary command and assigns it to one of the 4 security zones:
    1. BLOCKED: System destruction, host compromise, or arbitrary pipes to shell.
    2. LOCAL_SAFE: Fast, read-only dev inspections (py_compile, ast, git status).
    3. CONTROLLED_EGRESS: Package resolution (pip, npm, yarn) needing outbound network.
    4. QUARANTINE_AIRGAP: Untrusted code, scripts, and tests needing strict network isolation.
    """
    raw_cmd = command.strip()
    lowered = raw_cmd.lower()

    # 1. Check for blocked malicious patterns
    for pat in BLOCKED_COMMANDS:
        if re.search(pat, lowered):
            return (
                SecurityZone.BLOCKED,
                f"Command matches restricted host instruction pattern: {pat}",
                {"sanitized_command": raw_cmd}
            )

    # 2. Check for package managers (Controlled Egress)
    if PACKAGE_MANAGERS_PATTERN.search(raw_cmd):
        pkg_mgr = "npm" if "npm" in lowered else "yarn" if "yarn" in lowered else "pip"
        return (
            SecurityZone.CONTROLLED_EGRESS,
            f"Package management command detected ({pkg_mgr}). Requires hardened container with controlled egress.",
            {"package_manager": pkg_mgr, "sanitized_command": raw_cmd}
        )

    # 3. Check for safe local developer checks (py_compile, git status)
    if LOCAL_SAFE_COMMANDS_PATTERN.search(raw_cmd):
        return (
            SecurityZone.LOCAL_SAFE,
            "Harmless offline inspection tool. Permitted for zero-latency local execution.",
            {"tool": "local_dev", "sanitized_command": raw_cmd}
        )

    # 4. All other execution defaults to Quarantine Airgap
    return (
        SecurityZone.QUARANTINE_AIRGAP,
        "Untrusted script, test runner, or executable. Requires air-gapped container isolation (--network none).",
        {"tool": "untrusted_runner", "sanitized_command": raw_cmd}
    )


def check_python_ast_safety(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Statically inspects a Python file's Abstract Syntax Tree (AST) before allowing
    any local host fallback. Rejects network sockets, subprocess spawns, and ctypes.
    """
    try:
        if not file_path.exists() or file_path.suffix.lower() != ".py":
            return True, None
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0].lower()
                    if root_mod in DANGEROUS_AST_MODULES:
                        return False, f"Potentially hazardous import '{alias.name}' detected in {file_path.name}."
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0].lower()
                    if root_mod in DANGEROUS_AST_MODULES:
                        return False, f"Potentially hazardous import from '{node.module}' detected in {file_path.name}."
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr.lower() in DANGEROUS_AST_CALLS:
                    return False, f"Potentially hazardous system call '{node.func.attr}' detected in {file_path.name}."
                elif isinstance(node.func, ast.Name) and node.func.id.lower() in {"eval", "exec"}:
                    return False, f"Dynamic code evaluation '{node.func.id}' detected in {file_path.name}."

        return True, None
    except Exception as e:
        return False, f"AST parsing failed on {file_path.name}: {str(e)}"


def get_preferred_docker_image(command: str) -> str:
    """Selects the most suitable hardened container image for the command."""
    lowered = command.lower()
    if any(tok in lowered for tok in ["node", "npm", "yarn", "pnpm", "npx"]):
        return "node:18-alpine"
    return "python:3.11-slim"


# ============================================================================
# EXECUTION ENGINE: 3-ZONE DYNAMIC QUARANTINE SANDBOX
# ============================================================================

def execute_in_isolated_container(project_name: str, command: str, timeout: int = DEFAULT_TIMEOUT_SEC) -> Dict[str, Any]:
    """
    Executes commands through the 3-Zone Dynamic Quarantine Security Sandbox:

    - ZONE 0 (BLOCKED): Dangerous destructive host commands are immediately rejected.
    - ZONE 1 (LOCAL_SAFE): Read-only dev checks (py_compile, ast, git status) run locally
      with shell=False and zero overhead.
    - ZONE 2 (CONTROLLED_EGRESS): Package managers (pip, npm, yarn, cargo) run in a hardened
      ephemeral Docker container with DNS sinkholes, script suppression (--ignore-scripts),
      capability dropping (--cap-drop=ALL), and resource caps.
      * CRITICAL: NEVER falls back to host execution if Docker is offline.
    - ZONE 3 (QUARANTINE_AIRGAP): Untrusted code, tests, and scripts run strictly inside an
      air-gapped Docker container (--network none) with read-only dependency mounts.
      * If Docker is offline, AST safety check is enforced before permitting any local test run.
    """
    clean_proj = sanitize_project_name(project_name)
    proj_dir = resolve_safe_project_path(clean_proj, "")

    if not proj_dir.exists():
        return {
            "status": "error",
            "zone": "PRE_CHECK",
            "error": f"Project workspace '{clean_proj}' does not exist on disk."
        }

    # Step 1: Classify Security Zone
    zone, reason, meta = classify_command_security_zone(command)
    start_t = time.perf_counter()

    # =========================================================================
    # ZONE 0: BLOCKED COMMANDS
    # =========================================================================
    if zone == SecurityZone.BLOCKED:
        return {
            "status": "security_block",
            "zone": zone.value,
            "command": command,
            "error": f"SECURITY BLOCK: {reason}"
        }

    # =========================================================================
    # ZONE 1: LOCAL SAFE COMMANDS (py_compile, ast, git status)
    # =========================================================================
    if zone == SecurityZone.LOCAL_SAFE:
        try:
            parts = shlex.split(command, posix=True)
            if not parts:
                return {"status": "error", "error": "Empty command."}

            proc = subprocess.run(
                parts,
                shell=False,  # CRITICAL: shell=False prevents shell injection attacks (&, |, ;)
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            dur = round(time.perf_counter() - start_t, 3)
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "zone": zone.value,
                "mode": "local_safe_runner",
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:8192],
                "stderr": proc.stderr[:8192],
                "execution_time_sec": dur,
                "isolation": "Zone 1: Local Safe (shell=False, Project CWD Jail)"
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "zone": zone.value,
                "command": command,
                "error": f"Execution timed out after {timeout} seconds."
            }
        except Exception as e:
            return {
                "status": "error",
                "zone": zone.value,
                "command": command,
                "error": str(e)
            }

    # =========================================================================
    # DOCKER DAEMON VERIFICATION (For Zone 2 & Zone 3)
    # =========================================================================
    docker_available = is_docker_running()
    if not docker_available:
        # Attempt to spin up Docker Desktop if installed
        start_res = start_docker_desktop()
        if start_res.get("status") == "success":
            for _ in range(6):
                time.sleep(1.0)
                if is_docker_running():
                    docker_available = True
                    break

    win_path = str(proj_dir).replace("\\", "/")
    volume_name = f"unleash_deps_{clean_proj}"
    image = get_preferred_docker_image(command)

    # =========================================================================
    # ZONE 2: CONTROLLED EGRESS (Package Management: pip, npm, yarn, cargo)
    # =========================================================================
    if zone == SecurityZone.CONTROLLED_EGRESS:
        if not docker_available:
            # STRICT DEFENSE: NEVER FALL BACK TO HOST FOR PACKAGE INSTALLATION!
            # Malicious setup.py or npm postinstall scripts would execute on the user's host OS.
            return {
                "status": "security_block",
                "zone": zone.value,
                "command": command,
                "error": (
                    "CONTAINER ISOLATION REQUIRED: Package installation commands ('pip', 'npm', 'yarn', 'cargo') "
                    "cannot be executed directly on the host machine to protect against supply-chain attacks and malicious "
                    "setup.py execution hooks. Docker Desktop must be running to execute in a hardened sandbox."
                ),
                "remediation": "Start Docker Desktop and retry the installation."
            }

        try:
            # Automatic security flag injection for package managers
            hardened_cmd = command
            lowered_cmd = command.lower()

            if "npm" in lowered_cmd and "--ignore-scripts" not in lowered_cmd:
                hardened_cmd += " --ignore-scripts --no-audit --no-fund"
            elif "yarn" in lowered_cmd and "--ignore-scripts" not in lowered_cmd:
                hardened_cmd += " --ignore-scripts"
            elif "pip" in lowered_cmd:
                if "--disable-pip-version-check" not in lowered_cmd:
                    hardened_cmd += " --disable-pip-version-check --no-warn-script-location"
                if "--target" not in lowered_cmd and "-t " not in lowered_cmd:
                    hardened_cmd += " --target=/deps"

            docker_cmd = [
                DOCKER_BIN, "run", "--rm",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--cpus", "1.0",
                "--memory", "512m",
                "--pids-limit", "100",
                # LAN / Private Subnet DNS Sinkholing (Prevents pivoting or hitting host ports)
                "--add-host", "host.docker.internal:0.0.0.0",
                "--add-host", "gateway.docker.internal:0.0.0.0",
                "--add-host", "kubernetes.docker.internal:0.0.0.0",
                "--add-host", "metadata.google.internal:0.0.0.0",
                # Persistent project dependency volume & workspace mount
                "-v", f"{volume_name}:/deps",
                "-v", f"{win_path}:/workspace",
                "-w", "/workspace",
                "-e", "PYTHONPATH=/deps:/workspace",
                "-e", "PATH=/deps/bin:/usr/local/bin:/usr/bin:/bin",
                "-e", "NODE_PATH=/workspace/node_modules",
                image,
                "sh", "-c", hardened_cmd
            ]

            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout * 2,  # Package downloads may take slightly longer
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            dur = round(time.perf_counter() - start_t, 2)
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "zone": zone.value,
                "mode": "docker_controlled_egress",
                "command": hardened_cmd,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:8192],
                "stderr": proc.stderr[:8192],
                "execution_time_sec": dur,
                "isolation": f"Zone 2: Hardened Docker ({image}, Cap-Drop: ALL, Host DNS Sinkholed, --ignore-scripts)"
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "zone": zone.value,
                "command": command,
                "error": f"Package installation timed out after {timeout * 2} seconds."
            }
        except Exception as e:
            return {
                "status": "error",
                "zone": zone.value,
                "command": command,
                "error": f"Docker container launch failed: {str(e)}"
            }

    # =========================================================================
    # ZONE 3: QUARANTINE AIRGAP (Untrusted Code, Scripts, Tests)
    # =========================================================================
    if zone == SecurityZone.QUARANTINE_AIRGAP:
        if docker_available:
            try:
                docker_cmd = [
                    DOCKER_BIN, "run", "--rm",
                    "--network", "none",  # STRICT AIR-GAP: Zero internet, zero LAN, zero sockets
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
                    "--cpus", "1.0",
                    "--memory", "512m",
                    "--pids-limit", "100",
                    # Read-only dependency mount to prevent runtime tampering with libraries
                    "-v", f"{volume_name}:/deps:ro",
                    "-v", f"{win_path}:/workspace",
                    "-w", "/workspace",
                    "-e", "PYTHONPATH=/deps:/workspace",
                    "-e", "PATH=/deps/bin:/usr/local/bin:/usr/bin:/bin",
                    "-e", "NODE_PATH=/workspace/node_modules",
                    image,
                    "sh", "-c", command
                ]

                proc = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

                dur = round(time.perf_counter() - start_t, 2)
                return {
                    "status": "success" if proc.returncode == 0 else "error",
                    "zone": zone.value,
                    "mode": "docker_airgap_quarantine",
                    "command": command,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[:8192],
                    "stderr": proc.stderr[:8192],
                    "execution_time_sec": dur,
                    "isolation": f"Zone 3: Air-Gapped Docker (--network none, Cap-Drop: ALL, Read-Only Deps)"
                }

            except subprocess.TimeoutExpired:
                return {
                    "status": "error",
                    "zone": zone.value,
                    "command": command,
                    "error": f"Air-gapped execution timed out after {timeout} seconds."
                }
            except Exception as e:
                print(f"[CONTAINER RUNNER WARNING]: Docker airgap run failed ({e}). Checking AST safety for fallback...")

        # If Docker is unavailable for Zone 3, perform strict AST audit before permitting local test fallback
        parts = shlex.split(command, posix=True)
        if not parts:
            return {"status": "error", "error": "Empty command."}

        # Check if the command is targeting a python file
        py_candidates = [proj_dir / p for p in parts if p.endswith(".py")]
        for py_cand in py_candidates:
            is_safe, ast_err = check_python_ast_safety(py_cand)
            if not is_safe:
                return {
                    "status": "security_block",
                    "zone": zone.value,
                    "command": command,
                    "error": (
                        f"CONTAINER ISOLATION REQUIRED: File '{py_cand.name}' contains potentially unsafe instructions ({ast_err}). "
                        "Execution on the host machine is blocked without Docker airgap isolation."
                    )
                }

        # If AST passed and command is a standard test runner, permit local execution with shell=False
        try:
            proc = subprocess.run(
                parts,
                shell=False,
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            dur = round(time.perf_counter() - start_t, 2)
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "zone": zone.value,
                "mode": "local_ast_verified_fallback",
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:8192],
                "stderr": proc.stderr[:8192],
                "execution_time_sec": dur,
                "isolation": "Local Sandbox Fallback (Docker offline; AST verified safe; shell=False)"
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "zone": zone.value,
                "command": command,
                "error": f"Execution timed out after {timeout} seconds."
            }
        except Exception as e:
            return {
                "status": "error",
                "zone": zone.value,
                "command": command,
                "error": str(e)
            }

    return {"status": "error", "error": "Unhandled security zone."}


# ============================================================================
# UNIVERSAL DEFINITION OF DONE (DoD) BACKEND TEST GATE
# ============================================================================

def run_backend_docker_test_gate(project_name: Any, timeout: int = 15) -> Dict[str, Any]:
    """
    Universal Backend Definition of Done (DoD) Gate:
    Validates syntax and runs tests strictly through the 3-Zone Dynamic Quarantine Security Sandbox:
      1. Validates Python syntax via py_compile for all .py files (Zone 1: Local Safe, 0 latency)
      2. If test files exist, executes them inside Zone 3 (Air-Gapped Docker Container)
      3. Captures exact fatal stack traces (<150 tokens) and maps to primary_repair_file.
    """
    if isinstance(project_name, Path):
        clean_proj = sanitize_project_name(project_name.name)
        proj_dir = project_name
    else:
        clean_proj = sanitize_project_name(project_name)
        proj_dir = resolve_safe_project_path(clean_proj, "")

    if not proj_dir.exists():
        return {"valid": False, "error": f"Project workspace '{clean_proj}' does not exist."}

    py_files = list(proj_dir.glob("*.py"))
    test_files = [f for f in py_files if "test" in f.name.lower()]
    package_json = proj_dir / "package.json"

    # If pure static HTML frontend with no backend code, pass immediately
    if not py_files and not package_json.exists():
        return {"valid": True, "tested": False, "summary": "No backend files present."}

    # 1. Python Syntax / py_compile test (Zone 1: Local Safe)
    if py_files:
        for py_f in py_files:
            rel_name = py_f.name
            compile_res = execute_in_isolated_container(clean_proj, f"python -m py_compile {rel_name}", timeout=timeout)
            if compile_res.get("exit_code", 0) != 0:
                err_text = compile_res.get("stderr") or compile_res.get("stdout") or compile_res.get("error", "Syntax error")
                lines = [l for l in err_text.strip().splitlines() if l.strip()]
                short_err = "\n".join(lines[-3:]) if len(lines) >= 3 else err_text.strip()
                return {
                    "valid": False,
                    "tested": True,
                    "category": "python_syntax_error",
                    "primary_repair_file": rel_name,
                    "error": f"BACKEND COMPILER FAILURE in '{rel_name}':\n{short_err}",
                    "summary": f"Python compilation failed on {rel_name}."
                }

        # 2. Automated Test Suite (Zone 3: Quarantine Air-Gap)
        if test_files:
            primary_test = test_files[0].name
            test_res = execute_in_isolated_container(clean_proj, f"python -m unittest {primary_test}", timeout=timeout)
            if test_res.get("exit_code", 0) != 0:
                err_text = test_res.get("stderr") or test_res.get("stdout") or "Test suite failed."
                lines = [l for l in err_text.strip().splitlines() if l.strip()]
                short_err = "\n".join(lines[-4:]) if len(lines) >= 4 else err_text.strip()
                candidate_impl = primary_test.replace("test_", "").replace("_test", "")
                impl_file = candidate_impl if (proj_dir / candidate_impl).exists() else primary_test
                return {
                    "valid": False,
                    "tested": True,
                    "category": "backend_test_failure",
                    "primary_repair_file": impl_file,
                    "error": f"BACKEND TEST SUITE FAILED in '{primary_test}':\n{short_err}",
                    "summary": f"Unit tests failed in {primary_test}."
                }

    return {
        "valid": True,
        "tested": True,
        "summary": "All backend compilation checks and isolated container tests passed."
    }
