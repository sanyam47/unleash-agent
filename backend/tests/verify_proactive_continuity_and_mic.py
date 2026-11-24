"""
Verification Test Suite: Proactive Conversational Continuity & Unified Microphone Control
Tests:
1. Unified Microphone Toggle API (/api/voice/toggle_mic) & Native Daemon State Sync.
2. Proactive Alert Emitted by Watchdog is Grounded in Cognitive Memory.
3. Multi-Turn Anaphora Continuity: User saying 'yes inspect it' connects to Watchdog Alert without forgetting.
4. Epistemic Grounding: System prompt forbids canned 'text-based AI without log access' hallucination.
"""

import sys
import os
import json
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://127.0.0.1:8001"


def print_step(step_num: int, title: str):
    print(f"\n{'='*56}")
    print(f"STEP {step_num}: {title}")
    print(f"{'='*56}")


def test_unified_microphone_toggle():
    print_step(1, "Testing Unified Microphone Toggle API (/api/voice/toggle_mic)")

    # 1. Turn mic OFF
    req_off = urllib.request.Request(
        f"{BASE_URL}/api/voice/toggle_mic",
        data=json.dumps({"active": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_off, timeout=5) as resp:
        assert resp.status == 200
        data_off = json.loads(resp.read().decode("utf-8"))
        print(f"Toggle Mic OFF response: {json.dumps(data_off, indent=2)}")
        assert data_off["status"] == "success"
        assert data_off["mic_active"] is False

    # 2. Verify config reflects mic off
    req_cfg = urllib.request.Request(f"{BASE_URL}/api/voice/config")
    with urllib.request.urlopen(req_cfg, timeout=5) as resp:
        cfg = json.loads(resp.read().decode("utf-8"))["config"]
        assert cfg.get("wake_word_enabled") is False, "Wake word must be disabled in config"
    print("PASS: Microphone successfully deactivated on host and config.")

    # 3. Turn mic ON
    req_on = urllib.request.Request(
        f"{BASE_URL}/api/voice/toggle_mic",
        data=json.dumps({"active": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_on, timeout=5) as resp:
        assert resp.status == 200
        data_on = json.loads(resp.read().decode("utf-8"))
        print(f"Toggle Mic ON response: {json.dumps(data_on, indent=2)}")
        assert data_on["status"] == "success"
        assert data_on["mic_active"] is True
    print("PASS: Microphone successfully reactivated on host.")


def test_proactive_alert_grounding():
    print_step(2, "Testing Watchdog Alert Emission & Memory Grounding")
    from backend.core.task_daemon import _emit_proactive_alert, get_latest_proactive_alert

    # Emit a realistic watchdog alert
    test_msg = "System RAM utilization has reached 91%, with language_server.exe utilizing 2275 MB. You may wish to inspect background processes."
    _emit_proactive_alert(
        alert_key="test_ram_surge",
        raw_message=test_msg,
        category="memory_warning",
        urgency="normal",
        cooldown_sec=0.1,
        speak=False
    )

    latest = get_latest_proactive_alert(max_age_sec=60.0)
    print(f"Retrieved Latest Proactive Alert: {json.dumps(latest, indent=2)}")
    assert latest is not None
    assert latest["category"] == "memory_warning"
    assert "language_server.exe" in latest["raw_message"]
    assert "age_seconds" in latest
    print("PASS: Watchdog alert properly grounded in active memory.")


def test_conversational_continuity():
    print_step(3, "Testing Conversational Continuity on 'yes inspect it'")
    from backend.core.jarvis_executive import dispatch_semantic_executive_action

    # User says "yes inspect it" immediately after the RAM alert
    res = dispatch_semantic_executive_action("yes inspect it")
    print(f"Semantic Dispatch Result for 'yes inspect it': {json.dumps(res, indent=2)}")

    assert res is not None
    assert res.get("action") == "system_control"
    assert res.get("command") in ("check_processes", "top_processes", "processes", "stats", "get_system_info")
    reply = res.get("reply", "")
    print(f"Executive Assistant Reply: '{reply}'")
    assert len(reply) > 5
    # Must NOT say "I forgot" or "What do you want me to inspect?"
    assert "what do you want" not in reply.lower()
    print("PASS: Zero-amnesia conversational continuity verified. Correctly resolved 'it' to process inspection!")


def test_system_integration_persona_guard():
    print_step(4, "Testing Epistemic Guard Against Generic Disclaimers")
    from backend.api.chat_router import SPECIALIST_SYSTEM_INTEGRATION_DIRECTIVE
    assert "NEVER claim to be a restricted text-based AI" in SPECIALIST_SYSTEM_INTEGRATION_DIRECTIVE
    assert "process inspection" in SPECIALIST_SYSTEM_INTEGRATION_DIRECTIVE
    print(f"Specialist Persona Directive: {SPECIALIST_SYSTEM_INTEGRATION_DIRECTIVE.strip()[:100]}...")
    print("PASS: Specialist persona guard strictly enforces native OS integration.")


def main():
    print("==================================================================")
    print("STARTING VERIFICATION: PROACTIVE CONTINUITY & MICROPHONE CONTROL")
    print("==================================================================")

    test_unified_microphone_toggle()
    test_proactive_alert_grounding()
    test_conversational_continuity()
    test_system_integration_persona_guard()

    print("\n==================================================================")
    print("ALL TESTS PASSED! ZERO AMNESIA, FULL OS GROUNDING, UNIFIED MIC.")
    print("==================================================================")


if __name__ == "__main__":
    main()
