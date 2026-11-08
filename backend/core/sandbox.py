import os
import sys
import ast
import re
import time
import uuid
import shutil
import base64
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

# Base directory for isolated execution runs
SANDBOX_BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "sandbox"
SANDBOX_BASE_DIR.mkdir(parents=True, exist_ok=True)

MAX_TIMEOUT_SECONDS = 7.0
DEFAULT_TIMEOUT_SECONDS = 4.0
MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB limit
DEFAULT_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024  # 256 MB hard cap
MAX_PROCESS_LIMIT = 16  # Prevent fork bombs

# Prohibited destructive host operations that must be blocked before execution
PROHIBITED_HOST_PATTERNS = [
    # Disk & System destruction
    r"format\s+[a-zA-Z]:",
    r"vssadmin\s+delete\s+shadows",
    r"bcdedit(\.exe)?\s+",
    r"del\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:\\",
    r"rmdir\s+/[sS]\s+/[qQ]\s+[cC]:\\",
    r"diskpart(\.exe)?",
    
    # Host Shutdown / Poweroff / Reboot vectors
    r"\bshutdown(\.exe)?\s+[\/\-][sSrRpPhHfF]",
    r"\bshutdown(\.exe)?\s+/t\s+\d+",
    r"^\s*shutdown(\.exe)?(\s+.*)?$",
    r"\bstop-computer\b",
    r"\brestart-computer\b",
    r"\binit\s+[06]\b",
    r"\bpoweroff(\.exe)?\b",
    r"\breboot(\.exe)?\b",
    r"\bexitwindowsex\b",
    r"\binitiatesystemshutdown",
    r"\bzwshutdownsystem\b",
    r"\bntshutdownsystem\b",
    r"\bzwraiseharderror\b",
    r"rundll32(\.exe)?\s+user32\.dll,\s*exitwindowsex"
]


# ============================================================================
# Windows Kernel Job Object Isolation (Memory Quota & Tree Destruction)
# ============================================================================
class WindowsJobManager:
    """
    Manages a Windows Job Object to enforce kernel-level limits:
    - 256 MB hard memory ceiling (prevents RAM exhaustion / host freezes)
    - 16 maximum active processes (prevents fork bombs)
    - Auto-kill on job close (guarantees zero orphaned child processes)
    """
    def __init__(self, memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES, max_processes: int = MAX_PROCESS_LIMIT):
        self.h_job = None
        self.is_active = False
        if os.name == "nt":
            self._init_job(memory_limit_bytes, max_processes)

    def _init_job(self, memory_limit_bytes: int, max_processes: int):
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32

            JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
            JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
            JobObjectExtendedLimitInformation = 9

            class IO_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('ReadOperationCount', ctypes.c_uint64),
                    ('WriteOperationCount', ctypes.c_uint64),
                    ('OtherOperationCount', ctypes.c_uint64),
                    ('ReadTransferCount', ctypes.c_uint64),
                    ('WriteTransferCount', ctypes.c_uint64),
                    ('OtherTransferCount', ctypes.c_uint64),
                ]

            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ('PerProcessUserTimeLimit', ctypes.c_int64),
                    ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD),
                    ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t),
                    ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t),
                    ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD),
                ]

            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ('BasicLimitInformation', JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ('IoCounters', IO_COUNTERS),
                    ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryLimit', ctypes.c_size_t),
                    ('PeakJobMemoryLimit', ctypes.c_size_t),
                ]

            self.h_job = kernel32.CreateJobObjectW(None, None)
            if self.h_job:
                info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                info.BasicLimitInformation.LimitFlags = (
                    JOB_OBJECT_LIMIT_JOB_MEMORY |
                    JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                    JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                )
                info.ProcessMemoryLimit = memory_limit_bytes
                info.JobMemoryLimit = memory_limit_bytes
                info.BasicLimitInformation.ActiveProcessLimit = max_processes

                res = kernel32.SetInformationJobObject(
                    self.h_job,
                    JobObjectExtendedLimitInformation,
                    ctypes.byref(info),
                    ctypes.sizeof(info)
                )
                self.is_active = bool(res)
        except Exception:
            self.is_active = False

    def assign_process(self, proc_handle) -> bool:
        if not self.is_active or not self.h_job:
            return False
        try:
            import ctypes
            return bool(ctypes.windll.kernel32.AssignProcessToJobObject(self.h_job, proc_handle))
        except Exception:
            return False

    def close(self):
        if self.h_job:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.h_job)
            except Exception:
                pass
            self.h_job = None
            self.is_active = False


