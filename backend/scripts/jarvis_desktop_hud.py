"""
Jarvis Floating Gyroscopic Sphere HUD - Always-On-Top Windows Per-Pixel Alpha Overlay

Features:
1. True 32-bit Per-Pixel Alpha layered window (zero dark rectangle, zero jagged edges).
2. Always-On-Top without stealing focus (WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE).
3. Continuous 3D Gyroscopic Core animation + Jarvis-style reactive "pop" when speaking/responding.
4. System-wide Global Hotkey (`Ctrl+Shift+Space`, plus fallback `Ctrl+Alt+J`) to summon/hide anywhere.
5. Independent user-controlled Mic toggle (left-click sphere):
   - Hiding the sphere pauses all UI rendering/polling (`0%` UI CPU) while leaving
     background tasks and the user's Mic ON/OFF choice completely untouched.
6. Works both synced with FastAPI (`http://127.0.0.1:8001`) and standalone in-process if server is offline.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.gyro_sphere_renderer import GyroSphereRenderer, SphereVisualState


BACKEND_URL = os.getenv("UNLEASH_HUD_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
STATE_FILE = PROJECT_ROOT / "backend" / "data" / "voice_profiles" / "hud_state.json"
HUD_IPC_HOST = "127.0.0.1"
HUD_IPC_PORT = int(os.getenv("UNLEASH_HUD_IPC_PORT", "48001"))

WINDOW_CLASS = "UnleashGyroSphereHUDWindow"
WINDOW_TITLE = "Unleash Gyro Sphere HUD"
MUTEX_NAME = "Local\\UnleashAgentGyroSphereHUDMutex"

# Win32 constants
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

WM_DESTROY = 0x0002
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_MOUSELEAVE = 0x02A3
WM_HOTKEY = 0x0312
WM_APP = 0x8000
WM_USER_SHOW = WM_APP + 1
WM_USER_HIDE = WM_APP + 2
WM_USER_QUIT = WM_APP + 3
WM_TRAYICON = WM_APP + 10

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
VK_J = 0x4A

HOTKEY_PRIMARY_ID = 1      # Ctrl + Shift + Space
HOTKEY_SECONDARY_ID = 2    # Ctrl + Alt + J

SW_HIDE = 0
SW_SHOWNA = 8
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_RIGHTBUTTON = 0x0002

MENU_TOGGLE_MIC = 1001
MENU_BARGE_IN = 1002
MENU_OPEN_STUDIO = 1003
MENU_HIDE = 1004
MENU_QUIT = 1005
MENU_QUIT_APP = 1006

TIMER_FRAME_ID = 1
FRAME_INTERVAL_MS = 33  # ~30 FPS when visible; stopped completely when hidden


# Win32 ctypes structures
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


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


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HANDLE),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("hwndTrack", wintypes.HWND),
        ("dwHoverTime", wintypes.DWORD),
    ]


def _setup_win32_api():
    """Configures explicit 64-bit safe argtypes/restypes for Win32 API functions."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t

    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND

    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND

    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.PostMessageW.restype = wintypes.BOOL

    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
        wintypes.HDC, ctypes.POINTER(POINT), wintypes.COLORREF,
        ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL

    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.TrackMouseEvent.argtypes = [ctypes.POINTER(TRACKMOUSEEVENT)]

    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
    gdi32.CreateBitmap.restype = wintypes.HBITMAP
    user32.CreateIconIndirect.argtypes = [ctypes.c_void_p]
    user32.CreateIconIndirect.restype = wintypes.HICON
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.DestroyIcon.restype = wintypes.BOOL
    ctypes.windll.shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]
    ctypes.windll.shell32.Shell_NotifyIconW.restype = wintypes.BOOL

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    return user32, gdi32, kernel32


