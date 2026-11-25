"""
GUI Pilot - Phase 4: Desktop Mouse, Keyboard & GUI Automation for Jarvis AI Assistant.

Enables Jarvis to:
1. Click anywhere on desktop or within application windows (left, right, double-click).
2. Type arbitrary Unicode text into focused desktop inputs (e.g. WhatsApp, VS Code, Notepad, Terminal).
3. Trigger native Windows keyboard shortcuts and hotkeys (Ctrl+C, Ctrl+V, Win+D, Alt+Tab, Enter, Esc).
4. Move cursor and scroll desktop content.
5. Inspect cursor coordinates and screen metrics in real time.

Built on pure native Win32 API (SendInput, SetCursorPos, WinSta0) for zero-dependency,
sub-millisecond execution and complete Windows 11 compatibility.
"""

import os
import sys
import time
import json
import ctypes
import subprocess
from typing import Dict, Any, List, Optional, Tuple

if os.name == "nt":
    from ctypes import wintypes
    user32 = ctypes.windll.user32
else:
    wintypes = None
    user32 = None

def _ensure_desktop_station():
    """Attaches current thread to interactive desktop WinSta0\\Default if running in subshell."""
    if os.name != "nt" or user32 is None:
        return
    try:
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


if os.name == "nt":
    # Win32 INPUT Structures
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("mi", MOUSEINPUT),
            ("ki", KEYBDINPUT),
            ("hi", HARDWAREINPUT),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", wintypes.DWORD),
            ("u", _INPUT_UNION),
        ]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

# Virtual Key Mappings
VK_MAP = {
    # Modifiers
    "ctrl": 0x11, "control": 0x11, "lctrl": 0xA2, "rctrl": 0xA3,
    "shift": 0x10, "lshift": 0xA0, "rshift": 0xA1,
    "alt": 0x12, "lalt": 0xA4, "ralt": 0xA5,
    "win": 0x5B, "windows": 0x5B, "cmd": 0x5B, "lwin": 0x5B, "rwin": 0x5C,

    # Control Keys
    "enter": 0x0D, "return": 0x0D,
    "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "spacebar": 0x20,
    "tab": 0x09,
    "backspace": 0x08, "bs": 0x08,
    "delete": 0x2E, "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pgup": 0x21,
    "pagedown": 0x22, "pgdn": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "capslock": 0x14,

    # Function Keys
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}


def _send_vk(vk_code: int, keyup: bool = False):
    """Sends a single virtual key event."""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.u.ki.wVk = vk_code
    inp.u.ki.wScan = 0
    inp.u.ki.dwFlags = KEYEVENTF_KEYUP if keyup else 0
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _send_unicode_char(ch: str):
    """Sends a Unicode character keystroke (press + release)."""
    code = ord(ch)
    # Key down
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.u.ki.wVk = 0
    inp_down.u.ki.wScan = code
    inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE

    # Key up
    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.u.ki.wVk = 0
    inp_up.u.ki.wScan = code
    inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    inputs = (INPUT * 2)(inp_down, inp_up)
    user32.SendInput(2, inputs, ctypes.sizeof(INPUT))


def desktop_cursor_pos() -> Dict[str, Any]:
    """Returns the current mouse cursor coordinates and screen resolution."""
    _ensure_desktop_station()
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return {
        "success": True,
        "x": pt.x,
        "y": pt.y,
        "screen_width": w,
        "screen_height": h,
        "message": f"Cursor at ({pt.x}, {pt.y}) on {w}x{h} screen"
    }


def desktop_move(x: int, y: int) -> Dict[str, Any]:
    """Moves the mouse cursor to absolute coordinates (x, y)."""
    _ensure_desktop_station()
    user32.SetCursorPos(int(x), int(y))
    return {
        "success": True,
        "x": int(x),
        "y": int(y),
        "message": f"Mouse cursor moved to ({x}, {y})"
    }


def desktop_click(
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    clicks: int = 1
) -> Dict[str, Any]:
    """
    Clicks at the specified desktop coordinates (or at current cursor position).
    
    Args:
        x: Optional target X coordinate (None uses current cursor pos).
        y: Optional target Y coordinate (None uses current cursor pos).
        button: 'left' (default), 'right', or 'middle'.
        clicks: 1 for single click, 2 for double click.
    """
    _ensure_desktop_station()
    if x is not None and y is not None:
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.02)

    # Get current pos for reporting
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    curr_x, curr_y = pt.x, pt.y

    b_lower = button.lower().strip()
    if b_lower == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    elif b_lower == "middle":
        down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    for i in range(max(1, int(clicks))):
        user32.mouse_event(down_flag, 0, 0, 0, 0)
        time.sleep(0.02)
        user32.mouse_event(up_flag, 0, 0, 0, 0)
        if clicks > 1 and i < clicks - 1:
            time.sleep(0.06)

    action_name = "double-click" if clicks == 2 else f"{button}-click"
    return {
        "success": True,
        "action": action_name,
        "button": button,
        "clicks": clicks,
        "x": curr_x,
        "y": curr_y,
        "message": f"Performed {action_name} at ({curr_x}, {curr_y})"
    }


