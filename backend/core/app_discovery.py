import sys
import shutil
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import winreg
except ImportError:
    winreg = None


def get_dynamic_app_registry_file() -> Path:
    # Use the established data directory
    return Path(__file__).resolve().parent.parent / "data" / "dynamic_app_registry.json"


def scan_windows_apps() -> Dict[str, Dict[str, str]]:
    """
    Dynamically scans installed applications and system PATH across Windows, macOS, and Linux.
    Returns a mapping of lowercase alias to metadata (exe, display_name, source).
    """
    apps: Dict[str, Dict[str, str]] = {}

    if os.name == "nt" and winreg is not None:
        # 1. Windows Registry: App Paths
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
        common_bins = ["code", "cmd", "powershell", "notepad", "calc"]
    elif sys.platform == "darwin":
        # macOS: /Applications and ~/Applications
        for app_dir in [Path("/Applications"), Path.home() / "Applications"]:
            if app_dir.exists():
                for bundle in app_dir.glob("*.app"):
                    alias = bundle.stem.lower()
                    apps[alias] = {"exe": str(bundle), "display_name": bundle.stem, "source": "macos_apps"}
        common_bins = ["code", "open", "zsh", "bash", "python3"]
    else:
        # Linux: .desktop entries
        for desktop_dir in [Path("/usr/share/applications"), Path.home() / ".local/share/applications"]:
            if desktop_dir.exists():
                for df in desktop_dir.glob("*.desktop"):
                    alias = df.stem.lower()
                    apps[alias] = {"exe": df.stem, "display_name": df.stem, "source": "desktop_entry"}
        common_bins = ["code", "firefox", "google-chrome", "chromium", "gnome-terminal", "bash", "python3"]

    # System PATH lookup
    for common in common_bins:
        if common not in apps:
            found = shutil.which(common)
            if found:
                apps[common] = {"exe": found, "display_name": common, "source": "path"}

    return apps


scan_system_apps = scan_windows_apps

def refresh_app_cache():
    """Refreshes and saves the dynamic app registry."""
    apps = scan_windows_apps()
    reg_file = get_dynamic_app_registry_file()
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    with open(reg_file, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2)
    return apps
