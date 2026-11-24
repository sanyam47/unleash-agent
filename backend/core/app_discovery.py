import winreg
import shutil
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

def get_dynamic_app_registry_file() -> Path:
    # Use the established data directory
    return Path(__file__).resolve().parent.parent / "data" / "dynamic_app_registry.json"

def scan_windows_apps() -> Dict[str, Dict[str, str]]:
    """
    Dynamically scans Windows App Paths and system PATH for executables.
    Returns a mapping of name (alias) to metadata (exe_path, display_name).
    """
    apps = {}
    
    # 1. Registry: App Paths
    paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
    ]
    
    for hkey, subkey in paths:
        try:
            with winreg.OpenKey(hkey, subkey) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        app_key = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, app_key) as app_key_val:
                            exe_path, _ = winreg.QueryValueEx(app_key_val, "")
                            name = app_key.lower().replace(".exe", "")
                            if name not in apps:
                                apps[name] = {
                                    "exe": exe_path,
                                    "display_name": app_key,
                                    "source": "registry"
                                }
                    except OSError:
                        continue
        except OSError:
            continue

    # 2. System PATH (shutil.which) - only for common ones or if not in registry
    # We won't flood it, but ensure essentials are captured
    for common in ["code", "cmd", "powershell", "notepad", "calc"]:
        if common not in apps:
            found = shutil.which(common)
            if found:
                apps[common] = {"exe": found, "display_name": common, "source": "path"}
                
    return apps

def refresh_app_cache():
    """Refreshes and saves the dynamic app registry."""
    apps = scan_windows_apps()
    reg_file = get_dynamic_app_registry_file()
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    with open(reg_file, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2)
    return apps
