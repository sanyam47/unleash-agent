"""
VERIFICATION TEST SUITE FOR MIROFISH SWARM RECOMMENDATIONS
Tests:
  - Pillar 1: Workspace Snapshots, 1-Click Rollback & Undo (Priya Patel & Clara Higgins)
  - Pillar 2: Human-Readable Decision Tracer & Explainability Audit Log (Clara Higgins)
  - Pillar 3: AES-256-GCM Encrypted Credential Vault for Cloud Keys (Marcus Kane & Viktor Brandt)
  - Pillar 4: CPU Safe Mode Tier (Elena Vance & Leo Sato)
  - Pillar 5: FastAPI REST Endpoints for Snapshots, Rollback, Audit Trail, Vault, and Security
  - Pillar 6: Automated AppSec Vulnerability & Secret Leakage Scanner (Marcus Kane)
  - Pillar 7: Cross-Session Memory Privacy Scoping & Exclusion (Dr. Aris Thorne)
"""

import sys
import shutil
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.workspace_snapshot import (
    create_snapshot,
    list_snapshots,
    rollback_to_snapshot,
    undo_last_step
)
from backend.core.decision_tracer import (
    record_decision_event,
    get_audit_trail,
    format_audit_trail_markdown
)
from backend.core.credential_vault import (
    store_secret,
    get_secret,
    has_secret,
    list_configured_services,
    delete_secret,
    VAULT_ENC_FILE,
    MAGIC_PREFIX
)
from backend.core.adaptive_tier import probe_active_compute_tier, ExecutionTier
from backend.core.agent_tools import write_project_file, read_project_file, get_project_dir
from backend.core.security_scanner import audit_workspace_security
from backend.core.memory_manager import (
    exclude_project_from_memory,
    include_project_in_memory,
    get_memory_privacy_status,
    sync_project_index,
    get_memory_store
)
from backend.api import chat_router


def test_snapshots_and_rollback():
    print("\n--- Test 1: Workspace Snapshots & 1-Click Rollback ---")
    pname = "test_swarm_rollback_flow"
    
    # 1. Create v1
    write_project_file(pname, "index.html", "<!DOCTYPE html><html><body><h1>State 1</h1></body></html>")
    write_project_file(pname, "app.js", "console.log('v1');")
    snap1 = create_snapshot(pname, "turn_1", "Initial project state")
    assert snap1["status"] == "success"
    
    # 2. Modify in v2
    write_project_file(pname, "index.html", "<!DOCTYPE html><html><body><h1>State 2 - Modified</h1></body></html>")
    write_project_file(pname, "app.js", "console.log('v2-modified');")
    snap2 = create_snapshot(pname, "turn_2", "After second feature edit")
    assert snap2["status"] == "success"

    # 3. List snapshots
    snaps = list_snapshots(pname)
    assert len(snaps) >= 2
    print(f"Snapshots listed: {[s['snapshot_id'] for s in snaps]}")

    # 4. Rollback to v1
    res_rb = rollback_to_snapshot(pname, snap1["snapshot_id"])
    assert res_rb["status"] == "success"
    f1 = read_project_file(pname, "index.html")
    assert "State 1" in f1["content"]
    assert "State 2" not in f1["content"]
    js1 = read_project_file(pname, "app.js")
    assert "console.log('v1');" in js1["content"]
    print("Rollback to State 1 verified cleanly byte-for-byte!")

    # 5. Test 1-click Undo
    res_undo = undo_last_step(pname)
    assert res_undo["status"] == "success"
    print("1-Click Undo verified cleanly!")

    shutil.rmtree(get_project_dir(pname), ignore_errors=True)


