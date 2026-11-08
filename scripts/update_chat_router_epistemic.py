import os
import re

chat_router_path = r"c:\coding\ai-trainer\backend\api\chat_router.py"
with open(chat_router_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

# 1. Add epistemic calibration to base_sys and knowledge proposal discovery
target1 = """    # Prepare message payload
    payload_messages = []
    base_sys = req.system_prompt.strip() if (req.system_prompt and req.system_prompt.strip()) else "You are an uncensored, highly capable, intelligent AI assistant."
    
    # 0.1 Dynamic Antigravity Skill Routing & Efficiency Detection"""

replacement1 = """    # Prepare message payload
    payload_messages = []
    base_sys = req.system_prompt.strip() if (req.system_prompt and req.system_prompt.strip()) else "You are an uncensored, highly capable, intelligent AI assistant."

    # 0.0 Epistemic Calibration & Self-Awareness of Ignorance
    epistemic_directive = (
        "\\n\\n### EPISTEMIC CALIBRATION & KNOWLEDGE BOUNDARY DIRECTIVES:\\n"
        "1. Real-World Knowledge Limits: You must strictly distinguish between verified facts in your weights and uncertain domain entities (such as obscure biological plant/flower taxonomy, rare insects, specialized pharmacology, OBD2 codes, or proprietary exploits).\\n"
        "2. Zero Hallucination Policy: When asked to identify, diagnose, or explain an entity where you lack verified high-confidence knowledge or where visual/text details are incomplete, DO NOT GUESS OR INVENT PLAUSIBLE-SOUNDING ENTITIES.\\n"
        "3. Explicitly Acknowledge Ignorance: State clearly: 'I cannot identify or confirm this with high certainty based on my base weights alone.'\\n"
        "4. Knowledge Acquisition: Note that an authoritative domain knowledge base can be downloaded and connected to ground your answers with 100% precision."
    )
    base_sys = f"{base_sys}{epistemic_directive}"

    # 0.01 Check for Epistemic Knowledge Gap & Premier Database Discovery
    knowledge_proposal = None
    try:
        from backend.core.knowledge_broker import detect_unknown_domain
        from backend.core.cyber_rag import DB_PATH
        import sqlite3

        existing_categories = []
        if DB_PATH.exists():
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT category FROM cyber_docs")
            existing_categories = [r[0] for r in cur.fetchall()]
            conn.close()

        user_texts_for_k = [m.content for m in req.messages if m.role == "user" and m.content]
        latest_user_text_for_k = user_texts_for_k[-1] if user_texts_for_k else ""
        knowledge_proposal = detect_unknown_domain(latest_user_text_for_k, existing_categories)
    except Exception as e:
        print(f"[KNOWLEDGE_BROKER] Detection error: {e}")

    # 0.1 Dynamic Antigravity Skill Routing & Efficiency Detection"""

# 2. Append knowledge proposal tag to reply if detected and not already present
target2 = """            return {
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

replacement2 = """            agent_reply = agent_res["reply"]
            if knowledge_proposal and "[KNOWLEDGE_ACQUIRE_PROPOSAL:" not in agent_reply:
                agent_reply += f"\\n\\n[KNOWLEDGE_ACQUIRE_PROPOSAL:{knowledge_proposal['domain_key']}:{knowledge_proposal['database_name']}:{knowledge_proposal['description']}:{knowledge_proposal['source_url']}]"

            return {
                "reply": agent_reply,
                "agentic": True,
                "project_name": agent_res["project_name"],
                "created_files": agent_res["created_files"],
                "steps": agent_res["steps"],
                "telemetry": agent_res["telemetry"],
                "rag_sources": rag_sources,
                "active_skills": active_skills_names,
                "bake_recommendation": bake_recommendation,
                "knowledge_proposal": knowledge_proposal
            }"""

target3 = """        return {
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

replacement3 = """        reply_content = msg.get("content", "")
        if knowledge_proposal and "[KNOWLEDGE_ACQUIRE_PROPOSAL:" not in reply_content:
            reply_content += f"\\n\\n[KNOWLEDGE_ACQUIRE_PROPOSAL:{knowledge_proposal['domain_key']}:{knowledge_proposal['database_name']}:{knowledge_proposal['description']}:{knowledge_proposal['source_url']}]"

        return {
            "status": "success",
            "model": req.model,
            "reply": reply_content,
            "role": msg.get("role", "assistant"),
            "rag_sources": rag_sources,
            "active_skills": active_skills_names,
            "bake_recommendation": bake_recommendation,
            "knowledge_proposal": knowledge_proposal,
            "telemetry": {
                "eval_tokens": eval_count,
                "tokens_per_second": tok_per_sec,
                "total_duration_sec": round(elapsed, 2),
                "eval_duration_sec": round(eval_duration_ns / 1e9, 2)
            }
        }"""

# 3. Add POST /knowledge/acquire endpoint
target4 = """# ========================================================
# AGENTIC WORKSPACE & PROJECT FILE APIS
# ========================================================"""

replacement4 = """# ========================================================
# AUTONOMOUS KNOWLEDGE ACQUISITION APIS
# ========================================================

class AcquireKnowledgeRequest(BaseModel):
    domain_key: str
    model: Optional[str] = "global"


@router.post("/knowledge/acquire")
def acquire_knowledge_endpoint(req: AcquireKnowledgeRequest):
    \"\"\"
    Downloads and sets up the premier authoritative knowledge database for a domain,
    embeds the records into local Vector RAG, and registers a runtime specialist skill.
    \"\"\"
    from backend.core.knowledge_broker import install_knowledge_database
    try:
        res = install_knowledge_database(req.domain_key, model_scope=req.model or "global")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================
# AGENTIC WORKSPACE & PROJECT FILE APIS
# ========================================================"""

errors = []
if target1 not in normalized: errors.append("target1")
if target2 not in normalized: errors.append("target2")
if target3 not in normalized: errors.append("target3")
if target4 not in normalized: errors.append("target4")

if errors:
    print(f"ERROR: Missing targets: {errors}")
else:
    normalized = normalized.replace(target1, replacement1, 1)
    normalized = normalized.replace(target2, replacement2, 1)
    normalized = normalized.replace(target3, replacement3, 1)
    normalized = normalized.replace(target4, replacement4, 1)
    with open(chat_router_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: chat_router.py updated with epistemic calibration and /knowledge/acquire.")
