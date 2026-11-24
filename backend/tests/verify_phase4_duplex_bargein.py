"""
Comprehensive Automated Verification for Phase 4:
Duplex Hands-Free Voice with Real-Time Barge-In (<15ms audio cutoff).
Validates Win32 MCI non-blocking player, duplex state machine, and REST endpoints.
"""

import sys
import os
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://127.0.0.1:8001"


def print_step(num: int, title: str):
    print(f"\n========================================================")
    print(f"STEP {num}: {title}")
    print(f"========================================================")


def test_barge_in_direct_cutoff_latency():
    print_step(1, "Testing Direct Win32 MCI Barge-In Cutoff Latency (<15ms)")
    from backend.core.voice_pilot import play_audio_file, stop_speaking, is_speaking, AUDIO_CACHE_DIR

    # Locate a sample mp3 in cache
    sample_mp3 = None
    for f in AUDIO_CACHE_DIR.glob("*.mp3"):
        if f.is_file() and f.stat().st_size > 1000:
            sample_mp3 = str(f.resolve())
            break

    assert sample_mp3 is not None, "At least one cached audio file must exist for testing"
    print(f"Using audio test file: {sample_mp3}")

    # Queue playback
    play_res = play_audio_file(sample_mp3, serialize=True)
    assert play_res.get("success") is True, f"play_audio_file failed: {play_res}"

    # Wait 40ms for playback worker to start
    time.sleep(0.04)
    assert is_speaking() is True, "Assistant must be in SPEAKING state"

    # Execute Barge-In cutoff
    t0 = time.perf_counter()
    cutoff_ms = stop_speaking()
    local_latency = (time.perf_counter() - t0) * 1000.0

    print(f"Reported cutoff latency: {cutoff_ms:.3f} ms")
    print(f"Total measured call latency: {local_latency:.3f} ms")

    assert cutoff_ms < 15.0, f"Barge-in cutoff latency MUST be under 15ms! Got: {cutoff_ms:.3f}ms"
    assert is_speaking() is False, "Speaker playback must be stopped after barge-in"

    print("PASS: Direct Win32 barge-in cutoff latency is < 15ms.")


def test_duplex_state_reporting():
    print_step(2, "Testing Duplex State Reporting & Telemetry")
    from backend.core.voice_pilot import get_duplex_state
    from backend.core.wake_word_listener import get_duplex_listener_status

    audio_state = get_duplex_state()
    print(f"Audio duplex state: {json.dumps(audio_state, indent=2)}")

    assert "is_speaking" in audio_state
    assert "last_cutoff_ms" in audio_state
    assert "barge_in_ready" in audio_state and audio_state["barge_in_ready"] is True

    listener_status = get_duplex_listener_status()
    print(f"Listener duplex status: {json.dumps(listener_status, indent=2)}")

    assert "duplex_state" in listener_status
    assert "barge_in_enabled" in listener_status and listener_status["barge_in_enabled"] is True
    assert "barge_in_count" in listener_status

    print("PASS: Duplex state reporting validated.")


def test_api_duplex_status_endpoint():
    print_step(3, "Testing API GET /api/voice/duplex_status")
    req = urllib.request.Request(f"{BASE_URL}/api/voice/duplex_status")
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        print(f"API duplex_status: {json.dumps(data, indent=2)}")

        assert data.get("status") == "success"
        assert "duplex_state" in data
        assert "barge_in_enabled" in data
        assert data.get("barge_in_enabled") is True

    print("PASS: GET /api/voice/duplex_status endpoint validated.")


def test_api_barge_in_endpoint():
    print_step(4, "Testing API POST /api/voice/barge_in and POST /api/voice/stop")

    # 1. Start audio playback via voice_pilot
    from backend.core.voice_pilot import play_audio_file, AUDIO_CACHE_DIR
    sample_mp3 = next(AUDIO_CACHE_DIR.glob("*.mp3"))
    play_audio_file(str(sample_mp3.resolve()), serialize=True)
    time.sleep(0.04)

    # 2. Trigger Barge-In via API POST /api/voice/barge_in
    req = urllib.request.Request(
        f"{BASE_URL}/api/voice/barge_in",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        print(f"POST /api/voice/barge_in response: {json.dumps(data, indent=2)}")

        assert data.get("status") == "success"
        cutoff_ms = data.get("cutoff_ms", 999.0)
        assert cutoff_ms < 15.0, f"API Barge-in cutoff must be < 15ms! Got: {cutoff_ms}ms"

    # 3. Test POST /api/voice/stop endpoint
    req_stop = urllib.request.Request(
        f"{BASE_URL}/api/voice/stop",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_stop, timeout=10) as resp:
        assert resp.status == 200
        data_stop = json.loads(resp.read().decode("utf-8"))
        print(f"POST /api/voice/stop response: {json.dumps(data_stop, indent=2)}")
        assert data_stop.get("status") == "success"
        assert "cutoff_ms" in data_stop
        assert data_stop.get("cutoff_ms", 999.0) < 15.0

    print("PASS: API barge_in and stop endpoints validated.")


def test_duplex_state_transitions():
    print_step(5, "Testing Duplex State Transitions: SPEAKING -> BARGE-IN -> LISTENING")
    from backend.core.voice_pilot import play_audio_file, AUDIO_CACHE_DIR, is_speaking
    from backend.core.wake_word_listener import trigger_manual_barge_in, get_duplex_listener_status

    sample_mp3 = next(AUDIO_CACHE_DIR.glob("*.mp3"))

    # Transition 1: Queue speech
    play_audio_file(str(sample_mp3.resolve()), serialize=True)
    time.sleep(0.04)
    status_speaking = get_duplex_listener_status()
    assert status_speaking["is_speaking"] is True
    assert status_speaking["duplex_state"] == "SPEAKING"
    print("State during playback: SPEAKING (Verified)")

    # Transition 2: User interrupts -> Barge-In
    barge_result = trigger_manual_barge_in(reason="simulated_user_speech")
    print(f"Barge-in result: {barge_result}")
    assert barge_result["status"] == "success"
    assert barge_result["cutoff_ms"] < 15.0

    # Transition 3: Shift to LISTENING
    status_after = get_duplex_listener_status()
    assert status_after["is_speaking"] is False
    assert status_after["duplex_state"] == "LISTENING"
    print("State immediately after barge-in: LISTENING (Verified)")

    print("PASS: Full duplex state machine transitions verified.")


def main():
    print("==================================================================")
    print("STARTING PHASE 4 VERIFICATION: DUPLEX VOICE WITH REAL-TIME BARGE-IN")
    print("==================================================================")

    test_barge_in_direct_cutoff_latency()
    test_duplex_state_reporting()
    test_api_duplex_status_endpoint()
    test_api_barge_in_endpoint()
    test_duplex_state_transitions()

    print("\n==================================================================")
    print("ALL 5 STEPS IN PHASE 4 VERIFICATION PASSED PERFECTLY!")
    print("Sub-15ms audio cutoff verified. Duplex state transitions green.")
    print("==================================================================")


if __name__ == "__main__":
    main()
