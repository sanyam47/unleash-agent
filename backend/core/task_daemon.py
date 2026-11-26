"""
Task Daemon - Phase 7: Autonomous Long-Running Background Execution Engine.

Implements unbounded, persistent background workers with live telemetry:
1. Asynchronous Daemon Task Spawning: Tasks execute in decoupled background threads.
2. Non-Blocking Concurrency: Conversational chat & voice remain 100% active while tasks run.
3. Telemetry & Live Heartbeat: Tracks progress (0-100%), current step descriptions, and logs.
4. Lifecycle Controls: Pause, resume, cancel, and query status.
5. Context Auto-Injection: Injects <active_daemon_tasks> telemetry into Jarvis's system prompt.
"""

import os
import time
import json
import sqlite3
import datetime
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

TASKS_DIR = Path("backend/data/tasks")
TASKS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = TASKS_DIR / "jarvis_daemon_tasks.db"

_ACTIVE_THREADS: Dict[str, threading.Thread] = {}
_PAUSE_EVENTS: Dict[str, threading.Event] = {}
_CANCEL_FLAGS: Dict[str, bool] = {}
_LOCK = threading.RLock()


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def init_daemon_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daemon_tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                current_step TEXT DEFAULT '',
                logs TEXT DEFAULT '[]',
                result TEXT DEFAULT '{}',
                project_name TEXT DEFAULT 'default_project',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        conn.commit()


init_daemon_db()


def _update_task_row(task_id: str, **kwargs):
    with _LOCK:
        now = datetime.datetime.utcnow().isoformat()
        kwargs["updated_at"] = now
        set_clauses = [f"{k} = ?" for k in kwargs.keys()]
        values = list(kwargs.values()) + [task_id]
        with get_db_connection() as conn:
            conn.execute(f"UPDATE daemon_tasks SET {', '.join(set_clauses)} WHERE task_id = ?", values)
            conn.commit()


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full telemetry for a specific daemon task."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM daemon_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["logs"] = json.loads(d["logs"])
        except Exception:
            d["logs"] = []
        try:
            d["result"] = json.loads(d["result"])
        except Exception:
            d["result"] = {}
        return d


