import re
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional

def extract_prompt_keywords(prompt: str) -> List[str]:
    """Extracts search keywords (nouns, domain terms) from user prompt dynamically."""
    stop_words = {
        "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is", "are",
        "make", "build", "create", "code", "develop", "generate", "implement", "write",
        "with", "my", "your", "like", "using", "from", "that", "this", "app", "application",
        "website", "site", "project", "system", "please", "can", "you", "me", "working", "works", "work", "click", "views", "view", "page", "pages", "add", "remove", "update", "delete", "buttons", "button", "implement"
    }
    cleaned = re.sub(r'[^a-zA-Z0-9\s\-]', ' ', prompt.lower())
    words = [w.strip() for w in cleaned.split() if len(w.strip()) > 2]
    keywords = [w for w in words if w not in stop_words]
    return keywords or ["web", "application"]


def extract_atomic_requirements(prompt: str) -> Dict[str, Any]:
    """
    Antigravity Atomic Requirement Extraction:
    Dynamically extracts brand names, featured personas (teachers, doctors, founders),
    and core feature directives without domain hardcoding.
    """
    reqs = {
        "brand_name": None,
        "persona_name": None,
        "explicit_features": []
    }

    # 1. Extract Brand / Project Name (e.g. named New Vinayak Tuition Center)
    brand_match = re.search(r'\b(?:named|called|titled)\s+["\']?([^,.\n]+?)(?:["\']?\s+(?:featuring|with|by|for|and)|["\']?$)', prompt, re.IGNORECASE)
    if brand_match:
        b = brand_match.group(1).strip()
        if len(b) > 2 and len(b) < 60:
            reqs["brand_name"] = b.title()

    # 2. Extract Featured Persona (teacher, trainer, founder, author, doctor, coach, etc.)
    # Note \b after group ensures "coach" does not match "coaching"
    persona_match = re.search(r'\b(?:teacher|trainer|instructor|faculty|founder|author|mentor|doctor|coach|expert|director)\b\s*(?:name)?\s*(?:as|is|named)?\s*["\']?([a-zA-Z\s]{3,35})["\']?', prompt, re.IGNORECASE)
    if not persona_match:
        persona_match = re.search(r'\bfeaturing\s+(?:teacher|founder|instructor)?\s*["\']?([a-zA-Z\s]{3,35})["\']?', prompt, re.IGNORECASE)
    if not persona_match:
        persona_match = re.search(r'\b(?:portfolio|resume|cv|website|page|site)\s+(?:for|of)\s+["\']?([a-zA-Z\s]{3,35})["\']?', prompt, re.IGNORECASE)

    if persona_match:
        p = persona_match.group(1).strip()
        p = re.sub(r'\s+(?:and|with|for|in|at)\b.*$', '', p, flags=re.IGNORECASE).strip()
        if len(p) > 2 and len(p) < 40:
            reqs["persona_name"] = p.title()

    # 3. Extract Explicit Feature clauses ("with X", "featuring Y", "where we can Z")
    with_matches = re.findall(r'\b(?:with|where we can|featuring|support|allow|have)\s+([^,.\n]+)', prompt, re.IGNORECASE)
    for wm in with_matches:
        feat = wm.strip()
        if len(feat) > 3 and len(feat) < 60:
            reqs["explicit_features"].append(feat)

    # 4. Extract Core Interactive Capabilities (CRUD & Operations)
    capabilities = {}
    lowered = prompt.lower()
    if re.search(r'\b(add|create|new|insert|upload|register|post)\b', lowered):
        capabilities["add"] = True
    if re.search(r'\b(remove|delete|drop|trash|clear|cancel)\b', lowered):
        capabilities["delete"] = True
    if re.search(r'\b(update|edit|modify|change|rename)\b', lowered):
        capabilities["update"] = True
    if re.search(r'\b(search|filter|find|query)\b', lowered):
        capabilities["search"] = True

    reqs["capabilities"] = capabilities
    return reqs


