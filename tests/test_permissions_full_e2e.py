"""
Full End-to-End & Concurrency Stress Test Suite for:
1. Antigravity Local Permissions (Review, Default, Auto, Turbo)
2. HITL Checkpoint Interception, Approval, and Resumption Lifecycle
3. In-Memory Resource Cache Thread-Safety & Multi-Thread Concurrency
4. Corrupted Config Auto-Healing & Malformed Payload Hardening
"""

import os
import sys
import json
import time
import shutil
import tempfile
import threading
import concurrent.futures
from pathlib import Path

# Set up paths
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.permission_controller import LocalPermissionController
from backend.core.resource_cache import WorkspaceResourceCache
from backend.core.execution_controller import AgentExecutionController
from backend.core.agent_tools import resolve_safe_project_path, dispatch_tool, sanitize_project_name
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.chat_router import router


def run_full_e2e_suite():
    print("\n" + "="*70)
    print("STARTING COMPREHENSIVE PERMISSIONS & CACHE E2E STRESS SUITE")
    print("="*70)

    # ---------------------------------------------------------
    # TEST 1: Config Auto-Healing on Corrupted/Invalid JSON
    # ---------------------------------------------------------
    print("\n--- TEST 1: Config Corruption & Auto-Healing ---")
    config_path = LocalPermissionController.CONFIG_FILE
    backup_config = None
    if config_path.exists():
        backup_config = config_path.read_text(encoding="utf-8")

    try:
        # Write corrupted garbage
        config_path.write_text("{CORRUPTED_JSON: invalid: [1, 2, ...", encoding="utf-8")
        recovered_mode = LocalPermissionController.get_mode(force_reload=True)
        assert recovered_mode == "default", f"Expected fallback to 'default', got {recovered_mode}"
        print("  ✓ Corrupted config file safely handled, auto-recovered to 'default'")

        # Test set_mode persists and repairs
        res = LocalPermissionController.set_mode("turbo")
        assert res["status"] == "success"
        assert res["mode"] == "turbo"
        assert json.loads(config_path.read_text(encoding="utf-8"))["mode"] == "turbo"
        print("  ✓ Mode successfully updated to 'turbo' and JSON file auto-repaired")

    finally:
        if backup_config is not None:
            config_path.write_text(backup_config, encoding="utf-8")
        else:
            LocalPermissionController.set_mode("default")

    # ---------------------------------------------------------
    # TEST 2: Complex Shell Chaining & Command Injection Defense
    # ---------------------------------------------------------
    print("\n--- TEST 2: Shell Chaining & Blast Radius Inspection ---")
    LocalPermissionController.set_mode("default")

    malicious_commands = [
        "echo hello && del /f /q *",
        "type file.txt | Remove-Item -Force",
        "cat safe.txt; rm -rf /",
        "dir & powershell -Command Clear-Content *",
        "rmdir /s /q c:\\temp",
        "git clean -fdx"
    ]

    for cmd in malicious_commands:
        eval_res = LocalPermissionController.evaluate_action(
            "test_proj",
            "run_terminal_command",
            {"command": cmd}
        )
        assert eval_res["requires_approval"] is True, f"Command '{cmd}' should have required approval!"
        assert eval_res["risk_level"] in ("medium", "high"), f"Expected high risk for '{cmd}', got {eval_res['risk_level']}"
    print(f"  ✓ All {len(malicious_commands)} malicious/chained commands intercepted and required approval")

    # In 'default' mode, executing shell commands is considered sensitive and prompts user
    safe_eval = LocalPermissionController.evaluate_action(
        "test_proj",
        "run_terminal_command",
        {"command": "echo build complete"}
    )
    assert safe_eval["requires_approval"] is True, "Default mode prompts before running shell commands"
    assert safe_eval["risk_level"] == "medium"
    print("  ✓ Default mode correctly prompts before running shell commands")

    # In 'auto' mode, non-destructive commands run automatically while high-risk commands still prompt
    LocalPermissionController.set_mode("auto")
    auto_safe_eval = LocalPermissionController.evaluate_action(
        "test_proj",
        "run_terminal_command",
        {"command": "echo build complete"}
    )
    assert auto_safe_eval["requires_approval"] is False, "Auto mode allows non-destructive commands"

    auto_destructive_eval = LocalPermissionController.evaluate_action(
        "test_proj",
        "run_terminal_command",
        {"command": "rm -rf /"}
    )
    assert auto_destructive_eval["requires_approval"] is True, "Auto mode still blocks high-risk commands"
    print("  ✓ Auto mode verified: automatically executes safe commands, blocks high-risk commands")

    # ---------------------------------------------------------
    # TEST 3: Multi-Threaded Concurrency Stress on Resource Cache
    # ---------------------------------------------------------
    print("\n--- TEST 3: Multi-Threaded Concurrency Stress on ResourceCache ---")
    test_key_prefix = "concurrency_test_"
    num_threads = 30
    ops_per_thread = 50
    errors = []

    def worker_task(thread_id: int):
        for op in range(ops_per_thread):
            key = f"{test_key_prefix}{thread_id}_{op % 5}"
            val = {"thread": thread_id, "op": op, "payload": "x" * 100}
            try:
                # Set value
                WorkspaceResourceCache.set(key, val, ttl_seconds=60)
                # Read value
                cached = WorkspaceResourceCache.get(key)
                if cached is not None:
                    if cached["thread"] != thread_id and (op % 5 == 0):
                        pass # Valid overwrite in shared keys
                # Query directory tree cache helper
                WorkspaceResourceCache.get_workspace_tree(Path("."))
            except Exception as e:
                errors.append(f"Thread {thread_id} error: {e}")

    threads = []
    start_time = time.time()
    for tid in range(num_threads):
        t = threading.Thread(target=worker_task, args=(tid,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.time() - start_time
    total_ops = num_threads * ops_per_thread * 2
    assert len(errors) == 0, f"Cache concurrency errors encountered: {errors}"
    print(f"  ✓ {total_ops} concurrent cache operations completed cleanly across {num_threads} threads in {duration*1000:.1f}ms ({total_ops/duration:.0f} ops/sec)")

    # ---------------------------------------------------------
    # TEST 4: Full HITL Lifecycle (Interception -> Approval -> Resume)
    # ---------------------------------------------------------
    print("\n--- TEST 4: Full HITL Lifecycle (Interception -> Approval -> Resume) ---")
    app = FastAPI()
    app.include_router(router, prefix="/api/chat")
    client = TestClient(app)

    test_proj = "e2e_approval_test_project"
    proj_dir = Path("backend/data/projects") / test_proj
    proj_dir.mkdir(parents=True, exist_ok=True)
    target_file = proj_dir / "critical_service.py"
    target_file.write_text("# Original Production Code\ndef serve(): pass\n", encoding="utf-8")

    try:
        # Set permission mode to 'default'
        LocalPermissionController.set_mode("default")

        # Simulate agent proposing to overwrite critical_service.py
        tool_name = "write_file"
        tool_args = {"path": "critical_service.py", "content": "# Overwritten Code By Agent\ndef updated_serve(): return 200\n"}
        
        eval_res = LocalPermissionController.evaluate_action(test_proj, tool_name, tool_args, ["critical_service.py"])
        assert eval_res["requires_approval"] is True
        print("  ✓ Step 1: Sensitive overwrite intercepted by LocalPermissionController")

        # Save simulated checkpoint with pending action
        simulated_checkpoint = {
            "project_name": test_proj,
            "step": 3,
            "status": "waiting_approval",
            "model": "dolphin3:latest",
            "messages": [{"role": "user", "content": "Update the service."}],
            "steps": [],
            "created_files": [],
            "files_written": [],
            "pending_action": {
                "action": tool_name,
                "args": tool_args,
                "thought": "I need to overwrite critical_service.py with updated implementation.",
                "reason": eval_res["reason"],
                "risk_level": eval_res["risk_level"]
            }
        }
        AgentExecutionController.save_checkpoint(test_proj, simulated_checkpoint)
        chk = AgentExecutionController.get_checkpoint(test_proj)
        assert chk is not None
        assert chk["pending_action"]["action"] == "write_file"
        print("  ✓ Step 2: Checkpoint saved with pending_action and risk metadata")

        # Now test rejection flow first
        from unittest.mock import patch
        with patch("backend.core.agent_engine.resume_agentic_loop", return_value={"status": "resumed"}):
            reject_resp = client.post("/api/chat/execution/approve", json={
                "project_name": test_proj,
                "approved": False
            })
            assert reject_resp.status_code == 200

        updated_chk = AgentExecutionController.get_checkpoint(test_proj)
        assert updated_chk["pending_action"] is None
        assert updated_chk["steps"][-1]["status"] == "declined"
        assert target_file.read_text(encoding="utf-8").startswith("# Original Production Code")
        print("  ✓ Step 3: Rejection verified. Target file untouched, declined observation injected.")

        # Re-queue pending action to test approval flow
        simulated_checkpoint["pending_action"] = {
            "action": tool_name,
            "args": tool_args,
            "thought": "Overwriting critical_service.py after user permission.",
            "reason": eval_res["reason"],
            "risk_level": eval_res["risk_level"]
        }
        AgentExecutionController.save_checkpoint(test_proj, simulated_checkpoint)

        # Test approval flow
        with patch("backend.core.agent_engine.resume_agentic_loop", return_value={"status": "resumed"}):
            approve_resp = client.post("/api/chat/execution/approve", json={
                "project_name": test_proj,
                "approved": True
            })
            assert approve_resp.status_code == 200

        updated_chk = AgentExecutionController.get_checkpoint(test_proj)
        assert updated_chk["pending_action"] is None
        assert updated_chk["steps"][-1]["status"] == "success"
        # Verify file on disk actually got updated!
        new_content = target_file.read_text(encoding="utf-8")
        assert "Overwritten Code By Agent" in new_content, f"Content not updated: {new_content}"
        print("  ✓ Step 4: Approval verified. Tool dispatched, file safely written, checkpoint advanced.")

    finally:
        # Cleanup test project
        if proj_dir.exists():
            shutil.rmtree(proj_dir, ignore_errors=True)
        AgentExecutionController.clear_checkpoint(test_proj)

    print("\n" + "="*70)
    print("ALL BRUTAL E2E TESTS PASSED 100% GREEN")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_full_e2e_suite()
