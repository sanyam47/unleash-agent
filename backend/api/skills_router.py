import os
import json
import uuid
import re
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

SKILLS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "skills_library.json")

router = APIRouter(prefix="/api/skills", tags=["Skills Studio"])

class SkillModel(BaseModel):
    id: str
    name: str
    category: str = "general"
    description: str
    version: str = "1.0.0"
    author: str = "Community"
    system_instructions: str
    tools: List[str] = []
    github_url: Optional[str] = None
    source_path: Optional[str] = None
    installed: bool = False
    is_active: bool = False

class InstallSkillRequest(BaseModel):
    skill_id: Optional[str] = None
    github_url: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = "custom"
    description: Optional[str] = ""
    system_instructions: Optional[str] = ""

class BakeModelRequest(BaseModel):
    base_model: str
    new_model_name: Optional[str] = None
    overwrite_existing: bool = True
    skill_ids: List[str]

DEFAULT_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "skill-rea",
        "name": "REA: Reverse Engineer Anything",
        "category": "reverse-engineering",
        "description": "Agentic reverse engineering toolkit inspired by morluto/rea. Equips the model with disassembler reasoning, binary decompilation heuristics, PE/ELF header analysis, and protocol reconstruction workflows.",
        "version": "1.2.0",
        "author": "morluto",
        "github_url": "https://github.com/morluto/rea",
        "installed": True,
        "is_active": True,
        "tools": ["ghidra_decompile", "pe_entropy", "binary_strings", "ast_unmangle"],
        "system_instructions": (
            "You are operating with the REA (Reverse Engineer Anything) specialist skill active.\n"
            "Key operational directives:\n"
            "1. Deep Analysis: When given binary code, assembly (x86/x64/ARM), bytecode, or obfuscated source, systematically break down control flow, data structures, and function calls.\n"
            "2. Evidence-Based Deduction: Anchor every claim to concrete disassembly offsets, strings, or structural indicators.\n"
            "3. Reconstruction: Provide clean pseudocode or idiomatic reimplementations (in Python, C, or Go) of reverse-engineered algorithms.\n"
            "4. Protocol & Format Auditing: Reconstruct byte layouts, packing headers, and network packet structures accurately."
        )
    },
    {
        "id": "skill-cve-exploit-auditor",
        "name": "Cybersecurity & Exploit Auditor",
        "category": "security",
        "description": "Audits source code and memory management for CVE patterns, buffer overflows, RCE primitives, and deserialization flaws.",
        "version": "2.0.1",
        "author": "OffSec Labs",
        "github_url": "https://github.com/mitre/cve-schema",
        "installed": True,
        "is_active": False,
        "tools": ["cve_lookup", "memory_taint_check", "fuzz_payload_gen"],
        "system_instructions": (
            "You are equipped with the Cybersecurity & Exploit Auditor skill.\n"
            "Examine code and architectures strictly from an offensive security and defensive audit perspective.\n"
            "Identify memory safety issues, race conditions, authentication bypasses, and provide remediation patches alongside root-cause analysis."
        )
    },
    {
        "id": "skill-web-recon",
        "name": "Web Scraping & DOM Hunter",
        "category": "web",
        "description": "Automated headless browser navigation, anti-bot bypass strategies, CSS/XPath selector extraction, and API intercept mapping.",
        "version": "1.1.0",
        "author": "ScraperDevs",
        "github_url": "https://github.com/scrapy/scrapy",
        "installed": False,
        "is_active": False,
        "tools": ["playwright_browse", "dom_query", "curl_impersonate"],
        "system_instructions": (
            "You are equipped with the Web Scraping & DOM Hunter skill.\n"
            "Specialize in dynamic DOM parsing, network payload inspection, WebSocket reverse-engineering, and generating robust Playwright/Puppeteer/BeautifulSoup extraction scripts."
        )
    },
    {
        "id": "skill-kernel-debugger",
        "name": "Kernel Driver & Memory Forensic",
        "category": "reverse-engineering",
        "description": "Low-level Windows/Linux driver analysis, IOCTL handler mapping, virtual memory paging, and crash dump analysis.",
        "version": "1.0.0",
        "author": "KernelSys",
        "github_url": "https://github.com/volatilityfoundation/volatility3",
        "installed": False,
        "is_active": False,
        "tools": ["volatility_scan", "ioctl_fuzzer", "pdb_parser"],
        "system_instructions": (
            "You are operating with the Kernel Driver & Memory Forensic skill.\n"
            "Specialize in Ring-0 internals, Windows Kernel IRP dispatch routines, memory dump forensics, and kernel rootkit detection."
        )
    },
    {
        "id": "skill-api-contract-gen",
        "name": "API Reverse Engineer & OpenAPI Generator",
        "category": "coding",
        "description": "Inspects raw network traffic or compiled client apps and automatically reconstructs strict OpenAPI / Swagger schemas and client SDKs.",
        "version": "1.3.0",
        "author": "APIFoundry",
        "github_url": "https://github.com/OAI/OpenAPI-Specification",
        "installed": False,
        "is_active": False,
        "tools": ["har_parser", "schema_infer", "sdk_builder"],
        "system_instructions": (
            "You are equipped with the API Reverse Engineer skill.\n"
            "Given raw HTTP request/response traces or client binary disassembly, systematically infer parameter types, headers, authentication flows, and produce valid OpenAPI 3.1 JSON/YAML schemas."
        )
    }
]

