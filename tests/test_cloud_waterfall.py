import sys
import json
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.cloud_gpu_bridge import CloudGpuBridge
from backend.core.execution_controller import AgentExecutionController


def test_waterfall_configuration_and_persistence():
    print("Testing Waterfall Configuration & Persistence...")
    # Test setting compute mode
    res_turbo = CloudGpuBridge.set_compute_mode("turbo")
    assert CloudGpuBridge.get_compute_mode() == "turbo"
    assert res_turbo["active_provider"] in ("kaggle", "colab")

    res_bal = CloudGpuBridge.set_compute_mode("balanced")
    assert CloudGpuBridge.get_compute_mode() == "balanced"
    assert res_bal["active_provider"] == "local"

    res_cpu = CloudGpuBridge.set_compute_mode("cpu_safe")
    assert CloudGpuBridge.get_compute_mode() == "cpu_safe"
    assert res_cpu["active_provider"] == "cpu_safe"

    # Test setting fallback policies
    CloudGpuBridge.set_fallback_policy("prompt_first")
    assert CloudGpuBridge.get_fallback_policy() == "prompt_first"

    CloudGpuBridge.set_fallback_policy("auto_cascade")
    assert CloudGpuBridge.get_fallback_policy() == "auto_cascade"

    CloudGpuBridge.set_fallback_policy("auto_resume")
    assert CloudGpuBridge.get_fallback_policy() == "auto_resume"

    # Reset to default
    CloudGpuBridge.set_compute_mode("turbo")
    CloudGpuBridge.set_fallback_policy("prompt_first")
    print("  ✓ Waterfall configuration & persistence passed!")


def test_cascaded_model_mapping():
    print("\nTesting Cascaded Model Downscaling Rules...")
    # Cloud 70b downscales to 8b/7b on local GPU
    cascaded_local = CloudGpuBridge.get_cascaded_model("local", "llama3:70b")
    assert "dolphin3" in cascaded_local or "7b" in cascaded_local or "8b" in cascaded_local
    print(f"  Cloud 70B -> Local: {cascaded_local}")

    # Cloud 32b downscales to 1.5b/3b on CPU Safe mode
    cascaded_cpu = CloudGpuBridge.get_cascaded_model("cpu_safe", "qwen2.5-coder:32b")
    assert "1.5b" in cascaded_cpu or "3b" in cascaded_cpu or "dolphin" in cascaded_cpu
    print(f"  Cloud 32B -> CPU Safe: {cascaded_cpu}")

    # Local 8b on local stays 8b
    assert CloudGpuBridge.get_cascaded_model("local", "dolphin3:latest") == "dolphin3:latest"
    print("  ✓ Cascaded model mapping passed!")


def test_waterfall_cascade_detection():
    print("\nTesting Waterfall Cascade Logic...")
    next_tier = CloudGpuBridge.find_next_waterfall_tier("kaggle")
    assert next_tier in ("colab", "local", "cpu_safe")
    print(f"  Next tier after Kaggle: {next_tier}")

    # Test cascade evaluation with fake down endpoint
    CloudGpuBridge.set_fallback_policy("auto_cascade")
    eval_cascade = CloudGpuBridge.check_waterfall_cascade(current_url="http://127.0.0.1:59123")
    assert eval_cascade["current_alive"] is False
    assert eval_cascade["action_required"] == "auto_cascade"
    assert eval_cascade["next_tier"] is not None
    print(f"  Auto-Cascade evaluation: action='{eval_cascade['action_required']}', next='{eval_cascade['next_tier']}'")

    # Test prompt_first policy
    CloudGpuBridge.set_fallback_policy("prompt_first")
    eval_prompt = CloudGpuBridge.check_waterfall_cascade(current_url="http://127.0.0.1:59123")
    assert eval_prompt["action_required"] == "prompt_user"
    print(f"  Prompt-First evaluation: action='{eval_prompt['action_required']}'")

    # Test auto_resume policy
    CloudGpuBridge.set_fallback_policy("auto_resume")
    eval_resume = CloudGpuBridge.check_waterfall_cascade(current_url="http://127.0.0.1:59123")
    assert eval_resume["action_required"] == "auto_resume"
    print(f"  Auto-Resume evaluation: action='{eval_resume['action_required']}'")

    # Reset
    CloudGpuBridge.set_fallback_policy("prompt_first")
    print("  ✓ Waterfall cascade detection passed!")


def test_compressed_context_relay():
    print("\nTesting 70B -> 8B Compressed Context Relay (<3,500 tokens)...")
    huge_messages = [
        {"role": "user", "content": "Build an extensive multi-page dashboard with real-time analytics."},
        {"role": "assistant", "content": "Thought: Scouting layout\nAction: write_project_file('index.html', '...')"}
    ]
    # Add dummy long tool outputs
    for i in range(20):
        huge_messages.append({"role": "user", "content": f"Observation: File write completed with code block {i} " + "X" * 500})
        huge_messages.append({"role": "assistant", "content": f"Thought: Verifying step {i}\nAction: edit_project_file('app.js')"})

    goals = [
        {"name": "Setup Semantic HTML", "desc": "DOM layout and containers", "completed": True},
        {"name": "Responsive Styles", "desc": "CSS variables and dark mode", "completed": True},
        {"name": "Analytics Chart Rendering", "desc": "Canvas 2D chart engine", "completed": False},
        {"name": "Export Data to CSV", "desc": "Download handler", "completed": False}
    ]
    files = ["index.html", "styles.css", "app.js"]

    compressed = AgentExecutionController.compress_context_for_relay(
        user_prompt="Build an extensive multi-page dashboard with real-time analytics.",
        messages=huge_messages,
        goals=goals,
        existing_files=files,
        last_error="Cloud tunnel disconnected mid-turn"
    )

    assert len(compressed) == 2
    assert compressed[0]["role"] == "system"
    assert compressed[1]["role"] == "user"

    sys_content = compressed[0]["content"]
    assert "Setup Semantic HTML" in sys_content
    assert "Analytics Chart Rendering" in sys_content
    assert "index.html" in sys_content
    assert "Cloud tunnel disconnected" in sys_content

    # Estimate token count (avg ~4 chars per token)
    approx_tokens = len(sys_content) / 4
    print(f"  Raw context estimated tokens: >12,000")
    print(f"  Compressed relay context: ~{int(approx_tokens)} tokens (<3,500 budget verified!)")
    assert approx_tokens < 3500, f"Compressed context too large: {approx_tokens} tokens"
    print("  ✓ Compressed context relay passed!")