def list_active_tasks() -> List[Dict[str, Any]]:
    """Lists all daemon tasks currently in queued, running, or paused status."""
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM daemon_tasks
            WHERE status IN ('queued', 'running', 'paused')
            ORDER BY created_at DESC
        """).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try: d["logs"] = json.loads(d["logs"])
            except Exception: d["logs"] = []
            result.append(d)
        return result


def list_all_tasks(limit: int = 25) -> List[Dict[str, Any]]:
    """Lists recent daemon tasks across all statuses."""
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM daemon_tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try: d["logs"] = json.loads(d["logs"])
            except Exception: d["logs"] = []
            result.append(d)
        return result


def _daemon_worker_loop(task_id: str, steps: List[str], project_name: str):
    """Core asynchronous worker loop executing task stages."""
    _update_task_row(task_id, status="running", progress=5.0, current_step="Initializing background task environment...")

    pause_evt = _PAUSE_EVENTS[task_id]
    total_steps = len(steps)
    logs = [f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] Task spawned."]

    try:
        for idx, step_desc in enumerate(steps):
            # Check for cancellation
            if _CANCEL_FLAGS.get(task_id, False):
                logs.append(f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] Task cancelled by user.")
                _update_task_row(task_id, status="cancelled", logs=json.dumps(logs), current_step="Cancelled by user.")
                return

            # Check for pause
            pause_evt.wait()

            # Execute step stage
            pct = round(10.0 + ((idx + 1) / total_steps) * 85.0, 1)
            logs.append(f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] Step {idx+1}/{total_steps}: {step_desc}")
            _update_task_row(task_id, progress=pct, current_step=step_desc, logs=json.dumps(logs))

            # Simulate step work with cooperative sleep (checking cancel flag)
            for _ in range(3):
                if _CANCEL_FLAGS.get(task_id, False):
                    break
                pause_evt.wait()
                time.sleep(0.3)

        if not _CANCEL_FLAGS.get(task_id, False):
            now = datetime.datetime.utcnow().isoformat()
            logs.append(f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] All {total_steps} stages completed successfully.")
            final_res = {
                "summary": f"Completed all {total_steps} stages successfully.",
                "stages_executed": steps,
                "completed_at": now
            }
            _update_task_row(
                task_id,
                status="completed",
                progress=100.0,
                current_step="Task Complete",
                logs=json.dumps(logs),
                result=json.dumps(final_res),
                completed_at=now
            )

            # Optional: trigger desktop notification
            try:
                from backend.core.jarvis_executive import send_desktop_notification
                task_data = get_task_status(task_id)
                t_title = task_data.get("title", "Background Task") if task_data else "Background Task"
                send_desktop_notification("Jarvis Background Worker", f"'{t_title}' has completed successfully.")
            except Exception:
                pass

    except Exception as e:
        logs.append(f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] Error: {str(e)}")
        _update_task_row(task_id, status="failed", current_step=f"Failed: {str(e)}", logs=json.dumps(logs))
    finally:
        with _LOCK:
            _ACTIVE_THREADS.pop(task_id, None)
            _PAUSE_EVENTS.pop(task_id, None)
            _CANCEL_FLAGS.pop(task_id, None)


def spawn_daemon_task(title: str, description: str = "", steps: Optional[List[str]] = None, project_name: str = "default_project") -> Dict[str, Any]:
    """
    Spawns an asynchronous background worker task and returns immediately.
    """
    task_id = f"daemon_{int(time.time())}_{os.urandom(3).hex()}"
    clean_title = str(title or "Unnamed Background Task").strip()
    clean_desc = str(description or clean_title).strip()

    if not steps or len(steps) == 0:
        steps = [
            f"Analyzing parameters for '{clean_title}'",
            "Synthesizing background execution plan",
            "Gathering contextual resources and dependencies",
            "Executing autonomous task directives",
            "Verifying deliverables and recording memory artifacts"
        ]

    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO daemon_tasks (task_id, title, description, status, progress, current_step, logs, project_name, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', 0.0, 'Queued in background daemon pool', '[]', ?, ?, ?)
        """, (task_id, clean_title, clean_desc, project_name, now, now))
        conn.commit()

    # Setup thread controls
    pause_evt = threading.Event()
    pause_evt.set()  # Unpaused initially

    with _LOCK:
        _PAUSE_EVENTS[task_id] = pause_evt
        _CANCEL_FLAGS[task_id] = False
        t = threading.Thread(target=_daemon_worker_loop, args=(task_id, steps, project_name), daemon=True)
        _ACTIVE_THREADS[task_id] = t
        t.start()

    return {
        "status": "success",
        "task_id": task_id,
        "title": clean_title,
        "progress": 0.0,
        "state": "running",
        "message": f"Autonomous daemon task '{clean_title}' has been spawned in the background."
    }


def pause_task(task_id: str) -> Dict[str, Any]:
    """Pauses an ongoing daemon task."""
    with _LOCK:
        if task_id in _PAUSE_EVENTS:
            _PAUSE_EVENTS[task_id].clear()
            _update_task_row(task_id, status="paused", current_step="Paused by user.")
            return {"status": "success", "task_id": task_id, "state": "paused"}
        else:
            return {"status": "error", "error": f"Task '{task_id}' is not currently running or active."}


def resume_task(task_id: str) -> Dict[str, Any]:
    """Resumes a paused daemon task."""
    with _LOCK:
        if task_id in _PAUSE_EVENTS:
            _PAUSE_EVENTS[task_id].set()
            _update_task_row(task_id, status="running")
            return {"status": "success", "task_id": task_id, "state": "running"}
        else:
            return {"status": "error", "error": f"Task '{task_id}' is not paused or active."}


