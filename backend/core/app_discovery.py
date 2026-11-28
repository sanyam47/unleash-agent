import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import winreg
except ImportError:
    winreg = None

_CACHE_TTL_SECONDS = 24 * 3600


def get_dynamic_app_registry_file() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "dynamic_app_registry.json"


def _normalize_app_key(name: str) -> str:
    clean = re.sub(r"[^\w\s]", " ", (name or "").lower())
    return re.sub(r"\s+", " ", clean).strip()


def _scan_start_menu_shortcuts(apps: Dict[str, Dict[str, str]]) -> None:
    """Indexes Windows Start Menu .lnk shortcuts dynamically."""
    roots = []
    for env_key in ("ProgramData", "APPDATA"):
        base = os.environ.get(env_key)
        if base:
            p = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            if p.exists():
                roots.append(p)

    for root in roots:
        try:
            for lnk in root.rglob("*.lnk"):
                stem = lnk.stem.strip()
                norm = _normalize_app_key(stem)
                if not norm or "uninstall" in norm or "readme" in norm or "help" in norm:
                    continue
                if norm not in apps:
                    apps[norm] = {
                        "shortcut": str(lnk),
                        "display_name": stem,
                        "source": "start_menu",
                    }
        except OSError:
            continue


def _scan_windows_start_apps(apps: Dict[str, Dict[str, str]]) -> None:
    """Queries Windows Get-StartApps (includes Microsoft Store / UWP apps like WhatsApp) dynamically."""
    try:
        c_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=c_flags,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return
        raw = json.loads(proc.stdout.strip())
        entries = raw if isinstance(raw, list) else [raw]
        for item in entries:
            if not isinstance(item, dict):
                continue
            disp = str(item.get("Name") or "").strip()
            app_id = str(item.get("AppID") or "").strip()
            norm = _normalize_app_key(disp)
            if not norm or not app_id or "uninstall" in norm:
                continue
            # Prefer real Store/UWP app_id when present
            if norm not in apps or apps[norm].get("source") == "path":
                apps[norm] = {
                    "app_id": app_id,
                    "display_name": disp,
                    "source": "startapps",
                }
    except Exception:
        pass


def scan_windows_apps() -> Dict[str, Dict[str, str]]:
    """
    Dynamically scans installed applications across Registry App Paths, Start Menu shortcuts,
    Windows StartApps/UWP packages, and system PATH.
    """
    apps: Dict[str, Dict[str, str]] = {}

    if os.name == "nt" and winreg is not None:
        # 1. Windows Registry: App Paths
        paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]
        for hkey, subkey in paths:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            app_key = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, app_key) as app_key_val:
                                exe_path, _ = winreg.QueryValueEx(app_key_val, "")
                                name = _normalize_app_key(app_key.lower().replace(".exe", ""))
                                if name and name not in apps:
                                    apps[name] = {
                                        "exe": exe_path,
                                        "display_name": app_key.replace(".exe", "").replace(".EXE", ""),
                                        "source": "registry",
                                    }
                        except OSError:
                            continue
            except OSError:
                continue

        # 2. Start Menu .lnk shortcuts & installed UWP/Store apps
        _scan_start_menu_shortcuts(apps)
        _scan_windows_start_apps(apps)
        common_bins = ["code", "cmd", "powershell", "notepad", "calc", "wt", "explorer", "chrome", "msedge", "brave"]
    elif sys.platform == "darwin":
        for app_dir in [Path("/Applications"), Path.home() / "Applications"]:
            if app_dir.exists():
                for bundle in app_dir.glob("*.app"):
                    alias = _normalize_app_key(bundle.stem)
                    if alias:
                        apps[alias] = {"exe": str(bundle), "display_name": bundle.stem, "source": "macos_apps"}
        common_bins = ["code", "open", "zsh", "bash", "python3"]
    else:
        for desktop_dir in [Path("/usr/share/applications"), Path.home() / ".local/share/applications"]:
            if desktop_dir.exists():
                for df in desktop_dir.glob("*.desktop"):
                    alias = _normalize_app_key(df.stem)
                    if alias:
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


def find_best_app_match(query: str, registry: Dict[str, Dict[str, Any]]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Matches a natural app request (e.g. 'whatsapp', 'vs code', 'calculator') against
    discovered apps using exact, compact, word-token, and safe similarity matching.
    """
    q = _normalize_app_key(query)
    if not q or not registry:
        return None

    # 1. Exact key or display_name match
    if q in registry:
        return q, registry[q]
    for k, meta in registry.items():
        if _normalize_app_key(meta.get("display_name", "")) == q:
            return k, meta

    # 2. Space-insensitive match ('vs code' == 'vscode', 'whats app' == 'whatsapp')
    q_compact = q.replace(" ", "")
    for k, meta in registry.items():
        if k.replace(" ", "") == q_compact or _normalize_app_key(meta.get("display_name", "")).replace(" ", "") == q_compact:
            return k, meta

    # 3. Clean whole-word token prefix/containment (prefer shortest matching display/key)
    token_hits = []
    for k, meta in registry.items():
        words = k.split()
        if q in words or (len(q) >= 4 and k.startswith(q + " ")):
            token_hits.append((len(k), k, meta))
    if token_hits:
        token_hits.sort(key=lambda item: item[0])
        _, k, meta = token_hits[0]
        return k, meta

    # 4. Safe fuzzy match against discovered app keys
    if len(q) >= 4:
        close = difflib.get_close_matches(q, list(registry.keys()), n=1, cutoff=0.78)
        if close:
            k = close[0]
            return k, registry[k]
    return None


def refresh_app_cache(force: bool = False) -> Dict[str, Dict[str, str]]:
    """Loads cached dynamic app registry if fresh (<24h), otherwise rescans OS apps."""
    reg_file = get_dynamic_app_registry_file()
    if not force and reg_file.exists():
        try:
            age = time.time() - reg_file.stat().st_mtime
            if age < _CACHE_TTL_SECONDS:
                with open(reg_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, dict) and cached:
                    return cached
        except Exception:
            pass

    apps = scan_windows_apps()
    try:
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)
    except Exception:
        pass
    return apps