def search_huggingface_schema(keywords: List[str]) -> Optional[Dict[str, Any]]:
    """
    Dynamically queries Hugging Face datasets hub for schemas and metadata.
    Uses in-memory cache to eliminate external network latency (<0.1ms on hit).
    Times out in 1.5s to ensure the Scout pre-flight never hangs.
    """
    for kw in keywords[:3]:
        cache_key = f"hf_dataset_{kw.lower()}"
        try:
            from backend.core.resource_cache import WorkspaceResourceCache
            cached = WorkspaceResourceCache.get_scout_contract(cache_key)
            if cached:
                return cached
        except Exception:
            pass

        try:
            url = f"https://huggingface.co/api/datasets?search={urllib.parse.quote(kw)}&limit=3&full=true"
            req = urllib.request.Request(url, headers={"User-Agent": "AITrainer-Scout/2.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if data and isinstance(data, list):
                    for item in data:
                        ds_id = item.get("id", "")
                        desc = item.get("description", "") or ""
                        desc_clean = re.sub(r'[\r\n\t]+', ' ', desc).strip()
                        if len(desc_clean) > 200:
                            desc_clean = desc_clean[:200] + "..."
                        result = {
                            "source": "Hugging Face Hub",
                            "dataset_id": ds_id,
                            "keyword": kw,
                            "description": desc_clean or f"Authoritative dataset for '{kw}'",
                            "tags": [t for t in item.get("tags", []) if isinstance(t, str) and not t.startswith("region:")][:4],
                            "downloads": item.get("downloads", 0)
                        }
                        try:
                            from backend.core.resource_cache import WorkspaceResourceCache
                            WorkspaceResourceCache.set_scout_contract(cache_key, result)
                        except Exception:
                            pass
                        return result
        except Exception:
            # Silently fall through to local gateway fallback
            continue
    return None


def run_scout_phase(user_prompt: str, project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Autonomous Scout Pre-Flight Engine:
    1. Dissects prompt into technical requirements (Data vs Tool vs Game vs CLI).
    2. Queries Hugging Face / Gateway datasets dynamically (zero hardcoding).
    3. Performs Atomic Requirement Extraction (brand name, persona name, specific features).
    4. Produces a strict Architecture Contract:
       - Dynamic file dependency tree (files needed)
       - Data schema & seed models (< 250 tokens)
       - Required semantic section layout
       - DOM ID & event binding contract
    """
    start_t = time.perf_counter()
    lowered = user_prompt.lower()
    keywords = extract_prompt_keywords(user_prompt)

    # 1. Project Archetype & Tech Stack Inference
    is_cli_or_python = bool(re.search(r'\b(python|cli|script|terminal|scraper|bot|backend|api\s+server|fastapi|flask)\b', lowered))
    is_game = bool(re.search(r'\b(game|arcade|snake|pong|flappy|tetris|breakout|platformer|space\s+shooter)\b', lowered)) or ("canvas" in lowered and "game" in lowered)
    is_tool = bool(re.search(r'\b(calculator|stopwatch|pomodoro|timer|todo\s+list|drawing\s+pad|markdown\s+previewer)\b', lowered))
    is_data_app = not is_cli_or_python and not is_game and not is_tool

    # 2. Dynamic Dataset / Reference Schema Search
    dataset_info = None
    # If project already exists and has established files, check if user is asking to update/modify it
    is_existing_project = project_dir and (project_dir / "index.html").exists()
    if is_data_app and not is_existing_project:
        dataset_info = search_huggingface_schema(keywords)
        # Check local gateway datasets if Hugging Face was offline or empty
        if not dataset_info:
            try:
                from backend.core.knowledge_gateway import query_knowledge_gateway
                gw_res = query_knowledge_gateway(user_prompt)
                if gw_res.get("matched"):
                    dataset_info = {
                        "source": "Verified Knowledge Gateway",
                        "dataset_id": gw_res.get("dataset_id"),
                        "dataset_name": gw_res.get("dataset_name"),
                        "description": "Local cached domain architecture and verified schema."
                    }
            except Exception:
                pass

    # 3. Dynamic File Dependency Tree Generation
    files_plan = []
    if is_cli_or_python:
        files_plan = [
            {"path": "requirements.txt", "purpose": "Python dependencies and runtime packages", "depends_on": []},
            {"path": "main.py", "purpose": "Primary entrypoint, CLI argument parser, and business logic", "depends_on": ["requirements.txt"]}
        ]
    elif is_game:
        files_plan = [
            {"path": "index.html", "purpose": "HTML5 Canvas viewport, HUD score overlays, and game controls", "depends_on": []},
            {"path": "styles.css", "purpose": "Fullscreen arcade styling, HUD typography, and button states", "depends_on": ["index.html"]},
            {"path": "app.js", "purpose": "Game loop (requestAnimationFrame), collision physics, and keyboard handlers", "depends_on": ["index.html"]}
        ]
    elif is_tool:
        files_plan = [
            {"path": "index.html", "purpose": "Interactive tool layout, input fields, and output displays", "depends_on": []},
            {"path": "styles.css", "purpose": "Clean responsive interface, action buttons, and active states", "depends_on": ["index.html"]},
            {"path": "app.js", "purpose": "Tool state machine, calculation logic, and DOM event listeners", "depends_on": ["index.html"]}
        ]
    else:
        # Full Responsive Data-Driven Web Application (e.g. Netflix, Coaching Center, Store, Dashboard, Portal)
        # 3 modular files (HTML, CSS, JS) is the proven sweet spot for 8B models (keeps state in app.js, avoids data.js syntax bottlenecks)
        files_plan = [
            {"path": "index.html", "purpose": "Multi-section semantic layout with navbar, hero, interactive cards/grid, and Add/Edit modals", "depends_on": []},
            {"path": "styles.css", "purpose": "Modern design system, responsive card grid, typography, badges, and modal overlays", "depends_on": ["index.html"]},
            {"path": "app.js", "purpose": "Client-side state manager, initial seed records, CRUD functions (Add/Delete/Update), filtering, and event listeners", "depends_on": ["index.html"]}
        ]

    # 4. Extract Atomic Requirements (Brand, Persona, Capabilities)
    atomic_reqs = extract_atomic_requirements(user_prompt)
    brand_name = atomic_reqs.get("brand_name")
    persona_name = atomic_reqs.get("persona_name")
    explicit_features = atomic_reqs.get("explicit_features") or []
    capabilities = atomic_reqs.get("capabilities") or {}

    # 5. Generate Dynamic DOM & Interaction Contract
    primary_entity = keywords[0] if keywords else "item"
    if is_existing_project:
        try:
            html_txt = (project_dir / "index.html").read_text(encoding="utf-8", errors="ignore")
            grid_match = re.search(r'id=["\']([a-zA-Z0-9_-]+)(?:Grid|Container|List)["\']', html_txt, re.IGNORECASE)
            if grid_match:
                primary_entity = grid_match.group(1).lower()
        except Exception:
            pass
    dom_contract = {
        "primary_container": f"#{primary_entity}Grid" if is_data_app else "#appContainer",
        "filter_or_search": f"#{primary_entity}Search" if is_data_app else "#controlInput",
        "action_button": f"#submit{primary_entity.capitalize()}Btn" if is_data_app else "#actionBtn",
        "feedback_element": f"#{primary_entity}Count" if is_data_app else "#statusDisplay"
    }

    if capabilities.get("add"):
        dom_contract["add_form"] = f"#add{primary_entity.capitalize()}Form"
        dom_contract["add_input"] = f"#{primary_entity}TitleInput"
        dom_contract["add_submit_btn"] = f"#submitAdd{primary_entity.capitalize()}Btn"

    if capabilities.get("delete"):
        dom_contract["delete_action"] = f".btn-delete-{primary_entity}"

    if capabilities.get("update"):
        dom_contract["update_modal"] = f"#edit{primary_entity.capitalize()}Modal"

    # Dynamic Section Checklist based on domain and extracted entities
    section_checklist = ["Header with brand identity & navigation", "Hero showcase with search or call-to-action"]
    if persona_name:
        section_checklist.append(f"Featured Spotlight section showcasing '{persona_name}' (credentials, bio, photo/avatar card)")
    if capabilities.get("add"):
        section_checklist.append(f"Interactive 'Add {primary_entity.capitalize()}' Form or Modal with input fields and submit button")
    if is_data_app:
        section_checklist.append(f"Interactive dynamic card grid / catalog displaying items with action buttons")
    if capabilities.get("update"):
        section_checklist.append(f"Interactive 'Edit / Update' Modal or dialog allowing editing existing {primary_entity} details")
    elif is_game:
        section_checklist.append("Canvas game arena with HUD score overlay and control buttons")
    elif is_tool:
        section_checklist.append("Interactive control panel, input workspace, and dynamic results display")
    section_checklist.append("Footer with navigation links, contact info, and copyright")

    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

    # 6. Build Compact Injection Contract for Builder Model (< 250 tokens)
    scout_contract_text = (
        f"=== SCOUT ARCHITECTURE CONTRACT [Dynamic Planning: {elapsed_ms}ms] ===\n"
        f"Task Category: {'Data-Driven Web Application' if is_data_app else ('CLI Python Script' if is_cli_or_python else ('Interactive Game' if is_game else 'Productivity Tool'))}\n"
        f"Required Target Files (Topological Order): {[f['path'] for f in files_plan]}\n"
    )

    if brand_name or persona_name or explicit_features:
        scout_contract_text += "MANDATORY PROMPT ENTITIES (Acceptance Gate Verified):\n"
        if brand_name:
            scout_contract_text += f"- Brand / Project Name: '{brand_name}' (MUST appear in header, title, and hero)\n"
        if persona_name:
            scout_contract_text += f"- Featured Persona: '{persona_name}' (MUST have dedicated spotlight card or bio section)\n"
        if explicit_features:
            scout_contract_text += f"- Explicit Directives: {', '.join(explicit_features)}\n"

    if capabilities:
        scout_contract_text += "MANDATORY INTERACTIVE CAPABILITIES (Strict Acceptance Gate Verified):\n"
        if capabilities.get("add"):
            scout_contract_text += "- ADD: You MUST create an Add form/inputs in index.html and push to state array in app.js.\n"
        if capabilities.get("delete"):
            scout_contract_text += "- DELETE: You MUST create a Delete/Remove button on each card and remove items from state in app.js.\n"
        if capabilities.get("update"):
            scout_contract_text += "- UPDATE: You MUST create an Edit/Update button and modal/flow to modify existing items in app.js.\n"
        if capabilities.get("search"):
            scout_contract_text += "- SEARCH: You MUST implement live search filtering as user types in input.\n"

    if section_checklist and not is_cli_or_python:
        scout_contract_text += "REQUIRED SEMANTIC SECTIONS (Do NOT create 1-button stubs!):\n"
        for idx, s in enumerate(section_checklist, 1):
            scout_contract_text += f"  {idx}. {s}\n"

    if dataset_info:
        scout_contract_text += (
            f"Authoritative Dataset Grounding [Source: {dataset_info['source']}]:\n"
            f"- Dataset ID: {dataset_info.get('dataset_id') or dataset_info.get('dataset_name')}\n"
            f"- Description: {dataset_info.get('description')}\n"
            f"MANDATE: Populate the UI and mock records using authentic schema attributes of this domain.\n"
        )

    scout_contract_text += (
        f"Mandatory DOM Contract (Parity Check):\n"
        f"- Target Container ID: '{dom_contract['primary_container']}'\n"
        f"- Interaction Input ID: '{dom_contract['filter_or_search']}'\n"
        f"- Primary Action Button ID: '{dom_contract['action_button']}'\n"
        f"- Status / Counter ID: '{dom_contract['feedback_element']}'\n"
        f"RULE: Every ID declared in HTML MUST be bound to a real click/input event handler in app.js!\n"
    )

    return {
        "is_data_app": is_data_app,
        "is_game": is_game,
        "is_tool": is_tool,
        "is_cli": is_cli_or_python,
        "keywords": keywords,
        "dataset_info": dataset_info,
        "files_plan": files_plan,
        "dom_contract": dom_contract,
        "contract_text": scout_contract_text,
        "elapsed_ms": elapsed_ms,
        "entities": atomic_reqs
    }