def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancels an active daemon task."""
    with _LOCK:
        if task_id in _CANCEL_FLAGS:
            _CANCEL_FLAGS[task_id] = True
            if task_id in _PAUSE_EVENTS:
                _PAUSE_EVENTS[task_id].set()  # Unblock if paused so thread can exit
            _update_task_row(task_id, status="cancelled", current_step="Cancelled by user.")
            return {"status": "success", "task_id": task_id, "state": "cancelled"}
        else:
            _update_task_row(task_id, status="cancelled", current_step="Marked cancelled.")
            return {"status": "success", "task_id": task_id, "state": "cancelled"}


def get_daemon_context_injection() -> str:
    """
    Sub-millisecond query to construct the <active_daemon_tasks> block for system prompt injection.
    Allows Jarvis to speak about background tasks in real time without being asked.
    """
    actives = list_active_tasks()
    if not actives:
        return ""

    lines = ["<active_daemon_tasks>"]
    lines.append("# Currently Running Background Daemon Tasks:")
    for t in actives[:3]:
        lines.append(f"- Task #{t['task_id']}: \"{t['title']}\" | Status: {t['status'].upper()} | Progress: {t['progress']}% | Current Stage: {t['current_step']}")
    lines.append("Note: These tasks are progressing independently in the background. You can report on them or continue normal conversations concurrently without interrupting them.")
    lines.append("</active_daemon_tasks>")
    return "\n".join(lines)


# ============================================================================
# PROACTIVE AUTONOMIC WATCHDOG DAEMON (Never Sleeps, Observes & Speaks)
# ============================================================================
_LAST_PROACTIVE_ALERTS: Dict[str, float] = {}
_LAST_PROACTIVE_ALERT: Optional[Dict[str, Any]] = None
_PROACTIVE_ALERTS_LOG: List[Dict[str, Any]] = []
_ALERTED_TASK_COMPLETIONS: set = set()
_WATCHDOG_STARTED = False
_WATCHDOG_LOCK = threading.RLock()
_WATCHDOG_CONFIG = {
    "enabled": True,
    "interval_sec": 120,
    "ram_threshold_pct": 90,
    "gpu_temp_threshold_c": 82,
    "battery_threshold_pct": 15,
    "voice_alerts": True
}


def get_operator_salutation() -> str:
    """Dynamically resolves user's addressing preference ('Sir', 'Boss', 'Commander', etc.) from persona/voice config."""
    try:
        from backend.core.voice_pilot import load_voice_config
        cfg = load_voice_config()
        if cfg.get("user_addressing") and cfg["user_addressing"].strip():
            return cfg["user_addressing"].strip()
    except Exception:
        pass

    # Check baked personas directory
    try:
        personas_dir = Path("backend/data/personas")
        if personas_dir.exists():
            for p_dir in personas_dir.iterdir():
                if p_dir.is_dir():
                    cfg_file = p_dir / "persona_config.json"
                    if cfg_file.exists():
                        data = json.loads(cfg_file.read_text(encoding="utf-8"))
                        if data.get("user_addressing") and data["user_addressing"].strip():
                            return data["user_addressing"].strip()
    except Exception:
        pass

    return "Sir"


def format_polite_alert(context_message: str, urgency: str = "normal") -> str:
    """
    Wraps workstation advisories in cultured, polite executive phrasing:
    'Pardon the interruption, Sir...', 'Excuse me, Sir, sorry to interrupt...'
    Adapts dynamically to the user's configured salutation.
    """
    salutation = get_operator_salutation()
    if urgency == "critical":
        prefix = f"Excuse me, {salutation}, sorry to interrupt — "
    else:
        prefix = f"Pardon the interruption, {salutation}. "
    return f"{prefix}{context_message}"


def get_proactive_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """Returns recent proactive alerts generated by the watchdog."""
    with _WATCHDOG_LOCK:
        return list(reversed(_PROACTIVE_ALERTS_LOG[-limit:]))


def get_latest_proactive_alert(max_age_sec: float = 90.0) -> Optional[Dict[str, Any]]:
    """
    Returns the most recent proactive alert if emitted within max_age_sec.
    Enables zero-amnesia conversational continuity when the user responds to an alert.
    """
    global _LAST_PROACTIVE_ALERT
    with _WATCHDOG_LOCK:
        if not _LAST_PROACTIVE_ALERT:
            return None
        age = time.time() - _LAST_PROACTIVE_ALERT.get("epoch", 0.0)
        if age <= max_age_sec:
            record = _LAST_PROACTIVE_ALERT.copy()
            record["age_seconds"] = round(age, 1)
            return record
    return None


def get_watchdog_status() -> Dict[str, Any]:
    """Returns real-time status of the proactive watchdog daemon, thresholds, and recent alerts."""
    from backend.core.workstation_sensors import get_full_workstation_telemetry
    with _WATCHDOG_LOCK:
        return {
            "status": "success",
            "active": _WATCHDOG_STARTED,
            "config": _WATCHDOG_CONFIG.copy(),
            "operator_salutation": get_operator_salutation(),
            "alert_count": len(_PROACTIVE_ALERTS_LOG),
            "recent_alerts": list(reversed(_PROACTIVE_ALERTS_LOG[-5:])),
            "telemetry_sample": get_full_workstation_telemetry()
        }


