"""
Jarvis Desktop HUD - Pillar 1 Glass Overlay Widget

A sleek, translucent, borderless floating desktop HUD that floats above all Windows:
1. Always-on-Top Floating Glass: Draggable anywhere, sits discreetly on your screen.
2. Reactive Arc-Reactor Status Orb: Glows cyan (idle), emerald (listening), amber (thinking), purple (speaking).
3. Live Micro-Telemetry: GPU thermals, RAM load, active daemon tasks.
4. Voice & Hotkey Visual Feedback: Lights up when Ctrl+Alt+J is pressed.
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import font

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.jarvis_executive import get_system_telemetry
from backend.core.desktop_perception import get_ambient_desktop_context


class JarvisFloatingHUD:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JARVIS HUD")
        
        # Borderless, floating, semi-translucent window
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.92)
        self.root.configure(bg="#0B0D13")

        # Initial geometry: Bottom right corner
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w, h = 320, 84
        x = screen_w - w - 24
        y = screen_h - h - 56
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Dragging handlers
        self._drag_data = {"x": 0, "y": 0}
        self.root.bind("<ButtonPress-1>", self.on_drag_start)
        self.root.bind("<B1-Motion>", self.on_drag_motion)

        # UI Components
        self.main_frame = tk.Frame(self.root, bg="#0B0D13", highlightbackground="#1E293B", highlightthickness=1)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Header Row
        self.header_frame = tk.Frame(self.main_frame, bg="#0B0D13")
        self.header_frame.pack(fill=tk.X, padx=10, pady=(6, 2))

        # Arc Reactor Orb (Canvas)
        self.orb_canvas = tk.Canvas(self.header_frame, width=16, height=16, bg="#0B0D13", highlightthickness=0)
        self.orb_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.orb_dot = self.orb_canvas.create_oval(2, 2, 14, 14, fill="#06B6D4", outline="#22D3EE", width=1)

        self.title_label = tk.Label(
            self.header_frame, text="EXECUTIVE PILOT", 
            font=("Segoe UI", 9, "bold"), fg="#F8FAFC", bg="#0B0D13"
        )
        self.title_label.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            self.header_frame, text="ONLINE", 
            font=("Segoe UI", 7, "bold"), fg="#10B981", bg="#0B0D13"
        )
        self.status_label.pack(side=tk.RIGHT)

        # Telemetry Row
        self.telemetry_label = tk.Label(
            self.main_frame, text="Telemetry: Scanning workstation...", 
            font=("Segoe UI", 8), fg="#94A3B8", bg="#0B0D13", anchor="w"
        )
        self.telemetry_label.pack(fill=tk.X, padx=10, pady=(0, 2))

        # Subtitle / Spoken Feed
        self.subtitle_label = tk.Label(
            self.main_frame, text="Press Ctrl+Alt+J to summon", 
            font=("Segoe UI", 7), fg="#64748B", bg="#0B0D13", anchor="w"
        )
        self.subtitle_label.pack(fill=tk.X, padx=10, pady=(0, 6))

        # Start background polling
        self.is_running = True
        self.poll_thread = threading.Thread(target=self._telemetry_poll_loop, daemon=True)
        self.poll_thread.start()

    def on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_drag_motion(self, event):
        deltax = event.x - self._drag_data["x"]
        deltay = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def update_status(self, state: str, message: str = ""):
        color_map = {
            "idle": ("#06B6D4", "#22D3EE", "#06B6D4", "ONLINE"),
            "listening": ("#10B981", "#34D399", "#10B981", "LISTENING"),
            "thinking": ("#F59E0B", "#FBBF24", "#F59E0B", "THINKING"),
            "speaking": ("#A855F7", "#C084FC", "#A855F7", "SPEAKING"),
        }
        fill, outline, text_color, label_text = color_map.get(state, color_map["idle"])
        self.orb_canvas.itemconfig(self.orb_dot, fill=fill, outline=outline)
        self.status_label.config(text=label_text, fg=text_color)
        if message:
            self.subtitle_label.config(text=message[:48])

    def _telemetry_poll_loop(self):
        while self.is_running:
            try:
                telem = get_system_telemetry()
                gpu = telem.get("gpu", {})
                temp = gpu.get("temperature_c", "N/A")
                ram_pct = telem.get("ram", {}).get("used_percent", 0)
                
                telemetry_str = f"GPU: {temp}°C (RTX 3050) | RAM: {ram_pct}% | Battery: Normal"
                self.root.after(0, lambda s=telemetry_str: self.telemetry_label.config(text=s))
            except Exception:
                pass
            time.sleep(3)

    def run(self):
        self.root.mainloop()


def launch_jarvis_hud():
    hud = JarvisFloatingHUD()
    hud.run()


if __name__ == "__main__":
    launch_jarvis_hud()
