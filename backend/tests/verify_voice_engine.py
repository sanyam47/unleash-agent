"""
Voice Engine and Persona Exclusivity Verification Test Suite
"""
import urllib.request
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE_URL = "http://127.0.0.1:8001"

def api_get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))

def api_post(endpoint, payload):
    url = f"{BASE_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))

def run_tests():
    print("=== [1] Testing GET /api/voice/available_voices ===")
    voices = api_get("/api/voice/available_voices")
    assert voices.get("status") == "success", "available_voices status failed"
    net_voices = [v["id"] for v in voices.get("internet_voices", [])]
    sapi_voices = [v["id"] for v in voices.get("fallback_voices", [])]
    print(f"Internet voices available: {net_voices}")
    print(f"Fallback voices available: {sapi_voices}")
    assert "none" in net_voices, "'none' voice missing from internet voices"
    assert "en-US-GuyNeural" in net_voices, "GuyNeural missing"
    assert "en-GB-RyanNeural" in net_voices, "RyanNeural missing"
    print("-> PASS: available_voices verified!\n")

    print("=== [2] Testing POST /api/voice/config (Voice & Wake Word settings persistence) ===")
    cfg_update = {
        "default_internet_voice": "en-US-GuyNeural",
        "default_fallback_voice": "male",
        "auto_speak_replies": True
    }
    cfg_res = api_post("/api/voice/config", cfg_update)
    assert cfg_res.get("status") == "success"
    active_cfg = cfg_res.get("config", {})
    assert active_cfg.get("default_internet_voice") == "en-US-GuyNeural"
    assert active_cfg.get("default_fallback_voice") == "male"
    print("-> PASS: voice config update verified!\n")

    print("=== [3] Testing POST /api/voice/test_voice with Neural Voice (Guy Neural) ===")
    test_neural = api_post("/api/voice/test_voice", {
        "voice": "en-US-GuyNeural",
        "fallback_voice": "default",
        "text": "Autonomous systems diagnostic test.",
        "play_on_host": False
    })
    print(f"Neural Test Result: {test_neural}")
    assert test_neural.get("success") == True, "Neural test synthesis failed"
    assert "audio_url" in test_neural, "Missing audio_url in synthesis result"
    print("-> PASS: Neural voice synthesis verified!\n")

    print("=== [4] Testing POST /api/voice/test_voice with Pure Offline SAPI (voice: 'none') ===")
    test_offline = api_post("/api/voice/test_voice", {
        "voice": "none",
        "fallback_voice": "male",
        "text": "Local offline speech calibrated.",
        "play_on_host": False
    })
    print(f"Offline Test Result: {test_offline}")
    assert test_offline.get("success") == True, "Offline SAPI synthesis failed"
    print("-> PASS: Pure offline voice synthesis verified!\n")

    print("=== [5] Testing Persona Bake Voice Binding Persistence ===")
    from pathlib import Path
    bake_payload = {
        "agent_name": "Atlas",
        "role_mandate": "Tactical Systems Specialist",
        "user_addressing": "Commander",
        "creator": "Engineering",
        "sarcasm_level": 20,
        "autonomy_level": 50,
        "calm_under_fire": 100,
        "verbosity": 25,
        "core_directive": "Execute mission objectives with total fidelity.",
        "pushback_rule": "Warn of hazards immediately.",
        "specialist_domains": ["System Architecture", "Security"],
        "base_model": "cyber-specialist:latest",
        "internet_voice": "en-US-GuyNeural",
        "fallback_voice": "male"
    }
    from backend.core.voice_pilot import get_model_voice_profile
    # Check that jarvis directory on disk resolves its configured RyanNeural
    j_net, j_sapi = get_model_voice_profile("jarvis:latest")
    print(f"Model 'jarvis:latest' voice profile from disk: Internet='{j_net}', Fallback='{j_sapi}'")
    assert j_net == "en-GB-RyanNeural", f"Expected en-GB-RyanNeural, got {j_net}"
    
    # Check that generic model resolves global default
    g_net, g_sapi = get_model_voice_profile("llama3:latest")
    print(f"Model 'llama3:latest' voice profile: Internet='{g_net}', Fallback='{g_sapi}'")
    assert g_net == "en-US-GuyNeural", f"Expected en-US-GuyNeural, got {g_net}"
    print("-> PASS: Model voice resolution verified!\n")

    print("=== [6] Testing Neutrality & Clean Separation ===")
    from backend.core.voice_pilot import AVAILABLE_INTERNET_VOICES
    for v in AVAILABLE_INTERNET_VOICES:
        v_name = v.get("name", "")
        assert "jarvis" not in v_name.lower(), f"Trademark found in voice: {v_name}"
        assert "friday" not in v_name.lower(), f"Trademark found in voice: {v_name}"
    print("-> PASS: All voice labels are clean and neutral!\n")

    print("=== ALL TESTS PASSED! ===")

if __name__ == "__main__":
    run_tests()
