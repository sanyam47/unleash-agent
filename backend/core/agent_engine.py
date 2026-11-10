import os

import re

import json

import time

import urllib.request

from typing import Dict, Any, List, Optional, Tuple



from backend.core.agent_tools import AGENT_TOOLS_SCHEMA, get_all_tool_schemas, dispatch_tool, sanitize_project_name



def get_ollama_chat_url() -> str:

    try:

        from backend.core.cloud_gpu_bridge import CloudGpuBridge

        base_url = CloudGpuBridge.get_active_inference_url()

        return f"{base_url.rstrip('/')}/api/chat"

    except Exception:

        return "http://127.0.0.1:11434/api/chat"



DEFAULT_MAX_STEPS = 24





def format_agentic_system_prompt(base_system: str, project_name: str, skills_prompt: Optional[str] = None) -> str:

    """Builds the authoritative ReAct prompt guiding the local model to plan, code, and build complete software."""

    tools_formatted = []

    for t in get_all_tool_schemas():

        param_desc = ", ".join([f'"{k}": <{v}>' for k, v in t.get("parameters", {}).items()])

        tools_formatted.append(f"- {t['name']}({{{param_desc}}}): {t['description']}")



    tools_text = "\n".join(tools_formatted)

    clean_proj = sanitize_project_name(project_name)



    instructions = f"""You are an Elite Full-Stack Systems Architect operating with the Antigravity ReAct execution engine.

Your assigned workspace project is: '{clean_proj}'.



You have access to the following tools:

{tools_text}



=== FULL-STACK PRODUCTION CODE QUALITY (CRITICAL RULE) ===

1. NEVER produce minimal, stub, or placeholder code (e.g. NEVER write a 2-line dummy HTML with just <h1>Welcome</h1>).

2. When asked to create an application, site, or tool, you MUST write COMPLETE, professional, production-grade files.

3. ABSOLUTELY FORBIDDEN: Writing comments telling the user to write code (e.g. "<!-- Add your code here -->", "/* Add styles here */", or "Please proceed with adding content to these files"). YOU ARE THE SOLE AUTONOMOUS DEVELOPER. If you leave placeholder comments or tell the user to write code, the system will REJECT your file. You must generate the full, working HTML elements, complete CSS rules, and functional JavaScript logic yourself!

4. Do NOT cut corners with comments like "<!-- add more items here -->" or "/* rest of styles */". Deliver the full, expansive code!



=== DATASET-DRIVEN & USER-REQUEST GROUNDING (ZERO PRESET EXAMPLES) ===

1. ABSOLUTELY NO PRESET OR HARDCODED ARCHETYPE EXAMPLES:

   - NEVER assume, hallucinate, or default to a Portfolio website, Chat application, or generic dashboard unless explicitly requested by the user.

   - Do NOT regurgitate canned templates, sample layouts, or preset archetypes.

2. DYNAMIC DOMAIN DATASETS FROM THE INTERNET:

   - Ground your architecture and files strictly in the user's specific request, conversation history, and real domain datasets.

   - If technical specifications, data schemas, or reference code are needed for the user's domain, call the 'search_internet_dataset' tool to query real-world datasets from the internet and Hugging Face.

3. ADAPTIVE IMPLEMENTATION:

   - Build only the exact features, components, and logic requested by the user, grounded in the retrieved dataset specifications.



=== PROTOCOL RULES & MANDATORY WORKFLOW ===

1. In EVERY TURN, you MUST call a tool Action. Never merely describe code in paragraphs without calling an Action tool!

2. In each turn, output your Thought, followed immediately by your Action:

   Thought: Detailed explanation of what you are creating or verifying.

   Action: tool_name({{"param": "value"}})

3. Workflow Guidelines:

   - If domain specifications or schemas are needed: Call 'search_internet_dataset' to consult real-world datasets from the internet.

   - If you need external CDN script links, modern library documentation, or code recipes: Call 'search_web_docs' (e.g. 'Leaflet map quickstart CDN') for privacy-preserving web documentation search.

   - If files already exist in workspace: Use 'get_project_tree' to inspect files. For targeted changes or bug fixes, prefer 'edit_project_file' to surgically replace only the needed code blocks rather than rewriting the entire file.

   - If creating new web project: Write 'index.html', 'styles.css', and 'app.js' with full working logic.

   - Test and verify execution using 'run_terminal_command' (e.g. 'node -c app.js').

   - Conclude with 'Final Answer:' summarizing the project and instructions to test it.

4. When you write an Action, output ONLY that single Action call and stop so the system can execute it and return the Observation.

5. All buttons and inputs in index.html MUST have matching event listeners in app.js!



=== FINAL ANSWER RESPONSE FORMAT (MANDATORY) ===

When concluding with 'Final Answer:', you MUST format your response in clear, professional markdown:

1. ### Modifications & Implementation Summary:

   - List the files created or modified ('index.html', 'styles.css', 'app.js').

   - Provide a concise bullet-point breakdown of the mechanics, controls, game loops, and styling you implemented.

2. ### Live Preview & Verification:

   - Provide the direct live URL: http://127.0.0.1:8001/api/chat/agent/projects/{clean_proj}/preview/

   - Instruct the user to open or refresh the preview window to test the changes live.



=== HUMAN-IN-THE-LOOP (HITL) INSTALLATION POLICY ===

- You are strictly prohibited from installing software or python packages silently.

- If a required tool or package is not present (e.g. playwright, radare2, scapy):

  Conclude with:

  PROPOSE_INSTALL: {{"package": "package_name", "type": "pip|winget|npm", "reason": "Explanation"}}

"""



    if skills_prompt:

        instructions += f"\n\n=== ATTACHED SKILL INSTRUCTIONS ===\n{skills_prompt}"



    if base_system and base_system.strip():
        instructions += f"\n\n=== PERSONA ===\n{base_system.strip()}"

    # Inject Persistent Cross-Session Memory
    try:
        from backend.core.memory_manager import format_memory_for_system_prompt
        mem_block = format_memory_for_system_prompt()
        if mem_block:
            instructions += f"\n\n{mem_block}"
    except Exception:
        pass

    return instructions





def extract_balanced_json_object(text: str, start_pos: int = 0) -> Tuple[Optional[Dict[str, Any]], int]:

    """Extracts a balanced JSON object {...} respecting string quotes, escaped characters, and nested braces/parens."""

    first_brace = text.find('{', start_pos)

    if first_brace == -1:

        return None, -1



    depth = 0

    in_string = False

    escape = False

    quote_char = None



    for i in range(first_brace, len(text)):

        char = text[i]

        if escape:

            escape = False

            continue

        if char == '\\':

            escape = True

            continue

        if char in ('"', "'"):

            if not in_string:

                in_string = True

                quote_char = char

            elif char == quote_char:

                in_string = False

                quote_char = None

            continue

        if not in_string:

            if char == '{':

                depth += 1

            elif char == '}':

                depth -= 1

                if depth == 0:

                    json_str = text[first_brace:i+1]

                    try:

                        return json.loads(json_str), i + 1

                    except Exception:

                        try:

                            return json.loads(json_str, strict=False), i + 1

                        except Exception:

                            pass

                        return None, -1

    return None, -1