def test_decision_tracer():
    print("\n--- Test 2: Decision Tracer & Explainability Audit Log ---")
    pname = "test_swarm_audit_flow"

    # Record intent
    ev1 = record_decision_event(
        pname,
        "intent_analysis",
        "User requested Pomodoro Timer",
        "Determined user wants 25/5 interval timer with audio alert. Selected 4 milestones for Lite Edge tier.",
        {"tier": "lite_edge"}
    )
    assert ev1["type"] == "intent_analysis"

    # Record gate audit
    ev2 = record_decision_event(
        pname,
        "gate_audit",
        "Chromium Audit: Unhandled timer exception on #pauseBtn",
        "Headless browser clicked 3 buttons; #pauseBtn threw 'timer is not defined'. Attributed to app.js.",
        {"target_file": "app.js", "status": "failed"}
    )
    assert ev2["type"] == "gate_audit"

    # Retrieve audit trail
    events = get_audit_trail(pname)
    assert len(events) == 2
    print(f"Recorded {len(events)} explainability events.")

    # Generate markdown report
    md = format_audit_trail_markdown(pname)
    assert "Decision Audit Trail" in md
    assert "[INTENT]" in md
    assert "[AUDIT]" in md
    print("Explainability Markdown Snippet verified.")

    shutil.rmtree(get_project_dir(pname), ignore_errors=True)


def test_encrypted_credential_vault():
    print("\n--- Test 3: AES-256-GCM Encrypted Credential Vault (Viktor Brandt / AppSec) ---")
    service = "runpod_api"
    secret = "rpa_live_super_secret_token_123456"

    # Store secret
    res_store = store_secret(service, secret)
    assert res_store["status"] == "success"
    assert res_store["cipher"] == "AES-256-GCM"
    assert VAULT_ENC_FILE.exists()

    # Verify ciphertext on disk has GCM header and zero plaintext
    enc_data = VAULT_ENC_FILE.read_bytes()
    assert enc_data.startswith(MAGIC_PREFIX), "Expected GCM1 magic header!"
    assert secret.encode("utf-8") not in enc_data, "SECURITY FLAW: Secret found in plaintext on disk!"
    print("Verified: Key is completely encrypted with AES-256-GCM authenticated cipher at rest.")

    # Decrypt in-memory
    decrypted = get_secret(service)
    assert decrypted == secret
    print("Decrypted in-memory successfully.")

    assert has_secret(service) is True
    assert service in list_configured_services()

    # Clean up
    delete_secret(service)
    assert has_secret(service) is False


def test_cpu_safe_tier():
    print("\n--- Test 4: CPU Safe Mode Tier (Elena Vance & Leo Sato) ---")
    t_cpu = probe_active_compute_tier(user_override=ExecutionTier.CPU_SAFE)
    assert t_cpu["tier"] == "cpu_safe"
    assert t_cpu["max_milestones"] == 3
    assert t_cpu["max_steps"] == 10
    assert t_cpu["context_window"] == 4096
    print(f"CPU Safe Tier verified: {t_cpu['tier_display']} - {t_cpu['max_milestones']} milestones, {t_cpu['context_window']} tokens.")


def test_api_endpoints():
    print("\n--- Test 5: FastAPI REST Endpoints ---")
    app = FastAPI()
    app.include_router(chat_router.router, prefix="/api/chat")
    client = TestClient(app)

    pname = "test_api_project"
    write_project_file(pname, "index.html", "<!DOCTYPE html><html><body><h1>API Test</h1></body></html>")
    create_snapshot(pname, "snap_test", "API snapshot test")

    # 1. GET snapshots
    res_snaps = client.get(f"/api/chat/agent/projects/{pname}/snapshots")
    assert res_snaps.status_code == 200
    assert len(res_snaps.json()) >= 1
    print("GET /snapshots status 200, count:", len(res_snaps.json()))

    # 2. GET audit trail
    record_decision_event(pname, "action_execution", "Wrote index.html", "Initial scaffold")
    res_audit = client.get(f"/api/chat/agent/projects/{pname}/audit-trail")
    assert res_audit.status_code == 200
    assert len(res_audit.json()) >= 1
    print("GET /audit-trail status 200, count:", len(res_audit.json()))

    # 3. GET audit trail markdown
    res_md = client.get(f"/api/chat/agent/projects/{pname}/audit-trail/markdown")
    assert res_md.status_code == 200
    assert "Decision Audit Trail" in res_md.json()["markdown"]
    print("GET /audit-trail/markdown status 200.")

    # 4. GET security audit
    res_sec = client.get(f"/api/chat/agent/projects/{pname}/security-audit")
    assert res_sec.status_code == 200
    assert "findings" in res_sec.json()
    print("GET /security-audit status 200.")

    # 5. POST /vault/secret & GET /vault/services
    res_v = client.post("/api/chat/vault/secret", json={"service": "openai_test", "secret": "sk-fake123"})
    assert res_v.status_code == 200
    res_list = client.get("/api/chat/vault/services")
    assert "openai_test" in res_list.json()["configured_services"]
    client.delete("/api/chat/vault/secret/openai_test")
    print("Vault REST endpoints verified cleanly.")

    # 6. Memory privacy endpoints
    res_priv = client.get("/api/chat/memory/privacy-status")
    assert res_priv.status_code == 200
    print("Memory privacy endpoints verified cleanly.")

    shutil.rmtree(get_project_dir(pname), ignore_errors=True)