def load_hud_prefs() -> Dict[str, Any]:
    """Loads persisted floating sphere coordinates and user preferences."""
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_hud_prefs(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Saves HUD position cleanly without touching voice config."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cur = load_hud_prefs()
        cur.update(updates)
        STATE_FILE.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        return cur
    except Exception:
        return {}


def rgba_to_premultiplied_bgra(img: Image.Image, hit_radius_px: int = 38) -> bytes:
    """
    Converts an RGBA PIL Image to Windows premultiplied BGRA DIB bytes.
    Also enforces tiny alpha >= 2 within `hit_radius_px` so clicks inside open gaps
    between orbital rings still hit the floating sphere cleanly without visible background box.
    """
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    h, w, _ = arr.shape
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    yy, xx = np.mgrid[0:h, 0:w]
    dist_sq = (xx - cx) ** 2 + (yy - cy) ** 2
    inside_hit = (dist_sq <= (hit_radius_px ** 2)) & (arr[:, :, 3] < 2)
    arr[inside_hit, 3] = 2

    a = arr[:, :, 3:4].astype(np.uint16)
    rgb_pre = ((arr[:, :, :3].astype(np.uint16) * a) // 255).astype(np.uint8)
    bgra = np.empty_like(arr)
    bgra[:, :, 0] = rgb_pre[:, :, 2]
    bgra[:, :, 1] = rgb_pre[:, :, 1]
    bgra[:, :, 2] = rgb_pre[:, :, 0]
    bgra[:, :, 3] = arr[:, :, 3]
    return bgra.tobytes()


class BackendBridge:
    """
    Synchronizes sphere state & Mic toggles with `http://127.0.0.1:8001` when live,
    and falls back cleanly to in-process voice/task modules when running standalone.
    """

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")
        self._state_lock = threading.Lock()
        self._visual_state = SphereVisualState()
        self._server_online = False
        self._last_poll = 0.0
        self._poll_in_flight = False
        self._optimistic_mic_until = 0.0
        self._standalone_listener_active = False

    def snapshot(self) -> SphereVisualState:
        with self._state_lock:
            return SphereVisualState(
                mode=self._visual_state.mode,
                mic_active=self._visual_state.mic_active,
                speech_energy=self._visual_state.speech_energy,
                task_progress=self._visual_state.task_progress,
                active_tasks_count=self._visual_state.active_tasks_count,
                hovered=self._visual_state.hovered,
            )

    def set_hovered(self, hovered: bool):
        with self._state_lock:
            self._visual_state.hovered = hovered

    def _http_json(self, path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, timeout: float = 0.8) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        headers = {}
        data_bytes = None
        token = os.getenv("UNLEASH_API_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def poll_once(self) -> SphereVisualState:
        """Fetches fresh state from backend or standalone in-process modules."""
        data: Optional[Dict[str, Any]] = None
        try:
            data = self._http_json("/api/daemon/hud/state", timeout=0.6)
            self._server_online = True
            # Hand off in-process mic listener cleanly if FastAPI server just came online
            if self._standalone_listener_active:
                try:
                    from backend.core.wake_word_listener import stop_native_wake_word_daemon
                    stop_native_wake_word_daemon()
                except Exception:
                    pass
                self._standalone_listener_active = False
        except Exception:
            self._server_online = False
            data = self._poll_standalone()

        if isinstance(data, dict):
            with self._state_lock:
                # Preserve immediate click toggle briefly so rapid poll never flickers old state back
                if time.monotonic() >= self._optimistic_mic_until:
                    self._visual_state.mic_active = bool(data.get("mic_active", False))
                mode = str(data.get("duplex_state", "IDLE")).upper()
                if data.get("is_speaking"):
                    mode = "SPEAKING"
                elif mode == "IDLE" and self._visual_state.mic_active and data.get("is_listening"):
                    mode = "LISTENING"
                elif mode == "IDLE" and int(data.get("active_tasks_count", 0)) > 0:
                    mode = "THINKING"
                self._visual_state.mode = mode
                self._visual_state.speech_energy = float(data.get("speech_energy", 0.0) or 0.0)
                self._visual_state.active_tasks_count = int(data.get("active_tasks_count", 0) or 0)
                self._visual_state.task_progress = float(data.get("top_task_progress", 0.0) or 0.0)
        return self.snapshot()

    def maybe_poll_async(self):
        """Non-blocking throttled poll: fast (90ms) when active/speaking, gentle (450ms) when idle."""
        now = time.monotonic()
        st = self.snapshot()
        interval = 0.09 if (st.mode in ("SPEAKING", "THINKING", "LISTENING") or st.mic_active or st.active_tasks_count > 0) else 0.45
        if self._poll_in_flight or (now - self._last_poll) < interval:
            return
        self._poll_in_flight = True
        self._last_poll = now

        def _worker():
            try:
                self.poll_once()
            finally:
                self._poll_in_flight = False

        threading.Thread(target=_worker, daemon=True).start()

    def _poll_standalone(self) -> Dict[str, Any]:
        """Direct in-process fallback when Web Studio server is stopped."""
        mic_active = False
        duplex: Dict[str, Any] = {"is_listening": False, "is_speaking": False, "duplex_state": "IDLE", "speech_energy": 0.0}
        active_tasks: list = []
        try:
            from backend.core.voice_pilot import load_voice_config
            mic_active = bool(load_voice_config().get("wake_word_enabled", False))
        except Exception:
            pass
        try:
            from backend.core.wake_word_listener import get_duplex_listener_status
            duplex = get_duplex_listener_status()
        except Exception:
            pass
        try:
            from backend.core.task_daemon import list_active_tasks
            active_tasks = list_active_tasks()
        except Exception:
            pass
        top = active_tasks[0] if active_tasks else None
        return {
            "mic_active": mic_active,
            "is_listening": bool(duplex.get("is_listening", False)),
            "is_speaking": bool(duplex.get("is_speaking", False)),
            "duplex_state": duplex.get("duplex_state", "IDLE"),
            "speech_energy": float(duplex.get("speech_energy", 0.0) or 0.0),
            "active_tasks_count": len(active_tasks),
            "top_task_progress": float(top.get("progress", 0.0)) if top else 0.0,
        }

    def toggle_mic_async(self) -> bool:
        """Optimistically flips user Mic state and syncs cleanly without changing HUD visibility."""
        with self._state_lock:
            new_state = not self._visual_state.mic_active
            self._visual_state.mic_active = new_state
            if new_state and self._visual_state.mode == "IDLE":
                self._visual_state.mode = "LISTENING"
            elif not new_state and self._visual_state.mode == "LISTENING":
                self._visual_state.mode = "IDLE"
            self._optimistic_mic_until = time.monotonic() + 1.5

        def _worker():
            try:
                res = self._http_json("/api/voice/toggle_mic", method="POST", payload={"active": new_state}, timeout=2.0)
                if isinstance(res, dict) and "mic_active" in res:
                    with self._state_lock:
                        self._visual_state.mic_active = bool(res["mic_active"])
                return
            except Exception:
                pass
            # Standalone fallback
            try:
                from backend.core.voice_pilot import update_voice_config
                from backend.core.wake_word_listener import start_native_wake_word_daemon, stop_native_wake_word_daemon
                update_voice_config({"wake_word_enabled": new_state})
                if new_state:
                    start_native_wake_word_daemon(in_background=True)
                    self._standalone_listener_active = True
                else:
                    stop_native_wake_word_daemon()
                    self._standalone_listener_active = False
            except Exception as e:
                print(f"[Gyro HUD Standalone Mic Notice]: {e}")

        threading.Thread(target=_worker, daemon=True).start()
        return new_state

    def trigger_barge_in_async(self):
        def _worker():
            try:
                self._http_json("/api/voice/stop", method="POST", payload={}, timeout=1.0)
                return
            except Exception:
                pass
            try:
                from backend.core.voice_pilot import stop_speaking
                stop_speaking()
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()


class JarvisFloatingHUD:
    """
    Native Windows Per-Pixel Alpha Floating Gyroscopic Sphere HUD.
    Maintains compatibility with `JarvisFloatingHUD` / `launch_jarvis_hud`.
    """

    def __init__(self, start_visible: bool = True, size: int = 104):
        self.user32, self.gdi32, self.kernel32 = _setup_win32_api()
        self._enable_dpi_awareness()

        self.render_size = int(size)
        self.scale = self._get_dpi_scale()
        self.win_size = max(96, min(148, int(round(96 * self.scale))))
        self.renderer = GyroSphereRenderer(size=self.render_size)
        self.bridge = BackendBridge()

        self.visible = False
        self._start_visible = bool(start_visible)
        self._hwnd: Optional[wintypes.HWND] = None
        self._last_frame_t = time.monotonic()

        # Drag vs click state
        self._mouse_down = False
        self._drag_moved = False
        self._down_cursor = (0, 0)
        self._down_win_pos = (0, 0)
        self._tracking_hover = False
        self._pos_x, self._pos_y = self._initial_position()

        # Keep WNDPROC reference alive so GC never frees callback
        self._wndproc_ref = WNDPROC(self._wnd_proc)
        self._tray_icon_handle: Optional[wintypes.HICON] = None
        self._tray_added = False
        self._ipc_stop = threading.Event()
        self._ipc_sock: Optional[socket.socket] = None
        self._create_window()
        self._register_hotkeys()
        self._add_tray_icon()
        self._start_ipc_server()

    @staticmethod
    def _enable_dpi_awareness():
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def _get_dpi_scale(self) -> float:
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
            return max(1.0, min(1.75, float(dpi) / 96.0))
        except Exception:
            return 1.0

    def _initial_position(self) -> Tuple[int, int]:
        vx = self.user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        vy = self.user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        vw = self.user32.GetSystemMetrics(78) or self.user32.GetSystemMetrics(0)
        vh = self.user32.GetSystemMetrics(79) or self.user32.GetSystemMetrics(1)
        sw = self.user32.GetSystemMetrics(0)
        sh = self.user32.GetSystemMetrics(1)
        prefs = load_hud_prefs()
        px = prefs.get("x")
        py = prefs.get("y")
        if isinstance(px, int) and isinstance(py, int) and vx <= px <= (vx + vw - 40) and vy <= py <= (vy + vh - 40):
            return px, py
        # Default bottom-right sleek floating spot above taskbar
        return sw - self.win_size - 28, sh - self.win_size - 64

    def _create_window(self):
        hinst = self.kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.hCursor = self.user32.LoadCursorW(None, 32512)  # IDC_ARROW
        wc.lpszClassName = WINDOW_CLASS
        self.user32.RegisterClassExW(ctypes.byref(wc))

        ex_style = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = self.user32.CreateWindowExW(
            ex_style,
            WINDOW_CLASS,
            WINDOW_TITLE,
            WS_POPUP,
            self._pos_x,
            self._pos_y,
            self.win_size,
            self.win_size,
            None,
            None,
            hinst,
            None,
        )
        if not self._hwnd:
            raise RuntimeError("Failed to create Win32 layered window for Jarvis Gyro Sphere HUD.")

    def _register_hotkeys(self):
        if not self._hwnd:
            return
        # Primary: Ctrl + Shift + Space
        ok_primary = self.user32.RegisterHotKey(self._hwnd, HOTKEY_PRIMARY_ID, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_SPACE)
        # Secondary optional shortcut: Ctrl + Alt + J
        self.user32.RegisterHotKey(self._hwnd, HOTKEY_SECONDARY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_J)
        if not ok_primary:
            print("[Gyro HUD Notice]: Primary hotkey Ctrl+Shift+Space already in use; Ctrl+Alt+J remains active.")

    def _unregister_hotkeys(self):
        if not self._hwnd:
            return
        self.user32.UnregisterHotKey(self._hwnd, HOTKEY_PRIMARY_ID)
        self.user32.UnregisterHotKey(self._hwnd, HOTKEY_SECONDARY_ID)

    def _push_frame_to_window(self, rgba_img: Image.Image):
        """Uploads 32-bit premultiplied BGRA bitmap cleanly to Win32 UpdateLayeredWindow (zero GDI leak)."""
        if not self._hwnd:
            return
        if rgba_img.size != (self.win_size, self.win_size):
            resample = getattr(Image, "Resampling", Image).LANCZOS
            rgba_img = rgba_img.resize((self.win_size, self.win_size), resample)

        hit_r = int(round(38 * (self.win_size / 104.0)))
        bgra_bytes = rgba_to_premultiplied_bgra(rgba_img, hit_radius_px=hit_r)

        screen_dc = None
        mem_dc = None
        hbmp = None
        old_bmp = None
        try:
            screen_dc = self.user32.GetDC(None)
            if not screen_dc:
                return
            mem_dc = self.gdi32.CreateCompatibleDC(screen_dc)
            if not mem_dc:
                return

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = self.win_size
            bmi.biHeight = -self.win_size  # Top-down DIB
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = DIB_RGB_COLORS

            bits_ptr = ctypes.c_void_p()
            hbmp = self.gdi32.CreateDIBSection(screen_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits_ptr), None, 0)
            if not hbmp or not bits_ptr.value:
                return

            old_bmp = self.gdi32.SelectObject(mem_dc, hbmp)
            ctypes.memmove(bits_ptr, bgra_bytes, len(bgra_bytes))

            pt_dst = POINT(self._pos_x, self._pos_y)
            pt_src = POINT(0, 0)
            sz = SIZE(self.win_size, self.win_size)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

            ok_ulw = self.user32.UpdateLayeredWindow(
                self._hwnd,
                screen_dc,
                ctypes.byref(pt_dst),
                ctypes.byref(sz),
                mem_dc,
                ctypes.byref(pt_src),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            )
            if not ok_ulw:
                err = self.kernel32.GetLastError()
                if not getattr(self, "_ulw_warned", False):
                    self._ulw_warned = True
                    print(f"[Gyro HUD Warning]: UpdateLayeredWindow failed (winerr={err})")
        finally:
            if mem_dc and old_bmp:
                self.gdi32.SelectObject(mem_dc, old_bmp)
            if hbmp:
                self.gdi32.DeleteObject(hbmp)
            if mem_dc:
                self.gdi32.DeleteDC(mem_dc)
            if screen_dc:
                self.user32.ReleaseDC(None, screen_dc)

    def _render_tick(self):
        if not self.visible:
            return
        now = time.monotonic()
        dt = now - self._last_frame_t
        self._last_frame_t = now

        self.bridge.maybe_poll_async()
        st = self.bridge.snapshot()
        frame = self.renderer.render_frame(st, dt=dt)
        self._push_frame_to_window(frame)

    def show(self):
        """Summons the floating sphere immediately (<15ms) without blocking on network or disturbing tasks/mic."""
        if not self._hwnd:
            return
        if not self._tray_added:
            self._add_tray_icon()
        self.visible = True
        self._last_frame_t = time.monotonic()
        self.renderer.trigger_click_impulse()
        # Instant non-blocking local snapshot + async server sync
        frame = self.renderer.render_frame(self.bridge.snapshot(), dt=1 / 30.0)
        self._push_frame_to_window(frame)
        self.user32.ShowWindow(self._hwnd, SW_SHOWNA)
        self.user32.SetWindowPos(self._hwnd, HWND_TOPMOST, self._pos_x, self._pos_y, self.win_size, self.win_size, SWP_NOACTIVATE)
        self.user32.SetTimer(self._hwnd, TIMER_FRAME_ID, FRAME_INTERVAL_MS, None)
        # Immediately schedule non-blocking sync
        self.bridge._last_poll = 0.0
        self.bridge.maybe_poll_async()

    def hide(self):
        """Hides the floating sphere and pauses rendering (`0%` UI CPU) without touching Mic state."""
        if not self._hwnd:
            return
        self.visible = False
        self.user32.KillTimer(self._hwnd, TIMER_FRAME_ID)
        self.user32.ShowWindow(self._hwnd, SW_HIDE)
        save_hud_prefs({"x": int(self._pos_x), "y": int(self._pos_y)})

    def toggle_visibility(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def _show_context_menu(self):
        if not self._hwnd:
            return
        st = self.bridge.snapshot()
        menu = self.user32.CreatePopupMenu()
        mic_label = "Turn Mic OFF" if st.mic_active else "Turn Mic ON"
        self.user32.AppendMenuW(menu, MF_STRING, MENU_TOGGLE_MIC, mic_label)
        if st.mode == "SPEAKING":
            self.user32.AppendMenuW(menu, MF_STRING, MENU_BARGE_IN, "Stop Speaking")
        self.user32.AppendMenuW(menu, MF_STRING, MENU_OPEN_STUDIO, "Open Unleash Studio")
        self.user32.AppendMenuW(menu, MF_STRING, MENU_HIDE, "Hide Sphere (Ctrl+Shift+Space)")
        self.user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        self.user32.AppendMenuW(menu, MF_STRING, MENU_QUIT, "Quit Sphere Only")
        self.user32.AppendMenuW(menu, MF_STRING, MENU_QUIT_APP, "Quit Unleash App")

        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        self.user32.SetForegroundWindow(self._hwnd)
        cmd = self.user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON, pt.x, pt.y, 0, self._hwnd, None)
        self.user32.DestroyMenu(menu)

        if cmd == MENU_TOGGLE_MIC:
            self.renderer.trigger_click_impulse()
            self.bridge.toggle_mic_async()
        elif cmd == MENU_BARGE_IN:
            self.bridge.trigger_barge_in_async()
        elif cmd == MENU_OPEN_STUDIO:
            webbrowser.open(BACKEND_URL)
        elif cmd == MENU_HIDE:
            self.hide()
        elif cmd == MENU_QUIT:
            self.quit()
        elif cmd == MENU_QUIT_APP:
            try:
                self.bridge._http_json("/api/daemon/app/shutdown", method="POST", payload={}, timeout=0.8)
            except Exception:
                pass
            self.quit()

    def _create_tray_orb_hicon(self) -> Optional[wintypes.HICON]:
        """Generates a crisp 16x16 monochrome-cyan orb HICON for the Windows notification tray."""
        try:
            class ICONINFO(ctypes.Structure):
                _fields_ = [
                    ("fIcon", wintypes.BOOL),
                    ("xHotspot", wintypes.DWORD),
                    ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP),
                    ("hbmColor", wintypes.HBITMAP),
                ]

            size = 16
            yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
            dist = np.sqrt((xx - 7.5) ** 2 + (yy - 7.5) ** 2)
            bgra = np.zeros((size, size, 4), dtype=np.uint8)
            inside = dist <= 6.8
            ring = (dist >= 4.7) & (dist <= 6.4)
            core = dist <= 2.6
            bgra[inside, :3] = [24, 20, 17]
            bgra[inside, 3] = 240
            bgra[ring, :3] = [215, 210, 200]
            bgra[ring, 3] = 255
            bgra[core, :3] = [180, 225, 110]
            bgra[core, 3] = 255

            screen_dc = self.user32.GetDC(None)
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = size
            bmi.biHeight = -size
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = DIB_RGB_COLORS
            bits = ctypes.c_void_p()
            hbm_color = self.gdi32.CreateDIBSection(screen_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
            ctypes.memmove(bits, bgra.tobytes(), size * size * 4)
            hbm_mask = self.gdi32.CreateBitmap(size, size, 1, 1, None)

            ii = ICONINFO(True, 0, 0, hbm_mask, hbm_color)
            hicon = self.user32.CreateIconIndirect(ctypes.byref(ii))
            self.gdi32.DeleteObject(hbm_color)
            self.gdi32.DeleteObject(hbm_mask)
            self.user32.ReleaseDC(None, screen_dc)
            return hicon
        except Exception:
            return None

    def _tray_struct(self):
        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uTimeoutOrVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON),
            ]

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._tray_icon_handle or 0
        nid.szTip = "Unleash Gyro Sphere (Ctrl+Shift+Space)"
        return nid

    def _add_tray_icon(self):
        if not self._hwnd or self._tray_added:
            return
        try:
            if not self._tray_icon_handle:
                self._tray_icon_handle = self._create_tray_orb_hicon()
            nid = self._tray_struct()
            if ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
                self._tray_added = True
        except Exception:
            pass

    def _remove_tray_icon(self):
        if not self._hwnd:
            return
        try:
            if self._tray_added:
                nid = self._tray_struct()
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                self._tray_added = False
            if self._tray_icon_handle:
                self.user32.DestroyIcon(self._tray_icon_handle)
                self._tray_icon_handle = None
        except Exception:
            pass

    def _start_ipc_server(self):
        """Starts lightweight 127.0.0.1 control socket so Studio UI controls the sphere across Window Stations."""
        try:
            port = int(os.getenv("UNLEASH_HUD_IPC_PORT", str(HUD_IPC_PORT)))
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((HUD_IPC_HOST, port))
            sock.listen(4)
            sock.settimeout(0.5)
            self._ipc_sock = sock
        except Exception:
            self._ipc_sock = None
            return

        def _serve():
            while not self._ipc_stop.is_set() and self._ipc_sock is not None:
                try:
                    conn, _ = self._ipc_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                try:
                    with conn:
                        conn.settimeout(0.5)
                        cmd = conn.recv(64).decode("utf-8", errors="ignore").strip().upper()
                        resp = {"status": "ok", "running": True, "visible": bool(self.visible)}
                        if cmd == "SHOW" and self._hwnd:
                            self.user32.PostMessageW(self._hwnd, WM_USER_SHOW, 0, 0)
                            resp["visible"] = True
                        elif cmd == "HIDE" and self._hwnd:
                            self.user32.PostMessageW(self._hwnd, WM_USER_HIDE, 0, 0)
                            resp["visible"] = False
                        elif cmd == "TOGGLE" and self._hwnd:
                            nxt = not bool(self.visible)
                            self.user32.PostMessageW(self._hwnd, WM_USER_SHOW if nxt else WM_USER_HIDE, 0, 0)
                            resp["visible"] = nxt
                        elif cmd == "QUIT" and self._hwnd:
                            self.user32.PostMessageW(self._hwnd, WM_USER_QUIT, 0, 0)
                            resp["running"] = False
                        conn.sendall(json.dumps(resp).encode("utf-8"))
                except Exception:
                    pass

        threading.Thread(target=_serve, daemon=True, name="GyroHUDIPCThread").start()

    def _stop_ipc_server(self):
        self._ipc_stop.set()
        if self._ipc_sock is not None:
            try:
                self._ipc_sock.close()
            except Exception:
                pass
            self._ipc_sock = None

    def quit(self):
        if not self._hwnd:
            return
        save_hud_prefs({"x": int(self._pos_x), "y": int(self._pos_y)})
        self._stop_ipc_server()
        self.user32.KillTimer(self._hwnd, TIMER_FRAME_ID)
        self._unregister_hotkeys()
        self._remove_tray_icon()
        self.user32.DestroyWindow(self._hwnd)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            return self._wnd_proc_inner(hwnd, msg, wparam, lparam)
        except Exception:
            return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _wnd_proc_inner(self, hwnd, msg, wparam, lparam):
        if msg == WM_QUERYENDSESSION:
            return 1
        if msg == WM_ENDSESSION:
            if wparam:
                try:
                    save_hud_prefs({"x": int(self._pos_x), "y": int(self._pos_y)})
                    if self.bridge._standalone_listener_active:
                        from backend.core.wake_word_listener import stop_native_wake_word_daemon
                        stop_native_wake_word_daemon()
                except Exception:
                    pass
                self._stop_ipc_server()
                self._remove_tray_icon()
                self._unregister_hotkeys()
                self.user32.PostQuitMessage(0)
            return 0
        if msg == WM_TRAYICON:
            ev = lparam & 0xFFFF
            if ev == WM_LBUTTONUP:
                self.toggle_visibility()
            elif ev == WM_RBUTTONUP:
                self._show_context_menu()
            return 0
        if msg == WM_HOTKEY:
            self.toggle_visibility()
            return 0
        if msg == WM_USER_SHOW:
            self.show()
            return 0
        if msg == WM_USER_HIDE:
            self.hide()
            return 0
        if msg == WM_USER_QUIT:
            self.quit()
            return 0
        if msg == WM_TIMER and wparam == TIMER_FRAME_ID:
            self._render_tick()
            return 0

        if msg == WM_LBUTTONDOWN:
            pt = POINT()
            self.user32.GetCursorPos(ctypes.byref(pt))
            self._mouse_down = True
            self._drag_moved = False
            self._down_cursor = (pt.x, pt.y)
            self._down_win_pos = (self._pos_x, self._pos_y)
            self.user32.SetCapture(hwnd)
            return 0

        if msg == WM_MOUSEMOVE:
            if not self._tracking_hover:
                self._tracking_hover = True
                self.bridge.set_hovered(True)
                tme = TRACKMOUSEEVENT(ctypes.sizeof(TRACKMOUSEEVENT), 0x00000002, hwnd, 0)
                self.user32.TrackMouseEvent(ctypes.byref(tme))

            if self._mouse_down:
                pt = POINT()
                self.user32.GetCursorPos(ctypes.byref(pt))
                dx = pt.x - self._down_cursor[0]
                dy = pt.y - self._down_cursor[1]
                if not self._drag_moved and (dx * dx + dy * dy) >= 25:
                    self._drag_moved = True
                if self._drag_moved:
                    self._pos_x = self._down_win_pos[0] + dx
                    self._pos_y = self._down_win_pos[1] + dy
                    self.user32.SetWindowPos(
                        hwnd, HWND_TOPMOST, self._pos_x, self._pos_y,
                        self.win_size, self.win_size, SWP_NOSIZE | SWP_NOACTIVATE,
                    )
            return 0

        if msg == WM_LBUTTONUP:
            if self._mouse_down:
                self.user32.ReleaseCapture()
                self._mouse_down = False
                if self._drag_moved:
                    save_hud_prefs({"x": int(self._pos_x), "y": int(self._pos_y)})
                else:
                    # Short click toggles user Mic ON/OFF independently of visibility
                    self.renderer.trigger_click_impulse()
                    self.bridge.toggle_mic_async()
            return 0

        if msg == WM_MOUSELEAVE:
            self._tracking_hover = False
            self.bridge.set_hovered(False)
            return 0

        if msg == WM_RBUTTONUP:
            self._show_context_menu()
            return 0

        if msg == WM_DESTROY:
            self.user32.PostQuitMessage(0)
            return 0

        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def run(self):
        if self._start_visible:
            self.show()
        msg = wintypes.MSG()
        while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self.user32.TranslateMessage(ctypes.byref(msg))
            self.user32.DispatchMessageW(ctypes.byref(msg))


def _signal_existing_instance(show_on_signal: bool = True) -> bool:
    """Checks for a running HUD instance; signals it to show if found cleanly."""
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(WINDOW_CLASS, WINDOW_TITLE)
    if hwnd:
        user32.PostMessageW(hwnd, WM_USER_SHOW if show_on_signal else WM_USER_HIDE, 0, 0)
        return True
    return False


def launch_jarvis_hud(start_visible: bool = True):
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_err = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if last_err == ERROR_ALREADY_EXISTS:
        _signal_existing_instance(show_on_signal=start_visible)
        return

    try:
        hud = JarvisFloatingHUD(start_visible=start_visible)
        hud.run()
    finally:
        if mutex:
            kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unleash-Agent Floating Gyroscopic Sphere HUD")
    parser.add_argument("--hidden", action="store_true", help="Start hidden in standby with Ctrl+Shift+Space armed")
    parser.add_argument("--visible", action="store_true", help="Show the sphere immediately on launch")
    args = parser.parse_args()
    launch_jarvis_hud(start_visible=(not args.hidden))
