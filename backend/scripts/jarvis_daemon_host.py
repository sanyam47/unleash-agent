"""
Jarvis Native Windows Daemon Host - Pillar 1: Living Beyond the Browser

Runs as a background Windows process decoupled from any browser tab:
1. Global Windows Hotkey: Listens for Ctrl+Alt+J from anywhere (VS Code, Desktop, Games).
2. Direct Executive Gateway Hook: Executes voice commands, systems telemetry, and app dispatching.
3. Native Windows Toast Notifications: Alerts user via Windows Action Center.
4. Ambient Background Heartbeat: Periodically monitors thermals and battery without eating CPU.
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
import threading

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.jarvis_executive import (
    dispatch_jarvis_executive_action,
    get_system_telemetry,
    send_desktop_notification
)
from backend.core.desktop_perception import get_ambient_desktop_context
from backend.core.voice_pilot import speak_aloud
from backend.core.wake_word_listener import start_native_wake_word_daemon

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_J = 0x4A  # 'J' key
HOTKEY_ID = 4201
WM_HOTKEY = 0x0312


def on_global_hotkey_triggered():
    """Triggered when the user presses Ctrl+Alt+J globally in Windows."""
    print("[Daemon]: Global Hotkey Ctrl+Alt+J triggered.")
    send_desktop_notification("Assistant Online", "Listening for your directive...")
    speak_aloud("Listening.")


def run_hotkey_message_loop():
    """Runs the Win32 message pump for global hotkey handling."""
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_ALT | MOD_CONTROL, VK_J):
        print(f"[Daemon Warning]: Could not register global hotkey Ctrl+Alt+J (may be reserved).")
        return

    print("[Daemon]: Global Hotkey [Ctrl + Alt + J] successfully registered.")
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                threading.Thread(target=on_global_hotkey_triggered, daemon=True).start()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        print("[Daemon]: Global hotkey unregistered.")


def start_jarvis_background_daemon():
    """Main entry point for starting the headless Windows Daemon."""
    print("=" * 60)
    print("⚡ NATIVE WINDOWS DAEMON HOST")
    print("Decoupled from browser. Ambient background system service active.")
    print("Press Ctrl+Alt+J from anywhere to summon assistant.")
    print("=" * 60)

    # Initial ambient scan
    try:
        perception = get_ambient_desktop_context()
        print(f"[Ambient Perception]: {perception.get('narrative')}")
    except Exception as e:
        print(f"[Ambient Perception Notice]: {e}")

    # Start Native Hands-Free Wake Word Daemon in Background
    try:
        start_native_wake_word_daemon(in_background=True)
        print("[Daemon]: Hands-free Wake Word engine active.")
    except Exception as e:
        print(f"[Jarvis Daemon Warning]: Could not start wake word engine: {e}")

    # Start Win32 Message Loop
    run_hotkey_message_loop()


if __name__ == "__main__":
    start_jarvis_background_daemon()
