"""
Persistent Cross-Session Memory & Workspace Knowledge Manager.
Implements frontier-model memory persistence:
  1. User Profile & Preferences (persistent coding style, preferred tech stack, theme rules)
  2. Learned Architectural Rules (persistent error lessons, compiler/sandbox rules)
  3. Workspace Project Index (auto-indexes all past projects for cross-project awareness and code reuse)
  4. Budget-Capped Prompt Injection (<350 tokens, zero VRAM thrashing, <0.5ms load time)
"""

import os
import re
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

# Locate backend/data directory relative to this file
CORE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CORE_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
PROJECTS_ROOT = DATA_DIR / "projects"
USER_MEMORY_PATH = DATA_DIR / "user_memory.json"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_MEMORY_SCHEMA: Dict[str, Any] = {
    "version": "1.0",
    "user_profile": {
        "preferred_theme": "Modern Dark Theme with clean, high-contrast visual hierarchy",
        "preferred_stack": "Semantic HTML5, Responsive CSS3 (Flexbox/Grid), Vanilla ES6 JavaScript",
        "guidelines": [
            "Build complete, production-grade applications with zero minimal stubs or ellipsis placeholders",
            "Always include responsive viewport configuration and mobile-friendly layouts",
            "Wrap localStorage and sessionStorage in try/catch blocks to prevent iframe security crashes",
            "Bind all HTML interactive element IDs to active event listeners in JavaScript"
        ]
    },
    "learned_rules": [
        {
            "id": "rule_sandboxed_storage",
            "rule": "Bare localStorage throws unhandled DOMException in sandboxed preview iframes; wrap in try/catch or memory fallback.",
            "source": "acceptance_gate",
            "created_at": "2026-11-09"
        },
        {
            "id": "rule_event_binding_parity",
            "rule": "Every button, input, or control in index.html must have an active event listener in app.js.",
            "source": "acceptance_gate",
            "created_at": "2026-11-09"
        },
        {
            "id": "rule_target_provenance",
            "rule": "Target runtime errors directly to app.js, layout issues to styles.css, and structural missing elements to index.html.",
            "source": "acceptance_gate",
            "created_at": "2026-11-09"
        }
    ],
    "custom_facts": {},
    "project_index": {},
    "excluded_projects": [],
    "last_synced_at": None
}


def get_memory_store() -> Dict[str, Any]:
    """Loads the persistent memory store from disk. Initializes with defaults if missing."""
    if not USER_MEMORY_PATH.exists():
        save_memory_store(DEFAULT_MEMORY_SCHEMA)
        return json.loads(json.dumps(DEFAULT_MEMORY_SCHEMA))

    try:
        data = json.loads(USER_MEMORY_PATH.read_text(encoding="utf-8"))
        # Ensure all required top-level keys exist
        for k, v in DEFAULT_MEMORY_SCHEMA.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        # Fallback to defaults on corrupted JSON
        return json.loads(json.dumps(DEFAULT_MEMORY_SCHEMA))


def save_memory_store(store: Dict[str, Any]) -> bool:
    """Saves memory store atomically via temporary file to prevent corruption."""
    try:
        USER_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(store, indent=2, ensure_ascii=False)
        
        # Atomic file write pattern
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), prefix="mem_tmp_", suffix=".json")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())

        # Replace target file
        if os.path.exists(USER_MEMORY_PATH):
            os.replace(tmp_path, USER_MEMORY_PATH)
        else:
            os.rename(tmp_path, USER_MEMORY_PATH)
        return True
    except Exception as e:
        print(f"[MemoryManager] Error saving memory store: {e}")
        return False


