"""
Autonomous Goal-Completion Engine & Micro-Goal Stepper for Unleash-Agent.
Implements the Devin/SWE-agent style goal decomposition and autonomous ReAct loop:
1. Decomposes user prompt into 2-4 atomic, verifiable milestones.
2. Inspects codebase files on disk (AST, DOM IDs, APIs) to evaluate milestone completion.
3. Automatically re-prompts the model turn-by-turn with targeted feedback until all milestones pass.
"""

import re
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


def decompose_goals(
    user_prompt: str,
    scout_res: Optional[Dict[str, Any]] = None,
    max_milestones: int = 4
) -> List[Dict[str, Any]]:
    """
    Decomposes the user's prompt into atomic, verifiable milestones.
    Dynamically scaled according to active compute tier (4 on Lite, 6 on Balanced, 8 on Ultra).
    """
    lowered = user_prompt.lower()
    milestones: List[Dict[str, Any]] = []

    # Milestone 1: Visual Foundation & Layout Shell (Always required)
    brand = (scout_res or {}).get("entities", {}).get("brand_name")
    persona = (scout_res or {}).get("entities", {}).get("persona_name")
    
    m1_desc = "Semantic layout (<header>, <main>, <section>) and responsive styling."
    if brand:
        m1_desc += f" Must feature brand '{brand}'."
    if persona:
        m1_desc += f" Must include spotlight card for '{persona}'."

    milestones.append({
        "id": "milestone_layout",
        "name": "Semantic Layout & Theme Styling",
        "desc": m1_desc,
        "required_signals": ["<header", "<section", "<main"],
        "status": "pending",
        "turn_verified": None
    })

    # Milestone: Timer / Pomodoro / Clock
    if any(k in lowered for k in ["timer", "pomodoro", "countdown", "stopwatch", "clock"]) and len(milestones) < max_milestones:
        modes_hint = "with break toggles" if any(k in lowered for k in ["break", "work", "mode", "toggle"]) else "with controls"
        milestones.append({
            "id": "milestone_timer",
            "name": f"Timer Engine & Countdown ({modes_hint})",
            "desc": "Working countdown/timer interval, start/pause/reset controls, and time display element.",
            "required_signals": ["setinterval", "clearinterval", "date.now", "start", "pause", "timer"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Sound / Audio Feedback
    if any(k in lowered for k in ["sound", "audio", "beep", "sfx", "tone", "feedback"]) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_audio",
            "name": "Audio Feedback Engine (Web Audio API / SFX)",
            "desc": "Synthesized audio feedback (AudioContext/oscillator) or sound effects triggered by user actions.",
            "required_signals": ["audiocontext", "webkitaudiocontext", "audio", "oscillator", "playbeep", "sound"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Task List / Objective Queue / Todo
    if any(k in lowered for k in ["task", "tasks", "todo", "objective", "goals", "checklist", "check off"]) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_tasks",
            "name": "Task Queue & Interactive Completion",
            "desc": "Input to add tasks, dynamic list rendering, and completion toggle (checkbox / strike-through).",
            "required_signals": ["task", "todo", "checkbox", "done", "completed", "input"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Search / Filter / Category Queries
    if any(k in lowered for k in ["search", "filter", "find", "query", "filter by", "categories"]) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_search",
            "name": "Live Search & Filter Engine",
            "desc": "Search input with live filtering over items or dynamic search results.",
            "required_signals": ["filter", "search", "includes", "indexof", "queryselector", "input"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: E-Commerce Storefront / Shopping Cart
    if any(k in lowered for k in ["cart", "store", "shop", "checkout", "ecommerce", "price", "buy"]) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_cart",
            "name": "Cart Drawer & Checkout Engine",
            "desc": "Interactive product cards with Add-to-Cart handlers, cart badge counter, and cart modal/drawer.",
            "required_signals": ["cart", "add to cart", "price", "quantity", "checkout", "drawer"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Canvas / Game Arena / 3D Simulation
    if any(k in lowered for k in ["game", "canvas", "arcade", "physics", "solar system", "webgl", "animation", "player"]) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_canvas_game",
            "name": "Canvas Rendering & Interactive Controls",
            "desc": "HTML5 Canvas loop with 2D/WebGL rendering (requestAnimationFrame) and user control buttons.",
            "required_signals": ["<canvas", "getcontext", "requestanimationframe", "ctx."],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Persistence / Local Storage (Unlocked for Balanced & Ultra tiers or explicitly requested)
    if (max_milestones > 4 or any(k in lowered for k in ["save", "load", "storage", "persist", "history"])) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_persistence",
            "name": "State Persistence & Storage Engine",
            "desc": "Client-side state persistence (localStorage/sessionStorage with safe try/catch wrapper) to retain data across reloads.",
            "required_signals": ["localstorage", "sessionstorage", "setitem", "getitem", "json.stringify"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Theme Switcher / Visual Customization (Unlocked for Balanced & Ultra tiers or requested)
    if (max_milestones > 4 or any(k in lowered for k in ["theme", "dark", "mode", "accent", "color", "toggle"])) and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_theme",
            "name": "Theme & Presentation Customization",
            "desc": "Interactive theme toggle (dark/light mode or visual presets) updating CSS variables and data attributes.",
            "required_signals": ["theme", "dark", "light", "data-theme", "style", "class"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: Responsive Mobile & Multi-Viewport Layout (Unlocked for Ultra tier)
    if max_milestones >= 8 and len(milestones) < max_milestones:
        milestones.append({
            "id": "milestone_responsive",
            "name": "Responsive Multi-Device Layout",
            "desc": "Adaptive mobile & tablet layout using media queries, flexible grid/flexbox, and viewport optimization.",
            "required_signals": ["@media", "flex-wrap", "grid-template-columns", "viewport"],
            "status": "pending",
            "turn_verified": None
        })

    # Milestone: General Interactive CRUD Operations (if specific features above didn't trigger)
    capabilities = (scout_res or {}).get("capabilities", {})
    if len(milestones) < 2 and (capabilities.get("add") or capabilities.get("delete") or capabilities.get("update")):
        milestones.append({
            "id": "milestone_crud",
            "name": "Interactive State & CRUD Handlers",
            "desc": "Full state management in app.js with dynamic addition, removal, or editing of items.",
            "required_signals": ["addeventlistener", "push", "filter", "innerhtml", "createelement"],
            "status": "pending",
            "turn_verified": None
        })

    # Guarantee at least 2 milestones for genuine multi-step execution
    if len(milestones) < 2:
        milestones.append({
            "id": "milestone_interactivity",
            "name": "Dynamic DOM Event Handlers & State Management",
            "desc": "Click handlers, inputs, and state updates wired in app.js matching the prompt.",
            "required_signals": ["addeventlistener", "queryselector", "onclick"],
            "status": "pending",
            "turn_verified": None
        })

    # Dynamically cap according to compute tier profile
    return milestones[:max_milestones]


def verify_milestones(proj_dir: Path, milestones: List[Dict[str, Any]], current_step: int = 1) -> Dict[str, Any]:
    """
    Evaluates codebase on disk against each milestone's required signals and DOM elements.
    Returns completion state, updated milestones, and prescriptive next-step feedback for the LLM.
    """
    html_file = proj_dir / "index.html"
    js_file = proj_dir / "app.js"
    css_file = proj_dir / "styles.css"
    py_files = list(proj_dir.glob("*.py"))

    html_content = html_file.read_text(encoding="utf-8", errors="replace").lower() if html_file.exists() else ""
    js_content = js_file.read_text(encoding="utf-8", errors="replace").lower() if js_file.exists() else ""
    css_content = css_file.read_text(encoding="utf-8", errors="replace").lower() if css_file.exists() else ""
    py_content = " ".join([f.read_text(encoding="utf-8", errors="replace").lower() for f in py_files])

    all_code = f"{html_content}\n{js_content}\n{css_content}\n{py_content}"

    completed_count = 0
    next_uncompleted: Optional[Dict[str, Any]] = None

    for m in milestones:
        m_id = m["id"]
        is_verified = False

        if m_id == "milestone_layout":
            # Needs HTML file, doctype, at least 2 semantic tags or canvas, and linked styles
            has_html = html_file.exists() and len(html_content) > 300
            has_semantic = any(tag in html_content for tag in ["<header", "<section", "<main", "<nav", "<canvas"])
            has_css = css_file.exists() and len(css_content) > 100
            is_verified = has_html and has_semantic and (has_css or "style" in html_content)

        elif m_id == "milestone_timer":
            has_interval = any(s in js_content for s in ["setinterval", "clearinterval", "date.now"])
            has_time_ui = any(s in html_content for s in ["timer", "clock", "countdown", "00:", "25:", "time", "dial"])
            has_controls = any(s in all_code for s in ["start", "pause", "reset"])
            is_verified = has_interval and has_time_ui and has_controls

        elif m_id == "milestone_audio":
            has_audio = any(s in js_content for s in [
                "audiocontext", "webkitaudiocontext", "audio(", "createoscillator",
                "playbeep", "playaudio", "sound", "sfx"
            ])
            is_verified = has_audio

        elif m_id == "milestone_tasks":
            has_task_ui = any(s in html_content for s in ["task", "todo", "objective", "goal"])
            has_task_logic = any(s in js_content for s in [
                "task", "todo", "checkbox", "done", "complete", "push(", "array", "li"
            ])
            is_verified = has_task_ui and has_task_logic

        elif m_id == "milestone_search":
            has_search_ui = any(s in html_content for s in ["search", "filter", "input"])
            has_search_logic = any(s in js_content for s in ["filter(", "includes(", "indexof(", "keyup", "input"])
            is_verified = has_search_ui and has_search_logic

        elif m_id == "milestone_cart":
            has_cart_ui = any(s in html_content for s in ["cart", "shop", "checkout", "product"])
            has_cart_logic = any(s in js_content for s in ["cart", "price", "count", "drawer", "modal"])
            is_verified = has_cart_ui and has_cart_logic

        elif m_id == "milestone_canvas_game":
            has_canvas = "<canvas" in html_content
            has_render = any(s in js_content for s in ["getcontext", "requestanimationframe", "ctx."])
            is_verified = has_canvas and has_render

        elif m_id in ("milestone_crud", "milestone_interactivity"):
            has_listeners = "addeventlistener" in js_content or "onclick" in html_content
            has_state = any(s in js_content for s in ["let ", "const ", "var "]) and len(js_content) > 150
            is_verified = has_listeners and has_state

        elif m_id == "milestone_persistence":
            has_storage = any(s in js_content for s in ["localstorage", "sessionstorage", "setitem", "getitem", "json.stringify"])
            is_verified = has_storage

        elif m_id == "milestone_theme":
            has_theme = any(s in all_code for s in ["theme", "dark", "light", "data-theme", "toggle-theme", "theme-toggle"])
            is_verified = has_theme

        elif m_id == "milestone_responsive":
            has_resp = any(s in css_content for s in ["@media", "flex-wrap", "grid-template-columns", "minmax"]) or "viewport" in html_content
            is_verified = has_resp

        else:
            # Fallback signal matching
            req_sigs = m.get("required_signals", [])
            signals_found = sum(1 for s in req_sigs if s in all_code)
            is_verified = signals_found >= max(1, len(req_sigs) // 2)

        if is_verified:
            m["status"] = "verified"
            if not m.get("turn_verified"):
                m["turn_verified"] = current_step
            completed_count += 1
        else:
            m["status"] = "pending"
            if not next_uncompleted:
                next_uncompleted = m

    all_completed = (completed_count == len(milestones))

    # Formulate prescriptive prompt injection for the next turn
    feedback_lines = []
    if not all_completed and next_uncompleted:
        verified_names = [m["name"] for m in milestones if m["status"] == "verified"]
        if verified_names:
            feedback_lines.append(f"Completed Milestones ({completed_count}/{len(milestones)}): {', '.join(verified_names)}")
        feedback_lines.append(
            f"NEXT UNCOMPLETED MILESTONE: '{next_uncompleted['name']}'\n"
            f"Requirement: {next_uncompleted['desc']}\n"
            f"MANDATORY AUTONOMOUS ACTION: You are not allowed to conclude or declare final answer yet. "
            f"You MUST use 'edit_project_file' or 'write_project_file' to implement '{next_uncompleted['name']}' now!"
        )

    return {
        "all_completed": all_completed,
        "completed_count": completed_count,
        "total_count": len(milestones),
        "milestones": milestones,
        "next_uncompleted": next_uncompleted,
        "feedback_prompt": "\n".join(feedback_lines)
    }


def format_goal_checklist_for_prompt(milestones: List[Dict[str, Any]]) -> str:
    """Formats the goal checklist for injection into system prompt or user turn."""
    lines = [
        "=== AUTONOMOUS GOAL CHECKLIST (Acceptance Criteria) ===",
        "You must complete every milestone below before declaring 'Final Answer':"
    ]
    for idx, m in enumerate(milestones, 1):
        mark = "[x] [VERIFIED]" if m["status"] == "verified" else "[ ] [PENDING]"
        lines.append(f"  {idx}. {mark} {m['name']}: {m['desc']}")
    lines.append("RULE: The autonomous harness will reject early stops until all items show [VERIFIED]!")
    return "\n".join(lines)
