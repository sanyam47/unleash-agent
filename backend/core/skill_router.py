"""
Skill Router & Efficiency Detector for Local AI Models
Implements 3-Tier Robust Detection:
1. Deterministic Slash Commands & Explicit Mentions (/rea, /coderabbit, /ralph, etc.) -> 100% force activation.
2. Semantic & Behavioral Intent Scoring (triggers, tool names, description heuristics).
3. Graceful Clean Fallback: If no confident match is found, keeps prompt clean (0 skills, baseline model).
4. Cognitive Load & Efficiency Drop Detection: Proactively warns when multiple heavy skills cause token inflation.
"""

import re
from typing import List, Dict, Any, Optional, Tuple

# Mapping of slash-command aliases and IDs
SKILL_ALIASES = {
    "skill-rea": ["/rea", "/reverse", "/disasm", "/decompile"],
    "skill-cve-exploit-auditor": ["/cve", "/exploit", "/audit-sec", "/security"],
    "skill-coderabbit-review": ["/coderabbit", "/review", "/pr-review", "/audit-code"],
    "skill-ralph-loop": ["/ralph", "/ralph-loop", "/loop", "/test-fix"],
    "skill-web-recon": ["/scrape", "/recon", "/dom-hunter"],
    "skill-kernel-debugger": ["/kernel", "/windbg", "/ring0"],
    "skill-api-contract-gen": ["/api-spec", "/openapi", "/swagger"]
}

SKILL_INTENT_TRIGGERS = {
    "skill-rea": [
        r"\bdisassembl", r"\bdecompile", r"\bbinary\b", r"\bhex\b", r"\basm\b", r"\bassembly\b",
        r"\bghidra\b", r"\bida\b", r"\br2\b", r"\bradare\b", r"\bpe header\b", r"\belf header\b",
        r"\breverse engineer", r"\bx86\b", r"\bx64\b", r"\barm64\b", r"\bcontrol flow graph\b",
        r"\bcfg\b", r"\bopcode\b", r"\bpayload unpack", r"\bobfuscat"
    ],
    "skill-cve-exploit-auditor": [
        r"\bcve\b", r"\bexploit\b", r"\bvulnerability\b", r"\bbuffer overflow\b", r"\brce\b",
        r"\btaint\b", r"\bmemory leak\b", r"\buse-after-free\b", r"\buaf\b", r"\brop\b",
        r"\bpayload gen\b", r"\bformat string\b", r"\bsql injection\b", r"\bxss\b",
        r"\bsecurity audit\b", r"\bpenetration\b", r"\bred team\b"
    ],
    "skill-coderabbit-review": [
        r"\bcode review\b", r"\bpr review\b", r"\bpull request\b", r"\bgit diff\b",
        r"\breview this code\b", r"\breview my\b", r"\baudit this code\b", r"\bcoderabbit\b",
        r"\bstatic analysis\b", r"\blint review\b"
    ],
    "skill-ralph-loop": [
        r"\bralph\b", r"\btest loop\b", r"\bautonomous fix\b", r"\bdebug loop\b",
        r"\bkeep trying until tests pass\b", r"\btest-and-repair\b", r"\bauto-repair\b",
        r"\biterate until green\b"
    ],
    "skill-web-recon": [
        r"\bscraping\b", r"\bscrape\b", r"\bplaywright\b", r"\bpuppeteer\b", r"\bdom\b",
        r"\banti-bot\b", r"\bcloudflare bypass\b", r"\bxpath\b", r"\bcss selector\b",
        r"\bcrawler\b", r"\bbeautifulsoup\b"
    ],
    "skill-kernel-debugger": [
        r"\bkernel\b", r"\bring-0\b", r"\bring0\b", r"\bdriver\b", r"\bioctl\b",
        r"\bvolatility\b", r"\bcrash dump\b", r"\bblue screen\b", r"\bbsod\b",
        r"\brootkit\b", r"\bwindows paging\b"
    ],
    "skill-api-contract-gen": [
        r"\bopenapi\b", r"\bswagger\b", r"\bapi contract\b", r"\bhar file\b",
        r"\breconstruct api\b", r"\brest api spec\b"
    ]
}