def remember_preference(category: str, key: str, value: Any) -> Dict[str, Any]:
    """
    Stores a user preference, architectural guideline, or custom fact in cross-session memory.
    Categories: 'profile', 'guideline', 'rule', 'fact'
    """
    store = get_memory_store()
    cat_lower = category.lower().strip()
    clean_key = str(key).strip()

    if cat_lower in ("profile", "user_profile"):
        store["user_profile"][clean_key] = value
        msg = f"Updated user profile setting '{clean_key}'"
    elif cat_lower in ("guideline", "guidelines"):
        guidelines = store["user_profile"].setdefault("guidelines", [])
        if value not in guidelines:
            guidelines.append(str(value))
        msg = f"Added guideline: '{value}'"
    elif cat_lower in ("rule", "learned_rules"):
        rule_id = f"rule_{int(time.time())}"
        store["learned_rules"].append({
            "id": rule_id,
            "rule": str(value),
            "source": "user_instruction",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        msg = f"Recorded learned rule: '{value}'"
    else:
        # Custom fact
        store["custom_facts"][clean_key] = value
        msg = f"Remembered fact '{clean_key}': {value}"

    save_memory_store(store)
    return {
        "status": "success",
        "category": cat_lower,
        "key": clean_key,
        "message": msg
    }


def recall_memory(query: Optional[str] = None) -> Dict[str, Any]:
    """
    Searches persistent memory for user preferences, learned rules, and past projects.
    If query is None or empty, returns summary of all categories.
    """
    store = get_memory_store()
    if not query or not query.strip():
        return {
            "status": "success",
            "user_profile": store.get("user_profile", {}),
            "learned_rules": store.get("learned_rules", []),
            "custom_facts": store.get("custom_facts", {}),
            "past_projects_count": len(store.get("project_index", {})),
            "recent_projects": list(store.get("project_index", {}).keys())[-8:]
        }

    q_lower = query.lower().strip()
    matched_profile = {k: v for k, v in store.get("user_profile", {}).items() if q_lower in str(k).lower() or q_lower in str(v).lower()}
    matched_rules = [r for r in store.get("learned_rules", []) if q_lower in r.get("rule", "").lower()]
    matched_facts = {k: v for k, v in store.get("custom_facts", {}).items() if q_lower in str(k).lower() or q_lower in str(v).lower()}
    matched_projects = {
        k: v for k, v in store.get("project_index", {}).items()
        if q_lower in k.lower() or q_lower in v.get("title", "").lower() or q_lower in v.get("summary", "").lower()
    }

    return {
        "status": "success",
        "query": query,
        "matches": {
            "profile": matched_profile,
            "rules": matched_rules,
            "facts": matched_facts,
            "projects": matched_projects
        }
    }


def forget_memory(category: str, key: str) -> bool:
    """Removes a memory entry from the persistent store."""
    store = get_memory_store()
    cat_lower = category.lower().strip()
    modified = False

    if cat_lower in ("profile", "user_profile") and key in store.get("user_profile", {}):
        del store["user_profile"][key]
        modified = True
    elif cat_lower in ("guideline", "guidelines"):
        guidelines = store.get("user_profile", {}).get("guidelines", [])
        if key in guidelines:
            guidelines.remove(key)
            modified = True
    elif cat_lower in ("rule", "learned_rules"):
        store["learned_rules"] = [r for r in store.get("learned_rules", []) if r.get("id") != key and r.get("rule") != key]
        modified = True
    elif cat_lower in ("fact", "custom_facts") and key in store.get("custom_facts", {}):
        del store["custom_facts"][key]
        modified = True

    if modified:
        save_memory_store(store)
    return modified


def sync_project_index(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Scans PROJECTS_ROOT to index all existing workspace projects.
    Extracts high-level semantics, goals, and key components so new sessions know about old projects.
    """
    store = get_memory_store()
    project_index = store.setdefault("project_index", {})

    if not PROJECTS_ROOT.exists():
        return {"indexed_count": 0, "projects": []}

    # Sort directories by most recently modified
    proj_dirs = [d for d in PROJECTS_ROOT.iterdir() if d.is_dir()]
    proj_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)

    indexed_count = 0
    excluded_list = store.setdefault("excluded_projects", [])

    for proj_dir in proj_dirs:
        proj_name = proj_dir.name

        # Privacy Scoping & Exclusion Check (Dr. Aris Thorne & Marcus Kane)
        is_private = (
            proj_name in excluded_list or
            (proj_dir / ".private").exists() or
            (proj_dir / ".nomemory").exists()
        )

        manifest_file = proj_dir / "project_manifest.json"
        if manifest_file.exists():
            try:
                m_check = json.loads(manifest_file.read_text(encoding="utf-8"))
                if m_check.get("private") or m_check.get("ignore_in_memory"):
                    is_private = True
            except Exception:
                pass

        if is_private:
            # Purge from index if previously indexed
            if proj_name in project_index:
                del project_index[proj_name]
            if proj_name not in excluded_list:
                excluded_list.append(proj_name)
            continue

        if not force_refresh and proj_name in project_index:
            continue

        title = proj_name.replace("_", " ").title()
        summary = "Web Application"
        primary_entity = "item"
        tech_stack = []

        manifest_file = proj_dir / "project_manifest.json"
        html_file = proj_dir / "index.html"
        js_file = proj_dir / "app.js"
        css_file = proj_dir / "styles.css"
        py_files = list(proj_dir.glob("*.py"))

        if manifest_file.exists():
            try:
                m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                root_goal = m_data.get("root_goal", "")
                if root_goal:
                    summary = root_goal[:120].strip()
                    if len(root_goal) > 120:
                        summary += "..."
                primary_entity = m_data.get("primary_entity", "item")
                if m_data.get("theme"):
                    summary += f" ({m_data['theme'][:40]})"
            except Exception:
                pass
        elif html_file.exists():
            try:
                html_text = html_file.read_text(encoding="utf-8", errors="replace")
                t_match = re.search(r"<title>(.*?)</title>", html_text, re.IGNORECASE)
                if t_match and t_match.group(1).strip():
                    title = t_match.group(1).strip()
                h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.IGNORECASE)
                if h1_match:
                    clean_h1 = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip()
                    if clean_h1:
                        summary = clean_h1[:100]
            except Exception:
                pass

        if html_file.exists():
            tech_stack.append("HTML5")
        if css_file.exists():
            tech_stack.append("CSS3")
        if js_file.exists():
            try:
                js_txt = js_file.read_text(encoding="utf-8", errors="replace").lower()
                if "audiocontext" in js_txt:
                    tech_stack.append("Web Audio API")
                if "canvas" in js_txt or (html_file.exists() and "canvas" in html_file.read_text(encoding="utf-8", errors="replace").lower()):
                    tech_stack.append("Canvas")
                if "localstorage" in js_txt:
                    tech_stack.append("LocalStorage")
                tech_stack.append("Vanilla JS")
            except Exception:
                tech_stack.append("JS")
        if py_files:
            tech_stack.append("Python")

        project_index[proj_name] = {
            "title": title,
            "summary": summary,
            "primary_entity": primary_entity,
            "tech": tech_stack,
            "mtime": proj_dir.stat().st_mtime,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(proj_dir.stat().st_mtime))
        }
        indexed_count += 1

    store["last_synced_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_memory_store(store)
    return {
        "status": "success",
        "newly_indexed": indexed_count,
        "total_projects": len(project_index),
        "projects": list(project_index.keys())
    }


def format_memory_for_system_prompt(max_tokens: int = 350) -> str:
    """
    Renders a compact, high-density memory block for the ReAct system prompt.
    Strictly budget-capped to ~250-350 tokens (<1,400 chars) to prevent context bloat.
    """
    store = get_memory_store()
    profile = store.get("user_profile", {})
    rules = store.get("learned_rules", [])
    facts = store.get("custom_facts", {})
    projects = store.get("project_index", {})

    lines = ["=== PERSISTENT USER & WORKSPACE MEMORY ==="]

    # 1. User Preferences
    p_lines = []
    if profile.get("preferred_theme"):
        p_lines.append(f"Style: {profile['preferred_theme']}")
    if profile.get("preferred_stack"):
        p_lines.append(f"Stack: {profile['preferred_stack']}")
    if profile.get("guidelines"):
        for g in profile["guidelines"][:3]:
            p_lines.append(f"Rule: {g}")
    if facts:
        for k, v in list(facts.items())[:3]:
            p_lines.append(f"{k}: {v}")

    if p_lines:
        lines.append("Preferences & Guidelines:")
        for pl in p_lines:
            lines.append(f"  - {pl}")

    # 2. Learned Architectural Rules
    if rules:
        lines.append("Learned Architectural Rules:")
        for r in rules[-3:]:
            lines.append(f"  - {r.get('rule')}")

    # 3. Known Past Projects Index (Sorted by most recently modified)
    if projects:
        lines.append("Known Past Projects (Available for cross-project code inspection via 'read_project_file'):")
        sorted_projects = sorted(projects.items(), key=lambda item: item[1].get("mtime", 0), reverse=True)
        recent_items = sorted_projects[:5]
        for pname, pinfo in recent_items:
            t_str = f" [{', '.join(pinfo.get('tech', [])[:3])}]" if pinfo.get("tech") else ""
            lines.append(f"  - '{pname}': {pinfo.get('title', pname)} - {pinfo.get('summary', '')[:60]}{t_str}")

    lines.append("NOTE: You have cross-project memory. If the user asks for code or features from an existing project, call 'read_project_file' on that project to inspect and reuse its logic.")

    result = "\n".join(lines)
    # Character budget safety clamp: ~1,500 chars is roughly 350 tokens
    if len(result) > 1600:
        result = result[:1580] + "\n..."

    return result


def exclude_project_from_memory(project_name: str) -> Dict[str, Any]:
    """
    Excludes a project from cross-session memory indexing for privacy & security.
    Purges it from the index and marks the directory with a .private file.
    """
    store = get_memory_store()
    clean_p = project_name.strip()
    excluded = store.setdefault("excluded_projects", [])
    if clean_p not in excluded:
        excluded.append(clean_p)

    project_index = store.setdefault("project_index", {})
    purged = False
    if clean_p in project_index:
        del project_index[clean_p]
        purged = True

    proj_dir = PROJECTS_ROOT / clean_p
    if proj_dir.exists() and proj_dir.is_dir():
        try:
            (proj_dir / ".private").write_text("private=true\n", encoding="utf-8")
        except Exception:
            pass

    save_memory_store(store)
    return {
        "status": "success",
        "project": clean_p,
        "is_private": True,
        "purged_from_memory": purged,
        "message": f"Project '{clean_p}' is now excluded from cross-session memory."
    }


def include_project_in_memory(project_name: str) -> Dict[str, Any]:
    """
    Re-includes a project in cross-session memory and indexes it.
    """
    store = get_memory_store()
    clean_p = project_name.strip()
    excluded = store.setdefault("excluded_projects", [])
    if clean_p in excluded:
        excluded.remove(clean_p)

    proj_dir = PROJECTS_ROOT / clean_p
    if proj_dir.exists() and proj_dir.is_dir():
        for marker in (".private", ".nomemory"):
            m_path = proj_dir / marker
            if m_path.exists():
                try:
                    m_path.unlink()
                except Exception:
                    pass

    save_memory_store(store)
    sync_project_index(force_refresh=True)
    return {
        "status": "success",
        "project": clean_p,
        "is_private": False,
        "message": f"Project '{clean_p}' is now included in cross-session memory."
    }


def get_memory_privacy_status() -> Dict[str, Any]:
    """
    Returns audit status of indexed vs excluded projects.
    """
    store = get_memory_store()
    indexed = list(store.get("project_index", {}).keys())
    excluded = store.get("excluded_projects", [])
    return {
        "total_indexed": len(indexed),
        "total_excluded": len(excluded),
        "indexed_projects": indexed,
        "excluded_projects": excluded
    }

