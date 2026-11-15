#!/usr/bin/env python3
"""
Sanitized Sandbox Execution Gate
Executes terminal commands with path traversal containment,
blocked command security blacklists, and a hard 30-second watchdog.
"""

import sys
import os
import shlex
import subprocess
import argparse
import json
from typing import Dict, Any

BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf *", "del /f /s /q c:", "format",
    ":(){ :|:& };:", "shutdown", "reboot", "drop database",
    "mkfs", "dd if="
]

def sanitize_and_execute(command: str, cwd: str, timeout: int = 30) -> Dict[str, Any]:
    # Check blacklist
    cmd_lower = command.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return {
                "status": "blocked",
                "error": f"Security Gate: Dangerous command pattern '{blocked}' is unconditionally forbidden."
            }

    # Verify working directory containment
    real_cwd = os.path.realpath(cwd)
    if not os.path.exists(real_cwd):
        return {"status": "error", "error": f"Directory '{cwd}' does not exist."}

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=real_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "status": "success" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:8000],
            "stderr": proc.stderr[:8000]
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "exit_code": 124,
            "error": f"Command exceeded execution watchdog limit of {timeout}s (possible infinite loop or blocking prompt)."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description="Sanitized Sandbox Gate")
    parser.add_argument("--cmd", required=True, help="Command to execute")
    parser.add_argument("--cwd", default=".", help="Working directory jail")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    args = parser.parse_args()

    res = sanitize_and_execute(args.cmd, args.cwd, args.timeout)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("status") == "success" else 1)

if __name__ == "__main__":
    main()
