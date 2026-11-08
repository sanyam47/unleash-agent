import os

chat_router_path = r"c:\coding\ai-trainer\backend\api\chat_router.py"
with open(chat_router_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target = """        chosen, bake_recommendation = route_skills_dynamically(
            user_prompt=latest_user_text,
            installed_skills=all_skills,
            explicit_skill_ids=req.skill_ids,
            current_model=req.model
        )"""

replacement = """        chosen, bake_recommendation, sanitized_user_text = route_skills_dynamically(
            user_prompt=latest_user_text,
            installed_skills=all_skills,
            explicit_skill_ids=req.skill_ids,
            current_model=req.model
        )
        if sanitized_user_text and req.messages and req.messages[-1].role == "user":
            req.messages[-1].content = sanitized_user_text"""

if target in normalized:
    normalized = normalized.replace(target, replacement, 1)
    with open(chat_router_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: chat_router.py updated with sanitized_user_text and slash support.")
else:
    print("ERROR: Target not found in chat_router.py")
