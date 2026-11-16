"""
Procedural Habit Miner - Pillar 3: Autonomous User Behavior Graph

Silently and continuously observes user workstation habits without requiring manual entry:
1. Active App & Session Tracker: Periodically logs running creative/dev tools.
2. Temporal Pattern Extraction: Identifies peak productive hours (e.g. night coding).
3. Stack & Ecosystem Affinity: Measures reliance on Python, Docker, Node, Windows CLI.
4. Autonomous Habit Synthesis: Produces a high-signal behavioral persona memory for Jarvis.
"""

import os
import time
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.core.desktop_perception import get_interactive_session_processes

HABITS_DIR = Path("backend/data/habits")
HABITS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = HABITS_DIR / "jarvis_habits.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_habit_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                hour_of_day INTEGER NOT NULL,
                active_apps TEXT NOT NULL,
                dev_stack TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS habit_profiles (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL NOT NULL,
                last_updated TEXT NOT NULL
            );
        """)
        conn.commit()


# Initialize database schema
init_habit_db()


def record_habit_observation() -> Dict[str, Any]:
    """
    Called by the proactive watchdog daemon loop (every 60-120 seconds).
    Silently logs running applications and infers emergent user habits.
    """
    now = datetime.datetime.now()
    now_iso = now.isoformat()
    hour = now.hour

    apps = get_interactive_session_processes(top_n=8)
    app_names = [a["name"] for a in apps]
    
    dev_stack = []
    names_lower = [n.lower() for n in app_names]
    if any("antigravity" in n or "code" in n or "language_server" in n for n in names_lower):
        dev_stack.append("IDE / Antigravity")
    if any("docker" in n for n in names_lower):
        dev_stack.append("Docker")
    if any("python" in n for n in names_lower):
        dev_stack.append("Python")
    if any("chrome" in n or "msedge" in n for n in names_lower):
        dev_stack.append("Browser")
    if any("whatsapp" in n or "telegram" in n for n in names_lower):
        dev_stack.append("Messaging")

    apps_str = ", ".join(app_names)
    stack_str = ", ".join(dev_stack)

    with get_db() as conn:
        conn.execute("""
            INSERT INTO activity_log (timestamp, hour_of_day, active_apps, dev_stack)
            VALUES (?, ?, ?, ?)
        """, (now_iso, hour, apps_str, stack_str))
        conn.commit()

    # Re-synthesize high-level habits periodically
    return synthesize_user_habits()


def synthesize_user_habits() -> Dict[str, Any]:
    """
    Mines raw activity logs to extract persistent behavioral habits.
    """
    with get_db() as conn:
        total_rows = conn.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        if total_rows < 1:
            return {"status": "insufficient_data", "summary": "Observing initial user activity patterns..."}

        # 1. Peak hours analysis
        hour_counts = conn.execute("""
            SELECT hour_of_day, COUNT(*) as cnt 
            FROM activity_log 
            GROUP BY hour_of_day 
            ORDER BY cnt DESC 
            LIMIT 3
        """).fetchall()
        peak_hours = [r["hour_of_day"] for r in hour_counts]

        # 2. Top applications
        recent_logs = conn.execute("""
            SELECT active_apps, dev_stack FROM activity_log ORDER BY id DESC LIMIT 50
        """).fetchall()

    app_freq: Dict[str, int] = {}
    stack_freq: Dict[str, int] = {}
    for r in recent_logs:
        for a in r["active_apps"].split(", "):
            if a.strip():
                app_freq[a.strip()] = app_freq.get(a.strip(), 0) + 1
        for s in r["dev_stack"].split(", "):
            if s.strip():
                stack_freq[s.strip()] = stack_freq.get(s.strip(), 0) + 1

    top_apps = sorted(app_freq.items(), key=lambda x: x[1], reverse=True)[:5]
    top_stack = sorted(stack_freq.items(), key=lambda x: x[1], reverse=True)[:4]

    # Synthesize habit summary
    work_time_desc = "Night developer" if any(h >= 20 or h <= 4 for h in peak_hours) else "Daytime developer"
    fav_stack = [s[0] for s in top_stack if s[0]]
    fav_apps = [a[0] for a in top_apps if a[0]]

    summary_text = (
        f"Work schedule: {work_time_desc} (active around {', '.join(f'{h}:00' for h in peak_hours)}). "
        f"Primary tools: {', '.join(fav_apps[:3])}. "
        f"Ecosystem stack: {', '.join(fav_stack)}."
    )

    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO habit_profiles (key, value, confidence, last_updated)
            VALUES (?, ?, ?, ?)
        """, ("user_profile", summary_text, min(1.0, 0.4 + (total_rows * 0.02)), datetime.datetime.now().isoformat()))
        conn.commit()

    return {
        "status": "active",
        "observations_count": total_rows,
        "peak_hours": peak_hours,
        "top_apps": [a[0] for a in top_apps],
        "top_stack": [s[0] for s in top_stack],
        "summary": summary_text
    }


def get_current_habit_summary() -> str:
    """Returns the current synthesized habit summary for cognitive context injection."""
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM habit_profiles WHERE key = 'user_profile'").fetchone()
            if row and row["value"]:
                return row["value"]
    except Exception:
        pass
    return "Work schedule: Active systems developer. Primary environment: Antigravity IDE, Python & Docker."