def scan_user_environment_skills() -> List[Dict[str, Any]]:
    """
    Scans the user's environment (~/.gemini plugins & skills)
    and automatically ingests user-provided skills (CodeRabbit, Ralph Loop, etc.)
    into the App Skills Library.
    """
    discovered: List[Dict[str, Any]] = []
    gemini_base = os.path.expanduser(r"~\.gemini")
    if not os.path.exists(gemini_base):
        return discovered

    search_dirs = [
        # 1. Project-level local skills directory (e.g. c:/coding/ai-trainer/skills/)
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "skills")),
        # 2. User Downloads / Custom skills folder
        os.path.expanduser(r"~\Downloads\skills"),
        os.path.expanduser(r"~\.skills"),
        # 3. Standard Antigravity / Gemini ecosystem plugins & skills
        os.path.join(gemini_base, "config", "plugins"),
        os.path.join(gemini_base, "antigravity", "skills"),
        os.path.join(gemini_base, "antigravity", "builtin", "skills")
    ]

    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, dirs, files in os.walk(sdir):
            if "SKILL.md" in files:
                skill_path = os.path.join(root, "SKILL.md")
                try:
                    with open(skill_path, "r", encoding="utf-8") as f:
                        raw = f.read()

                    # Parse YAML frontmatter if present
                    name = os.path.basename(root)
                    desc = f"User skill from {os.path.basename(root)}"
                    body = raw

                    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
                    if fm_match:
                        fm_text, body = fm_match.group(1), fm_match.group(2)
                        for line in fm_text.splitlines():
                            if line.startswith("name:"):
                                name = line.replace("name:", "").strip()
                            elif line.startswith("description:"):
                                desc = line.replace("description:", "").strip()

                    skill_id = f"skill-{re.sub(r'[^a-zA-Z0-9]', '-', name.lower()).strip('-')}"
                    
                    # Deduce category and clean display name
                    cat = "custom"
                    if "coderabbit" in name.lower() or "review" in name.lower():
                        cat = "code-review"
                        author = "CodeRabbit AI"
                    elif "ralph" in name.lower() or "loop" in name.lower():
                        cat = "autonomous-loop"
                        author = "Ralph Loop Engine"
                    elif "ui" in name.lower():
                        cat = "ui-design"
                        author = "Antigravity UI"
                    elif "automation" in name.lower():
                        cat = "automation"
                        author = "Antigravity Workflows"
                    else:
                        author = "User Workspace"

                    display_name = name.replace("-", " ").title()

                    discovered.append({
                        "id": skill_id,
                        "name": display_name,
                        "category": cat,
                        "description": desc,
                        "version": "1.0.0",
                        "author": author,
                        "source_path": skill_path,
                        "installed": True,
                        "is_active": False,
                        "tools": ["skill_automated_workflow"],
                        "system_instructions": body.strip()
                    })
                except Exception as e:
                    print(f"Error scanning skill at {skill_path}: {e}")

    return discovered

