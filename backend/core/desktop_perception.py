"""
Desktop Perception Engine - Ambient Digital Perception for Jarvis.

Provides non-intrusive, continuous awareness of the user's desktop environment:
1. Interactive Process & Workspace Perception: Discovers top running user applications in Session 1.
2. Dev & Creative Stack Detection: Recognizes active IDEs (VS Code, Antigravity), Docker, Python, Node, Browsers.
3. Resource Monopoly Auditor: Identifies high RAM/CPU processes before they cause system hitching.
4. Ambient Narrative Formatter: Produces a high-signal situational brief for Jarvis's cognitive core.
"""

import os
import json
import time
import subprocess
from typing import Dict, Any, List, Optional


def get_interactive_session_processes(top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieves top active user applications using workstation_sensors' zero-bloat native Win32/cached reader (<5ms).
    """
    try:
        from backend.core.workstation_sensors import get_live_top_processes
        raw = get_live_top_processes(top_n=top_n) or []
        results: List[Dict[str, Any]] = []
        for item in raw:
            pname = str(item.get("name") or "")
            if not pname:
                continue
            results.append({
                "pid": item.get("pid"),
                "name": pname[:-4] if pname.lower().endswith(".exe") else pname,
                "ram_mb": item.get("memory_mb", 0.0),
                "cpu_sec": 0.0,
            })
        if results:
            return results
    except Exception:
        pass

    try:
        import psutil
        procs: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = proc.info
                pname = info.get("name") or ""
                if not pname:
                    continue
                mem_info = info.get("memory_info")
                rss = getattr(mem_info, "rss", 0) if mem_info else 0
                if rss <= 0:
                    continue
                procs.append({
                    "pid": info.get("pid"),
                    "name": pname[:-4] if pname.lower().endswith(".exe") else pname,
                    "ram_mb": round(rss / (1024 * 1024), 1),
                    "cpu_sec": 0.0,
                })
            except Exception:
                continue
        procs.sort(key=lambda x: x["ram_mb"], reverse=True)
        return procs[:top_n]
    except Exception:
        return []


def get_ambient_desktop_context() -> Dict[str, Any]:
    """
    Generates an ambient contextual snapshot of the user's active workstation state.
    """
    apps = get_interactive_session_processes(top_n=12)
    
    app_names = [a["name"].lower() for a in apps]
    
    dev_stack = []
    if any("code" in n or "antigravity" in n or "language_server" in n for n in app_names):
        dev_stack.append("IDE / Code Editor (Antigravity)")
    if any("docker" in n for n in app_names):
        # Check if actual containers are running or if only Docker Desktop service is idle
        has_running_containers = False
        try:
            d_res = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if d_res.returncode == 0 and d_res.stdout.strip():
                has_running_containers = True
        except Exception:
            pass

        if has_running_containers:
            dev_stack.append("Docker Containers (Active)")
        else:
            dev_stack.append("Docker Desktop (Idle Daemon)")
    if any("python" in n for n in app_names):
        dev_stack.append("Python Runtime")
    if any("node" in n for n in app_names):
        dev_stack.append("Node.js Runtime")
    if any("chrome" in n or "msedge" in n or "firefox" in n for n in app_names):
        dev_stack.append("Web Browser")
    if any("whatsapp" in n or "telegram" in n or "discord" in n or "slack" in n for n in app_names):
        dev_stack.append("Messaging & Comms")
        
    top_ram_hog = apps[0] if apps else None
    
    narrative_parts = []
    if dev_stack:
        narrative_parts.append(f"Active environment: {', '.join(dev_stack)}.")
    if top_ram_hog:
        narrative_parts.append(f"Top memory consumer: {top_ram_hog['name']} ({top_ram_hog['ram_mb']} MB).")
        
    narrative = " ".join(narrative_parts) if narrative_parts else "Workstation idle."
    
    return {
        "status": "success",
        "timestamp": time.time(),
        "dev_stack": dev_stack,
        "top_processes": apps[:6],
        "top_ram_consumer": top_ram_hog,
        "narrative": narrative
    }
