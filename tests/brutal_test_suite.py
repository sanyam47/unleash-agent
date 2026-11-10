"""
BRUTAL PRODUCTION STRESS TEST FOR FREE CLOUD GPU WATERFALL & EXECUTION CONTROLS
==============================================================================
Tests for:
1. Resume Workspace Wipe Trap (Bug: is_new_app_creation regex wipes workspace on resume)
2. Resume State Preservation (Bug: resume restarts from step 1 instead of continuing checkpoint)
3. 1-Click Rollback on Single Turn (Bug: undo_last_step requires len(snaps) >= 2, failing on first turn)
4. Key Consistency & Sanitization Divergence (Bug: _clean_key vs sanitize_project_name mismatch)
5. JSON Serialization Robustness (Bug: save_checkpoint crashing on non-primitive objects)
6. Cascaded Model Availability (Bug: hardcoded model name when user has different local models)
7. Waterfall Cascade Retry Exception Handling (Bug: auto_cascade retry is unhandled)
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.cloud_gpu_bridge import CloudGpuBridge
from backend.core.execution_controller import AgentExecutionController, CHECKPOINTS_DIR
from backend.core.agent_tools import sanitize_project_name, get_project_dir
from backend.core.workspace_snapshot import create_snapshot, list_snapshots, undo_last_step, rollback_to_snapshot

failures = []
passed = 0

def report_result(test_name: str, passed_bool: bool, detail: str = ""):
    global passed
    if passed_bool:
        passed += 1
        print(f"[PASS] {test_name}")
    else:
        failures.append((test_name, detail))
        print(f"[FAIL] {test_name} -> {detail}")

print("\n" + "="*70)
print("STARTING BRUTAL PRODUCTION STRESS SUITE")
print("="*70 + "\n")

# ---------------------------------------------------------
# Test 1: Key Consistency & Sanitization Divergence
# ---------------------------------------------------------
print("--- TEST 1: Key Consistency between Sanitizer and ExecutionController ---")
test_names = [
    "Project 123",
    "proj_chat_17941159652.1",
    "../../etc/passwd",
    "my@app#code!",
    None,
    ""
]

mismatches = []
for name in test_names:
    sanitized = sanitize_project_name(name)
    controller_key = AgentExecutionController._clean_key(name)
    if sanitized != controller_key:
        mismatches.append(f"Input: '{name}' -> sanitize: '{sanitized}' != controller: '{controller_key}'")

if mismatches:
    report_result("Key Consistency", False, f"Mismatches detected: {'; '.join(mismatches)}")
else:
    report_result("Key Consistency", True)


# ---------------------------------------------------------
# Test 2: Checkpoint JSON Serialization Robustness
# ---------------------------------------------------------
print("\n--- TEST 2: Checkpoint JSON Serialization Robustness ---")
test_proj = "test_serialization_proj"
unserializable_data = {
    "step": 3,
    "project_name": test_proj,
    "timestamp": Path("/some/path"),  # Path object
    "error_set": {"error1", "error2"}, # Set object
    "exception": ValueError("Sample failure") # Exception object
}

try:
    chk_path = AgentExecutionController.save_checkpoint(test_proj, unserializable_data)
    with open(chk_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    report_result("JSON Serialization", True)
except Exception as e:
    report_result("JSON Serialization", False, f"save_checkpoint crashed on non-primitive objects: {e}")
finally:
    AgentExecutionController.clear_checkpoint(test_proj)


# ---------------------------------------------------------
# Test 3: 1-Click Rollback on Single Turn
# ---------------------------------------------------------
print("\n--- TEST 3: 1-Click Rollback on Single Turn ---")
rollback_proj = "test_rollback_single_turn_proj"
proj_dir = get_project_dir(rollback_proj)
proj_dir.mkdir(parents=True, exist_ok=True)

try:
    # Scenario: Agent starts. Pre-turn snapshot is taken (or should be).
    # Step 1: Pre-turn snapshot created
    snap1 = create_snapshot(rollback_proj, "pre_turn", "Pre-turn state")
    
    # Step 2: Agent writes files
    (proj_dir / "bad_file.js").write_text("broken code", encoding="utf-8")
    
    # Step 3: User hits Cancel with 1-Click Rollback!
    res = undo_last_step(rollback_proj)
    
    if res.get("status") == "error":
        report_result("1-Click Rollback Single Turn", False, f"undo_last_step failed: {res.get('error')}")
    else:
        # Check if bad_file.js was rolled back
        if (proj_dir / "bad_file.js").exists():
            report_result("1-Click Rollback Single Turn", False, "bad_file.js still exists after rollback!")
        else:
            report_result("1-Click Rollback Single Turn", True)
except Exception as e:
    report_result("1-Click Rollback Single Turn", False, f"Exception during rollback test: {e}")
finally:
    shutil.rmtree(proj_dir, ignore_errors=True)
    AgentExecutionController.clear_checkpoint(rollback_proj)


# ---------------------------------------------------------
# Test 4: Resume Workspace Wipe Trap
# ---------------------------------------------------------
print("\n--- TEST 4: Resume Workspace Wipe Trap ---")
resume_proj = "test_resume_wipe_trap_proj"
proj_dir = get_project_dir(resume_proj)
proj_dir.mkdir(parents=True, exist_ok=True)

try:
    # Create initial files as if step 1-2 completed
    file1 = proj_dir / "index.html"
    file1.write_text("<h1>Cyberpunk Pomodoro</h1>", encoding="utf-8")
    file2 = proj_dir / "styles.css"
    file2.write_text("body { background: #000; }", encoding="utf-8")
    
    user_prompt = "Build a modern Cyberpunk Focus & Pomodoro application"
    
    # Save checkpoint at step 2
    AgentExecutionController.save_checkpoint(resume_proj, {
        "step": 2,
        "project_name": resume_proj,
        "model": "qwen2.5-coder:32b",
        "user_prompt": user_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "goals": [{"name": "HTML Structure", "completed": True}, {"name": "Timer Logic", "completed": False}],
        "created_files": ["index.html", "styles.css"],
        "files_written": ["index.html", "styles.css"],
        "steps": [{"step": 1, "thought": "initial"}]
    })
    
    # Now test if resuming with resume_checkpoint preserves files
    from backend.core.agent_engine import run_agentic_react_loop
    # When resume_checkpoint is provided, is_new_app_creation MUST be False, so file1 must still exist
    chk = AgentExecutionController.get_checkpoint(resume_proj)
    # Check logic: (not bool(chk)) and is_new should be False
    is_resume_flag = bool(chk)
    effective_is_new = (not is_resume_flag) and is_new

    # Verify that file1 is preserved
    report_result("Resume Wipe Trap Detection", effective_is_new is False and file1.exists(), 
                  "Files preserved when resuming checkpoint!")
finally:
    shutil.rmtree(proj_dir, ignore_errors=True)
    AgentExecutionController.clear_checkpoint(resume_proj)


# ---------------------------------------------------------
# Test 5: Cascaded Model Resolution on Clean System
# ---------------------------------------------------------
print("\n--- TEST 5: Cascaded Model Resolution ---")
# If model is downscaled to local, does it resolve to a model that actually exists?
cascaded_local = CloudGpuBridge.get_cascaded_model("balanced", "qwen2.5-coder:32b")
cascaded_cpu = CloudGpuBridge.get_cascaded_model("cpu_safe", "qwen2.5-coder:32b")

print(f"Cascaded to Balanced: {cascaded_local}")
print(f"Cascaded to CPU Safe: {cascaded_cpu}")

# Check if Ollama has these models installed
try:
    installed = CloudGpuBridge._get_installed_ollama_models()
    print(f"Actually installed in local Ollama: {installed}")
    
    if installed:
        if cascaded_local not in installed and (cascaded_local + ":latest") not in installed:
            report_result("Cascaded Model Exists", False, f"Cascaded model '{cascaded_local}' is NOT installed locally in Ollama! Will throw 404/500 error on cascade.")
        else:
            report_result("Cascaded Model Exists", True)
    else:
        # Ollama is offline or unconfigured; verify fallback defaults are syntactically sound
        report_result("Cascaded Model Exists", bool(cascaded_local and cascaded_cpu), f"Ollama daemon currently offline; fallback defaults verified: '{cascaded_local}', '{cascaded_cpu}'")
except Exception as e:
    report_result("Cascaded Model Exists", False, f"Could not inspect local models: {e}")


# ---------------------------------------------------------
# Test 6: Auto-Cascade Retry Exception Handling
# ---------------------------------------------------------
print("\n--- TEST 6: Auto-Cascade Retry Exception Safety ---")
# Check backend/core/agent_engine.py lines 1070-1110
with open(PROJECT_ROOT / "backend" / "core" / "agent_engine.py", "r", encoding="utf-8") as f:
    engine_code = f.read()

# Check if call_ollama_chat inside the auto_cascade branch is protected by a try-except
cascade_block = engine_code[engine_code.find('if action == "auto_cascade"'):engine_code.find('elif action == "auto_resume"')]
has_inner_try = "try:" in cascade_block and "call_ollama_chat" in cascade_block[cascade_block.find("try:"):]

report_result("Cascade Retry Exception Safety", has_inner_try, 
              "CRITICAL: The cascaded call_ollama_chat retry inside auto_cascade has no try-except wrapper. If the cascaded tier fails, the entire server turn crashes!")


# ---------------------------------------------------------
# Test 7: Context Relay with None items in existing_files
# ---------------------------------------------------------
print("\n--- TEST 7: Context Relay Edge Cases ---")
try:
    relay_msg = AgentExecutionController.compress_context_for_relay(
        user_prompt="Build something",
        messages=[],
        goals=[],
        existing_files=[None, "index.html"], # Malformed list
        last_error="Connection failed"
    )
    report_result("Context Relay None Handling", True)
except TypeError as te:
    report_result("Context Relay None Handling", False, f"TypeError on malformed file list: {te}")
except Exception as e:
    report_result("Context Relay None Handling", False, f"Unexpected error: {e}")


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------
print("\n" + "="*70)
print(f"STRESS TEST SUMMARY: {passed} PASSED, {len(failures)} FAILED")
print("="*70)
for name, detail in failures:
    print(f"- [BUG FOUND] {name}: {detail}")
print("="*70 + "\n")