def load_skills() -> List[Dict[str, Any]]:
    os.makedirs(os.path.dirname(SKILLS_FILE), exist_ok=True)
    stored_data: List[Dict[str, Any]] = []
    if os.path.exists(SKILLS_FILE):
        try:
            with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                stored_data = json.load(f)
        except Exception:
            stored_data = []

    # Map existing statuses (installed, is_active)
    existing_map = {s["id"]: s for s in stored_data}

    # 1. Start with DEFAULT_CATALOG
    combined = []
    for d in DEFAULT_CATALOG:
        if d["id"] in existing_map:
            d["installed"] = existing_map[d["id"]].get("installed", d.get("installed", False))
            d["is_active"] = existing_map[d["id"]].get("is_active", d.get("is_active", False))
        combined.append(d)

    # 2. Ingest User Environment Skills (CodeRabbit, Ralph Loop, etc.)
    user_skills = scan_user_environment_skills()
    existing_ids = {s["id"] for s in combined}
    for u in user_skills:
        if u["id"] not in existing_ids:
            if u["id"] in existing_map:
                u["installed"] = existing_map[u["id"]].get("installed", True)
                u["is_active"] = existing_map[u["id"]].get("is_active", False)
            combined.append(u)
            existing_ids.add(u["id"])

    # 3. Retain any custom user imported skills that were saved in storage
    for s in stored_data:
        if s["id"] not in existing_ids:
            combined.append(s)
            existing_ids.add(s["id"])

    save_skills(combined)
    return combined

def save_skills(skills: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(SKILLS_FILE), exist_ok=True)
    with open(SKILLS_FILE, "w", encoding="utf-8") as f:
        json.dump(skills, f, indent=2)

@router.get("/list")
def list_skills():
    """Returns all available skills, their install status, and active chat states."""
    skills = load_skills()
    installed = [s for s in skills if s.get("installed")]
    catalog = [s for s in skills if not s.get("installed")]
    return {
        "installed": installed,
        "catalog": catalog,
        "active_ids": [s["id"] for s in installed if s.get("is_active")]
    }

@router.post("/install")
def install_skill(req: InstallSkillRequest):
    """Installs a skill from the marketplace or imports one from GitHub/URL/Custom."""
    skills = load_skills()
    
    # 1. Install from existing catalog ID
    if req.skill_id:
        for s in skills:
            if s["id"] == req.skill_id:
                s["installed"] = True
                save_skills(skills)
                return {"status": "success", "message": f"Installed skill '{s['name']}'", "skill": s}
        raise HTTPException(status_code=404, detail="Skill ID not found in catalog")
    
    # 2. Install from GitHub URL or Custom
    name = req.name or (req.github_url.split("/")[-1].replace(".git", "").replace("-", " ").title() if req.github_url else "Custom Skill")
    new_id = f"skill-{uuid.uuid4().hex[:8]}"
    instructions = req.system_instructions or f"You are equipped with the specialized {name} skill. Apply high precision domain expertise."
    
    new_skill = {
        "id": new_id,
        "name": name,
        "category": req.category or "custom",
        "description": req.description or f"Custom installed skill from {req.github_url or 'user definition'}.",
        "version": "1.0.0",
        "author": "Custom / GitHub",
        "github_url": req.github_url,
        "installed": True,
        "is_active": True,
        "tools": ["custom_tool_execution"],
        "system_instructions": instructions
    }
    skills.insert(0, new_skill)
    save_skills(skills)
    return {"status": "success", "message": f"Successfully created and installed '{name}'", "skill": new_skill}

@router.post("/uninstall/{skill_id}")
def uninstall_skill(skill_id: str):
    skills = load_skills()
    for s in skills:
        if s["id"] == skill_id:
            s["installed"] = False
            s["is_active"] = False
            save_skills(skills)
            return {"status": "success", "message": f"Uninstalled '{s['name']}'"}
    raise HTTPException(status_code=404, detail="Skill not found")

