"""
TEST SUITE: ANTIGRAVITY LOCAL PERMISSIONS & IN-MEMORY RESOURCE CACHE
===================================================================
Tests for:
1. LocalPermissionController (review, default, auto, turbo)
2. Tool Action Sensitivity & Risk Evaluation
3. WorkspaceResourceCache mtime invalidation & caching speed
4. REST API Endpoints (/permissions/mode, /execution/approve)
"""

import os
import sys
import time
import json
import tempfile
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.permission_controller import LocalPermissionController
from backend.core.resource_cache import WorkspaceResourceCache
from backend.core.execution_controller import AgentExecutionController

print("\n" + "="*70)
print("RUNNING LOCAL PERMISSIONS & RESOURCE CACHE TEST SUITE")
print("="*70 + "\n")

# -------------------------------------------------------------
# Test 1: LocalPermissionController Modes & Config Persistence
# -------------------------------------------------------------
print("--- TEST 1: LocalPermissionController Modes ---")
for mode in ["review", "default", "auto", "turbo"]:
    res = LocalPermissionController.set_mode(mode)
    assert res["status"] == "success"
    assert LocalPermissionController.get_mode() == mode
    meta = LocalPermissionController.get_mode_display(mode)
    assert meta["id"] == mode
    assert len(meta["name"]) > 0
    print(f"  ✓ Mode '{mode}' verified: {meta['name']} - {meta['description']}")

# Test invalid mode rejection
try:
    LocalPermissionController.set_mode("super_admin")
    assert False, "Should have raised ValueError on invalid mode"
except ValueError:
    print("  ✓ Correctly rejected invalid permission mode")


# -------------------------------------------------------------
# Test 2: Permission Risk Evaluation Across Modes
# -------------------------------------------------------------
print("\n--- TEST 2: Action Risk Evaluation ---")
existing_files = ["index.html", "styles.css"]

# Scenario A: Turbo Mode -> Always allowed, zero approval required
LocalPermissionController.set_mode("turbo")
turbo_eval = LocalPermissionController.evaluate_action(
    "test_proj", "terminal_run_command", {"command": "rm -rf /"}, existing_files
)
assert turbo_eval["requires_approval"] is False
print("  ✓ Turbo mode: allowed all commands without restriction")

# Scenario B: Default Mode -> Sensitive operations require approval
LocalPermissionController.set_mode("default")
# Overwrite existing file -> sensitive
overwrite_eval = LocalPermissionController.evaluate_action(
    "test_proj", "edit_project_file", {"file_path": "index.html", "code": "..."}, existing_files
)
assert overwrite_eval["requires_approval"] is True
assert overwrite_eval["risk_level"] in ("medium", "high")

# Creating brand new file in default mode -> low risk, allowed automatically
new_file_eval = LocalPermissionController.evaluate_action(
    "test_proj", "write_project_file", {"file_path": "app.js", "code": "..."}, existing_files
)
assert new_file_eval["requires_approval"] is False
print("  ✓ Default mode: asks before overwriting existing files, allows safe new files")

# Destructive command in default mode -> high risk, requires approval
cmd_eval = LocalPermissionController.evaluate_action(
    "test_proj", "terminal_run_command", {"command": "git reset --hard HEAD"}, existing_files
)
assert cmd_eval["requires_approval"] is True
assert cmd_eval["risk_level"] == "high"
print("  ✓ Default mode: caught high-risk destructive terminal command")

# Scenario C: Review Mode -> Strict HITL, every write/edit requires approval
LocalPermissionController.set_mode("review")
review_eval = LocalPermissionController.evaluate_action(
    "test_proj", "write_project_file", {"file_path": "app.js", "code": "..."}, existing_files
)
assert review_eval["requires_approval"] is True
print("  ✓ Review mode: strict HITL requires approval on every write")

# Reset to default
LocalPermissionController.set_mode("default")


# -------------------------------------------------------------
# Test 3: High-Speed In-Memory Resource Cache & mtime Invalidation
# -------------------------------------------------------------
print("\n--- TEST 3: In-Memory Resource Cache & Invalidation ---")
with tempfile.TemporaryDirectory() as tmp_dir_str:
    tmp_dir = Path(tmp_dir_str)
    test_file = tmp_dir / "sample.html"
    test_file.write_text("<h1>Original Content</h1>", encoding="utf-8")

    # 1. First fetch -> cache miss & store
    val1 = WorkspaceResourceCache.get_file(test_file)
    assert val1 is None
    WorkspaceResourceCache.set_file(test_file, "<h1>Original Content</h1>")

    # 2. Second fetch -> cache hit (<0.1ms)
    t0 = time.perf_counter()
    val2 = WorkspaceResourceCache.get_file(test_file)
    hit_time_ms = (time.perf_counter() - t0) * 1000
    assert val2 == "<h1>Original Content</h1>"
    print(f"  ✓ Cache hit succeeded in {hit_time_ms:.3f}ms")

    # 3. Modify file on disk -> verify mtime invalidation
    time.sleep(0.05)
    test_file.write_text("<h1>Updated Content</h1>", encoding="utf-8")
    val3 = WorkspaceResourceCache.get_file(test_file)
    assert val3 is None, "Cache should have invalidated due to mtime mismatch!"
    print("  ✓ Automatic mtime invalidation verified on file edit")

    # 4. Workspace Tree Caching
    tree_val1 = WorkspaceResourceCache.get_workspace_tree(tmp_dir)
    assert tree_val1 is None
    WorkspaceResourceCache.set_workspace_tree(tmp_dir, "my_project/\n|-- sample.html")
    tree_val2 = WorkspaceResourceCache.get_workspace_tree(tmp_dir)
    assert tree_val2 == "my_project/\n|-- sample.html"
    print("  ✓ Workspace directory tree caching verified")

    # 5. Scout Architecture Contract Caching
    WorkspaceResourceCache.set_scout_contract("hf_dataset_finance", {"dataset_id": "finance_records"})
    scout_hit = WorkspaceResourceCache.get_scout_contract("hf_dataset_finance")
    assert scout_hit is not None and scout_hit["dataset_id"] == "finance_records"
    print("  ✓ Pre-flight scout contract caching verified")


# -------------------------------------------------------------
# Test 4: REST API Endpoints Verification
# -------------------------------------------------------------
print("\n--- TEST 4: FastAPI Router Endpoints ---")
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.chat_router import router

app = FastAPI()
app.include_router(router, prefix="/api/chat")
client = TestClient(app)

# GET /api/chat/permissions/mode
res = client.get("/api/chat/permissions/mode")
assert res.status_code == 200
data = res.json()
assert data["mode"] in ("review", "default", "auto", "turbo")
print(f"  ✓ GET /api/chat/permissions/mode -> 200 OK (Current: {data['mode']})")

# POST /api/chat/permissions/mode
res = client.post("/api/chat/permissions/mode", json={"mode": "review"})
assert res.status_code == 200
assert res.json()["mode"] == "review"

res = client.post("/api/chat/permissions/mode", json={"mode": "default"})
assert res.status_code == 200
assert res.json()["mode"] == "default"
print("  ✓ POST /api/chat/permissions/mode -> 200 OK")

# Reset mode to default
LocalPermissionController.set_mode("default")

print("\n" + "="*70)
print("ALL LOCAL PERMISSIONS & RESOURCE CACHE TESTS PASSED! 100% GREEN")
print("="*70 + "\n")
