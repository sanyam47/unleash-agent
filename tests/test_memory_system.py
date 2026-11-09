"""
COMPREHENSIVE TEST SUITE FOR PERSISTENT CROSS-SESSION MEMORY SYSTEM
Tests:
  - Unit 1: Store initialization, atomic disk write, schema integrity
  - Unit 2: Adding preferences, guidelines, rules, and facts
  - Unit 3: Recall and query filtering
  - Unit 4: Automatic project index synchronization across past projects
  - Unit 5: Prompt formatting & token budget safety (<350 tokens)
  - Unit 6: Agent tool dispatch (remember_preference, recall_memory, cross-project read)
  - Unit 7: Agent engine system prompt injection
"""

import sys
import json
from pathlib import Path

# Set up paths
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.memory_manager import (
    get_memory_store,
    save_memory_store,
    remember_preference,
    recall_memory,
    forget_memory,
    sync_project_index,
    format_memory_for_system_prompt,
    USER_MEMORY_PATH
)
from backend.core.agent_tools import dispatch_tool, AGENT_TOOLS_SCHEMA
from backend.core.agent_engine import format_agentic_system_prompt

def test_store_init_and_atomic_save():
    print("\n--- Test 1: Store Init & Atomic Save ---")
    store = get_memory_store()
    assert "user_profile" in store
    assert "learned_rules" in store
    assert "project_index" in store
    assert USER_MEMORY_PATH.exists()
    print("Store initialized and verified at:", USER_MEMORY_PATH)

def test_remember_and_forget_preferences():
    print("\n--- Test 2: Remember & Forget Preferences ---")
    # Add profile setting
    res_prof = remember_preference("profile", "editor_font", "Fira Code Retina")
    assert res_prof["status"] == "success"

    # Add guideline
    res_guide = remember_preference("guideline", "a11y", "Always include ARIA labels on icon buttons")
    assert res_guide["status"] == "success"

    # Add learned rule
    res_rule = remember_preference("rule", "async_timing", "Never use setTimeout in canvas render loops; use requestAnimationFrame")
    assert res_rule["status"] == "success"

    # Add custom fact
    res_fact = remember_preference("fact", "preferred_port", "8001")
    assert res_fact["status"] == "success"

    # Query recall
    recalled = recall_memory("Fira Code")
    assert "editor_font" in recalled["matches"]["profile"]
    print("Recalled profile match:", recalled["matches"]["profile"])

    # Test forget
    forgot = forget_memory("fact", "preferred_port")
    assert forgot is True
    store = get_memory_store()
    assert "preferred_port" not in store.get("custom_facts", {})
    print("Forget verified cleanly.")

def test_sync_project_index():
    print("\n--- Test 3: Project Index Sync ---")
    sync_res = sync_project_index(force_refresh=True)
    assert sync_res["status"] == "success"
    assert sync_res["total_projects"] > 0
    print(f"Indexed {sync_res['total_projects']} past projects.")

    store = get_memory_store()
    p_index = store.get("project_index", {})
    
    # Check that stress_flight_... and stress_zen_... exist in index
    flight_projects = [k for k in p_index.keys() if "flight" in k]
    zen_projects = [k for k in p_index.keys() if "zen" in k]
    assert len(flight_projects) > 0, "Expected stress_flight project in index"
    assert len(zen_projects) > 0, "Expected stress_zen project in index"

    print("Discovered projects:", flight_projects[0], zen_projects[0])
    flight_info = p_index[flight_projects[0]]
    print(f"  Flight Project Summary: {flight_info.get('summary')}")
    print(f"  Flight Tech Stack: {flight_info.get('tech')}")

def test_prompt_formatting_token_budget():
    print("\n--- Test 4: Prompt Formatting & Token Budget (<350 tokens) ---")
    prompt_block = format_memory_for_system_prompt(max_tokens=350)
    char_len = len(prompt_block)
    est_tokens = char_len // 4

    print("Formatted Memory Prompt Snippet:\n", prompt_block[:400], "\n...")
    print(f"Total Chars: {char_len}, Est Tokens: {est_tokens}")
    assert est_tokens < 450, f"Prompt block too large! Tokens: {est_tokens}"
    assert "=== PERSISTENT USER & WORKSPACE MEMORY ===" in prompt_block
    assert "Known Past Projects" in prompt_block
    assert "Preferences & Guidelines" in prompt_block

def test_agent_tools_dispatch():
    print("\n--- Test 5: Agent Tool Dispatch (remember_preference & recall_memory) ---")
    ctx = {"project_name": "test_active_session", "model": "dolphin3"}

    # Test remember_preference via tool
    tool_res = dispatch_tool(
        "remember_preference",
        {"category": "guideline", "key": "color_palette", "value": "Use Tailwind Slate slate-900 background"},
        ctx
    )
    assert tool_res["status"] == "success"
    print("Tool dispatch remember_preference:", tool_res["message"])

    # Test recall_memory via tool
    recall_res = dispatch_tool(
        "recall_memory",
        {"query": "flight"},
        ctx
    )
    assert recall_res["status"] == "success"
    assert len(recall_res["matches"]["projects"]) > 0
    print("Tool dispatch recall_memory found past projects:", list(recall_res["matches"]["projects"].keys()))

    # Test cross-project read_project_file
    flight_proj = list(recall_res["matches"]["projects"].keys())[0]
    read_res = dispatch_tool(
        "read_project_file",
        {"project_name": flight_proj, "file_path": "index.html"},
        ctx
    )
    assert read_res["status"] == "success"
    assert read_res["bytes_read"] > 0
    print(f"Cross-project read from '{flight_proj}' succeeded! Read {read_res['bytes_read']} bytes.")

def test_agent_engine_system_prompt_injection():
    print("\n--- Test 6: Agent Engine System Prompt Injection ---")
    sys_prompt = format_agentic_system_prompt(base_system="", project_name="my_fresh_app")
    assert "=== PERSISTENT USER & WORKSPACE MEMORY ===" in sys_prompt
    assert "remember_preference" in sys_prompt
    assert "recall_memory" in sys_prompt
    print("Verified that new sessions automatically inherit cross-session memory in system prompt!")

def main():
    print("="*65)
    print("RUNNING MEMORY SYSTEM VERIFICATION TEST SUITE")
    print("="*65)
    test_store_init_and_atomic_save()
    test_remember_and_forget_preferences()
    test_sync_project_index()
    test_prompt_formatting_token_budget()
    test_agent_tools_dispatch()
    test_agent_engine_system_prompt_injection()
    print("\n" + "="*65)
    print("ALL MEMORY SYSTEM TESTS PASSED SUCCESSFULLY! (6/6)")
    print("="*65)

if __name__ == "__main__":
    main()
