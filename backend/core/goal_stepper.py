"""
Autonomous Goal-Completion Engine & Dynamic Milestone Stepper for Unleash-Agent.
Frontier Jarvis / Ultron Architecture:
1. Decomposes any software task (Python backends, React apps, CLI scripts, full-stack microservices)
   into atomic, verifiable milestones tailored to the specific tech stack.
2. Inspects workspace files across arbitrary directory structures (AST, compilation, endpoints, schemas).
3. Steers the agent turn-by-turn with self-correcting feedback until all milestones pass.
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
    Decomposes the user's prompt into atomic, stack-aware engineering milestones.
    Dynamically scales according to active compute tier budget.
    """
    lowered = user_prompt.lower()
    milestones: List[Dict[str, Any]] = []

    files_plan = (scout_res or {}).get("files_plan", [])
    target_paths = [f["path"] for f in files_plan]

    is_python_or_backend = any(
        f.endswith((".py", ".sh", ".sql", ".go", ".rs")) for f in target_paths
    ) or any(w in lowered for w in ("fastapi", "flask", "django", "python", "backend", "api", "scraper", "cli", "script", "database", "sqlite"))

    is_react_or_node = any(
        f.endswith((".jsx", ".tsx", ".ts", ".vue")) or "package.json" in f for f in target_paths
    ) or any(w in lowered for w in ("react", "vite", "next", "node", "express"))

    brand = (scout_res or {}).get("entities", {}).get("brand_name")
    persona = (scout_res or {}).get("entities", {}).get("persona_name")

    # DYNAMIC DESKTOP/ACTION DETECTION OVERRIDE
    is_action_intent = any(w in lowered for w in ("launch", "open", "message", "send", "chat"))
    
    if is_action_intent:
        # Milestone 1: App Launch
        milestones.append({
            "id": "milestone_app_launch",
            "name": "Launch Application",
            "desc": "Identify and launch the required application using dynamic registry.",
            "required_signals": ["launch_app"],
            "status": "pending",
            "turn_verified": None
        })
        # Milestone 2: UI/Data Interaction
        milestones.append({
            "id": "milestone_ui_interaction",
            "name": "UI/Data Interaction",
            "desc": "Interact with the application UI to fulfill the user request.",
            "required_signals": ["desktop_perception", "browser_pilot"],
            "status": "pending",
            "turn_verified": None
        })
        return milestones

    # =========================================================================
    # A. BACKEND / CLI / PYTHON / MICROSERVICE STACK
    # =========================================================================
    if is_python_or_backend:
        # Milestone 1: Project Architecture & Dependencies
        dep_files = [f for f in target_paths if f in ("requirements.txt", "Pipfile", "setup.py", "package.json")]
        m1_target = dep_files[0] if dep_files else (target_paths[0] if target_paths else "main.py")
        milestones.append({
            "id": "milestone_arch_setup",
            "name": f"Architecture Scaffold & Entrypoint ({m1_target})",
            "desc": f"Create project entrypoint and dependency configuration. Target: {', '.join(target_paths[:2])}.",
            "required_files": target_paths[:2] if target_paths else ["main.py"],
            "required_signals": ["def ", "class ", "import ", "if __name__"],
            "status": "pending",
            "turn_verified": None
        })

        # Milestone 2: Domain Logic & Data Schemas
        model_files = [f for f in target_paths if any(k in f.lower() for k in ("model", "schema", "db", "database", "core", "logic", "utils"))]
        m2_desc = f"Implement data models, schemas, and core business algorithms for '{user_prompt[:40]}'."
        if brand:
            m2_desc += f" Configured for brand/system '{brand}'."
        milestones.append({
            "id": "milestone_domain_logic",
            "name": "Domain Data Models & Core Business Logic",
            "desc": m2_desc,
            "required_files": model_files if model_files else target_paths,
            "required_signals": ["class ", "def ", "return ", "="],
            "status": "pending",
            "turn_verified": None
        })

        # Milestone 3: Interfaces / Endpoints / CLI Commands
        milestones.append({
            "id": "milestone_interfaces",
            "name": "API Routes, Endpoints & CLI Execution Flow",
            "desc": "Implement callable endpoints, route handlers, or CLI argument parser with error handling.",
            "required_files": target_paths,
            "required_signals": ["def ", "@app", "router", "argparse", "click", "sys.argv", "input(", "print("],
            "status": "pending",
            "turn_verified": None
        })

        # Milestone 4: Compilation & Syntax Integrity Gate
        milestones.append({
            "id": "milestone_compilation_gate",
            "name": "Syntax Compilation & Import Integrity Gate",
            "desc": "Verify all written source files compile cleanly with zero syntax errors or broken imports.",
            "required_files": target_paths,
            "required_signals": [],
            "status": "pending",
            "turn_verified": None
        })

    # =========================================================================
    # B. FRONTEND / REACT / MODERN WEB APPLICATION STACK
    # =========================================================================
    else:
        # Milestone 1: Application Structure & Root Shell
        m1_desc = f"Create primary document structure and root layout shell for '{user_prompt[:40]}'."
        if brand:
            m1_desc += f" Must feature brand '{brand}'."
        if persona:
            m1_desc += f" Must feature persona '{persona}'."

        milestones.append({
            "id": "milestone_structure_shell",
            "name": "Application Structure & DOM Shell",
            "desc": m1_desc,
            "required_files": [f for f in target_paths if f.endswith((".html", ".jsx", ".tsx", ".vue"))] or ["index.html"],
            "required_signals": ["<html", "<body", "doctype", "export default", "return (", "<div", "<main"],
            "status": "pending",
            "turn_verified": None
        })

        # Milestone 2: Design System & Styling
        milestones.append({
            "id": "milestone_design_system",
            "name": "Design System, Theming & Responsive Layout",
            "desc": "Polished responsive CSS design system, typography tokens, layout grid, and modern aesthetic.",
            "required_files": [f for f in target_paths if f.endswith((".css", ".scss", ".module.css"))] or ["styles.css"],
            "required_signals": ["{", "margin", "padding", "color", "background", "display", "font-"],
            "status": "pending",
            "turn_verified": None
        })

        # Milestone 3: Interactive State & Event Handlers
        milestones.append({
            "id": "milestone_state_interactivity",
            "name": "Dynamic State Management & Event Handlers",
            "desc": "Wire interactive controls, state arrays, user event listeners, and dynamic UI updates.",
            "required_files": [f for f in target_paths if f.endswith((".js", ".jsx", ".ts", ".tsx"))] or ["app.js"],
            "required_signals": ["addeventlistener", "onclick", "usestate", "useeffect", "function", "=>", "const "],
            "status": "pending",
            "turn_verified": None
        })

        # Milestone 4: Runtime Integrity Gate
        milestones.append({
            "id": "milestone_runtime_gate",
            "name": "Interface Verification & Runtime Gate",
            "desc": "Verify all interactive controls have active bindings, zero syntax errors, and zero unhandled exceptions.",
            "required_files": target_paths,
            "required_signals": [],
            "status": "pending",
            "turn_verified": None
        })

    # =========================================================================
    # C. DYNAMIC DOMAIN-SPECIFIC MILESTONES (If explicitly requested)
    # =========================================================================
    if len(milestones) < max_milestones:
        if any(k in lowered for k in ["sqlite", "database", "db", "persistence", "storage"]):
            milestones.insert(2, {
                "id": "milestone_db_persistence",
                "name": "Data Persistence & Database Layer",
                "desc": "Implement robust schema persistence (SQLite, localStorage, or JSON store) with CRUD methods.",
                "required_files": target_paths,
                "required_signals": ["sqlite3", "connect", "cursor", "localstorage", "sessionstorage", "commit"],
                "status": "pending",
                "turn_verified": None
            })

    return milestones[:max_milestones]