def score_skill_relevance(user_prompt: str, skill: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Computes a relevance score between the user prompt and a skill.
    Returns: (score, is_exact_slash_match)
    """
    prompt_lower = user_prompt.lower()
    skill_id = skill.get("id", "")

    # 1. Tier 1: Check Slash Command Aliases
    aliases = SKILL_ALIASES.get(skill_id, [])
    # Also include the skill's own ID as a slash command (e.g. /skill-rea)
    aliases.append(f"/{skill_id.replace('skill-', '')}")
    aliases.append(f"/{skill_id}")

    for alias in aliases:
        # Check if the prompt starts with the alias or contains it as a discrete token
        if re.search(r"(?:^|\s)" + re.escape(alias) + r"(?:\s|$)", prompt_lower):
            return 999.0, True

    # 2. Tier 2: Triggers & Keywords
    score = 0.0
    triggers = SKILL_INTENT_TRIGGERS.get(skill_id, [])
    for pat in triggers:
        if re.search(pat, prompt_lower):
            score += 3.0

    # Match skill name words (e.g. "reverse engineer", "exploit", "coderabbit")
    name_words = re.findall(r"\w+", skill.get("name", "").lower())
    for w in name_words:
        if len(w) > 3 and w in prompt_lower:
            score += 1.2

    # Match tools
    for t in skill.get("tools", []):
        if t.lower() in prompt_lower:
            score += 2.5

    # Match category
    cat = skill.get("category", "").lower()
    if cat and cat in prompt_lower:
        score += 1.5

    return score, False


def clean_slash_commands_from_prompt(user_prompt: str) -> str:
    """Strips leading or standalone slash command prefixes like /rea or /review from the user text."""
    cleaned = user_prompt
    for aliases in SKILL_ALIASES.values():
        for alias in aliases:
            cleaned = re.sub(r"(?i)(?:^|\s)" + re.escape(alias) + r"(?:\s|$)", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def route_skills_dynamically(
    user_prompt: str,
    installed_skills: List[Dict[str, Any]],
    explicit_skill_ids: Optional[List[str]] = None,
    current_model: str = "dolphin3:latest"
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], str]:
    """
    Antigravity Dynamic Skill Router:
    1. If user explicitly attached specific skills in UI (session.activeSkills), respect them.
    2. Check for explicit slash commands (/rea, /coderabbit, /ralph, etc.) -> 100% force match.
    3. If in dynamic auto-routing mode, calculate match scores:
       - If score >= 2.0: activate the TOP 1 matching skill.
       - If no skill reaches confidence (score < 2.0): fallback to clean base model (0 skills injected).
    4. Detect cognitive overload & efficiency drops when:
       - 2 or more heavy skills are requested simultaneously.
    Returns: (active_skills, bake_recommendation, sanitized_prompt)
    """
    installed_map = {s["id"]: s for s in installed_skills if s.get("installed")}

    # Candidate pool
    if explicit_skill_ids and len(explicit_skill_ids) > 0:
        candidates = [installed_map[sid] for sid in explicit_skill_ids if sid in installed_map]
        user_selected = True
    else:
        candidates = list(installed_map.values())
        user_selected = False

    active_skills: List[Dict[str, Any]] = []
    bake_recommendation: Optional[Dict[str, Any]] = None
    sanitized_prompt = user_prompt

    if not user_selected:
        # Check for explicit slash commands first
        forced_skills = []
        for s in candidates:
            score, is_exact = score_skill_relevance(user_prompt, s)
            if is_exact:
                forced_skills.append(s)

        if forced_skills:
            active_skills = forced_skills
            sanitized_prompt = clean_slash_commands_from_prompt(user_prompt)
        else:
            # Dynamic Semantic Matching
            best_skill = None
            highest_score = 0.0

            for s in candidates:
                sc, _ = score_skill_relevance(user_prompt, s)
                if sc > highest_score:
                    highest_score = sc
                    best_skill = s

            # Confidence Threshold: Must have at least 1 verified match (score >= 2.0)
            # If it fails to detect (e.g. general prompt, unknown domain), falls back to 0 skills!
            if best_skill and highest_score >= 2.0:
                active_skills = [best_skill]
            else:
                active_skills = []
    else:
        # User manually pinned specific skills
        active_skills = candidates

    # Efficiency Drop & Bake Detection
    # When multiple skills (>1) are attached, local 7B/8B models face attention drift, tool collision,
    # and context exhaustion. We proactively calculate the risk.
    if len(active_skills) >= 2 or (user_selected and len(active_skills) > 1):
        total_instructions_len = sum(len(s.get("system_instructions", "")) for s in active_skills)
        est_tokens = total_instructions_len // 4

        skill_names = [s.get("name") for s in active_skills]
        clean_model_base = current_model.split(":")[0]
        suggested_name = f"{clean_model_base}-specialist"

        bake_recommendation = {
            "needed": True,
            "skill_count": len(active_skills),
            "skill_ids": [s["id"] for s in active_skills],
            "skill_names": skill_names,
            "estimated_overhead_tokens": est_tokens,
            "base_model": current_model,
            "suggested_model_name": suggested_name,
            "reason": (
                f"You have {len(active_skills)} skills active simultaneously ({', '.join(skill_names)}). "
                f"Injecting multiple heavy tool sets via prompt overhead (~{est_tokens} tokens) "
                f"causes attention drift and slows down local 7B/8B models. "
                f"Baking them directly into weights or Modelfile eliminates runtime prompt bloat and restores 100% accuracy."
            )
        }

    return active_skills, bake_recommendation, sanitized_prompt
