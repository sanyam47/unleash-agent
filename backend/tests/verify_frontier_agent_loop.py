"""
Verification Suite for Unleash-Agent Deliberative Frontier Engine:
1. Safe absolute OS path access vs protected OS root blocking (C:\\Windows)
2. Economical numbered line-range read_file, list_dir, search_files, update_plan, run_command
3. Live checklist state streaming via agent_progress
4. parse_react_output safety (Final Answer with code blocks is not hijacked)
5. Full multi-turn Deliberative Frontier ReAct Loop with real file I/O, shell execution, and self-correction
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, r"c:\coding\ai-trainer")

from backend.core.agent_tools import (
    resolve_safe_project_path,
    read_project_file,
    list_dir,
    search_files,
    update_plan,
    dispatch_tool,
    get_tool_schemas,
)
from backend.core.agent_progress import get_project_progress
from backend.core.agent_engine import parse_react_output, run_agentic_react_loop, compact_frontier_messages


def test_path_security_and_tools():
    print("=== 1. TESTING UNIVERSAL WORKSTATION TOOLS & PATH SAFETY ===")

    # Allowed absolute path
    safe_p = resolve_safe_project_path("frontier_test", r"c:\coding\ai-trainer\README.md")
    assert safe_p.name == "README.md"

    # Blocked OS paths
    for bad in [r"C:\Windows\System32\cmd.exe", r"C:\Program Files\test.txt", r"C:\\", "../../Windows/win.ini"]:
        blocked = False
        try:
            resolve_safe_project_path("frontier_test", bad)
        except PermissionError:
            blocked = True
        assert blocked, f"Security failure: path '{bad}' was NOT blocked!"
    print("-> PASS: Protected OS roots & traversal paths blocked.")

    # Numbered line-range read_file
    r_res = read_project_file("frontier_test", r"c:\coding\ai-trainer\start_studio.bat", start_line=1, end_line=10)
    assert r_res["status"] == "success"
    assert "1: @echo off" in r_res["content"]
    assert r_res["start_line"] == 1 and r_res["end_line"] == 10
    print("-> PASS: Economical numbered read_file(start_line, end_line) verified.")

    # list_dir
    ld_res = list_dir("frontier_test", r"c:\coding\ai-trainer")
    assert ld_res["status"] == "success"
    names = [e["name"] for e in ld_res["entries"]]
    assert "start_studio.bat" in names and "backend" in names
    print("-> PASS: list_dir verified.")

    # search_files
    sf_res = search_files("frontier_test", "FRONTIER_TOOLS_SCHEMA", dir_path=r"c:\coding\ai-trainer\backend\core")
    assert sf_res["status"] == "success" and sf_res["match_count"] >= 1
    print(f"-> PASS: search_files located {sf_res['match_count']} match(es).")

    # update_plan -> agent_progress
    up_res = update_plan("frontier_test", [
        {"title": "Inspect workspace", "status": "done"},
        {"title": "Fix calculation bug", "status": "in_progress"},
        {"title": "Run pytest", "status": "pending"},
    ])
    assert up_res["status"] == "success"
    prog = get_project_progress("frontier_test")
    assert len(prog["plan_steps"]) == 3
    assert prog["plan_steps"][1]["status"] == "in_progress"
    print("-> PASS: update_plan live checklist propagated to agent_progress.")

    # FRONTIER_TOOLS_SCHEMA count (9 core + 4 general browser tools)
    ft = get_tool_schemas("frontier")
    assert len(ft) == 13
    print(f"-> PASS: Frontier schema exposes clean {len(ft)}-tool primitive set.")


def test_react_parser_safety():
    print("\n=== 2. TESTING PARSE_REACT_OUTPUT SAFETY ===")

    # Final Answer containing markdown snippet must NOT be hijacked as write_project_file
    sample = (
        "Thought: Verified the script works.\n"
        "Final Answer: Done! You can run it like this:\n"
        "```python\n"
        "print('hello world')\n"
        "```"
    )
    thought, action, args, final_ans = parse_react_output(sample)
    assert action is None, f"Final Answer code block was hijacked as action '{action}'!"
    assert final_ans is not None and "print('hello world')" in final_ans
    print("-> PASS: Final Answer with illustrative code block preserved cleanly.")

    # update_plan action parsing
    plan_txt = 'Thought: Plan the task.\nAction: update_plan({"steps": [{"title": "Read file", "status": "in_progress"}]})'
    t2, a2, args2, f2 = parse_react_output(plan_txt)
    assert a2 == "update_plan" and isinstance(args2.get("steps"), list)
    print("-> PASS: Multi-nested update_plan JSON parsed accurately.")


def test_deliberative_frontier_loop_e2e():
    print("\n=== 3. TESTING MULTI-STEP DELIBERATIVE FRONTIER LOOP E2E ===")
    tmp_dir = Path(tempfile.mkdtemp(prefix="unleash_frontier_e2e_"))
    try:
        script_path = tmp_dir / "calc.py"
        script_path.write_text(
            "def add(a, b):\n"
            "    return a - b  # deliberate bug\n\n"
            "assert add(2, 3) == 5, f'Expected 5, got {add(2, 3)}'\n"
            "print('ALL TESTS PASSED')\n",
            encoding="utf-8"
        )
        p_str = str(script_path).replace("\\", "\\\\")
        d_str = str(tmp_dir).replace("\\", "\\\\")

        # Scripted multi-turn LLM responses demonstrating:
        # Plan -> List/Read -> Run (fails!) -> Self-correct Edit -> Re-run (passes!) -> Final Answer
        turn_outputs = [
            f'Thought: Let me lay out a clear step-by-step plan first.\nAction: update_plan({{"steps": [{{"title": "Read calc.py", "status": "in_progress"}}, {{"title": "Run script & fix bug", "status": "pending"}}, {{"title": "Verify passing test", "status": "pending"}}]}})',
            f'Thought: Inspecting calc.py before running or changing anything.\nAction: read_file({{"file_path": "{p_str}", "start_line": 1, "end_line": 20}})',
            f'Thought: Let me run calc.py first to observe the actual failure.\nAction: run_command({{"command": "python calc.py", "cwd": "{d_str}"}})',
            f'Thought: The run failed with AssertionError because add() returns a - b instead of a + b. Editing surgically.\nAction: edit_file({{"file_path": "{p_str}", "target": "    return a - b  # deliberate bug", "replacement": "    return a + b"}})',
            f'Thought: Re-running calc.py to verify the fix passes with exit_code 0.\nAction: run_command({{"command": "python calc.py", "cwd": "{d_str}"}})',
            f'Thought: Updating plan to mark all steps done.\nAction: update_plan({{"steps": [{{"title": "Read calc.py", "status": "done"}}, {{"title": "Run script & fix bug", "status": "done"}}, {{"title": "Verify passing test", "status": "done"}}]}})',
            'Thought: Everything passed and is verified.\nFinal Answer: Fixed the subtraction bug in `add(a, b)` inside `calc.py` and verified `python calc.py` exits with code 0 (`ALL TESTS PASSED`).'
        ]
        turn_idx = {"i": 0}
        observed_messages = []

        def fake_call_unified_chat(model, messages, temperature=0.35, context_window=8192):
            idx = turn_idx["i"]
            turn_idx["i"] += 1
            observed_messages.append(messages[-1]["content"])
            return {
                "content": turn_outputs[idx],
                "eval_count": 40,
                "duration_sec": 0.05
            }

        from backend.core.permission_controller import LocalPermissionController
        with patch.object(LocalPermissionController, "get_mode", return_value="turbo"), \
             patch("backend.core.agent_engine.call_unified_chat", side_effect=fake_call_unified_chat):
            res = run_agentic_react_loop(
                model="qwen2.5-coder:7b",
                user_prompt=f"Fix the bug in {script_path} and verify tests pass.",
                project_name="frontier_e2e_test",
                agent_mode="frontier"
            )

        assert res.get("status") == "completed", f"Unexpected status: {res.get('status')} | reply={res.get('reply')}"
        assert "ALL TESTS PASSED" in res["reply"], f"Unexpected reply: {res.get('reply')}"
        assert turn_idx["i"] == 7, f"Expected 7 deliberate turns, got {turn_idx['i']}"
        # Verify self-correction cue was injected after exit_code != 0 on turn 3
        assert any("[SELF-CORRECTION]" in m for m in observed_messages), "Missing self-correction cue on failing run_command!"
        # Verify file on disk was genuinely fixed
        assert "return a + b" in script_path.read_text(encoding="utf-8")
        print(f"-> PASS: Executed {turn_idx['i']} deliberate turns (Plan -> Read -> Fail -> Self-Correct -> Edit -> Pass -> Final Answer).")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_dynamic_context_compaction():
    print("\n=== 4. TESTING DYNAMIC CONTEXT COMPACTION (4K vs 32K) ===")
    msgs = [
        {"role": "system", "content": "System prompt " * 40},
        {"role": "user", "content": "Fix my project"}
    ]
    steps = []
    for i in range(1, 9):
        msgs.append({"role": "assistant", "content": f"Thought: Step {i}\nAction: read_file({{\"file_path\": \"f{i}.py\"}})"})
        msgs.append({"role": "user", "content": ("line content " * 140)})
        steps.append({"step": i, "action": "read_file", "args": {"file_path": f"f{i}.py"}, "status": "success"})

    # 32K model keeps full history untouched
    uncompacted = compact_frontier_messages(msgs, context_window=32768, steps=steps, project_name="frontier_test")
    assert len(uncompacted) == len(msgs), f"32K model should not compact {len(msgs)} msgs prematurely"

    # 4K model compacts middle observations while keeping system, user, plan summary, and last 8 msgs
    compacted = compact_frontier_messages(msgs, context_window=4096, steps=steps, project_name="frontier_test")
    assert len(compacted) == 11, f"Expected 11 messages after compaction, got {len(compacted)}"
    assert "[CONTEXT COMPACTION:" in compacted[2]["content"]
    assert "Active Execution Plan:" in compacted[2]["content"]
    print("-> PASS: 4K context compacted cleanly while 32K context preserved full verbatim history.")


if __name__ == "__main__":
    test_path_security_and_tools()
    test_react_parser_safety()
    test_deliberative_frontier_loop_e2e()
    test_dynamic_context_compaction()
    print("\n=== ALL DELIBERATIVE FRONTIER ENGINE TESTS PASSED! ===")