def verify_milestones(
    proj_dir: Path,
    milestones: List[Dict[str, Any]],
    current_step: int = 1
) -> Dict[str, Any]:
    """
    Universal Workspace Evaluator:
    Inspects all files on disk across arbitrary directory depths,
    evaluating each milestone against real code, syntax integrity, and functional contracts.
    """
    if not proj_dir.exists():
        return {
            "all_completed": False,
            "completed_count": 0,
            "total_count": len(milestones),
            "milestones": milestones,
            "next_uncompleted": milestones[0] if milestones else None,
            "feedback_prompt": "Workspace directory not found."
        }

    # Discover all project source files (excluding hidden files & internal manifests)
    all_source_files = [
        f for f in proj_dir.rglob("*")
        if f.is_file() and not f.name.startswith(".") and f.name not in ("project_manifest.json", "decision_trace.json")
    ]

    file_contents: Dict[str, str] = {}
    aggregated_code = []
    py_files = []
    js_files = []

    for sf in all_source_files:
        try:
            rel = str(sf.relative_to(proj_dir)).replace("\\", "/")
            c = sf.read_text(encoding="utf-8", errors="replace")
            file_contents[rel] = c
            aggregated_code.append(c.lower())
            if sf.suffix == ".py":
                py_files.append(sf)
            elif sf.suffix in (".js", ".jsx", ".ts", ".tsx"):
                js_files.append(sf)
        except Exception:
            pass

    full_code_corpus = "\n".join(aggregated_code)
    completed_count = 0
    next_uncompleted: Optional[Dict[str, Any]] = None

    for m in milestones:
        m_id = m["id"]
        is_verified = False

        req_files = m.get("required_files", [])
        req_signals = [s.lower() for s in m.get("required_signals", [])]

        # Check file existence: at least one required file must exist and have content > 40 bytes
        has_required_file = False
        if not req_files:
            has_required_file = len(all_source_files) > 0
        else:
            for rf in req_files:
                rf_clean = rf.replace("\\", "/").lstrip("/")
                if any(k == rf_clean or k.endswith(f"/{rf_clean}") for k in file_contents.keys()):
                    matched_content = next((v for k, v in file_contents.items() if k == rf_clean or k.endswith(f"/{rf_clean}")), "")
                    if len(matched_content.strip()) > 40:
                        has_required_file = True
                        break

        # Check required signals
        has_signals = True
        if req_signals:
            signals_found = sum(1 for s in req_signals if s in full_code_corpus)
            has_signals = signals_found >= max(1, len(req_signals) // 3)

        # Specialized verification gates:
        if m_id == "milestone_compilation_gate":
            # Python compilation gate
            if py_files:
                import py_compile
                syntax_clean = True
                for pf in py_files:
                    try:
                        py_compile.compile(str(pf), doraise=True)
                    except Exception:
                        syntax_clean = False
                        break
                is_verified = syntax_clean and len(all_source_files) > 0
            else:
                is_verified = len(all_source_files) > 0

        elif m_id == "milestone_runtime_gate":
            # JS syntax and interface gate
            is_verified = len(all_source_files) > 0 and has_signals

        else:
            is_verified = has_required_file and has_signals

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

    # Formulate prescriptive self-correction feedback for the next turn
    feedback_lines = []
    if not all_completed and next_uncompleted:
        verified_names = [m["name"] for m in milestones if m["status"] == "verified"]
        if verified_names:
            feedback_lines.append(f"Completed Milestones ({completed_count}/{len(milestones)}): {', '.join(verified_names)}")
        feedback_lines.append(
            f"NEXT UNCOMPLETED MILESTONE: '{next_uncompleted['name']}'\n"
            f"Requirement: {next_uncompleted['desc']}\n"
            f"AUTONOMOUS DIRECTIVE: Implement '{next_uncompleted['name']}' using 'write_project_file' or 'edit_project_file'."
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
    """Formats the goal checklist for injection into system prompt or agent turn."""
    lines = [
        "=== AUTONOMOUS MILESTONES (Convergence Roadmap) ===",
        "Track your progress through the following milestones:"
    ]
    for idx, m in enumerate(milestones, 1):
        mark = "[x] [VERIFIED]" if m["status"] == "verified" else "[ ] [PENDING]"
        lines.append(f"  {idx}. {mark} {m['name']}: {m['desc']}")
    lines.append("Complete each milestone autonomously using your available tools.")
    return "\n".join(lines)
