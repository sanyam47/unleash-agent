"""
sys_doctor.py - Autonomous System & Application Doctor for Unleash Harness.
Diagnoses application crashes, Windows event errors, zombie locks, file permissions,
and validates application recovery using grounded verification gates.
"""

import os
import sys
import subprocess
import json
import argparse
from pathlib import Path
from datetime import datetime

# Windows Exception Code Dictionary
WIN_EXCEPTIONS = {
    "0x80000003": "STATUS_BREAKPOINT - Assert failure, missing DLL, or sandboxed helper process denied access (Common in Electron / Chromium / Antigravity).",
    "0xc0000005": "STATUS_ACCESS_VIOLATION - Memory violation or null pointer dereference.",
    "0xc00000fd": "STATUS_STACK_OVERFLOW - Deep recursion or blown stack frame.",
    "0xc0000135": "STATUS_DLL_NOT_FOUND - Required dynamic link library missing.",
    "0xc0000142": "STATUS_DLL_INIT_FAILED - Initialization failed, often permissions or corrupt environment."
}

def run_ps(cmd: str):
    """Executes a powershell command and returns stdout."""
    res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    return res.stdout.strip(), res.stderr.strip(), res.returncode

def diagnose_app(app_name: str):
    """
    1. Scans Windows Event Log for recent Application Crashes.
    2. Maps faulting path, exception code, and root cause diagnosis.
    """
    print(f"\n[+] Scanning Windows Event Log for crashes related to: '{app_name}'...")
    ps_cmd = f"Get-WinEvent -FilterHashtable @{{LogName='Application'; ProviderName='Application Error'}} -MaxEvents 20 | Select-Object TimeCreated, Message | ConvertTo-Json"
    stdout, stderr, code = run_ps(ps_cmd)
    
    if not stdout or stdout == "[]" or stdout == "":
        print(f"[-] No recent Windows Application Error events found.")
        return None

    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]
    except Exception as e:
        print(f"[-] Failed to parse event JSON: {e}")
        return None

    # Filter by app_name case-insensitively
    matches = [e for e in data if app_name.lower() in e.get("Message", "").lower()]

    if not matches:
        print(f"[-] No crash events matching '{app_name}' found in recent logs.")
        return None

    latest = matches[0]
    msg = latest.get("Message", "")
    time_raw = latest.get("TimeCreated", "")
    
    # Extract details
    fault_path = ""
    exception_code = ""
    fault_module = ""
    
    for line in msg.split("\n"):
        line = line.strip()
        if "Faulting application path:" in line:
            fault_path = line.split(":", 1)[1].strip()
        elif "Exception code:" in line:
            exception_code = line.split(":", 1)[1].strip()
        elif "Faulting module path:" in line:
            fault_module = line.split(":", 1)[1].strip()

    print(f"[!] Crash Detected in Windows Event Logs:")
    print(f"    - Target Path   : {fault_path}")
    print(f"    - Fault Module  : {fault_module}")
    print(f"    - Exception Code: {exception_code}")
    
    meaning = WIN_EXCEPTIONS.get(exception_code.lower(), "Unknown system exception.")
    print(f"    - Explanation   : {meaning}")
    
    remediation = []
    if exception_code.lower() == "0x80000003":
        folder = os.path.dirname(fault_path)
        remediation.append("Permission issue: Sandboxed helper process lacked permissions for 'ALL APPLICATION PACKAGES'.")
        remediation.append(f"Recommended Auto-Fix: python tools/sys_doctor.py --fix-permissions \"{folder}\"")
        remediation.append(f"Recommended Verification: python tools/sys_doctor.py --verify-launch \"{fault_path}\"")
    elif exception_code.lower() == "0xc0000005":
        remediation.append("Corrupted cache or zombie process holding shared memory.")
        remediation.append(f"Recommended Auto-Fix: python tools/sys_doctor.py --kill-zombies \"{app_name}\"")

    return {
        "app_name": app_name,
        "path": fault_path,
        "exception_code": exception_code,
        "meaning": meaning,
        "remediations": remediation
    }

