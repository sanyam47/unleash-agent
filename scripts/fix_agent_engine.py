import os

agent_engine_path = r"c:\coding\ai-trainer\backend\core\agent_engine.py"
with open(agent_engine_path, "r", encoding="utf-8") as f:
    text = f.read()

# Let's inspect lines up to parse_react_output
header_part = """import os
import re
import json
import time
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

from backend.core.agent_tools import AGENT_TOOLS_SCHEMA, dispatch_tool, sanitize_project_name

OLLAMA_API_CHAT = "http://127.0.0.1:11434/api/chat"
DEFAULT_MAX_STEPS = 6


def format_agentic_system_prompt(base_system: str, project_name: str, skills_prompt: Optional[str] = None) -> str:
    \"\"\"Builds the authoritative ReAct prompt guiding the local model to think, act, and verify.\"\"\"
    tools_formatted = []
    for t in AGENT_TOOLS_SCHEMA:
        param_desc = ", ".join([f'"{k}": <{v}>' for k, v in t.get("parameters", {}).items()])
        tools_formatted.append(f"- {t['name']}({{{param_desc}}}): {t['description']}")

    tools_text = "\\n".join(tools_formatted)

    clean_proj = sanitize_project_name(project_name)

    instructions = f\"\"\"You are an Autonomous AI Engineer operating with the Antigravity ReAct (Reasoning + Acting) execution engine.
Your assigned workspace project is: '{clean_proj}'.

You have access to the following tools:
{tools_text}

=== PROTOCOL RULES & MANDATORY WORKFLOW ===
1. To create, edit, or test files, you MUST use the Action tool directly on disk. Never merely describe code in chat paragraphs without calling the tool!
2. Follow this exact multi-step loop:

Example:
User: "Create a portfolio website."
Assistant:
Thought: I need to create index.html with the layout.
Action: write_project_file({{"file_path": "index.html", "content": "<!DOCTYPE html>\\n<html><head><title>Portfolio</title></head><body><h1>Welcome</h1></body></html>"}})

System returns:
Observation: {{"status": "success", "file": "index.html", "bytes_written": 85}}

Assistant:
Thought: Now I will create styles.css to apply a sleek dark theme.
Action: write_project_file({{"file_path": "styles.css", "content": "body {{ background: #0f172a; color: #f8fafc; font-family: sans-serif; }}"}})

System returns:
Observation: {{"status": "success", "file": "styles.css", "bytes_written": 74}}

Assistant:
Thought: Both index.html and styles.css have been written.
Final Answer: I have built the portfolio website with index.html and styles.css.

3. When you write an Action, output ONLY the Action call and stop.
4. When all files are written and verified, conclude with 'Final Answer:'.

=== HUMAN-IN-THE-LOOP (HITL) INSTALLATION POLICY ===
- You are strictly prohibited from installing software or python packages silently.
- If a required tool, CLI binary, or Python package is not present (e.g. playwright, radare2, scapy):
  You must NEVER attempt to run pip install or winget silently.
  Instead, conclude with:
  PROPOSE_INSTALL: {{"package": "package_name", "type": "pip|winget|npm", "reason": "Brief explanation of why it is needed"}}
  This generates an interactive single-click Approval Button for the user.
\"\"\"

    if skills_prompt:
        instructions += f"\\n\\n=== ATTACHED SKILL INSTRUCTIONS ===\\n{skills_prompt}"

    if base_system and base_system.strip():
        instructions += f"\\n\\n=== PERSONA ===\\n{base_system.strip()}"

    return instructions
"""

# Extract the rest of agent_engine.py starting from parse_react_output
parse_index = text.find("def parse_react_output(")
if parse_index == -1:
    raise ValueError("Could not find def parse_react_output in agent_engine.py")

rest_of_file = text[parse_index:]

new_content = header_part + "\n\n" + rest_of_file

with open(agent_engine_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_content)

print("SUCCESS: agent_engine.py corrected.")
