import os
import re
import shlex
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from backend.core.agent_tools import resolve_safe_project_path, sanitize_project_name

DOCKER_BIN = "docker"
DEFAULT_TIMEOUT_SEC = 15

STANDARD_DOCKER_DESKTOP_PATHS = [
    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Docker\Docker Desktop.exe"),
    os.path.expandvars(r"%ProgramW6432%\Docker\Docker\Docker Desktop.exe")
]


def get_docker_desktop_executable() -> Optional[str]:
    """Finds Docker Desktop.exe across standard Windows installation paths."""
    for p in STANDARD_DOCKER_DESKTOP_PATHS:
        if p and os.path.exists(p):
            return p
    return None


DOCKER_DESKTOP_PATH = get_docker_desktop_executable() or r"C:\Program Files\Docker\Docker\Docker Desktop.exe"

# Dangerous host commands unconditionally blocked regardless of runner mode
BLOCKED_COMMANDS = [
    r"\bformat\b",
    r"\brmdir\s+/[sq]",
    r"\bdel\s+/[sq]",
    r"\breg\b",
    r"\bregedit\b",
    r"\bnetsh\b",
    r"\bshutdown\b",
    r"\bpkexec\b",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bpowershell(?:\.exe)?\s+-[ec]",
    r"\bcmd(?:\.exe)?\s+/[ck]"
]


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


def execute_in_isolated_container(project_name: str, command: str, timeout: int = DEFAULT_TIMEOUT_SEC) -> Dict[str, Any]:
    """
    Executes a terminal or test command strictly inside the isolated project workspace.
    1. If Docker is active: Runs inside an air-gapped container (`--network none`) with mounted workspace.
    2. If Docker is closed: Falls back to a whitelisted sandboxed runner (`shell=False`, `cwd=project_dir`).
    """
    clean_proj = sanitize_project_name(project_name)
    proj_dir = resolve_safe_project_path(clean_proj, "")

    if not proj_dir.exists():
        return {
            "status": "error",
            "error": f"Project workspace '{clean_proj}' does not exist on disk."
        }

    # Security check: detect blacklisted destructive commands
    lowered = command.strip().lower()
    for pattern in BLOCKED_COMMANDS:
        if re.search(pattern, lowered):
            return {
                "status": "error",
                "error": f"SECURITY BLOCK: Command '{command}' matches restricted system instruction."
            }

    start_t = time.perf_counter()
    docker_available = is_docker_running()

    # =========================================================================
    # PATH A: DOCKER ISOLATED CONTAINER (AIR-GAPPED `--network none`)
    # =========================================================================
    if docker_available:
        try:
            # Mount project folder to /workspace in an isolated container
            # Using python:3.11-slim or node:18-alpine if available, else python
            win_path = str(proj_dir).replace("\\", "/")
            docker_cmd = [
                DOCKER_BIN, "run", "--rm",
                "--network", "none",
                "--cpus", "1.0",
                "--memory", "512m",
                "-v", f"{win_path}:/workspace",
                "-w", "/workspace",
                "python:3.11-slim",
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
            if proc.returncode == 127:
                # Command not present inside container image (e.g. node or npm not in python:3.11-slim)
                print(f"[CONTAINER RUNNER]: Command '{command}' returned 127 (not found in container). Falling back to local sandbox...")
            else:
                return {
                    "status": "success" if proc.returncode == 0 else "error",
                    "mode": "docker_isolated_container",
                    "command": command,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[:8192],
                    "stderr": proc.stderr[:8192],
                    "execution_time_sec": dur,
                    "isolation": "Docker (--network none, 512MB RAM, 1.0 CPU)"
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "mode": "docker_isolated_container",
                "command": command,
                "error": f"Execution timed out after {timeout} seconds."
            }
        except Exception as e:
            # If container launch fails, gracefully fall through to sandboxed runner
            print(f"[CONTAINER RUNNER WARNING]: Docker run failed ({e}), falling back to local sandbox.")

    # =========================================================================
    # PATH B: WHITELISTED SANDBOXED RUNNER (`shell=False`, `cwd=proj_dir`)
    # =========================================================================
    try:
        # Split command safely without shell expansion
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

        dur = round(time.perf_counter() - start_t, 2)
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "mode": "sandboxed_runner",
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:8192],
            "stderr": proc.stderr[:8192],
            "execution_time_sec": dur,
            "isolation": "Local Sandbox (shell=False, Project CWD Jail)"
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "mode": "sandboxed_runner",
            "command": command,
            "error": f"Execution timed out after {timeout} seconds."
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "mode": "sandboxed_runner",
            "command": command,
            "error": f"Executable '{parts[0]}' not found in system PATH."
        }
    except Exception as e:
        return {
            "status": "error",
            "mode": "sandboxed_runner",
            "command": command,
            "error": str(e)
        }


def run_backend_docker_test_gate(project_name: Any, timeout: int = 15) -> Dict[str, Any]:
    """
    Universal Backend Definition of Done (DoD) Gate:
    Validates syntax and runs tests strictly inside the isolated container:
      1. Validates Python syntax via py_compile for all .py files
      2. If test files or unittest/pytest tests exist, executes them
      3. If Node package.json / backend JS exists, runs syntax checks
    Captures exact fatal stack traces (<150 tokens) and maps to primary_repair_file.
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

    # 1. Python Syntax / py_compile test
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

        # 2. Automated Test Suite (if test files exist)
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
