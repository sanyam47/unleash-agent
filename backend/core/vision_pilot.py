"""
Vision Pilot - Phase 3: Multi-Modal Vision & Screen Perception for Jarvis AI Assistant.

Enables Jarvis to:
1. Capture high-resolution desktop and application screenshots (Win32 GDI / PIL / DirectX).
2. Perceive active open GUI application windows and their titles in <10ms (WinSta0 Win32 Enum).
3. Focus / bring windows to the foreground via native SwitchToThisWindow and SetForegroundWindow.
4. Analyze screen content, terminal traces, UI layouts, diagrams, and live apps
   using Cloud Gemini Vision (gemini-3.5-flash-lite / gemini-3.8-flash / flash-latest)
   or local Moondream VLM.
"""

import os
import sys
import time
import json
import base64
import subprocess
import csv
import io
import ctypes
from ctypes import wintypes
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Paths
SCREENSHOT_DIR = Path("backend/data/browser_screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_desktop_station():
    """Attaches current thread to interactive desktop WinSta0\\Default if running in subshell."""
    try:
        user32 = ctypes.windll.user32
        WINSTA_ALL = 0x37F
        DESKTOP_ALL = 0x1FF
        hwinsta = user32.OpenWindowStationW("WinSta0", False, WINSTA_ALL)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)
            hdesk = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
    except Exception:
        pass