def desktop_type(
    text: str,
    press_enter: bool = False,
    interval_ms: int = 5
) -> Dict[str, Any]:
    """
    Types text into the active desktop window with full Unicode support.
    
    Args:
        text: String of text to type.
        press_enter: Whether to press Enter after typing.
        interval_ms: Milliseconds delay between keystrokes.
    """
    _ensure_desktop_station()
    if not text and not press_enter:
        return {"success": False, "error": "No text or action specified."}

    for ch in text:
        if ch == "\n":
            _send_vk(0x0D, keyup=False)
            _send_vk(0x0D, keyup=True)
        else:
            _send_unicode_char(ch)
        if interval_ms > 0:
            time.sleep(interval_ms / 1000.0)

    if press_enter:
        time.sleep(0.05)
        _send_vk(0x0D, keyup=False)
        _send_vk(0x0D, keyup=True)

    preview = (text[:40] + "...") if len(text) > 40 else text
    return {
        "success": True,
        "typed_chars": len(text),
        "pressed_enter": press_enter,
        "message": f"Typed '{preview}' into active window{' [with Enter]' if press_enter else ''}"
    }


def desktop_hotkey(keys: str) -> Dict[str, Any]:
    """
    Executes a keyboard shortcut (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d', 'ctrl+shift+p', 'enter').
    
    Args:
        keys: Plus- or space-separated key combinations (e.g. 'ctrl+s', 'alt+f4', 'win+d').
    """
    _ensure_desktop_station()
    key_str = keys.strip().lower()
    if not key_str:
        return {"success": False, "error": "No hotkey combination specified."}

    # Normalize tokens
    tokens = [t.strip() for t in key_str.replace("+", " ").split() if t.strip()]
    if not tokens:
        return {"success": False, "error": f"Invalid hotkey '{keys}'"}

    vk_codes = []
    for token in tokens:
        if token in VK_MAP:
            vk_codes.append(VK_MAP[token])
        elif len(token) == 1 and token.isalnum():
            # Win32 alphanumeric VK code is uppercase ASCII code
            vk_codes.append(ord(token.upper()))
        else:
            return {"success": False, "error": f"Unrecognized key token '{token}' in '{keys}'"}

    # Press keys in forward sequence
    for vk in vk_codes:
        _send_vk(vk, keyup=False)
        time.sleep(0.01)

    time.sleep(0.03)

    # Release keys in reverse sequence
    for vk in reversed(vk_codes):
        _send_vk(vk, keyup=True)
        time.sleep(0.01)

    return {
        "success": True,
        "hotkey": keys,
        "keys_pressed": tokens,
        "message": f"Executed hotkey '{keys}' successfully."
    }


def desktop_scroll(amount: int = 3, direction: str = "down") -> Dict[str, Any]:
    """
    Scrolls the mouse wheel at current cursor position.
    
    Args:
        amount: Number of scroll notches (default 3).
        direction: 'down' (default) or 'up'.
    """
    _ensure_desktop_station()
    clicks = max(1, int(amount))
    delta = clicks * 120
    if direction.lower().strip() == "down":
        delta = -delta

    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
    return {
        "success": True,
        "direction": direction,
        "amount": clicks,
        "message": f"Scrolled mouse wheel {direction} ({clicks} units)."
    }


def list_ui_elements(window_title: Optional[str] = None, limit: int = 25) -> Dict[str, Any]:
    """
    Inspects real native desktop UI controls (buttons, inputs, menu items) via Windows UI Automation
    and returns their names, types, and exact center (x, y) coordinates — eliminating blind pixel guessing.
    """
    if os.name != "nt":
        return {"status": "error", "error": "Native UI Automation currently supported on Windows hosts only."}

    safe_limit = max(1, min(int(limit or 25), 50))
    title_filter = str(window_title or "").replace("'", "''").strip()

    ps_script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$target = $null
if ('{title_filter}' -ne '') {{
    $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($w in $wins) {{
        if ($w.Current.Name -like '*{title_filter}*') {{ $target = $w; break }}
    }}
}}
if ($null -eq $target) {{
    $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
    if ($null -ne $focused) {{
        $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
        $curr = $focused
        while ($null -ne $curr -and $walker.GetParent($curr) -ne $root) {{
            $curr = $walker.GetParent($curr)
        }}
        $target = $curr
    }}
}}
if ($null -eq $target) {{ Write-Output '[]'; exit 0 }}
$cond = New-Object System.Windows.Automation.OrCondition(
    (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)),
    (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)),
    (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::MenuItem)),
    (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::ListItem))
)
$els = $target.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
$out = @()
foreach ($el in $els) {{
    if ($out.Count -ge {safe_limit}) {{ break }}
    $r = $el.Current.BoundingRectangle
    if ($r.Width -lt 4 -or $r.Height -lt 4 -or [double]::IsInfinity($r.X)) {{ continue }}
    $name = ($el.Current.Name -replace '\\s+', ' ').Trim()
    if ($name -eq '') {{ continue }}
    $cx = [int]($r.X + ($r.Width / 2))
    $cy = [int]($r.Y + ($r.Height / 2))
    $out += [PSCustomObject]@{{ name = $name.Substring(0, [Math]::Min(60, $name.Length)); type = $el.Current.ControlType.ProgrammaticName -replace '^ControlType\\.',''; x = $cx; y = $cy }}
}}
$out | ConvertTo-Json -Compress
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        raw = (proc.stdout or "").strip()
        if not raw:
            return {"status": "success", "window_filter": title_filter or "focused", "elements": []}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return {
            "status": "success",
            "window_filter": title_filter or "focused",
            "count": len(parsed),
            "elements": parsed,
        }
    except Exception as e:
        return {"status": "error", "error": f"UI Automation inspection failed: {str(e)}"}
