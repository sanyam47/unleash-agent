import json
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional

MANIFEST_FILENAME = "project_manifest.json"

def extract_project_metadata(initial_prompt: str, scout_res: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Dynamically infers and compiles the Project Manifest from the user's initial prompt
    and Scout pre-flight analysis. 100% dynamic - never hardcoded.
    """
    lowered = initial_prompt.lower()
    
    # 1. Determine Archetype & Root Goal
    root_goal = initial_prompt.strip()
    if len(root_goal) > 120:
        root_goal = root_goal[:117] + "..."
        
    # 2. Extract Primary Entity
    primary_entity = "item"
    if scout_res and scout_res.get("keywords"):
        primary_entity = scout_res["keywords"][0]
    else:
        m = re.search(r'\b(series|movies?|videos?|products?|games?|tasks?|notes?|crypto|songs?|books?|recipes?|users?|posts?|cards?)\b', lowered)
        if m:
            matched_ent = m.group(1)
            primary_entity = matched_ent if matched_ent == "series" else matched_ent.rstrip("s")
            
    # 3. Dynamic Theme Archetype
    theme = "Modern Responsive Web Theme"
    if any(k in lowered for k in ["netflix", "dark", "cinema", "stream", "movie", "theater"]):
        theme = "Cinematic Dark Streaming Theme (#141414, #E50914 red accents, high-contrast cards)"
    elif any(k in lowered for k in ["amazon", "store", "shop", "e-commerce", "cart", "market"]):
        theme = "Modern E-Commerce Storefront (Product cards, price tags, shopping cart drawer)"
    elif any(k in lowered for k in ["game", "arcade", "retro", "canvas", "snake", "pong", "flappy"]):
        theme = "Retro Arcade Gaming Theme (Dark canvas arena, HUD score overlay, neon highlights)"
    elif any(k in lowered for k in ["crypto", "finance", "stock", "wallet", "trading", "dashboard"]):
        theme = "High-Tech Financial Dashboard (Data charts, metrics pills, real-time ticker style)"
    elif any(k in lowered for k in ["coaching", "school", "course", "learn", "tuition", "academy"]):
        theme = "Clean Academic Portal (Course tracks, faculty cards, enrollment modals)"
        
    # 4. Dynamic Active Views
    views = ["Home"]
    view_matches = re.findall(r'\b(home|series|movies|shows|episodes|cart|checkout|store|catalog|shop|settings|profile|analytics|about|contact|courses|classes)\b', lowered)
    for v in view_matches:
        v_title = v.capitalize()
        if v_title not in views:
            views.append(v_title)
    if len(views) == 1:
        views = ["Home", "Catalog", "Details"]

    return {
        "root_goal": root_goal,
        "primary_entity": primary_entity,
        "theme": theme,
        "active_views": views,
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S')
    }

def get_or_create_manifest(proj_dir: Path, user_prompt: str, scout_res: Optional[Dict[str, Any]] = None, is_new: bool = False) -> Dict[str, Any]:
    """
    Retrieves existing project manifest or dynamically creates one for a new project.
    Uses mtime LRU cache to prevent disk reads on hot turns.
    """
    manifest_file = proj_dir / MANIFEST_FILENAME
    if manifest_file.exists() and not is_new:
        try:
            from backend.core.resource_cache import WorkspaceResourceCache
            cached = WorkspaceResourceCache.get_manifest(manifest_file)
            if cached:
                return cached
        except Exception:
            pass

        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            try:
                from backend.core.resource_cache import WorkspaceResourceCache
                WorkspaceResourceCache.set_manifest(manifest_file, data)
            except Exception:
                pass
            return data
        except Exception:
            pass

    # Create new dynamic manifest
    manifest = extract_project_metadata(user_prompt, scout_res)
    try:
        proj_dir.mkdir(parents=True, exist_ok=True)
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        try:
            from backend.core.resource_cache import WorkspaceResourceCache
            WorkspaceResourceCache.set_manifest(manifest_file, manifest)
        except Exception:
            pass
    except Exception as e:
        print(f"[Manifest Write Error]: {e}")
    return manifest

def format_manifest_for_prompt(manifest: Dict[str, Any]) -> str:
    """
    Formats the project manifest into an authoritative continuity mandate for the LLM prompt.
    """
    if not manifest:
        return ""
    views_str = ", ".join(manifest.get("active_views", ["Home"]))
    return (
        "\n=== PERSISTENT PROJECT GOAL & MANIFEST ===\n"
        f"- Root Project Goal: {manifest.get('root_goal')}\n"
        f"- Primary Domain Entity: '{manifest.get('primary_entity')}'\n"
        f"- Visual Design & Theme: {manifest.get('theme')}\n"
        f"- Established Views / Pages: [{views_str}]\n"
        "CONTINUITY RULE: Even if user's follow-up prompt is brief (e.g. 'fix it', 'add a button'), "
        "you are continuing this exact project. Preserve this theme, branding, and entity model without inventing an unrelated app!\n"
    )