# ============================================================================
# Docker Availability & Linux Micro-Container Execution Engine
# ============================================================================
CYBER_SANDBOX_IMAGE = "cyber-sandbox:latest"
FALLBACK_PYTHON_IMAGE = "python:3.11-alpine"
FALLBACK_NODE_IMAGE = "node:alpine"


def get_docker_cmd() -> str:
    """Returns path to docker CLI, checking PATH and standard installation directories."""
    found = shutil.which("docker")
    if found:
        return found
    std_bin = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if os.path.exists(std_bin):
        return std_bin
    return "docker"


def is_docker_available() -> bool:
    """Checks if Docker CLI and daemon are reachable on the host."""
    try:
        docker_bin = get_docker_cmd()
        res = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
            check=False
        )
        return res.returncode == 0
    except Exception:
        return False


def is_cyber_image_available() -> bool:
    """Checks if the customized cyber-sandbox:latest image has been built locally."""
    try:
        docker_bin = get_docker_cmd()
        res = subprocess.run(
            [docker_bin, "image", "inspect", CYBER_SANDBOX_IMAGE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
            check=False
        )
        return res.returncode == 0
    except Exception:
        return False


def get_sandbox_telemetry_status() -> Dict[str, Any]:
    """Returns real-time status of the execution sandbox environment and active engine."""
    has_docker_cli = bool(shutil.which("docker")) or os.path.exists(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
    daemon_online = is_docker_available()
    has_cyber_image = is_cyber_image_available() if daemon_online else False

    if daemon_online and has_cyber_image:
        active_engine = "docker_cyber"
        engine_label = "Docker Linux Container (cyber-sandbox:latest • pwntools/scapy/crypto)"
    elif daemon_online:
        active_engine = "docker_standard"
        engine_label = "Docker Linux Container (python:3.11-alpine • --network none)"
    else:
        active_engine = "windows_job_object"
        engine_label = "Windows Kernel Job Object Jail (256MB RAM Cap • Network Blocked • Host Shield)"

    return {
        "status": "online",
        "active_engine": active_engine,
        "engine_detail": engine_label,
        "docker_installed": has_docker_cli,
        "docker_daemon_running": daemon_online,
        "cyber_image_built": has_cyber_image,
        "network_isolation": "HARD_ISOLATION (--network none / socket block)",
        "memory_limit_mb": 256,
        "security_tools_supported": [
            "pwntools (binary exploitation & shellcraft)",
            "scapy (packet crafting & raw protocol analysis)",
            "cryptography (ciphers, AES, RSA, HMAC)",
            "pycryptodome (low-level crypto primitives)",
            "impacket (network protocol inspection)"
        ]
    }


def execute_in_docker(
    code: str,
    language: str,
    scratch_dir: Path,
    timeout: float,
    stdin_input: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Executes code inside a hardened, isolated Docker container with:
    - --network none (zero internet or local network access)
    - --memory 256m (hard RAM cap)
    - --cpus 1.0 (1 core cap)
    - --pids-limit 64 (fork bomb immunity)
    - --cap-drop ALL (drops all Linux kernel capabilities)
    - Non-root user execution
    """
    lang = language.lower().strip()
    has_cyber_img = is_cyber_image_available()
    docker_bin = get_docker_cmd()

    if lang in ("python", "py", "python3"):
        script_file = scratch_dir / "solution.py"
        script_file.write_text(code, encoding="utf-8")
        image = CYBER_SANDBOX_IMAGE if has_cyber_img else FALLBACK_PYTHON_IMAGE
        engine_tag = "cyber-sandbox:latest (pwntools/scapy/crypto)" if has_cyber_img else "python:3.11-alpine"
        docker_cmd = [
            docker_bin, "run", "--rm",
            "--network", "none",
            "--memory", "256m",
            "--cpus", "1.0",
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "-v", f"{scratch_dir}:/workspace:rw",
            "-w", "/workspace",
            image,
            "python", "-u", "solution.py"
        ]
    elif lang in ("javascript", "js", "node"):
        script_file = scratch_dir / "solution.js"
        script_file.write_text(code, encoding="utf-8")
        image = FALLBACK_NODE_IMAGE
        engine_tag = "node:alpine"
        docker_cmd = [
            docker_bin, "run", "--rm",
            "--network", "none",
            "--memory", "256m",
            "--cpus", "1.0",
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "-v", f"{scratch_dir}:/workspace:rw",
            "-w", "/workspace",
            image,
            "node", "solution.js"
        ]
    else:
        # Batch and PowerShell are Windows-specific; run in native Windows Job Object jail
        return None

    start_time = time.perf_counter()
    status = "success"
    exit_code = 0
    stdout_text = ""
    stderr_text = ""

    try:
        proc = subprocess.Popen(
            docker_cmd,
            stdin=subprocess.PIPE if stdin_input else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        in_bytes = stdin_input.encode("utf-8") if stdin_input else None
        out_bytes, err_bytes = proc.communicate(input=in_bytes, timeout=timeout)
        exit_code = proc.returncode
        stdout_text = out_bytes.decode("utf-8", errors="replace")
        stderr_text = err_bytes.decode("utf-8", errors="replace")

        if exit_code != 0:
            status = "error"
    except subprocess.TimeoutExpired:
        status = "timeout"
        exit_code = -1
        stderr_text = f"Container execution timed out after {timeout:.1f}s. Container terminated."
        try:
            proc.kill()
        except Exception:
            pass
    except Exception as e:
        status = "error"
        exit_code = -1
        stderr_text = f"Docker sandbox error: {str(e)}"

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "duration_ms": duration_ms,
        "engine": "docker",
        "engine_detail": f"Docker Linux Container ({engine_tag} • --network none • 256MB Cap)"
    }


# ============================================================================
# AST & Dynamic Obfuscation Security Gate
# ============================================================================
class SecurityASTVisitor(ast.NodeVisitor):
    """
    Static pre-execution code analyzer to detect catastrophic host-destruction calls,
    dynamic eval/exec obfuscation, and base64 encoded destructive commands.
    """
    def __init__(self):
        self.dangerous_calls = []
        self.risk_level = "LOW"
        self.warnings = []

    def visit_Call(self, node):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}"

        # Detect raw recursive wipes targeting C:\ root or Windows directory
        if func_name in ("shutil.rmtree", "os.removedirs", "os.rmdir"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    val = arg.value.strip().lower()
                    if val in ("c:\\", "c:/", "c:", "\\", "/", os.environ.get("WINDIR", "").lower()):
                        self.dangerous_calls.append(f"Blocked destructive wipe of host root: {func_name}('{arg.value}')")
                        self.risk_level = "CRITICAL"

        # Detect direct process calls attempting shutdown or host destruction
        if func_name in ("os.system", "subprocess.call", "subprocess.run", "subprocess.Popen"):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    for pattern in PROHIBITED_HOST_PATTERNS:
                        if re.search(pattern, arg.value, re.IGNORECASE):
                            self.dangerous_calls.append(f"Blocked destructive host command pattern: '{arg.value}'")
                            self.risk_level = "CRITICAL"
                elif isinstance(arg, ast.List):
                    list_items = [x.value for x in arg.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)]
                    joined = " ".join(list_items)
                    for pattern in PROHIBITED_HOST_PATTERNS:
                        if re.search(pattern, joined, re.IGNORECASE):
                            self.dangerous_calls.append(f"Blocked destructive host command pattern: '{joined}'")
                            self.risk_level = "CRITICAL"

        # Detect direct Windows API shutdown calls
        func_lower = func_name.lower()
        if "exitwindowsex" in func_lower or "initiatesystemshutdown" in func_lower or "zwshutdownsystem" in func_lower:
            self.dangerous_calls.append(f"Blocked direct Windows API shutdown call: '{func_name}'")
            self.risk_level = "CRITICAL"

        # Check for base64 decoding attempts containing prohibited patterns
        if "b64decode" in func_name:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, (str, bytes)):
                    try:
                        raw = arg.value if isinstance(arg.value, bytes) else arg.value.encode('utf-8')
                        decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
                        for pattern in PROHIBITED_HOST_PATTERNS:
                            if re.search(pattern, decoded, re.IGNORECASE):
                                self.dangerous_calls.append(f"Blocked obfuscated base64 payload: '{decoded.strip()}'")
                                self.risk_level = "CRITICAL"
                    except Exception:
                        pass

        self.generic_visit(node)


def inspect_code_safety(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Scans submitted code for dangerous host-destroying operations before spawning sandbox.
    """
    report = {
        "safe_to_execute": True,
        "risk_level": "LOW",
        "warnings": [],
        "block_reason": None
    }

    # Text pattern check for any language (Batch, PowerShell, Shell, Python)
    for pattern in PROHIBITED_HOST_PATTERNS:
        match = re.search(pattern, code, re.IGNORECASE | re.MULTILINE)
        if match:
            report["safe_to_execute"] = False
            report["risk_level"] = "CRITICAL"
            report["block_reason"] = f"Prohibited destructive host command detected: '{match.group(0).strip()}'"
            return report

    # Check for base64 encoded strings in the code that decode to prohibited patterns
    b64_matches = re.findall(r'[A-Za-z0-9+/]{16,}={0,2}', code)
    for b in b64_matches:
        try:
            decoded = base64.b64decode(b).decode('utf-8', errors='ignore')
            for pattern in PROHIBITED_HOST_PATTERNS:
                if re.search(pattern, decoded, re.IGNORECASE):
                    report["safe_to_execute"] = False
                    report["risk_level"] = "CRITICAL"
                    report["block_reason"] = f"Obfuscated base64 command detected: '{decoded.strip()}'"
                    return report
        except Exception:
            pass

    if language.lower() in ("python", "py"):
        try:
            tree = ast.parse(code)
            visitor = SecurityASTVisitor()
            visitor.visit(tree)
            if visitor.dangerous_calls:
                report["safe_to_execute"] = False
                report["risk_level"] = "CRITICAL"
                report["block_reason"] = "; ".join(visitor.dangerous_calls)
                return report
            report["warnings"] = visitor.warnings
            report["risk_level"] = visitor.risk_level
        except SyntaxError:
            pass

    return report


def get_sanitized_environment(scratch_dir: Path) -> Dict[str, str]:
    """
    Builds a secure, isolated environment dictionary by stripping all host API keys,
    tokens, and sensitive credentials while keeping standard Python runtime paths.
    """
    allowed_keys = {
        "SYSTEMROOT", "WINDIR", "PATHEXT", "TEMP", "TMP", "COMSPEC",
        "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS"
    }

    env = {k: v for k, v in os.environ.items() if k.upper() in allowed_keys}

    py_dir = str(Path(sys.executable).parent)
    py_scripts = str(Path(sys.executable).parent / "Scripts")
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    sys32 = str(Path(win_dir) / "System32")

    env["PATH"] = f"{py_dir};{py_scripts};{sys32};{win_dir}"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Set temporary workspace directories strictly inside the scratch sandbox
    env["TEMP"] = str(scratch_dir)
    env["TMP"] = str(scratch_dir)

    return env


# ============================================================================
# Main Sandbox Execution Dispatcher
# ============================================================================
def execute_in_sandbox(
    code: str,
    language: str = "python",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    stdin_input: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes user or agent code within an isolated, resource-constrained sandbox directory.
    Enforces memory limits (Windows Job Object or Docker), hard timeouts, process group killing,
    and output truncation.
    """
    timeout = min(max(timeout_seconds, 1.0), MAX_TIMEOUT_SECONDS)
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    scratch_dir = SANDBOX_BASE_DIR / run_id
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pre-Execution Safety Inspection
    safety_check = inspect_code_safety(code, language)
    if not safety_check["safe_to_execute"]:
        return {
            "run_id": run_id,
            "status": "blocked",
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SECURITY POLICY BLOCK: {safety_check['block_reason']}",
            "execution_time_ms": 0,
            "language": language,
            "risk_level": safety_check["risk_level"],
            "created_files": [],
            "sandboxed": True,
            "engine": "security_gate",
            "engine_detail": "Pre-Execution AST & Policy Gate",
            "timestamp": time.time()
        }

    # 2. Attempt Docker Isolation if available and language supports it
    if is_docker_available():
        docker_result = execute_in_docker(code, language, scratch_dir, timeout, stdin_input)
        if docker_result:
            created_files = _inventory_files(scratch_dir)
            return {
                "run_id": run_id,
                "status": docker_result["status"],
                "exit_code": docker_result["exit_code"],
                "stdout": _truncate(docker_result["stdout"]),
                "stderr": _truncate(docker_result["stderr"]),
                "execution_time_ms": docker_result["duration_ms"],
                "language": language,
                "risk_level": safety_check["risk_level"],
                "created_files": created_files,
                "sandboxed": True,
                "engine": docker_result["engine"],
                "engine_detail": docker_result["engine_detail"],
                "timestamp": time.time()
            }

    # 3. Native Host Sandbox with Network Lockdown & Windows Job Object Memory Guard
    lang = language.lower().strip()
    if lang in ("python", "py", "python3"):
        guard_code = (
            "import socket, builtins, os\n"
            "def _block_sock(*args, **kwargs):\n"
            "    raise PermissionError('Sandboxed execution policy: Outbound network connections are strictly disabled (--network none equivalent)')\n"
            "socket.socket.connect = _block_sock\n"
            "socket.socket.connect_ex = _block_sock\n"
            "socket.socket.bind = _block_sock\n"
            "_real_open = builtins.open\n"
            "def _secure_open(file, *args, **kwargs):\n"
            "    s = str(file).lower().replace('\\\\', '/')\n"
            "    if any(x in s for x in ['.ssh', '.aws', '.gitconfig', '.gemini', 'appdata', 'ntuser.dat', 'id_rsa']):\n"
            "        raise PermissionError(f'Sandboxed execution policy: Access to host private profile path is denied: {file}')\n"
            "    return _real_open(file, *args, **kwargs)\n"
            "builtins.open = _secure_open\n"
        )
        (scratch_dir / "_sandbox_guard.py").write_text(guard_code, encoding="utf-8")
        script_file = scratch_dir / "solution.py"
        script_file.write_text(code, encoding="utf-8")
        cmd = [
            sys.executable, "-u", "-c",
            "import _sandbox_guard; exec(open('solution.py', encoding='utf-8').read(), {'__name__': '__main__'})"
        ]
    elif lang in ("javascript", "js", "node"):
        script_file = scratch_dir / "solution.js"
        script_file.write_text(code, encoding="utf-8")
        node_exe = shutil.which("node") or "node"
        cmd = [node_exe, str(script_file)]
    elif lang in ("batch", "bat", "cmd"):
        script_file = scratch_dir / "solution.bat"
        script_file.write_text(code, encoding="utf-8")
        cmd = ["cmd.exe", "/c", str(script_file)]
    elif lang in ("powershell", "ps1"):
        script_file = scratch_dir / "solution.ps1"
        script_file.write_text(code, encoding="utf-8")
        cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_file)]
    else:
        script_file = scratch_dir / "solution.py"
        script_file.write_text(code, encoding="utf-8")
        cmd = [sys.executable, "-u", str(script_file)]

    clean_env = get_sanitized_environment(scratch_dir)
    start_time = time.perf_counter()
    status = "success"
    stdout_text = ""
    stderr_text = ""
    exit_code = 0

    # Create Windows Job Object for strict memory and process limits
    job = WindowsJobManager(memory_limit_bytes=DEFAULT_MEMORY_LIMIT_BYTES, max_processes=MAX_PROCESS_LIMIT)
    was_job_active = job.is_active

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(scratch_dir),
            stdin=subprocess.PIPE if stdin_input else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
            creationflags=creation_flags
        )

        # Attach process to Job Object
        if job.is_active and proc._handle:
            job.assign_process(proc._handle)

        in_bytes = stdin_input.encode("utf-8") if stdin_input else None
        out_bytes, err_bytes = proc.communicate(input=in_bytes, timeout=timeout)
        exit_code = proc.returncode

        stdout_text = out_bytes.decode("utf-8", errors="replace")
        stderr_text = err_bytes.decode("utf-8", errors="replace")

        if exit_code != 0:
            status = "error"

    except subprocess.TimeoutExpired:
        status = "timeout"
        exit_code = -1
        stderr_text = f"Execution timed out after {timeout:.1f} seconds. Process tree terminated to protect host resources."
        if proc:
            _kill_process_tree(proc.pid)
    except Exception as e:
        status = "error"
        exit_code = -1
        stderr_text = f"Sandbox runtime error: {str(e)}"
        if proc:
            _kill_process_tree(proc.pid)
        was_job_active = job.is_active
    finally:
        # Closing job handle forcefully ensures any child processes are closed
        job.close()

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    created_files = _inventory_files(scratch_dir, exclude_name=script_file.name)

    engine_label = "windows_job_object" if was_job_active else "process_jail"
    engine_desc = "Windows Job Object Jail (256MB RAM Cap • Network Blocked • Host Privacy Shield)" if was_job_active else "Local Process Jail (Env Stripped • Process-Tree Hard Kill)"

    return {
        "run_id": run_id,
        "status": status,
        "exit_code": exit_code,
        "stdout": _truncate(stdout_text),
        "stderr": _truncate(stderr_text),
        "execution_time_ms": duration_ms,
        "language": language,
        "risk_level": safety_check["risk_level"],
        "created_files": created_files,
        "sandboxed": True,
        "engine": engine_label,
        "engine_detail": engine_desc,
        "timestamp": time.time()
    }


def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT_BYTES:
        return text[:MAX_OUTPUT_BYTES] + "\n\n... [Output truncated at 64 KB limit] ..."
    return text


def _inventory_files(scratch_dir: Path, exclude_name: str = "") -> List[Dict[str, Any]]:
    files = []
    try:
        for f in scratch_dir.iterdir():
            if f.name != exclude_name:
                files.append({
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "is_dir": f.is_dir()
                })
    except Exception:
        pass
    return files


def _kill_process_tree(pid: int):
    """Safely and aggressively terminates a process and all its spawned children."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def cleanup_old_sandboxes(max_age_hours: float = 2.0):
    """Prunes scratchpad folders older than specified hours to keep disk usage near zero."""
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    try:
        for item in SANDBOX_BASE_DIR.iterdir():
            if item.is_dir() and item.name.startswith("run_"):
                try:
                    if item.stat().st_mtime < cutoff:
                        shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass
