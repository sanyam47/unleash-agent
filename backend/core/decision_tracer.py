"""
Autonomous Decision Tracer & Explainability Audit Engine.
Provides human-readable transparency for AI coding decisions:
  1. Tracks prompt decomposition, milestone planning, and rationale.
  2. Records 5-layer acceptance gate evaluations (why a check failed or passed).
  3. Explains target-file provenance (why app.js was chosen over index.html).
  4. Stores per-project audit timeline at backend/data/projects/{project}/decision_trace.json.
"""

import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.core.agent_tools import get_project_dir, sanitize_project_name

MAX_AUDIT_EVENTS = 50


def get_trace_file(clean_proj: str) -> Path:
    """Returns the decision_trace.json file path for a project."""
    proj_dir = get_project_dir(clean_proj)
    proj_dir.mkdir(parents=True, exist_ok=True)
    return proj_dir / "decision_trace.json"


def record_decision_event(
    project_name: str,
    event_type: str,
    headline: str,
    rationale: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Appends an explainable decision event to the project's audit trail.
    Event types:
      - 'intent_analysis': What features the user requested and why.
      - 'scout_contract': Planned entity schema, DOM bindings, and files.
      - 'milestone_plan': Decomposed milestones based on hardware tier.
      - 'action_execution': Why a specific tool (write/edit/read) was dispatched.
      - 'gate_audit': Acceptance gate results (Node.js syntax, Chromium click tests).
      - 'provenance_routing': Why a defect was attributed to a specific file.
      - 'rollback': User or agent triggered rollback event.
    """
    clean_proj = sanitize_project_name(project_name)
    trace_file = get_trace_file(clean_proj)

    events = []
    if trace_file.exists():
        try:
            events = json.loads(trace_file.read_text(encoding="utf-8"))
            if not isinstance(events, list):
                events = []
        except Exception:
            events = []

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    event_obj = {
        "id": f"evt_{int(time.time() * 1000)}",
        "timestamp": ts,
        "type": event_type,
        "headline": headline,
        "rationale": rationale,
        "details": details or {}
    }

    events.append(event_obj)
    if len(events) > MAX_AUDIT_EVENTS:
        events = events[-MAX_AUDIT_EVENTS:]

    try:
        trace_file.write_text(json.dumps(events, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[DecisionTracer] Error writing trace file: {e}")

    return event_obj


def get_audit_trail(project_name: str) -> List[Dict[str, Any]]:
    """Returns all recorded decision events for a project in chronological order."""
    clean_proj = sanitize_project_name(project_name)
    trace_file = get_trace_file(clean_proj)
    if not trace_file.exists():
        return []
    try:
        return json.loads(trace_file.read_text(encoding="utf-8"))
    except Exception:
        return []


def format_audit_trail_markdown(project_name: str) -> str:
    """Generates an executive, human-readable markdown timeline of the agent's reasoning."""
    clean_proj = sanitize_project_name(project_name)
    events = get_audit_trail(clean_proj)
    if not events:
        return f"# Audit Trail for Project '{clean_proj}'\n\n*No decision events recorded yet.*"

    lines = [
        f"# Decision Audit Trail & Explainability: {clean_proj}",
        f"*Total Events Recorded: {len(events)}*",
        "\n---\n"
    ]

    for ev in events:
        icon = {
            "intent_analysis": "[INTENT]",
            "scout_contract": "[SCOUT]",
            "milestone_plan": "[PLAN]",
            "action_execution": "[ACTION]",
            "gate_audit": "[AUDIT]",
            "provenance_routing": "[REPAIR]",
            "rollback": "[ROLLBACK]"
        }.get(ev.get("type"), "[EVENT]")

        lines.append(f"### {icon} {ev.get('headline')} ({ev.get('timestamp')})")
        lines.append(f"**Rationale:** {ev.get('rationale')}")
        details = ev.get("details", {})
        if details:
            lines.append("```json")
            lines.append(json.dumps(details, indent=2))
            lines.append("```")
        lines.append("")

    return "\n".join(lines)