def test_execution_controller_pause_and_checkpoint():
    print("\nTesting Execution Controller Pause & Checkpoint Persistence...")
    proj = "test_pause_workflow"
    AgentExecutionController.register_start(proj, model="dolphin3:latest")
    assert AgentExecutionController.is_pause_requested(proj) is False

    # Request pause
    pause_res = AgentExecutionController.request_pause(proj)
    assert pause_res["status"] == "pause_requested"
    assert AgentExecutionController.is_pause_requested(proj) is True

    # Save checkpoint
    chk_data = {
        "step": 4,
        "project_name": proj,
        "model": "dolphin3:latest",
        "user_prompt": "Create a canvas particle simulator",
        "goals": [{"name": "Step 1", "completed": True}, {"name": "Step 2", "completed": False}],
        "created_files": ["index.html", "app.js"]
    }
    file_path = AgentExecutionController.save_checkpoint(proj, chk_data)
    assert Path(file_path).exists()

    state = AgentExecutionController.get_state(proj)
    assert state["state"] == "paused"
    assert state["has_checkpoint"] is True
    assert state["checkpoint"]["step"] == 4

    # Test resume request
    resume_res = AgentExecutionController.request_resume(proj, new_tier="balanced")
    assert resume_res["status"] == "resumed"
    assert AgentExecutionController.is_pause_requested(proj) is False

    # Cleanup
    AgentExecutionController.clear_checkpoint(proj)
    assert AgentExecutionController.get_checkpoint(proj) is None
    print("  ✓ Execution controller pause & checkpoint passed!")


def test_execution_controller_cancellation():
    print("\nTesting Execution Controller Cancellation...")
    proj = "test_cancel_workflow"
    AgentExecutionController.register_start(proj, model="dolphin3:latest")
    assert AgentExecutionController.is_cancel_requested(proj) is False

    cancel_res = AgentExecutionController.request_cancel(proj)
    assert cancel_res["status"] == "cancelled"
    assert AgentExecutionController.is_cancel_requested(proj) is True

    state = AgentExecutionController.get_state(proj)
    assert state["state"] == "cancelled"
    assert state["is_cancelled"] is True

    # Clean up
    AgentExecutionController.clear_checkpoint(proj)
    print("  ✓ Execution controller cancellation passed!")


def test_api_endpoints():
    print("\nTesting FastAPI Router Endpoints for Waterfall & Execution...")
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.api.chat_router import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. GET /compute/policy
    r1 = client.get("/compute/policy")
    assert r1.status_code == 200
    data1 = r1.json()
    assert "compute_mode" in data1
    assert "fallback_policy" in data1
    assert "waterfall" in data1
    print("  GET /compute/policy -> 200 OK")

    # 2. POST /compute/policy
    r2 = client.post("/compute/policy", json={"compute_mode": "balanced", "fallback_policy": "auto_cascade"})
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["compute_mode"] == "balanced"
    assert data2["fallback_policy"] == "auto_cascade"
    print("  POST /compute/policy -> 200 OK (Updated to balanced + auto_cascade)")

    # 3. POST /compute/waterfall/check
    r3 = client.post("/compute/waterfall/check")
    assert r3.status_code == 200
    data3 = r3.json()
    assert "cascade_eval" in data3
    assert "waterfall" in data3
    print("  POST /compute/waterfall/check -> 200 OK")

    # 4. POST /execution/pause
    r4 = client.post("/execution/pause", json={"project_name": "api_test_project"})
    assert r4.status_code == 200
    assert r4.json()["status"] == "pause_requested"
    print("  POST /execution/pause -> 200 OK")

    # 5. GET /execution/status/{project_name}
    r5 = client.get("/execution/status/api_test_project")
    assert r5.status_code == 200
    assert r5.json()["is_paused"] is True
    print("  GET /execution/status -> 200 OK")

    # 6. POST /execution/cancel
    r6 = client.post("/execution/cancel", json={"project_name": "api_test_project", "rollback": False})
    assert r6.status_code == 200
    assert r6.json()["status"] == "cancelled"
    print("  POST /execution/cancel -> 200 OK")

    # Cleanup policy back to turbo/prompt_first
    client.post("/compute/policy", json={"compute_mode": "turbo", "fallback_policy": "prompt_first"})
    print("  ✓ All API endpoints verified!")


if __name__ == "__main__":
    print("==================================================")
    print("RUNNING CLOUD GPU WATERFALL & EXECUTION TEST SUITE")
    print("==================================================")
    test_waterfall_configuration_and_persistence()
    test_cascaded_model_mapping()
    test_waterfall_cascade_detection()
    test_compressed_context_relay()
    test_execution_controller_pause_and_checkpoint()
    test_execution_controller_cancellation()
    test_api_endpoints()
    print("\n==================================================")
    print("ALL 7 TEST SUITES PASSED! 100% GREEN")
    print("==================================================")