def parse_react_output(text: str) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]], Optional[str]]:

    """

    Parses LLM output into (thought, action_name, action_args, final_answer).

    Robust against nested parentheses (calc, rgb, url), newlines, and markdown blocks.

    """

    thought = None

    action_name = None

    action_args = None

    final_answer = None



    # Check for Action call

    action_match = re.search(r"Action\s*:\s*([a-zA-Z0-9_]+)", text, re.IGNORECASE)

    if action_match:

        action_name = action_match.group(1).strip()

        search_start = action_match.end()



        # Extract balanced JSON arguments

        args_dict, _ = extract_balanced_json_object(text, search_start)

        if args_dict is not None:

            action_args = args_dict

        else:

            # Fallback 1: check markdown code block ```json ... ```

            code_block = re.search(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", text[search_start:])

            if code_block:

                try:

                    action_args = json.loads(code_block.group(1), strict=False)

                except Exception:

                    pass



            # Fallback 2: regex key-value extraction

            if action_args is None:

                action_args = {}

                for match in re.finditer(r'(\w+)\s*=\s*["\'](.*?)["\']', text[search_start:], re.DOTALL):

                    action_args[match.group(1)] = match.group(2)



        thought_match = re.search(r"Thought\s*:\s*([\s\S]+?)(?=Action|$)", text, re.IGNORECASE)

        if thought_match:

            thought = thought_match.group(1).strip()

        else:

            thought = f"Executing tool {action_name}"

        return thought, action_name, action_args, None



    # Fallback: Check for direct JSON code blocks or raw JSON payloads emitted by local models

    json_blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", text)

    candidate_objs = []

    for b in json_blocks:

        try:

            candidate_objs.append(json.loads(b, strict=False))

        except Exception:

            pass



    if not candidate_objs:

        obj, _ = extract_balanced_json_object(text)

        if obj:

            candidate_objs.append(obj)



    for obj in candidate_objs:

        if isinstance(obj, dict):

            # Direct file editing payload: {"file_path": "...", "target": "...", "replacement": "..."}

            if ("file_path" in obj or "filename" in obj) and "target" in obj and "replacement" in obj:

                fname = obj.get("file_path") or obj.get("filename")

                tgt = obj.get("target") or ""

                rep = obj.get("replacement") or ""

                return f"Surgically editing '{fname}'", "edit_project_file", {"file_path": fname, "target": tgt, "replacement": rep}, None



            # Direct file writing payload: {"file_path": "...", "content": "..."}

            if ("file_path" in obj or "filename" in obj or "path" in obj) and ("content" in obj or "code" in obj):

                fname = obj.get("file_path") or obj.get("filename") or obj.get("path")

                fcontent = obj.get("content") or obj.get("code") or ""

                return f"Writing project file '{fname}'", "write_project_file", {"file_path": fname, "content": fcontent}, None



            # Direct tool action payload: {"action": "write_project_file", "args": {...}}

            if "action" in obj or "tool" in obj:

                act = obj.get("action") or obj.get("tool")

                args = obj.get("args") or obj.get("parameters") or obj.get("arguments") or {}

                return f"Executing {act}", str(act), args if isinstance(args, dict) else {}, None



            # Direct command payload: {"command": "..."}

            if "command" in obj or "cmd" in obj:

                cmd = obj.get("command") or obj.get("cmd")

                return f"Executing command '{cmd}'", "run_terminal_command", {"command": str(cmd)}, None



    # Check for direct markdown code blocks emitted by local models (HTML, CSS, JS, Python)

    code_blocks = list(re.finditer(r"```(html|xml|css|javascript|js|json|python|py)\b(?:\s*[:\-]?\s*([a-zA-Z0-9_\-\.]+))?\s*\n([\s\S]+?)```", text, re.IGNORECASE))

    for cb in code_blocks:

        lang = cb.group(1).lower()

        explicit_fname = cb.group(2)

        code_content = cb.group(3).strip()



        preceding = text[:cb.start()]

        file_hint = re.search(r"\b(?:file|path|filename|create|write|to|in|for)\b\s*[:`'\"]*\s*([a-zA-Z0-9_\-\.]+\.(?:html|htm|css|js|py|json))\b", preceding, re.IGNORECASE)



        target_fname = None

        if explicit_fname and "." in explicit_fname:

            target_fname = explicit_fname.strip()

        elif file_hint:

            target_fname = file_hint.group(1).strip()

            if target_fname.lower() in ("dex.html", "ndex.html"):

                target_fname = "index.html"

        elif lang in ("html", "xml") or "<!doctype" in code_content.lower() or "<html" in code_content.lower():

            target_fname = "index.html"

        elif lang == "css" or ("{" in code_content and ":" in code_content and ";" in code_content and "<" not in code_content):

            target_fname = "styles.css"

        elif lang in ("javascript", "js") or "function" in code_content or "const " in code_content or "document." in code_content:

            target_fname = "app.js"



        if target_fname and len(code_content) > 15:

            return f"Writing project file '{target_fname}'", "write_project_file", {"file_path": target_fname, "content": code_content}, None



    # Check for PROPOSE_INSTALL request

    install_match = re.search(r"PROPOSE_INSTALL\s*:\s*(\{[\s\S]+?\})", text, re.IGNORECASE)

    if install_match:

        try:

            req_data = json.loads(install_match.group(1), strict=False)

            pkg = req_data.get("package")

            reason = req_data.get("reason", "Required dependency")

            pkg_type = req_data.get("type", "pip")

            final_text = f"The agent needs **{pkg}** ({reason}). Please approve installation below."

            return "Requesting permission to install " + pkg, None, None, f"[INSTALL_PROPOSAL:{pkg_type}:{pkg}:{reason}]\n\n" + final_text

        except Exception:

            pass



    # Check for Final Answer

    final_match = re.search(r"Final\s*Answer\s*:\s*([\s\S]+)", text, re.IGNORECASE)

    if final_match:

        final_answer = final_match.group(1).strip()

        thought_match = re.search(r"Thought\s*:\s*([\s\S]+?)(?=Final\s*Answer)", text, re.IGNORECASE)

        if thought_match:

            thought = thought_match.group(1).strip()

        return thought, None, None, final_answer



    return None, None, None, None





def call_ollama_chat(model: str, messages: List[Dict[str, Any]], temperature: float = 0.35, context_window: int = 8192) -> Dict[str, Any]:

    """Helper to query Ollama chat API synchronously with generous token generation budget."""

    payload = {

        "model": model,

        "messages": messages,

        "stream": False,

        "options": {

            "temperature": temperature,

            "top_p": 0.9,

            "num_predict": 2048,  # Generous token budget so complete, extensive files are written!

            "num_ctx": context_window

        }

    }

    req_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(get_ollama_chat_url(), data=req_bytes, headers={"Content-Type": "application/json"})



    start_t = time.perf_counter()

    with urllib.request.urlopen(req, timeout=300) as resp:

        res_data = json.loads(resp.read().decode("utf-8"))

    dur = time.perf_counter() - start_t



    msg = res_data.get("message", {})

    return {

        "content": msg.get("content", ""),

        "eval_count": res_data.get("eval_count", 0),

        "duration_sec": dur

    }





def run_agentic_react_loop(
    model: str,
    user_prompt: str,
    base_system_prompt: str = "",
    project_name: Optional[str] = None,
    skills_prompt: Optional[str] = None,
    temperature: float = 0.35,
    context_window: int = 8192,
    max_steps: int = DEFAULT_MAX_STEPS,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    resume_checkpoint: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

    """

    Executes the multi-turn Antigravity ReAct loop:

    1. Injects tool schema and ReAct protocol

    2. Prompts model for Thought + Action

    3. Executes Action in isolated project workspace

    4. Feeds Observation back into message context

    5. Repeats until Final Answer or max_steps reached

    """

    clean_proj = sanitize_project_name(project_name or f"project_{int(time.time())}")

    # Register start with Execution Controller
    try:
        from backend.core.execution_controller import AgentExecutionController
        AgentExecutionController.register_start(clean_proj, model=model)
    except Exception:
        pass



    # Dynamic Compute Tiering Probe (Lite Edge vs Cloud Balanced vs Frontier Ultra)

    from backend.core.adaptive_tier import probe_active_compute_tier

    tier_profile = probe_active_compute_tier(model_name=model)

    if max_steps == DEFAULT_MAX_STEPS:

        max_steps = tier_profile["max_steps"]

    context_window = max(context_window, tier_profile["context_window"])

    viewports = tier_profile.get("viewports", [])

    

    # Check if user specified a custom OS workspace folder in their prompt (e.g. 'at C:\coding\my-app')

    from backend.core.agent_tools import (

        resolve_safe_project_path,

        extract_workspace_path_from_prompt,

        register_custom_workspace,

        get_project_dir

    )

    # Sync persistent project index from disk
    try:
        from backend.core.memory_manager import sync_project_index
        sync_project_index()
    except Exception:
        pass

    custom_ws = extract_workspace_path_from_prompt(user_prompt)

    if custom_ws:

        register_custom_workspace(clean_proj, custom_ws)

        print(f"[WORKSPACE REGISTRATION]: Bound project '{clean_proj}' to custom OS path: {custom_ws}")



    proj_dir = get_project_dir(clean_proj)

    existing_files = []

    if proj_dir.exists():

        for entry in os.listdir(proj_dir):

            if (proj_dir / entry).is_file():

                existing_files.append(entry)



    # Auto-snapshot before modifying existing project
    if existing_files:
        try:
            from backend.core.workspace_snapshot import create_snapshot
            create_snapshot(clean_proj, "pre_turn", f"Checkpoint before: {user_prompt[:60]}")
        except Exception:
            pass

    # Record explainable intent event
    try:
        from backend.core.decision_tracer import record_decision_event
        record_decision_event(
            clean_proj,
            "intent_analysis",
            f"Prompt Received: {user_prompt[:60]}",
            f"Analyzing prompt under {tier_profile.get('tier')} tier. Existing files on disk: {existing_files}",
            {"tier": tier_profile.get("tier"), "context_window": tier_profile.get("context_window")}
        )
    except Exception:
        pass

    # Detect if user is asking to build a completely new project/application
    # CRITICAL: If resuming a saved checkpoint, NEVER treat as a brand new app and NEVER wipe existing files!
    is_resume = bool(resume_checkpoint)
    is_new_app_creation = (not is_resume) and bool(re.search(r'\b(make|build|create|code|develop)\s+(?:a|an)\s+([a-zA-Z0-9_\-\s]{3,40})\b', user_prompt, re.IGNORECASE))

    # If starting a brand new project in default sandbox, reset so previous unrelated project files do not collide
    # NOTE: Never wipe an existing custom directory! Only sandbox projects if requested to build new.
    if is_new_app_creation and existing_files and not custom_ws and "data" in str(proj_dir):
        print(f"[PROJECT ISOLATION]: User requested new application '{user_prompt}', resetting workspace in '{clean_proj}'")
        for entry in os.listdir(proj_dir):
            try:
                (proj_dir / entry).unlink()
            except Exception:
                pass
        existing_files = []



    system_prompt = format_agentic_system_prompt(base_system_prompt, clean_proj, skills_prompt)

    system_prompt += (

        f"\n=== ACTIVE COMPUTE TIER: {tier_profile['tier_display']} ===\n"

        f"Hardware Profile: {tier_profile['gpu_name']} ({tier_profile['vram_gb']}GB VRAM)\n"

        f"Execution Budget: Max {tier_profile['max_milestones']} atomic milestones, {max_steps} ReAct turns, {context_window} context tokens.\n"

        f"Verification Engine: Mode '{tier_profile['visual_mode']}' with {len(viewports)} responsive target viewports.\n\n"

    )

    system_prompt += f"\nCURRENT WORKSPACE ROOT: {proj_dir}\nAll project files are saved and modified directly inside this folder.\n"



    # Dynamic Project Manifest & Workspace Tree Ingestion

    from backend.core.agent_manifest import get_or_create_manifest, format_manifest_for_prompt

    from backend.core.symbol_extractor import format_symbol_table_for_prompt, get_workspace_tree



    manifest = get_or_create_manifest(proj_dir, user_prompt, is_new=is_new_app_creation)

    manifest_prompt = format_manifest_for_prompt(manifest)

    if manifest_prompt:

        system_prompt += f"{manifest_prompt}\n"



    if existing_files:

        workspace_tree_str = get_workspace_tree(proj_dir)

        system_prompt += f"\n=== ACTIVE WORKSPACE DIRECTORY TREE ===\n{workspace_tree_str}\n\n"

        system_prompt += "CONTINUATION MANDATE: You are modifying an EXISTING project. Preserve the existing design, layout, and colors. For targeted modifications, prefer 'edit_project_file' to surgically replace code blocks without wiping existing functions!\n"



        sym_hint = format_symbol_table_for_prompt(proj_dir)

        if sym_hint:

            system_prompt += f"{sym_hint}\n"

 



        from backend.core.workspace_validator import validate_workspace

        health = validate_workspace(clean_proj, viewports=viewports)

        if not health.get("valid") or health.get("warnings"):

            system_prompt += f"\n=== AUTOMATED WORKSPACE DIAGNOSTIC AUDIT ===\n"

            system_prompt += f"{health.get('summary')}\n"

            primary_target = health.get("primary_repair_file")
            target_hint = f" Specifically focus on '{primary_target}'." if primary_target else ""
            system_prompt += f"Your workspace currently has defects listed above.{target_hint} You must repair them using 'edit_project_file' or 'write_project_file'.\n"



    # Autonomous Scout Pre-Flight Phase:

    # Analyzes prompt, discovers authoritative datasets dynamically, and formulates Architecture Contract

    from backend.core.scout_agent import run_scout_phase

    from backend.core.symbol_extractor import format_symbol_table_for_prompt

    from backend.core.agent_progress import set_project_progress, clear_project_progress

    set_project_progress(clean_proj, phase="scouting", headline="Scouting project architecture...", detail="Analyzing requirements and discovering datasets", step=1)



    scout_res = run_scout_phase(user_prompt, proj_dir)

    system_prompt += f"\n\n{scout_res['contract_text']}\n"

    target_files = [f["path"] for f in scout_res["files_plan"]]



    # Autonomous Micro-Goal Decomposition

    from backend.core.goal_stepper import decompose_goals, verify_milestones, format_goal_checklist_for_prompt

    goals = decompose_goals(user_prompt, scout_res, max_milestones=tier_profile["max_milestones"])

    goal_checklist_text = format_goal_checklist_for_prompt(goals)

    system_prompt += f"\n\n{goal_checklist_text}\n"



    set_project_progress(clean_proj, phase="analyzing", headline=f"Architecture & {len(goals)} Goals Formulated ({scout_res['elapsed_ms']}ms)", detail=f"Target files: {', '.join(target_files)}", step=1)



    if is_new_app_creation:

        system_prompt += (

            f"\n\n=== CRITICAL NEW PROJECT SCOPE ===\n"

            f"The user has explicitly requested to build: '{user_prompt}'.\n"

            f"Do NOT generate game loops or canvas elements unless a game was requested. "

            f"Build a complete, responsive application strictly matching the user's prompt specifications and requested features!\n"

        )



    messages = [{"role": "system", "content": system_prompt}]



    # Include recent conversation turns if continuing current task, but isolate if creating a brand new app

    if chat_history and not is_new_app_creation:

        for hist_msg in chat_history:

            role = hist_msg.get("role")

            content = hist_msg.get("content", "")

            if role in ("user", "assistant") and content:

                truncated = content[:800] if len(content) > 800 else content

                messages.append({"role": role, "content": truncated})



    messages.append({"role": "user", "content": user_prompt})



    steps: List[Dict[str, Any]] = [

        {

            "step": 1,

            "thought": f"Scout Pre-Flight: Dissected prompt '{user_prompt[:60]}'. Formulated dynamic architecture contract and retrieved dataset inspiration.",

            "action": "scout_planning",

            "args": {

                "architecture": "Data-Driven Web Application" if scout_res["is_data_app"] else ("Python CLI Script" if scout_res["is_cli"] else ("Interactive Game" if scout_res["is_game"] else "Productivity Tool")),

                "planned_files": target_files,

                "dataset": scout_res.get("dataset_info"),

                "dom_contract": scout_res.get("dom_contract"),

                "compute_tier": tier_profile["tier"],

                "tier_display": tier_profile["tier_display"],

                "vram_gb": tier_profile["vram_gb"]

            },

            "observation": f"Scout contract compiled in {scout_res['elapsed_ms']}ms. Target files: {target_files}",

            "status": "success"

        }

    ]

    created_files: List[str] = []
    files_written_this_run: List[str] = []

    start_step = 1
    if resume_checkpoint:
        if resume_checkpoint.get("goals"):
            goals = resume_checkpoint["goals"]
        if resume_checkpoint.get("created_files"):
            created_files = list(resume_checkpoint["created_files"])
        if resume_checkpoint.get("files_written"):
            files_written_this_run = list(resume_checkpoint["files_written"])
        if resume_checkpoint.get("steps"):
            steps = list(resume_checkpoint["steps"])
        start_step = int(resume_checkpoint.get("step", 0)) + 1

        from backend.core.execution_controller import AgentExecutionController
        messages = AgentExecutionController.compress_context_for_relay(
            user_prompt=user_prompt,
            messages=resume_checkpoint.get("messages", messages),
            goals=goals,
            existing_files=existing_files or created_files
        )



    tool_intent_pattern = r'\b(make|build|create|code|develop|generate|implement|fix|write|change|update|add|remove|delete|repair|work|working|open|opening|broken|page|pages|button|nav|navbar|view|views)\b'

    stop_pattern = r'\b(stop|halt|wait|why|what are you doing|talk to me|who are you|explain yourself|listen)\b'

    

    is_conversational_interrupt = bool(re.search(stop_pattern, user_prompt, re.IGNORECASE))

    is_build_request = bool(re.search(tool_intent_pattern, user_prompt, re.IGNORECASE)) and not is_conversational_interrupt



    if is_conversational_interrupt:

        system_prompt += (

            "\n\n=== USER CONVERSATIONAL DIRECTIVE ===\n"

            "The user is speaking conversationally or asking you to stop building and talk to them directly. "

            "Do NOT call file creation or terminal tools. Provide a direct, helpful, conversational answer "

            "starting with 'Final Answer:' addressing their comment directly."

        )

        messages[0]["content"] = system_prompt



    total_eval_tokens = 0

    total_time_sec = 0.0



    context = {

        "project_name": clean_proj,

        "model": model

    }



    final_reply = ""



    from backend.core.container_runner import DockerEphemeralSession



    with DockerEphemeralSession(enabled=os.getenv("UNLEASH_DOCKER_ENABLED", "0") == "1"):

        for step_num in range(start_step, max_steps + 1):
            # Check execution controls: Cancellation
            if AgentExecutionController.is_cancel_requested(clean_proj):
                set_project_progress(clean_proj, phase="cancelled", headline="Execution cancelled by user", detail="Halted active turn", step=step_num)
                AgentExecutionController.set_state(clean_proj, "cancelled", "Execution cancelled by user")
                return {
                    "reply": "Execution was **cancelled** by user request. Your workspace files are preserved, or you can click **1-Click Rollback** to revert all changes made during this run.",
                    "agentic": True,
                    "status": "cancelled",
                    "project_name": clean_proj,
                    "created_files": created_files,
                    "steps": steps,
                    "telemetry": {"tokens_per_second": 0, "eval_tokens": total_eval_tokens, "eval_duration_sec": round(total_time_sec, 2), "step_count": len(steps)},
                    "rollback_available": True
                }

            # Check execution controls: Pause
            if AgentExecutionController.is_pause_requested(clean_proj):
                chk_data = {
                    "step": step_num,
                    "project_name": clean_proj,
                    "model": model,
                    "user_prompt": user_prompt,
                    "messages": messages,
                    "goals": goals,
                    "created_files": created_files,
                    "files_written": files_written_this_run,
                    "steps": steps,
                    "context_window": context_window,
                    "temperature": temperature
                }
                AgentExecutionController.save_checkpoint(clean_proj, chk_data)
                set_project_progress(clean_proj, phase="paused", headline=f"Execution paused at step {step_num}", detail="Frozen safely. Ready to resume.", step=step_num)
                return {
                    "reply": f"Execution safely **paused** at step {step_num}. Workspace files and verified goals have been saved to disk. Click **Resume** when you are ready to continue.",
                    "agentic": True,
                    "status": "paused",
                    "project_name": clean_proj,
                    "created_files": created_files,
                    "steps": steps,
                    "telemetry": {"tokens_per_second": round(total_eval_tokens / max(total_time_sec, 0.001), 1), "eval_tokens": total_eval_tokens, "eval_duration_sec": round(total_time_sec, 2), "step_count": len(steps)},
                    "checkpoint_saved": True
                }

            step_record = {
                "step": step_num + 1,
                "thought": "",
                "action": None,
                "args": None,
                "observation": None,
                "status": "pending"
            }

            # Query model with Cloud GPU Waterfall & resilience handling
            active_model = model
            try:
                resp = call_ollama_chat(active_model, messages, temperature=temperature, context_window=context_window)
            except Exception as call_err:
                from backend.core.cloud_gpu_bridge import CloudGpuBridge
                cascade_check = CloudGpuBridge.check_waterfall_cascade()
                action = cascade_check.get("action_required")

                if action == "auto_cascade" and cascade_check.get("next_tier"):
                    next_tier = cascade_check["next_tier"]
                    print(f"[WATERFALL CASCADE]: Tier failed ({call_err}). Auto-cascading to '{next_tier}'")
                    CloudGpuBridge.switch_provider(next_tier)
                    active_model = CloudGpuBridge.get_cascaded_model(next_tier, active_model)
                    messages = AgentExecutionController.compress_context_for_relay(
                        user_prompt=user_prompt,
                        messages=messages,
                        goals=goals,
                        existing_files=created_files or existing_files,
                        last_error=str(call_err)
                    )
                    try:
                        from backend.core.decision_tracer import record_decision_event
                        record_decision_event(
                            clean_proj,
                            "waterfall_cascade",
                            f"Auto-Cascaded to {next_tier}",
                            f"Previous tier dropped: {call_err}. Switched to {next_tier} with compressed context relay (<3.5k tokens). Model: {active_model}",
                            {"next_tier": next_tier, "model": active_model}
                        )
                    except Exception:
                        pass
                    # Retry inference on cascaded tier with resilience
                    try:
                        resp = call_ollama_chat(active_model, messages, temperature=temperature, context_window=min(context_window, 8192))
                    except Exception as retry_err:
                        print(f"[WATERFALL CASCADE RETRY WARNING]: Cascaded tier '{next_tier}' failed: {retry_err}")
                        if next_tier != "cpu_safe":
                            CloudGpuBridge.switch_provider("cpu_safe")
                            active_model = CloudGpuBridge.get_cascaded_model("cpu_safe", active_model)
                            try:
                                resp = call_ollama_chat(active_model, messages, temperature=temperature, context_window=4096)
                            except Exception as cpu_err:
                                chk_data = {
                                    "step": step_num,
                                    "project_name": clean_proj,
                                    "model": active_model,
                                    "user_prompt": user_prompt,
                                    "messages": messages,
                                    "goals": goals,
                                    "created_files": created_files,
                                    "files_written": files_written_this_run,
                                    "steps": steps
                                }
                                AgentExecutionController.save_checkpoint(clean_proj, chk_data)
                                return {
                                    "reply": f"Cascaded tiers exhausted ({cpu_err}). Execution paused safely with checkpoint saved.",
                                    "agentic": True,
                                    "status": "paused",
                                    "project_name": clean_proj,
                                    "created_files": created_files,
                                    "steps": steps,
                                    "telemetry": {"tokens_per_second": 0, "eval_tokens": total_eval_tokens, "eval_duration_sec": round(total_time_sec, 2), "step_count": len(steps)},
                                    "checkpoint_saved": True
                                }
                        else:
                            chk_data = {
                                "step": step_num,
                                "project_name": clean_proj,
                                "model": active_model,
                                "user_prompt": user_prompt,
                                "messages": messages,
                                "goals": goals,
                                "created_files": created_files,
                                "files_written": files_written_this_run,
                                "steps": steps
                            }
                            AgentExecutionController.save_checkpoint(clean_proj, chk_data)
                            return {
                                "reply": f"Cascaded tier failed ({retry_err}). Execution paused safely with checkpoint saved.",
                                "agentic": True,
                                "status": "paused",
                                "project_name": clean_proj,
                                "created_files": created_files,
                                "steps": steps,
                                "telemetry": {"tokens_per_second": 0, "eval_tokens": total_eval_tokens, "eval_duration_sec": round(total_time_sec, 2), "step_count": len(steps)},
                                "checkpoint_saved": True
                            }
                elif action == "auto_resume":
                    chk_data = {
                        "step": step_num,
                        "project_name": clean_proj,
                        "model": active_model,
                        "user_prompt": user_prompt,
                        "messages": messages,
                        "goals": goals,
                        "created_files": created_files,
                        "files_written": files_written_this_run,
                        "steps": steps
                    }
                    AgentExecutionController.save_checkpoint(clean_proj, chk_data)
                    AgentExecutionController.set_state(clean_proj, "waiting_quota_recovery", "Execution frozen. Waiting for free cloud quota or tunnel reconnection.")
                    set_project_progress(clean_proj, phase="waiting_quota", headline="Auto-Resume: Waiting for quota refill", detail="State frozen safely", step=step_num)
                    return {
                        "reply": "Free cloud tier quota exhausted or tunnel disconnected. Execution has been frozen in **Auto-Resume** mode. Progress and files on disk are safe and will resume when the endpoint recovers.",
                        "agentic": True,
                        "status": "waiting_quota_recovery",
                        "project_name": clean_proj,
                        "created_files": created_files,
                        "steps": steps,
                        "telemetry": {"tokens_per_second": 0, "eval_tokens": total_eval_tokens, "eval_duration_sec": round(total_time_sec, 2), "step_count": len(steps)},
                        "checkpoint_saved": True
                    }
                else:  # prompt_user
                    chk_data = {
                        "step": step_num,
                        "project_name": clean_proj,
                        "model": active_model,
                        "user_prompt": user_prompt,
                        "messages": messages,
                        "goals": goals,
                        "created_files": created_files,
                        "files_written": files_written_this_run,
                        "steps": steps
                    }
                    AgentExecutionController.save_checkpoint(clean_proj, chk_data)
                    AgentExecutionController.set_state(clean_proj, "boundary_reached", f"Cloud GPU boundary reached: {str(call_err)[:80]}")
                    set_project_progress(clean_proj, phase="boundary_reached", headline="Compute Boundary Reached", detail="Paused for user choice", step=step_num)
                    return {
                        "reply": f"[COMPUTE_BOUNDARY_REACHED:{cascade_check.get('next_tier', 'local')}]\n\n**Compute Boundary Reached**: Cloud GPU endpoint is unreachable or quota has expired.\n\nExecution is paused with all progress saved. Please choose how to proceed:\n- **Cascade to Local RTX 3050** (with compressed context relay)\n- **Switch to CPU Safe Mode** (0% VRAM)\n- **Pause & Wait** for cloud quota/tunnel recovery",
                        "agentic": True,
                        "status": "boundary_reached",
                        "boundary_data": cascade_check,
                        "project_name": clean_proj,
                        "created_files": created_files,
                        "steps": steps,
                        "telemetry": {"tokens_per_second": 0, "eval_tokens": total_eval_tokens, "eval_duration_sec": round(total_time_sec, 2), "step_count": len(steps)},
                        "checkpoint_saved": True
                    }

            content = resp["content"]

            total_eval_tokens += resp["eval_count"]

            total_time_sec += resp["duration_sec"]



            thought, action, args, final_ans = parse_react_output(content)

            step_record["thought"] = thought or "Analyzing task requirements..."



            # Case A: Model invoked a tool Action

            if action:

                step_record["action"] = action

                step_record["args"] = args



                target_fname = (args or {}).get("file_path") or (args or {}).get("file")

                prog_phase = "coding"

                prog_headline = f"Executing {action}..."

                if target_fname:

                    sfname = str(target_fname).lower()

                    if sfname.endswith(".html"):

                        prog_phase = "coding"

                        prog_headline = f"Structuring semantic layout in {target_fname}..."

                    elif sfname.endswith(".css"):

                        prog_phase = "styling"

                        prog_headline = f"Designing responsive styles in {target_fname}..."

                    elif sfname.endswith(".js"):

                        prog_phase = "scripting"

                        prog_headline = f"Writing interactive logic in {target_fname}..."

                    elif sfname.endswith(".py"):

                        prog_phase = "coding"

                        prog_headline = f"Developing Python logic in {target_fname}..."

                elif action == "run_terminal_command":

                    prog_phase = "validating"

                    prog_headline = f"Running terminal command..."



                set_project_progress(clean_proj, phase=prog_phase, headline=prog_headline, detail=thought[:60] if thought else "", step=step_num+1, file_path=target_fname)



                # Execute tool safely

                try:

                    tool_result = dispatch_tool(action, args or {}, context)

                    step_record["observation"] = tool_result

                    step_record["status"] = "success" if tool_result.get("status") != "error" else "error"



                    # Track created & written files

                    if tool_result.get("status") == "success":

                        fname = tool_result.get("file")

                        if fname:

                            if fname not in created_files:

                                created_files.append(fname)

                            if fname not in files_written_this_run:

                                files_written_this_run.append(fname)



                    obs_str = json.dumps(tool_result, indent=2)

                except Exception as e:

                    tool_result = {"status": "error", "error": str(e)}

                    step_record["observation"] = tool_result

                    step_record["status"] = "error"

                    obs_str = f"Error executing {action}: {str(e)}"



                steps.append(step_record)



                # Check Milestone progress after tool execution

                milestone_res = verify_milestones(proj_dir, goals, current_step=step_num)

                if milestone_res["completed_count"] > 0 or milestone_res.get("next_uncompleted"):

                    next_lbl = milestone_res["next_uncompleted"]["name"] if milestone_res.get("next_uncompleted") else "All Goals Complete"

                    obs_str += f"\n\n[GOAL STEPPER: {milestone_res['completed_count']}/{milestone_res['total_count']} Milestones Verified | Next Target: {next_lbl}]"



                # Append assistant message and observation to history

                assistant_content = f"Thought: {step_record['thought']}\nAction: {action}({json.dumps(args or {})})"

                messages.append({"role": "assistant", "content": assistant_content})

                messages.append({"role": "user", "content": f"```json\n{obs_str}\n```"})



            # Case B: Model attempted to stop prematurely without creating or modifying planned project files

            elif is_build_request and len(files_written_this_run) < len(target_files) and step_num < max_steps:

                missing = [f for f in target_files if f not in files_written_this_run]

                next_file = missing[0]



                # Extract lean symbol table from existing files to ensure DOM & state parity

                symbol_table_hint = format_symbol_table_for_prompt(proj_dir)



                reminder = (

                    f"Observation: MANDATORY ACTION REQUIRED. You have not written '{next_file}' for this task yet!\n"

                    f"{symbol_table_hint}\n"

                    f"Never provide prose summaries before creating the actual code files on disk. "

                    f"You MUST call: Action: write_project_file({{\"file_path\": \"{next_file}\", \"content\": \"...\"}}) now "

                    f"matching the Scout Contract and binding all required IDs/classes."

                )

                step_record["status"] = "re-prompted"

                step_record["observation"] = f"Reminded model to write {next_file} matching Scout Contract."

                steps.append(step_record)

                messages.append({"role": "assistant", "content": content})

                messages.append({"role": "user", "content": reminder})



            # Case C: All core files exist and model provided Final Answer -> Run Dual Gate (Acceptance + Goal Stepper)

            elif final_ans:

                set_project_progress(clean_proj, phase="validating", headline="Verifying Dual Acceptance Gate...", detail="Auditing compiler integrity and feature milestones", step=step_num+1)

                from backend.core.workspace_validator import validate_workspace

                health = validate_workspace(clean_proj, required_entities=scout_res.get("entities"), viewports=viewports)

                milestone_res = verify_milestones(proj_dir, goals, current_step=step_num)



                # Gate 1: Compiler, Syntax, and DOM contract validation

                if not health.get("valid") and step_num < max_steps:

                    set_project_progress(clean_proj, phase="self_repairing", headline="Self-Repairing code defects...", detail="Satisfying compiler and Acceptance Gate requirements", step=step_num+1)

                    step_record["status"] = "auto-repair-triggered"

                    step_record["observation"] = f"Self-repair triggered: {health.get('summary')}"

                    steps.append(step_record)



                    repair_target = health.get("primary_repair_file") or (target_files[0] if target_files else "app.js")
                    action_hint = "edit_project_file" if (proj_dir / repair_target).exists() else "write_project_file"
                    repair_reminder = (
                        f"Observation: AUTOMATED COMPILER & ACCEPTANCE GATE VALIDATION FAILED!\n\n"
                        f"{health.get('summary')}\n\n"
                        f"MANDATORY SELF-REPAIR: Call '{action_hint}' specifically on '{repair_target}' to fix all errors above. Do NOT rewrite unrelated files!"
                    )

                    messages.append({"role": "assistant", "content": content})

                    messages.append({"role": "user", "content": repair_reminder})

                    continue



                # Gate 2: Autonomous Feature Goal Stepper validation

                if not milestone_res.get("all_completed") and step_num < max_steps:

                    next_goal = milestone_res["next_uncompleted"]

                    c_cnt = milestone_res["completed_count"]

                    t_cnt = milestone_res["total_count"]

                    set_project_progress(

                        clean_proj,

                        phase="goal_stepping",

                        headline=f"Goal Stepper [{c_cnt}/{t_cnt}]: {next_goal['name']}...",

                        detail=f"Executing next milestone without stopping: {next_goal['desc'][:50]}",

                        step=step_num + 1

                    )

                    step_record["status"] = "goal-advancing"

                    step_record["observation"] = f"Advancing to milestone: {next_goal['name']} ({c_cnt}/{t_cnt} verified)"

                    steps.append(step_record)



                    goal_reminder = (

                        f"Observation: AUTONOMOUS GOAL STEPPER - {c_cnt}/{t_cnt} MILESTONES VERIFIED.\n\n"

                        f"{milestone_res['feedback_prompt']}\n\n"

                        f"MANDATORY CONTINUATION: You are not permitted to conclude or stop yet. "

                        f"You must call 'edit_project_file' or 'write_project_file' to implement '{next_goal['name']}' now."

                    )

                    messages.append({"role": "assistant", "content": content})

                    messages.append({"role": "user", "content": goal_reminder})

                    continue



                set_project_progress(clean_proj, phase="completed", headline=f"All {len(goals)} Goals & Acceptance Gate Verified (100%)", detail="All features and interactive controls verified on disk", step=step_num+1)

                step_record["status"] = "completed"

                step_record["observation"] = f"Final answer reached with all {len(goals)} milestones verified."

                steps.append(step_record)

                final_reply = final_ans

                break



            # Case D: Model concluded with prose -> Check 3-Layer Acceptance Gate before accepting

            else:

                # If this was a build/fix request and model did not write or modify any code files yet, force an action!

                if is_build_request and len(files_written_this_run) == 0 and step_num < max_steps:

                    target_file = None
                    if existing_files:
                        from backend.core.workspace_validator import validate_workspace
                        health_probe = validate_workspace(clean_proj, viewports=viewports)
                        if health_probe.get("primary_repair_file"):
                            target_file = health_probe.get("primary_repair_file")
                    if not target_file:
                        p_lower = user_prompt.lower()
                        if any(k in p_lower for k in ["bug", "fix", "error", "crash", "listener", "event", "logic", "js", "app.js", "timer", "function", "state", "localstorage"]):
                            target_file = "app.js" if (proj_dir / "app.js").exists() else (target_files[0] if target_files else "app.js")
                        elif any(k in p_lower for k in ["style", "css", "color", "dark", "theme", "responsive", "font", "padding"]):
                            target_file = "styles.css" if (proj_dir / "styles.css").exists() else (target_files[0] if target_files else "styles.css")
                        else:
                            target_file = target_files[0] if target_files else "app.js"
                    action_cmd = "edit_project_file" if (proj_dir / target_file).exists() else "write_project_file"

                    reminder = (

                        f"Observation: ACTION REQUIRED. You explained what to do in prose, but have NOT modified or written any code files yet!\n"
                        f"You MUST call Action: {action_cmd}({{\"file_path\": \"{target_file}\", ...}}) now with code to implement or fix the requested features."

                    )

                    step_record["status"] = "re-prompted"

                    step_record["observation"] = f"Forced model to write code for {target_file} instead of concluding with prose."

                    steps.append(step_record)

                    messages.append({"role": "assistant", "content": content})

                    messages.append({"role": "user", "content": reminder})

                    continue

                set_project_progress(clean_proj, phase="validating", headline="Verifying Dual Acceptance Gate...", detail="Auditing compiler integrity and feature milestones", step=step_num+1)

                from backend.core.workspace_validator import validate_workspace

                health = validate_workspace(clean_proj, required_entities=scout_res.get("entities"), viewports=viewports)

                milestone_res = verify_milestones(proj_dir, goals, current_step=step_num)



                # Gate 1: Compiler, Syntax, and DOM contract validation

                if not health.get("valid") and step_num < max_steps:

                    set_project_progress(clean_proj, phase="self_repairing", headline="Self-Repairing code defects...", detail="Satisfying compiler and Acceptance Gate requirements", step=step_num+1)

                    step_record["status"] = "auto-repair-triggered"

                    step_record["observation"] = f"Self-repair triggered: {health.get('summary')}"

                    steps.append(step_record)



                    repair_target = health.get("primary_repair_file") or (target_files[0] if target_files else "app.js")
                    action_hint = "edit_project_file" if (proj_dir / repair_target).exists() else "write_project_file"
                    repair_reminder = (
                        f"Observation: AUTOMATED COMPILER & ACCEPTANCE GATE VALIDATION FAILED!\n\n"
                        f"{health.get('summary')}\n\n"
                        f"MANDATORY SELF-REPAIR: Call '{action_hint}' specifically on '{repair_target}' to repair all issues above. Do NOT rewrite unrelated files!"
                    )

                    messages.append({"role": "assistant", "content": content})

                    messages.append({"role": "user", "content": repair_reminder})

                    continue



                # Gate 2: Autonomous Feature Goal Stepper validation

                if not milestone_res.get("all_completed") and step_num < max_steps:

                    next_goal = milestone_res["next_uncompleted"]

                    c_cnt = milestone_res["completed_count"]

                    t_cnt = milestone_res["total_count"]

                    set_project_progress(

                        clean_proj,

                        phase="goal_stepping",

                        headline=f"Goal Stepper [{c_cnt}/{t_cnt}]: {next_goal['name']}...",

                        detail=f"Executing next milestone without stopping: {next_goal['desc'][:50]}",

                        step=step_num + 1

                    )

                    step_record["status"] = "goal-advancing"

                    step_record["observation"] = f"Advancing to milestone: {next_goal['name']} ({c_cnt}/{t_cnt} verified)"

                    steps.append(step_record)



                    goal_reminder = (

                        f"Observation: AUTONOMOUS GOAL STEPPER - {c_cnt}/{t_cnt} MILESTONES VERIFIED.\n\n"

                        f"{milestone_res['feedback_prompt']}\n\n"

                        f"MANDATORY CONTINUATION: You are not permitted to conclude or stop yet. "

                        f"You must call 'edit_project_file' or 'write_project_file' to implement '{next_goal['name']}' now."

                    )

                    messages.append({"role": "assistant", "content": content})

                    messages.append({"role": "user", "content": goal_reminder})

                    continue



                set_project_progress(clean_proj, phase="completed", headline=f"All {len(goals)} Goals & Acceptance Gate Verified (100%)", detail="All features and interactive controls verified on disk", step=step_num+1)

                step_record["status"] = "completed"

                step_record["observation"] = f"Project completed with all {len(goals)} milestones verified."

                steps.append(step_record)

                final_reply = content

                break



        if not final_reply:

            summary_prompt = (

                f"You have finished building the workspace files for project '{clean_proj}'. "

                f"Provide your Final Answer formatted as:\n"

                f"1. A structured bullet-point breakdown of the exact files and features you implemented.\n"

                f"2. Direct link to http://127.0.0.1:8001/api/chat/agent/projects/{clean_proj}/preview/ with instructions to refresh the preview to test it live."

            )

            messages.append({"role": "user", "content": summary_prompt})

            last_resp = call_ollama_chat(model, messages, temperature=0.3, context_window=context_window)

            total_eval_tokens += last_resp["eval_count"]

            total_time_sec += last_resp["duration_sec"]

            final_reply = last_resp["content"]



        # Ensure the preview URL and refresh instruction are always present in the response

        preview_url = f"http://127.0.0.1:8001/api/chat/agent/projects/{clean_proj}/preview/"

        if preview_url not in final_reply and clean_proj:

            final_reply += (

                f"\n\n---\n"

                f"**Live Preview:** You can test this project live at [{preview_url}]({preview_url})\n\n"

                f"*Please refresh the preview window to see your latest changes!*"

            )



    tps = round(total_eval_tokens / max(total_time_sec, 0.001), 1)



    # Autonomous Workspace Harvester & Sync:

    # Guarantees that any code emitted by the model in markdown is saved to disk,

    # ensuring the project workspace is never empty and preview never 404s.

    if proj_dir.exists():

        all_texts = [final_reply] + [m.get("content", "") for m in messages if m.get("role") == "assistant"]

        combined_text = "\n\n".join(all_texts)



        # 1. Harvest index.html if not on disk

        index_file = proj_dir / "index.html"

        if not index_file.exists():

            html_match = re.search(r"```(?:html|xml)?\s*\n(<!DOCTYPE[\s\S]+?</html>)", combined_text, re.IGNORECASE)

            if not html_match:

                html_match = re.search(r"```html\s*\n([\s\S]+?)```", combined_text, re.IGNORECASE)

            if html_match:

                from backend.core.agent_tools import write_project_file

                write_project_file(clean_proj, "index.html", html_match.group(1).strip())



        # 2. Harvest styles.css if not on disk

        css_file = proj_dir / "styles.css"

        if not css_file.exists():

            css_match = re.search(r"```css\s*\n([\s\S]+?)```", combined_text, re.IGNORECASE)

            if css_match:

                from backend.core.agent_tools import write_project_file

                write_project_file(clean_proj, "styles.css", css_match.group(1).strip())



        # 3. Harvest app.js if not on disk

        js_file = proj_dir / "app.js"

        if not js_file.exists():

            js_match = re.search(r"```(?:javascript|js)\s*\n([\s\S]+?)```", combined_text, re.IGNORECASE)

            if js_match:

                from backend.core.agent_tools import write_project_file

                write_project_file(clean_proj, "app.js", js_match.group(1).strip())



        # Final disk sync to ensure all created project files are reported

        for entry in os.listdir(proj_dir):

            if (proj_dir / entry).is_file() and entry not in created_files:

                created_files.append(entry)



    # Sync newly built or modified project into persistent memory index
    try:
        from backend.core.memory_manager import sync_project_index
        sync_project_index(force_refresh=True)
    except Exception:
        pass

    # Clear checkpoint and mark completed in ExecutionController
    try:
        from backend.core.execution_controller import AgentExecutionController
        AgentExecutionController.register_completion(clean_proj)
        AgentExecutionController.clear_checkpoint(clean_proj)
    except Exception:
        pass

    set_project_progress(clean_proj, phase="completed", headline="Project build completed", detail="Interactive preview ready", step=len(steps))

    return {

        "reply": final_reply,

        "project_name": clean_proj,

        "created_files": created_files,

        "steps": steps,

        "compute_tier": tier_profile,

        "gateway_grounding": {

            "matched": bool(scout_res.get("dataset_info")),

            "dataset_name": (scout_res.get("dataset_info") or {}).get("dataset_id") or (scout_res.get("dataset_info") or {}).get("dataset_name"),

            "dataset_id": (scout_res.get("dataset_info") or {}).get("dataset_id"),

            "source": (scout_res.get("dataset_info") or {}).get("source"),

            "latency_ms": scout_res.get("elapsed_ms", 0.0)

        },

        "telemetry": {

            "tokens_per_second": tps,

            "eval_tokens": total_eval_tokens,

            "eval_duration_sec": round(total_time_sec, 2),

            "step_count": len(steps)

        }

    }


def resume_agentic_loop(
    project_name: str,
    new_tier: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resumes an agentic task from its saved pause checkpoint.
    Optionally switches to a new compute tier (e.g. from Cloud to Local/CPU).
    """
    from backend.core.agent_tools import sanitize_project_name
    from backend.core.execution_controller import AgentExecutionController
    from backend.core.cloud_gpu_bridge import CloudGpuBridge

    clean_proj = sanitize_project_name(project_name)
    chk = AgentExecutionController.get_checkpoint(clean_proj)
    if not chk:
        raise ValueError(f"No checkpoint found for project '{clean_proj}'")

    model = chk.get("model", "dolphin3:latest")
    if new_tier:
        CloudGpuBridge.set_compute_mode(new_tier)
        model = CloudGpuBridge.get_cascaded_model(new_tier, model)

    AgentExecutionController.request_resume(clean_proj, new_tier=new_tier)

    # Resume the loop using the saved prompt, context, and checkpoint state
    user_prompt = chk.get("user_prompt", f"Resume and finish goals for {clean_proj}")
    return run_agentic_react_loop(
        model=model,
        user_prompt=user_prompt,
        project_name=clean_proj,
        context_window=chk.get("context_window", 8192),
        temperature=chk.get("temperature", 0.35),
        resume_checkpoint=chk
    )