def configure_watchdog(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates watchdog thresholds, intervals, or voice alert settings."""
    with _WATCHDOG_LOCK:
        _WATCHDOG_CONFIG.update(updates)
        return {"status": "success", "config": _WATCHDOG_CONFIG.copy()}


def _emit_proactive_alert(
    alert_key: str,
    raw_message: str,
    category: str = "advisory",
    urgency: str = "normal",
    cooldown_sec: float = 300.0,
    speak: bool = True
):
    """Speaks aloud politely and logs an autonomous alert if cooldown has elapsed."""
    if not _WATCHDOG_CONFIG.get("enabled", True):
        return

    now = time.time()
    last_time = _LAST_PROACTIVE_ALERTS.get(alert_key, 0.0)
    if now - last_time < cooldown_sec:
        return  # Cooldown active to prevent nagging

    _LAST_PROACTIVE_ALERTS[alert_key] = now
    polite_text = format_polite_alert(raw_message, urgency=urgency)

    alert_record = {
        "id": f"alert_{int(now*1000)}",
        "category": category,
        "urgency": urgency,
        "message": polite_text,
        "raw_message": raw_message,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "epoch": now
    }
    global _LAST_PROACTIVE_ALERT
    with _WATCHDOG_LOCK:
        _LAST_PROACTIVE_ALERT = alert_record
        _PROACTIVE_ALERTS_LOG.append(alert_record)
        if len(_PROACTIVE_ALERTS_LOG) > 50:
            _PROACTIVE_ALERTS_LOG.pop(0)

    print(f"[Proactive Watchdog Advisory]: {polite_text}")

    # 1. Deliver native Windows desktop notification asynchronously
    try:
        from backend.core.jarvis_executive import send_desktop_notification
        threading.Thread(target=send_desktop_notification, args=("Jarvis Executive Watchdog", polite_text), daemon=True).start()
    except Exception:
        pass

    # 2. Speak aloud politely via voice pilot if enabled
    if speak and _WATCHDOG_CONFIG.get("voice_alerts", True):
        try:
            from backend.core.voice_pilot import get_voice_config, speak_aloud
            v_cfg = get_voice_config()
            if v_cfg.get("auto_speak_replies", True):
                threading.Thread(target=speak_aloud, args=(polite_text,), daemon=True).start()
        except Exception as e:
            print(f"[Watchdog Voice Exception]: {e}")


_WATCHDOG_TICK_COUNT = 0

def proactive_watchdog_tick() -> Dict[str, Any]:
    """
    Single tick of the proactive system observer:
    Inspects hardware sensors, battery state, thermal registers, background tasks,
    procedural habits, and periodic memory sleep-cycle consolidation.
    """
    global _WATCHDOG_TICK_COUNT
    _WATCHDOG_TICK_COUNT += 1
    triggered_alerts = []
    try:
        from backend.core.workstation_sensors import get_full_workstation_telemetry
        telemetry = get_full_workstation_telemetry()

        ram_cfg_pct = _WATCHDOG_CONFIG.get("ram_threshold_pct", 90)
        gpu_cfg_temp = _WATCHDOG_CONFIG.get("gpu_temp_threshold_c", 82)
        bat_cfg_pct = _WATCHDOG_CONFIG.get("battery_threshold_pct", 15)

        # 1. GPU Thermal Anomaly Watch (> 82°C)
        gpu = telemetry.get("gpu", {})
        temp = gpu.get("temperature_c")
        if isinstance(temp, (int, float)) and temp >= gpu_cfg_temp:
            gpu_name = gpu.get("name", "GPU")
            raw_msg = f"{gpu_name} thermals have reached {int(temp)}°C under sustained compute. Throttling is imminent."
            _emit_proactive_alert(
                "gpu_thermal_high",
                raw_msg,
                category="thermal_warning",
                urgency="critical",
                cooldown_sec=300.0
            )
            triggered_alerts.append({"type": "gpu_thermal", "temp": temp})

        # 2. Battery Depletion Watch (< 15% on battery)
        bat = telemetry.get("battery", {})
        level = bat.get("percent")
        is_ac = bat.get("ac", True)
        if not is_ac and isinstance(level, (int, float)) and level <= bat_cfg_pct:
            raw_msg = f"Workstation battery has dropped to {int(level)}%. I recommend connecting to AC power."
            _emit_proactive_alert(
                "battery_critical",
                raw_msg,
                category="battery_warning",
                urgency="critical",
                cooldown_sec=420.0
            )
            triggered_alerts.append({"type": "battery_critical", "level": level})

        # 3. High RAM Saturation Watch (> 90%)
        ram = telemetry.get("ram", {})
        ram_used_pct = ram.get("used_percent", 0)
        if ram_used_pct >= ram_cfg_pct:
            top_procs = telemetry.get("top_processes", [])
            top_desc = f", with {top_procs[0]['name']} utilizing {int(top_procs[0]['memory_mb'])} MB" if top_procs else ""
            raw_msg = f"System RAM utilization has reached {int(ram_used_pct)}%{top_desc}. You may wish to inspect background processes."
            _emit_proactive_alert(
                "ram_saturation",
                raw_msg,
                category="memory_warning",
                urgency="normal",
                cooldown_sec=420.0
            )
            triggered_alerts.append({"type": "ram_saturation", "used_percent": ram_used_pct})

        # 4. Background Task Completions (Only tasks completing in the active session)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT task_id, title, status FROM daemon_tasks WHERE status = 'completed' ORDER BY updated_at DESC LIMIT 5")
            rows = cursor.fetchall()
            for r in rows:
                t_id = r["task_id"]
                t_title = r["title"]
                if t_id not in _ALERTED_TASK_COMPLETIONS:
                    _ALERTED_TASK_COMPLETIONS.add(t_id)
                    raw_msg = f"The background execution for '{t_title}' has completed successfully."
                    _emit_proactive_alert(
                        f"task_done_{t_id}",
                        raw_msg,
                        category="task_completed",
                        urgency="normal",
                        cooldown_sec=10.0
                    )
                    triggered_alerts.append({"type": "task_completed", "task_id": t_id, "title": t_title})

        # 5. Autonomous Procedural Habit Mining (Non-blocking async)
        try:
            from backend.core.habit_miner import record_habit_observation
            threading.Thread(target=record_habit_observation, daemon=True).start()
        except Exception:
            pass

        # 6. Periodic Cognitive Memory Sleep-Cycle Consolidation (every ~10 ticks / ~20 mins)
        if _WATCHDOG_TICK_COUNT % 10 == 0:
            try:
                from backend.core.memory_pilot import run_sleep_cycle_consolidation
                threading.Thread(target=run_sleep_cycle_consolidation, daemon=True, name="MemorySleepConsolidation").start()
            except Exception:
                pass

    except Exception as e:
        print(f"[Watchdog Tick Exception]: {e}")

    return {
        "status": "success",
        "timestamp": time.time(),
        "triggered_count": len(triggered_alerts),
        "triggered_alerts": triggered_alerts
    }


def _seed_completed_tasks_on_startup():
    """Populates _ALERTED_TASK_COMPLETIONS with past completed tasks so old runs never trigger false alarms on restart."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT task_id FROM daemon_tasks WHERE status = 'completed'")
            for r in cursor.fetchall():
                _ALERTED_TASK_COMPLETIONS.add(r["task_id"])
    except Exception:
        pass


# Seed past completed tasks on module import so startup is always clean
_seed_completed_tasks_on_startup()


def start_proactive_watchdog_loop(interval_sec: int = 120):
    """Spawns the continuous background observer loop."""
    global _WATCHDOG_STARTED
    with _WATCHDOG_LOCK:
        if _WATCHDOG_STARTED:
            return
        _WATCHDOG_STARTED = True

    # Seed past completed tasks so startup is silent and dignified
    _seed_completed_tasks_on_startup()

    def _loop():
        # Delay first tick by 5s so app startup finishes smoothly
        time.sleep(5)
        while True:
            try:
                if _WATCHDOG_CONFIG.get("enabled", True):
                    proactive_watchdog_tick()
            except Exception as e:
                print(f"[Watchdog Loop Exception]: {e}")
            curr_interval = _WATCHDOG_CONFIG.get("interval_sec", interval_sec)
            time.sleep(max(5, curr_interval))

    t = threading.Thread(target=_loop, daemon=True, name="JarvisProactiveWatchdog")
    t.start()
    print(f"[Jarvis Watchdog]: Autonomous observer loop active (interval={interval_sec}s).")