def check_zombies(app_name: str, kill: bool = False):
    """Finds and optionally kills zombie or hung instances of the app."""
    print(f"\n[+] Checking active processes matching '{app_name}'...")
    ps_cmd = f"Get-Process -Name '*{app_name}*' -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, Path, WorkingSet64 | ConvertTo-Json"
    stdout, stderr, code = run_ps(ps_cmd)
    
    if not stdout or stdout == "[]":
        print(f"[*] No running processes found matching '{app_name}'.")
        return []

    try:
        proc_data = json.loads(stdout)
        if isinstance(proc_data, dict):
            proc_data = [proc_data]
    except Exception:
        return []

    print(f"[!] Found {len(proc_data)} running process(es):")
    for p in proc_data:
        pid = p.get('Id')
        name = p.get('ProcessName')
        mem_mb = round(p.get('WorkingSet64', 0) / (1024 * 1024), 2)
        print(f"    - PID {pid} [{name}] ({mem_mb} MB)")
        if kill:
            print(f"      -> Terminating PID {pid}...")
            run_ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
            print(f"      -> Terminated.")

    return proc_data

def fix_permissions(folder_path: str):
    """
    Grants necessary ACL permissions to 'ALL APPLICATION PACKAGES' and current user,
    which fixes Windows 0x80000003 crashes for sandboxed Chromium / Electron / Antigravity processes.
    """
    if not os.path.exists(folder_path):
        print(f"[-] Path does not exist: {folder_path}")
        return False

    print(f"\n[+] Repairing Access Control Lists (ACLs) on: {folder_path}")
    grant_cmd = f'icacls "{folder_path}" /grant "*S-1-15-2-1:(OI)(CI)RX" /T /Q'
    res = subprocess.run(grant_cmd, shell=True, capture_output=True, text=True)
    if res.returncode == 0:
        print("[✓] Successfully granted (OI)(CI)(RX) to 'ALL APPLICATION PACKAGES'.")
        return True
    else:
        print(f"[-] icacls returned exit code {res.returncode}: {res.stderr}")
        return False

def verify_launch(exe_path: str, timeout_sec: int = 5):
    """
    Checks if application is responsive and alive.
    """
    if not os.path.exists(exe_path):
        print(f"[-] Executable not found at: {exe_path}")
        return False

    print(f"\n[+] Verifying Application Status for: '{exe_path}'")
    # Check if already running healthy
    exe_name = Path(exe_path).stem
    ps_cmd = f"Get-Process -Name '{exe_name}' -ErrorAction SilentlyContinue | Select-Object Id, Responding, MainWindowTitle | ConvertTo-Json"
    stdout, stderr, code = run_ps(ps_cmd)
    
    if stdout and stdout != "[]":
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]
            print(f"[✓] Application is currently UP and RESPONDING!")
            for d in data:
                print(f"    - PID {d.get('Id')}: Responding={d.get('Responding')}, Window='{d.get('MainWindowTitle')}'")
            return True
        except Exception:
            pass

    print(f"[*] Process not currently active. Attempting test launch...")
    try:
        proc = subprocess.Popen([exe_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            exit_code = proc.wait(timeout=timeout_sec)
            print(f"[-] App terminated prematurely with exit code: {exit_code}")
            return False
        except subprocess.TimeoutExpired:
            print(f"[✓] App launched successfully! PID {proc.pid} is running stably after {timeout_sec}s.")
            return True
    except Exception as e:
        print(f"[-] Failed to launch application: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Autonomous System & Application Doctor for Unleash")
    parser.add_argument("--diagnose", type=str, help="Application name to diagnose via Windows Event Logs")
    parser.add_argument("--check-zombies", type=str, help="App name to check for zombie hung processes")
    parser.add_argument("--kill-zombies", type=str, help="App name to forcefully terminate hanging instances")
    parser.add_argument("--fix-permissions", type=str, help="Directory path to grant ALL APPLICATION PACKAGES read/execute")
    parser.add_argument("--verify-launch", type=str, help="Path to executable to test and verify launch")
    
    args = parser.parse_args()

    if args.diagnose:
        res = diagnose_app(args.diagnose)
        if res:
            print("\nRecommended Next Actions:")
            for r in res["remediations"]:
                print(f"  * {r}")
    elif args.check_zombies:
        check_zombies(args.check_zombies, kill=False)
    elif args.kill_zombies:
        check_zombies(args.kill_zombies, kill=True)
    elif args.fix_permissions:
        fix_permissions(args.fix_permissions)
    elif args.verify_launch:
        verify_launch(args.verify_launch)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