def capture_desktop(output_filename: Optional[str] = None, region: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Captures the primary desktop screen using high-speed Win32 GDI / PIL ImageGrab.
    
    Args:
        output_filename: Optional custom filename (e.g. 'my_screen.png').
        region: Optional [left, top, width, height] bounding box.
        
    Returns:
        dict with success, path, width, height, and timestamp.
    """
    _ensure_desktop_station()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = output_filename or f"desktop_{ts}.png"
    if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
        fname += ".png"
    target_path = SCREENSHOT_DIR / fname
    abs_path = str(target_path.resolve())

    width = 1920
    height = 1080
    captured = False
    err_notes = []

    # Attempt 1: Win32 GDI Capture (ultra-fast sub-100ms)
    try:
        from PIL import Image

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        height = user32.GetSystemMetrics(1)  # SM_CYSCREEN

        hdesktop = user32.GetDesktopWindow()
        hdesktop_dc = user32.GetWindowDC(hdesktop)
        hmem_dc = gdi32.CreateCompatibleDC(hdesktop_dc)
        hbitmap = gdi32.CreateCompatibleBitmap(hdesktop_dc, width, height)

        gdi32.SelectObject(hmem_dc, hbitmap)
        SRCCOPY = 0x00CC0020
        CAPTUREBLT = 0x40000000
        gdi32.BitBlt(hmem_dc, 0, 0, width, height, hdesktop_dc, 0, 0, SRCCOPY | CAPTUREBLT)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = width
        bi.biHeight = -height
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0

        buffer_size = width * height * 4
        buf = (ctypes.c_char * buffer_size)()
        gdi32.GetDIBits(hdesktop_dc, hbitmap, 0, height, buf, ctypes.byref(bi), 0)

        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hmem_dc)
        user32.ReleaseDC(hdesktop, hdesktop_dc)

        img = Image.frombytes("RGBA", (width, height), buf, "raw", "BGRA")
        img = img.convert("RGB")

        if region and len(region) == 4:
            rx, ry, rw, rh = region
            img = img.crop((rx, ry, rx + rw, ry + rh))
            width, height = img.size

        img.save(abs_path)
        captured = True
    except Exception as e:
        err_notes.append(f"GDI: {e}")

    # Attempt 2: PIL ImageGrab fallback
    if not captured:
        try:
            from PIL import ImageGrab
            bbox = (region[0], region[1], region[0] + region[2], region[1] + region[3]) if region else None
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
            img.save(abs_path)
            width, height = img.size
            captured = True
        except Exception as e:
            err_notes.append(f"ImageGrab: {e}")

    if not captured or not os.path.exists(abs_path):
        return {
            "success": False,
            "error": f"Failed to capture screen: {'; '.join(err_notes)}",
            "path": None
        }

    return {
        "success": True,
        "path": abs_path,
        "filename": fname,
        "width": width,
        "height": height,
        "timestamp": ts,
        "message": f"Desktop screen captured successfully ({width}x{height}) to {fname}"
    }


def list_open_windows(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Perceives all currently open interactive GUI application windows on the desktop.
    Uses ultra-fast native Win32 EnumWindows on WinSta0 (sub-10ms latency).
    Filters out system noise, background helpers, and invisible daemons.
    """
    _ensure_desktop_station()

    ignored_titles = {
        "n/a", "olemainthreadwndname", "default ime", "msctfime ui",
        "system resource meter", "d3dgear", "gdi+ window", "hidden",
        "program manager", "windows input experience"
    }

    windows = []
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title and title.lower() not in ignored_titles:
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                        # Query Process executable name
                        proc_name = "Application"
                        hproc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
                        if hproc:
                            pbuf = ctypes.create_unicode_buffer(1024)
                            size = wintypes.DWORD(1024)
                            if kernel32.QueryFullProcessImageNameW(hproc, 0, pbuf, ctypes.byref(size)):
                                proc_name = os.path.basename(pbuf.value)
                            kernel32.CloseHandle(hproc)

                        # Category classification
                        proc_lower = proc_name.lower()
                        title_lower = title.lower()
                        cat = "Application"
                        if any(b in proc_lower for b in ["chrome", "msedge", "brave", "firefox"]):
                            cat = "Web Browser"
                        elif any(e in proc_lower for e in ["code", "devenv", "notepad", "sublime", "pycharm"]):
                            cat = "Code Editor / IDE"
                        elif any(c in proc_lower or c in title_lower for c in ["whatsapp", "discord", "slack", "telegram", "teams"]):
                            cat = "Communication / Messaging"
                        elif any(t in proc_lower for t in ["windowsterminal", "cmd", "powershell", "mintty", "conhost"]):
                            cat = "Terminal / Shell"
                        elif any(m in proc_lower for m in ["spotify", "vlc", "wmplayer"]):
                            cat = "Media Player"

                        windows.append({
                            "hwnd": hwnd,
                            "process": proc_name,
                            "pid": pid.value,
                            "window_title": title,
                            "category": cat
                        })
            return True

        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(CMPFUNC(enum_cb), 0)

        return {
            "success": True,
            "count": len(windows),
            "windows": windows,
            "message": f"Found {len(windows)} active desktop window(s)."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "windows": []
        }


def focus_window(title_or_pid: str) -> Dict[str, Any]:
    """
    Brings an open window to the foreground by matching its window title, process name, or PID.
    Uses native Win32 SwitchToThisWindow and SetForegroundWindow.
    """
    target = str(title_or_pid).strip()
    if not target:
        return {"success": False, "error": "Target window title or PID cannot be empty."}

    _ensure_desktop_station()
    listing = list_open_windows()
    matched = None
    target_lower = target.lower()

    if listing.get("success"):
        for w in listing.get("windows", []):
            if (target_lower in w["window_title"].lower() or 
                target_lower in w["process"].lower() or 
                target == str(w["pid"])):
                matched = w
                break

    if not matched:
        return {
            "success": False,
            "error": f"No open window matching '{target}' found.",
            "target": target
        }

    hwnd = matched["hwnd"]
    user32 = ctypes.windll.user32
    try:
        # Restore if minimized
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        # Bring to foreground
        user32.SwitchToThisWindow(hwnd, True)
        user32.SetForegroundWindow(hwnd)
        success = True
    except Exception as e:
        success = False

    return {
        "success": success,
        "target": target,
        "matched_window": matched,
        "message": f"Brought window '{matched['window_title']}' ({matched['process']}) to focus."
    }


def analyze_screen_vision(
    image_path: Optional[str] = None,
    prompt: Optional[str] = None,
    region: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Analyzes desktop or image content using Cloud Gemini Vision or local Moondream VLM.
    If image_path is None, captures current desktop screen automatically.
    
    Args:
        image_path: Path to existing screenshot / image (or None to capture live).
        prompt: Specific question or instruction (e.g. 'Read the error in the terminal').
        region: Optional [left, top, width, height] crop.
        
    Returns:
        dict with success, analysis, image_path, and model used.
    """
    actual_path = image_path
    if not actual_path:
        cap = capture_desktop(region=region)
        if not cap.get("success"):
            return {
                "success": False,
                "error": f"Failed to capture screen for vision analysis: {cap.get('error')}"
            }
        actual_path = cap["path"]

    if not os.path.isabs(actual_path):
        actual_path = str(Path(actual_path).resolve())

    if not os.path.exists(actual_path):
        return {
            "success": False,
            "error": f"Screenshot image not found at {actual_path}"
        }

    try:
        with open(actual_path, "rb") as f:
            img_bytes = f.read()
    except Exception as e:
        return {"success": False, "error": f"Failed to read image file: {e}"}

    query_prompt = prompt or (
        "Analyze this desktop screenshot in detail. "
        "Describe: 1. Active applications and windows. "
        "2. Any visible error messages, terminal stack traces, or code snippets verbatim. "
        "3. UI layout, open tabs, and user activity."
    )

    # Tier 1: Cloud Gemini Vision via google-genai (prioritizing fast flash models)
    try:
        from backend.core.gemini_client import gemini_available, _get_client
        if gemini_available():
            client = _get_client()
            from google.genai import types
            part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.0-flash", "gemini-flash-latest"]
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[part, query_prompt]
                    )
                    txt = (response.text or "").strip()
                    if txt:
                        return {
                            "success": True,
                            "analysis": txt,
                            "image_path": actual_path,
                            "model_used": f"Cloud Gemini ({model_name})"
                        }
                except Exception as m_err:
                    continue
    except Exception as e:
        pass

    # Tier 2: Local Moondream VLM on Ollama
    try:
        import urllib.request
        from backend.core.llm_service import get_ollama_base_url
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        payload = {
            "model": "moondream:latest",
            "messages": [
                {
                    "role": "user",
                    "content": query_prompt,
                    "images": [b64_img]
                }
            ],
            "stream": False
        }
        req = urllib.request.Request(
            f"{get_ollama_base_url()}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return {
                    "success": True,
                    "analysis": content,
                    "image_path": actual_path,
                    "model_used": "Local Moondream VLM"
                }
    except Exception as e:
        pass

    return {
        "success": False,
        "error": "Both Cloud Gemini Vision and Local Moondream VLM were unavailable.",
        "image_path": actual_path
    }