@router.post("/toggle/{skill_id}")
def toggle_skill_active(skill_id: str):
    """One-click toggle to attach or detach a skill in the active Chat Arena session."""
    skills = load_skills()
    target_skill = None
    for s in skills:
        if s["id"] == skill_id:
            s["is_active"] = not s.get("is_active", False)
            target_skill = s
            break
            
    if not target_skill:
        raise HTTPException(status_code=404, detail="Skill not found")
        
    save_skills(skills)
    active_skills = [s for s in skills if s.get("installed") and s.get("is_active")]
    return {
        "status": "success",
        "skill_id": skill_id,
        "is_active": target_skill["is_active"],
        "active_skills_count": len(active_skills),
        "active_skills": active_skills
    }

@router.get("/active_prompt")
def get_active_skills_prompt():
    """Generates the combined system prompt fragment representing all currently active skills."""
    skills = load_skills()
    active_skills = [s for s in skills if s.get("installed") and s.get("is_active")]
    if not active_skills:
        return {"has_active": False, "prompt": "", "skills": []}
    
    parts = ["### ACTIVE SPECIALIST SKILLS & OPERATIONAL RUNTIME:\n"]
    for s in active_skills:
        parts.append(f"[{s['name'].upper()} - v{s.get('version', '1.0')}]")
        parts.append(s["system_instructions"].strip())
        parts.append("")
        
    return {
        "has_active": True,
        "prompt": "\n".join(parts),
        "skills": [{"id": s["id"], "name": s["name"], "tools": s.get("tools", [])} for s in active_skills]
    }

@router.post("/bake_into_model")
def bake_skills_into_model(req: BakeModelRequest):
    """
    Permanently bakes selected skill instructions into an Ollama Modelfile
    and compiles a model (supports both in-place overwrite or new standalone model).
    """
    import subprocess
    from backend.core.paths import PACKAGES_DIR
    
    target_name = req.new_model_name.strip() if req.new_model_name else ""
    if req.overwrite_existing or not target_name:
        clean_name = req.base_model.split(':')[0]
    else:
        clean_name = re.sub(r'[^a-zA-Z0-9_\-\.:]', '-', target_name.lower()).strip('-')
        if not clean_name:
            clean_name = req.base_model.split(':')[0]

    skills = load_skills()
    chosen_skills = [s for s in skills if s["id"] in req.skill_ids]
    if not chosen_skills:
        raise HTTPException(status_code=400, detail="No valid skills selected to bake into model")

    # Build permanent system persona with baked skill capabilities
    skill_text = "\n\n".join([f"### PERMANENT SKILL: {s['name']}\n{s['system_instructions']}" for s in chosen_skills])
    system_persona = (
        f"You are a specialized AI model permanently compiled with enhanced capabilities:\n\n"
        f"{skill_text}\n\n"
        "Always execute tasks adhering strictly to these specialized directives."
    )

    modelfile_content = f"""# Modelfile compiled automatically by AI Studio Skills Engine
FROM {req.base_model}

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM \"\"\"{system_persona}\"\"\"
"""
    os.makedirs(PACKAGES_DIR, exist_ok=True)
    modelfile_path = os.path.join(PACKAGES_DIR, f"Modelfile_baked_{clean_name}_{uuid.uuid4().hex[:6]}")
    with open(modelfile_path, "w", encoding="utf-8") as f:
        f.write(modelfile_content)

    try:
        subprocess.run(
            ["ollama", "create", clean_name, "-f", modelfile_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True
        )
        return {
            "status": "success",
            "model_name": clean_name,
            "base_model": req.base_model,
            "baked_skills": [s["name"] for s in chosen_skills],
            "message": f"Successfully compiled '{clean_name}' with {len(chosen_skills)} baked skill(s)! Ready in Chat Arena."
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Ollama compilation error: {e.stderr or e.stdout}")
    finally:
        if os.path.exists(modelfile_path):
            try:
                os.remove(modelfile_path)
            except Exception:
                pass
