import os

chat_router_path = r"c:\coding\ai-trainer\backend\api\chat_router.py"
with open(chat_router_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target1 = """    # 0.1 Active Skills Injection
    active_skills_names = []
    try:
        from backend.api.skills_router import load_skills
        all_skills = load_skills()
        if req.skill_ids is not None:
            chosen = [s for s in all_skills if s["id"] in req.skill_ids and s.get("installed")]
        else:
            chosen = [s for s in all_skills if s.get("installed") and s.get("is_active")]
            
        if chosen:
            skill_blocks = ["\\n\\n### ACTIVE SPECIALIST SKILLS & OPERATIONAL RUNTIME:"]
            for s in chosen:
                active_skills_names.append(s["name"])
                skill_blocks.append(f"[{s['name'].upper()} - v{s.get('version', '1.0')}]")
                skill_blocks.append(s["system_instructions"].strip())
            base_sys = f"{base_sys}\\n" + "\\n".join(skill_blocks)
    except Exception as e:
        print(f"[SKILLS] Injection error: {e}")"""

replacement1 = """    # 0.1 Dynamic Antigravity Skill Routing & Efficiency Detection
    active_skills_names = []
    bake_recommendation = None
    skill_blocks = []
    try:
        from backend.api.skills_router import load_skills
        from backend.core.skill_router import route_skills_dynamically
        all_skills = load_skills()

        # Extract latest user message text for dynamic intent routing
        user_texts = [m.content for m in req.messages if m.role == "user"]
        latest_user_text = user_texts[-1] if user_texts else ""

        chosen, bake_recommendation = route_skills_dynamically(
            user_prompt=latest_user_text,
            installed_skills=all_skills,
            explicit_skill_ids=req.skill_ids,
            current_model=req.model
        )

        if chosen:
            skill_blocks = ["\\n\\n### ACTIVE SPECIALIST SKILLS & OPERATIONAL RUNTIME:"]
            for s in chosen:
                active_skills_names.append(s["name"])
                skill_blocks.append(f"[{s['name'].upper()} - v{s.get('version', '1.0')}]")
                skill_blocks.append(s["system_instructions"].strip())
            base_sys = f"{base_sys}\\n" + "\\n".join(skill_blocks)
    except Exception as e:
        print(f"[SKILLS] Dynamic routing error: {e}")"""

target2 = """            return {
                "reply": agent_res["reply"],
                "agentic": True,
                "project_name": agent_res["project_name"],
                "created_files": agent_res["created_files"],
                "steps": agent_res["steps"],
                "telemetry": agent_res["telemetry"],
                "rag_sources": rag_sources,
                "active_skills": active_skills_names
            }"""

replacement2 = """            return {
                "reply": agent_res["reply"],
                "agentic": True,
                "project_name": agent_res["project_name"],
                "created_files": agent_res["created_files"],
                "steps": agent_res["steps"],
                "telemetry": agent_res["telemetry"],
                "rag_sources": rag_sources,
                "active_skills": active_skills_names,
                "bake_recommendation": bake_recommendation
            }"""

target3 = """        return {
            "status": "success",
            "model": req.model,
            "reply": msg.get("content", ""),
            "role": msg.get("role", "assistant"),
            "rag_sources": rag_sources,
            "active_skills": active_skills_names,
            "telemetry": {
                "eval_tokens": eval_count,
                "tokens_per_second": tok_per_sec,
                "total_duration_sec": round(elapsed, 2),
                "eval_duration_sec": round(eval_duration_ns / 1e9, 2)
            }
        }"""

replacement3 = """        return {
            "status": "success",
            "model": req.model,
            "reply": msg.get("content", ""),
            "role": msg.get("role", "assistant"),
            "rag_sources": rag_sources,
            "active_skills": active_skills_names,
            "bake_recommendation": bake_recommendation,
            "telemetry": {
                "eval_tokens": eval_count,
                "tokens_per_second": tok_per_sec,
                "total_duration_sec": round(elapsed, 2),
                "eval_duration_sec": round(eval_duration_ns / 1e9, 2)
            }
        }"""

if target1 not in normalized:
    print("ERROR: target1 not found")
elif target2 not in normalized:
    print("ERROR: target2 not found")
elif target3 not in normalized:
    print("ERROR: target3 not found")
else:
    normalized = normalized.replace(target1, replacement1, 1)
    normalized = normalized.replace(target2, replacement2, 1)
    normalized = normalized.replace(target3, replacement3, 1)
    with open(chat_router_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: chat_router.py updated with dynamic skill routing and bake recommendation.")