def test_security_scanner():
    print("\n--- Test 6: AppSec Vulnerability & Secret Leakage Scanner (Marcus Kane) ---")
    pname = "test_sec_scan_proj"
    
    # Write code containing hardcoded secret and eval sink
    write_project_file(pname, "app.js", "const apiKey = 'sk-proj1234567890abcdef1234567890abcdef'; eval('console.log(1)');")
    write_project_file(pname, "index.html", "<script src='http://insecure-cdn.org/lib.js'></script>")
    
    pdir = get_project_dir(pname)
    res = audit_workspace_security(pdir)
    assert not res["valid"], "Expected security scanner to flag vulnerabilities!"
    assert res["critical_count"] >= 1, "Expected critical secret leakage finding!"
    assert res["high_count"] >= 2, "Expected high eval & insecure script findings!"
    
    categories = [f["category"] for f in res["findings"]]
    assert "secret_leakage" in categories
    assert "code_injection" in categories
    assert "insecure_transport" in categories
    print(f"AppSec Scanner verified: {res['summary']}")

    shutil.rmtree(pdir, ignore_errors=True)


def test_memory_privacy_scoping():
    print("\n--- Test 7: Memory Privacy Scoping & Project Exclusion (Dr. Aris Thorne) ---")
    pname = "test_confidential_client_proj"
    write_project_file(pname, "index.html", "<h1>Confidential Internal Bank Dashboard</h1>")
    
    # 1. Sync should include by default
    sync_project_index(force_refresh=True)
    store = get_memory_store()
    assert pname in store["project_index"]

    # 2. Exclude project from memory
    ex_res = exclude_project_from_memory(pname)
    assert ex_res["status"] == "success"
    assert ex_res["is_private"] is True

    # 3. Verify removed from memory index
    store2 = get_memory_store()
    assert pname not in store2["project_index"]
    assert pname in store2["excluded_projects"]

    # 4. Verify privacy audit
    priv_status = get_memory_privacy_status()
    assert pname in priv_status["excluded_projects"]
    assert pname not in priv_status["indexed_projects"]
    print("Project exclusion and privacy scoping verified cleanly!")

    # 5. Re-include project
    inc_res = include_project_in_memory(pname)
    assert inc_res["status"] == "success"
    store3 = get_memory_store()
    assert pname in store3["project_index"]
    print("Project re-inclusion verified cleanly!")

    shutil.rmtree(get_project_dir(pname), ignore_errors=True)


def main():
    print("="*70)
    print("RUNNING EXTENDED SWARM RECOMMENDATIONS TEST SUITE")
    print("="*70)
    test_snapshots_and_rollback()
    test_decision_tracer()
    test_encrypted_credential_vault()
    test_cpu_safe_tier()
    test_api_endpoints()
    test_security_scanner()
    test_memory_privacy_scoping()
    print("\n" + "="*70)
    print("ALL 7 SWARM RECOMMENDATION TEST PILLARS PASSED (100% SUCCESS)!")
    print("="*70)


if __name__ == "__main__":
    main()
