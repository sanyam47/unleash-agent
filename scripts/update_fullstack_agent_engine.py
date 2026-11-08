import re
import json

code = '''import os
import re
import json
import time
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

from backend.core.agent_tools import AGENT_TOOLS_SCHEMA, dispatch_tool, sanitize_project_name

OLLAMA_API_CHAT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MAX_STEPS = 8


def format_agentic_system_prompt(base_system: str, project_name: str, skills_prompt: Optional[str] = None) -> str:
    \"\"\"Builds the authoritative ReAct prompt guiding the local model to plan, code, and build complete software.\"\"\"
    tools_formatted = []
    for t in AGENT_TOOLS_SCHEMA:
        param_desc = ", ".join([f'"{k}": <{v}>' for k, v in t.get("parameters", {}).items()])
        tools_formatted.append(f"- {t['name']}({{{param_desc}}}): {t['description']}")

    tools_text = "\\n".join(tools_formatted)
    clean_proj = sanitize_project_name(project_name)

    instructions = f\"\"\"You are an Elite Full-Stack Systems Architect operating with the Antigravity ReAct execution engine.
Your assigned workspace project is: '{clean_proj}'.

You have access to the following tools:
{tools_text}

=== FULL-STACK PRODUCTION CODE QUALITY (CRITICAL RULE) ===
1. NEVER produce minimal, stub, or placeholder code (e.g. NEVER write a 2-line dummy HTML with just <h1>Welcome</h1>).
2. When asked to create an application, e-commerce store, landing page, or tool, you MUST write COMPLETE, professional, production-grade files:
   - For an E-Commerce Website (e.g. Amazon-like store):
     * index.html: Complete HTML5 structure featuring a sticky navigation bar with search input and category dropdown, cart counter badge, hero promo carousel/banner, deals section, a rich responsive grid of at least 6-8 diverse realistic products (with image placeholders/SVG icons, star ratings, prime badges, real prices, and "Add to Cart" buttons), an interactive slide-out cart drawer, and a comprehensive multi-column footer.
     * styles.css: Full modern CSS (CSS variables, dark/light contrast, CSS Grid and Flexbox, hover transitions, shadows, product card cards, cart badge animations, and responsive media queries for mobile/desktop).
     * app.js: Complete JavaScript logic with interactive cart state (add to cart, quantity update, remove item, subtotal calculation, search filtering, and toast notification).
3. Do NOT cut corners with comments like "<!-- add more products here -->" or "/* rest of styles */". Deliver the full, expansive code!

=== PROTOCOL RULES & MANDATORY WORKFLOW ===
1. To create, edit, or test files, you MUST use the Action tool directly on disk. Never merely describe code in chat paragraphs without calling the tool!
2. In each turn, output your Thought, followed immediately by your Action:
   Thought: Detailed plan of what to build and why.
   Action: tool_name({{"param": "value"}})
3. When you write an Action, output ONLY that single Action call and stop so the system can execute it and return the Observation.
4. When all files (HTML, CSS, JS) are written, conclude with 'Final Answer:' summarizing the project.

=== HUMAN-IN-THE-LOOP (HITL) INSTALLATION POLICY ===
- You are strictly prohibited from installing software or python packages silently.
- If a required tool or package is not present (e.g. playwright, radare2, scapy):
  Conclude with:
  PROPOSE_INSTALL: {{"package": "package_name", "type": "pip|winget|npm", "reason": "Explanation"}}
\"\"\"

    if skills_prompt:
        instructions += f"\\n\\n=== ATTACHED SKILL INSTRUCTIONS ===\\n{skills_prompt}"

    if base_system and base_system.strip():
        instructions += f"\\n\\n=== PERSONA ===\\n{base_system.strip()}"

    return instructions


def extract_balanced_json_object(text: str, start_pos: int = 0) -> Tuple[Optional[Dict[str, Any]], int]:
    \"\"\"Extracts a balanced JSON object {...} respecting string quotes, escaped characters, and nested braces/parens.\"\"\"
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
        if char == '\\\\':
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
    \"\"\"
    Parses LLM output into (thought, action_name, action_args, final_answer).
    Robust against nested parentheses (calc, rgb, url), newlines, and markdown blocks.
    \"\"\"
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
                for k, _, v in re.findall(r'(\w+)\s*=\s*([\'"])(.*?)\2', text[search_start:], re.DOTALL):
                    action_args[k] = v

        thought_match = re.search(r"Thought\s*:\s*([\s\S]+?)(?=Action|$)", text, re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()
        else:
            thought = f"Executing tool {action_name}"
        return thought, action_name, action_args, None

    # Check for PROPOSE_INSTALL request
    install_match = re.search(r"PROPOSE_INSTALL\s*:\s*(\{[\s\S]+?\})", text, re.IGNORECASE)
    if install_match:
        try:
            req_data = json.loads(install_match.group(1), strict=False)
            pkg = req_data.get("package")
            reason = req_data.get("reason", "Required dependency")
            pkg_type = req_data.get("type", "pip")
            final_text = f"The agent needs **{pkg}** ({reason}). Please approve installation below."
            return "Requesting permission to install " + pkg, None, None, f"[INSTALL_PROPOSAL:{pkg_type}:{pkg}:{reason}]\\n\\n" + final_text
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
    \"\"\"Helper to query Ollama chat API synchronously with generous token generation budget.\"\"\"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": 4096,  # Generous token budget so complete, extensive files are written!
            "num_ctx": context_window
        }
    }
    req_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_API_CHAT, data=req_bytes, headers={"Content-Type": "application/json"})

    start_t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
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
    max_steps: int = DEFAULT_MAX_STEPS
) -> Dict[str, Any]:
    \"\"\"
    Executes the multi-turn Antigravity ReAct loop:
    1. Injects tool schema and ReAct protocol
    2. Prompts model for Thought + Action
    3. Executes Action in isolated project workspace
    4. Feeds Observation back into message context
    5. Repeats until Final Answer or max_steps reached
    \"\"\"
    clean_proj = sanitize_project_name(project_name or f"project_{int(time.time())}")
    system_prompt = format_agentic_system_prompt(base_system_prompt, clean_proj, skills_prompt)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    steps: List[Dict[str, Any]] = []
    created_files: List[str] = []
    total_eval_tokens = 0
    total_time_sec = 0.0

    context = {
        "project_name": clean_proj,
        "model": model
    }

    final_reply = ""

    for step_num in range(1, max_steps + 1):
        step_record = {
            "step": step_num,
            "thought": "",
            "action": None,
            "args": None,
            "observation": None,
            "status": "pending"
        }

        # Query model with 4096 output token capability
        resp = call_ollama_chat(model, messages, temperature=temperature, context_window=context_window)
        content = resp["content"]
        total_eval_tokens += resp["eval_count"]
        total_time_sec += resp["duration_sec"]

        thought, action, args, final_ans = parse_react_output(content)
        step_record["thought"] = thought or "Analyzing task requirements..."

        # If model gave Final Answer directly
        if final_ans:
            step_record["status"] = "completed"
            step_record["observation"] = "Final answer reached."
            steps.append(step_record)
            final_reply = final_ans
            break

        # If model called an Action
        if action:
            step_record["action"] = action
            step_record["args"] = args

            # Execute tool safely
            try:
                tool_result = dispatch_tool(action, args or {}, context)
                step_record["observation"] = tool_result
                step_record["status"] = "success" if tool_result.get("status") != "error" else "error"

                # Track created files
                if action == "write_project_file" and tool_result.get("status") == "success":
                    fname = tool_result.get("file")
                    if fname and fname not in created_files:
                        created_files.append(fname)

                obs_str = json.dumps(tool_result, indent=2)
            except Exception as e:
                tool_result = {"status": "error", "error": str(e)}
                step_record["observation"] = tool_result
                step_record["status"] = "error"
                obs_str = f"Error executing {action}: {str(e)}"

            steps.append(step_record)

            # Append assistant message and observation to history
            assistant_content = f"Thought: {step_record['thought']}\\nAction: {action}({json.dumps(args or {})})"
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": f"Observation: {obs_str}"})

        else:
            # Model generated prose without explicit Action or Final Answer
            step_record["status"] = "completed"
            step_record["observation"] = "Direct response generated."
            steps.append(step_record)
            final_reply = content
            break

    if not final_reply:
        summary_prompt = "You have executed the steps above. Provide your concise Final Answer summarizing the work completed and instructions to view/test the project."
        messages.append({"role": "user", "content": summary_prompt})
        last_resp = call_ollama_chat(model, messages, temperature=0.3, context_window=context_window)
        total_eval_tokens += last_resp["eval_count"]
        total_time_sec += last_resp["duration_sec"]
        final_reply = last_resp["content"]

    tps = round(total_eval_tokens / max(total_time_sec, 0.001), 1)

    return {
        "reply": final_reply,
        "project_name": clean_proj,
        "created_files": created_files,
        "steps": steps,
        "telemetry": {
            "tokens_per_second": tps,
            "eval_tokens": total_eval_tokens,
            "eval_duration_sec": round(total_time_sec, 2),
            "step_count": len(steps)
        }
    }
'''

with open(r"c:\coding\ai-trainer\backend\core\agent_engine.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(code)

print("SUCCESS: agent_engine.py rewritten with Full-Stack Production Directives and Robust Balanced Parser.")
