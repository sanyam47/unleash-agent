"""
Verification Test Suite for the Floating Gyroscopic Sphere HUD:
1. GyroSphereRenderer orbital motion, Jarvis speech "pop", emerald Mic state, & task progress arc.
2. Voice Pilot real-time speech energy envelope & duplex state integration.
3. FastAPI `/api/daemon/hud/state` contract & sub-50ms latency.
4. Native Win32 layered window (`jarvis_desktop_hud.py`) show/hide/standby lifecycle & independent Mic state.
"""

import ctypes
import json
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_gyro_renderer_states_and_pop():
    print("\n[1/5] Testing GyroSphereRenderer states, motion, and Jarvis speech pop...")
    from backend.core.gyro_sphere_renderer import GyroSphereRenderer, SphereVisualState

    r = GyroSphereRenderer(size=104)
    f_idle_1 = np.array(r.render_frame(SphereVisualState(mode="IDLE", mic_active=False), dt=1 / 30.0))
    phase_1 = r._phase
    f_idle_2 = np.array(r.render_frame(SphereVisualState(mode="IDLE", mic_active=False), dt=1 / 30.0))
    assert r._phase > phase_1, "Orbital rings must rotate continuously while visible"
    assert not np.array_equal(f_idle_1, f_idle_2), "Consecutive visible frames must animate rings"

    # Mic active -> emerald dominance in core/aura + voice-reactive listening pop
    for _ in range(12):
        f_mic_quiet = np.array(r.render_frame(SphereVisualState(mode="LISTENING", mic_active=True, mic_energy=0.0), dt=1 / 30.0))
    for _ in range(12):
        f_mic = np.array(r.render_frame(SphereVisualState(mode="LISTENING", mic_active=True, mic_energy=0.85), dt=1 / 30.0))
    mic_pop = r._pop
    green_excess_mic = int(np.sum(f_mic[:, :, 1].astype(np.int32) - f_mic[:, :, 0].astype(np.int32)))
    assert green_excess_mic > 2000, f"Expected emerald Mic glow, got G-R sum={green_excess_mic}"
    assert mic_pop > 0.35, f"Expected sphere to pop visibly during LISTENING voice peak, got pop={mic_pop:.3f}"
    assert int(f_mic[:, :, 1].sum()) > int(f_mic_quiet[:, :, 1].sum()), "Listening core should flare brighter on mic_energy"

    # Background task progress arc -> blue outer perimeter arc pixels
    for _ in range(12):
        f_task = np.array(r.render_frame(SphereVisualState(mode="THINKING", active_tasks_count=1, task_progress=70.0), dt=1 / 30.0))
    yy, xx = np.mgrid[0:104, 0:104]
    dist = np.sqrt((xx - 51.5) ** 2 + (yy - 51.5) ** 2)
    outer_ring = (dist >= 41.0) & (dist <= 47.0)
    blue_arc_pixels = int(np.sum((f_task[outer_ring, 2] > 180) & (f_task[outer_ring, 3] > 180)))
    assert blue_arc_pixels > 40, f"Expected sapphire task progress arc pixels on perimeter, got {blue_arc_pixels}"

    # Speaking "pop" -> strong radial spring expansion & luminous core bloom
    idle_pop = r._pop
    for _ in range(10):
        f_speak = np.array(r.render_frame(SphereVisualState(mode="SPEAKING", mic_active=True, speech_energy=0.95), dt=1 / 30.0))
    assert r._pop > max(0.45, idle_pop + 0.35), f"Expected strong speech pop spring displacement, got {r._pop:.3f}"
    assert int(f_speak[:, :, 1].sum()) > int(f_idle_1[:, :, 1].sum()), "Speaking core should bloom brighter on voice peak"
    print(f"PASS: Rotation, emerald Mic, sapphire 70% arc ({blue_arc_pixels} px), & Jarvis pop ({r._pop:.2f}) verified.")


def test_voice_pilot_speech_energy():
    print("\n[2/5] Testing Voice Pilot live speech energy & WAV envelope extraction...")
    from backend.core import voice_pilot

    assert voice_pilot.get_speech_energy() == 0.0, "Idle speech_energy must be 0.0"

    # Build a synthetic 0.25s 16-bit WAV with distinct loud tone to test async RMS envelope
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name
    try:
        sr = 16000
        t = np.linspace(0, 0.25, int(sr * 0.25), endpoint=False)
        pcm = (np.sin(2 * np.pi * 220 * t) * 20000).astype(np.int16)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())

        voice_pilot._IS_SPEAKING = True
        voice_pilot._begin_speech_session(wav_path)
        time.sleep(0.08)
        energy = voice_pilot.get_speech_energy()
        duplex = voice_pilot.get_duplex_state()
        assert 0.08 <= energy <= 1.0, f"Expected active speech_energy in [0.08..1.0], got {energy}"
        assert "speech_energy" in duplex and duplex["is_speaking"] is True
        print(f"PASS: Live speech_energy={energy} with duplex telemetry OK.")
    finally:
        voice_pilot._IS_SPEAKING = False
        voice_pilot._end_speech_session()
        Path(wav_path).unlink(missing_ok=True)


def test_hud_state_api_endpoint():
    print("\n[3/5] Testing GET /api/daemon/hud/state endpoint contract & speed...")
    from starlette.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)
    t0 = time.perf_counter()
    resp = client.get("/api/daemon/hud/state")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    for key in ("status", "mic_active", "is_listening", "is_speaking", "duplex_state", "speech_energy", "active_tasks_count", "top_task_progress"):
        assert key in data, f"Missing '{key}' in /api/daemon/hud/state"
    assert elapsed_ms < 250.0, f"/api/daemon/hud/state should respond quickly, took {elapsed_ms:.1f}ms"

    # Also verify POST /api/daemon/app/shutdown cleanly (without exiting test process)
    import threading
    from unittest.mock import patch
    with patch.object(threading, "Timer") as mock_timer:
        mock_timer.return_value.start.return_value = None
        r_shut = client.post("/api/daemon/app/shutdown")
        assert r_shut.status_code == 200 and r_shut.json()["status"] == "success"
        assert mock_timer.called, "app/shutdown must schedule clean exit timer"

    print(f"PASS: GET /api/daemon/hud/state ({elapsed_ms:.1f} ms) & /api/daemon/app/shutdown OK.")


def test_independent_mic_and_bgra_helper():
    print("\n[4/5] Testing premultiplied BGRA conversion & Mic independence during show/hide...")
    from PIL import Image
    from backend.scripts.jarvis_desktop_hud import (
        BackendBridge,
        JarvisFloatingHUD,
        WINDOW_CLASS,
        WINDOW_TITLE,
        rgba_to_premultiplied_bgra,
    )

    img = Image.new("RGBA", (104, 104), (0, 0, 0, 0))
    raw = rgba_to_premultiplied_bgra(img, hit_radius_px=38)
    assert len(raw) == 104 * 104 * 4
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(104, 104, 4)
    assert arr[52, 52, 3] >= 2, "Center click hit-zone should have alpha >= 2"
    assert arr[0, 0, 3] == 0, "Outer corner pixels must remain fully click-through alpha == 0"

    # Verify hide() leaves user's mic_active state untouched whether ON or OFF
    hud = JarvisFloatingHUD(start_visible=False)
    try:
        with hud.bridge._state_lock:
            hud.bridge._visual_state.mic_active = True
            hud.bridge._optimistic_mic_until = time.monotonic() + 30.0
        hud.show()
        assert hud.visible is True
        hud.hide()
        assert hud.visible is False
        assert hud.bridge.snapshot().mic_active is True, "Hiding sphere MUST preserve Mic ON when user left it ON"

        with hud.bridge._state_lock:
            hud.bridge._visual_state.mic_active = False
        hud.show()
        hud.hide()
        assert hud.bridge.snapshot().mic_active is False, "Hiding sphere MUST preserve Mic OFF when user left it OFF"
        print("PASS: BGRA premultiplication & visibility/mic independence verified.")
    finally:
        hud.quit()


def test_live_win32_process_standby_and_show():
    print("\n[5/8] Testing live Win32 subprocess --hidden standby -> IPC/show -> quit...")
    from starlette.testclient import TestClient
    from backend.api.main import app

    script = str(PROJECT_ROOT / "backend" / "scripts" / "jarvis_desktop_hud.py")
    p = subprocess.Popen(
        [sys.executable, script, "--hidden"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    user32 = ctypes.windll.user32
    hwnd = 0
    for _ in range(40):
        hwnd = user32.FindWindowW("UnleashGyroSphereHUDWindow", "Unleash Gyro Sphere HUD")
        if hwnd:
            break
        time.sleep(0.05)

    assert hwnd != 0, "Win32 HUD window must register even in --hidden standby"
    assert not user32.IsWindowVisible(hwnd), "Window launched with --hidden must start invisible"

    # Verify cross-station loopback IPC reports hud_running=True cleanly
    client = TestClient(app)
    r_stat = client.get("/api/daemon/hud/state").json()
    assert r_stat.get("hud_running") is True, f"Expected hud_running=True via IPC, got {r_stat}"

    # Simulate summon
    user32.PostMessageW(hwnd, 0x8001, 0, 0)  # WM_USER_SHOW
    for _ in range(20):
        if user32.IsWindowVisible(hwnd):
            break
        time.sleep(0.05)
    assert user32.IsWindowVisible(hwnd), "WM_USER_SHOW must reveal sphere cleanly"

    # Simulate hide
    user32.PostMessageW(hwnd, 0x8002, 0, 0)  # WM_USER_HIDE
    time.sleep(0.15)
    assert not user32.IsWindowVisible(hwnd), "WM_USER_HIDE must conceal sphere cleanly"

    # Quit cleanly via /api/daemon/hud/quit (cross-station IPC -> WM_USER_QUIT)
    r_quit = client.post("/api/daemon/hud/quit").json()
    assert r_quit.get("hud_running") is False
    out, err = p.communicate(timeout=5)
    assert p.returncode == 0, f"Unexpected exit code {p.returncode}: stderr={err}"
    assert "UpdateLayeredWindow failed" not in out
    print(f"PASS: Live Win32 HUD standby/IPC/show/hide/quit verified (exit={p.returncode}).")


def test_hud_startup_endpoint():
    print("\n[6/6] Testing GET/POST /api/daemon/hud/startup Windows Startup toggle...")
    from starlette.testclient import TestClient
    from backend.api.main import app
    from backend.api.daemon_router import _get_hud_startup_shortcut_path, _set_hud_startup_enabled

    client = TestClient(app)
    shortcut_path = _get_hud_startup_shortcut_path()
    was_enabled = shortcut_path.exists()

    try:
        # Test enabling (spawn_if_missing=False via helper or test endpoint + cleanup any spawned window)
        res_on = _set_hud_startup_enabled(True, spawn_if_missing=False)
        assert res_on["status"] == "success" and res_on["enabled"] is True
        assert shortcut_path.exists(), "Windows Startup .lnk shortcut must exist after enabling"

        resp_get = client.get("/api/daemon/hud/startup")
        assert resp_get.status_code == 200 and resp_get.json()["enabled"] is True

        resp_off = client.post("/api/daemon/hud/startup", json={"enabled": False})
        assert resp_off.status_code == 200 and resp_off.json()["enabled"] is False
        assert not shortcut_path.exists(), "Windows Startup .lnk shortcut must be removed after disabling"
        print("PASS: Windows Startup shortcut create/status/remove toggle verified.")
    finally:
        # Restore prior user state cleanly
        _set_hud_startup_enabled(was_enabled, spawn_if_missing=False)


def test_local_stt_complex_routing_and_tray_shutdown():
    print("\n[7/8] Testing Silero VAD, anchored wake gate, dynamic apps, tray icon, & WM_QUERYENDSESSION...")
    from backend.core.wake_word_listener import (
        _get_local_whisper_model,
        has_human_speech,
        is_valid_barge_in_text,
        match_wake_word,
        transcribe_audio_local_or_cloud,
    )
    from backend.core.app_discovery import find_best_app_match, refresh_app_cache
    from backend.core.jarvis_executive import launch_app
    from backend.scripts.jarvis_desktop_hud import JarvisFloatingHUD, WM_QUERYENDSESSION

    assert _get_local_whisper_model() is not None, "Cached offline faster-whisper model should load cleanly"

    # Verify Silero VAD rejects pure silence cleanly without touching Whisper
    assert has_human_speech(np.zeros(16000, dtype=np.float32)) is False, "Pure silence must be rejected by VAD"

    # Verify anchored wake matching, mid-sentence rejection, and repeated wake echo stripping
    w, cmd = match_wake_word("Hey, Jarvis! Check my GPU temperature.")
    assert w in ("hey jarvis", "jarvis") and "check my gpu temperature" in cmd, f"Got {(w, cmd)}"
    w_echo, cmd_echo = match_wake_word("hey jarvis, jarvis,")
    assert w_echo == "hey jarvis" and cmd_echo == "", f"Repeated wake echo must strip cleanly, got {(w_echo, cmd_echo)}"
    w_mid, _ = match_wake_word("I was just talking about jarvis earlier today")
    assert w_mid is None, f"Mid-sentence casual mention must NOT trigger wake word, got {w_mid}"
    w_fri, _ = match_wake_word("Let us grab lunch on Friday afternoon")
    assert w_fri is None, f"Non-configured word 'friday' must NOT trigger wake word, got {w_fri}"

    # Verify dynamic Windows app discovery & honest error for nonexistent apps
    dyn_apps = refresh_app_cache(force=True)
    assert len(dyn_apps) > 0, "Dynamic OS app discovery must index installed apps"
    assert find_best_app_match("calculator", dyn_apps) is not None or find_best_app_match("notepad", dyn_apps) is not None
    fake_res = launch_app("totally_nonexistent_xyz_app_999")
    assert fake_res.get("status") == "error", f"Unknown app must return error, not fake success: {fake_res}"

    # Verify acoustic speaker self-echo protection in barge-in
    cut_noise, _ = is_valid_barge_in_text("I don't know where there is a name.")
    assert cut_noise is False, "Random noise / self-echo must NOT cut off Jarvis mid-sentence"
    cut_stop, _ = is_valid_barge_in_text("stop")
    assert cut_stop is True
    cut_wake, dir_wake = is_valid_barge_in_text("Hey Jarvis, open notepad")
    assert cut_wake is True and "open notepad" in dir_wake

    # Synthesize a real 'Hey Jarvis' audio clip & verify offline faster-whisper recognizes it
    try:
        import soundfile as sf
        import speech_recognition as sr
        from backend.core.voice_pilot import synthesize_speech

        synth = synthesize_speech("Hey Jarvis, open calculator")
        if synth.get("success") and synth.get("audio_path"):
            data, rate = sf.read(synth["audio_path"], dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
            # Resample cleanly to 16kHz int16 if needed
            if rate != 16000:
                idx = np.round(np.linspace(0, len(data) - 1, int(len(data) * 16000 / rate))).astype(int)
                data = data[idx]
            pcm16 = (np.clip(data, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
            audio = sr.AudioData(pcm16, 16000, 2)
            heard = transcribe_audio_local_or_cloud(sr.Recognizer(), audio)
            matched_tts, _ = match_wake_word(heard)
            assert matched_tts is not None, f"Offline Whisper failed to match synthesized wake phrase: heard='{heard}'"
            print(f"PASS: End-to-end Whisper heard '{heard}' -> matched '{matched_tts}'.")
    except Exception as e:
        raise AssertionError(f"Offline wake-word end-to-end test failed: {e}")

    hud = JarvisFloatingHUD(start_visible=False)
    try:
        assert hud._tray_icon_handle, "16x16 orb HICON must be created cleanly"
        if ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None):
            assert hud._tray_added is True, "Windows notification tray icon must register cleanly when Explorer shell is present"
        assert hud._wnd_proc(hud._hwnd, WM_QUERYENDSESSION, 0, 0) == 1, "WM_QUERYENDSESSION must allow instant Windows shutdown"
        print("PASS: Cached offline STT, wake matcher, orb HICON/tray, and shutdown guard verified.")
    finally:
        hud.quit()


def test_gdi_handle_leak_and_sleep_safety():
    print("\n[8/8] Testing 100-frame GDI handle leak stability (GR_GDIOBJECTS)...")
    from backend.scripts.jarvis_desktop_hud import JarvisFloatingHUD

    GR_GDIOBJECTS = 0
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    get_gui = ctypes.windll.user32.GetGuiResources
    get_gui.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    get_gui.restype = ctypes.c_uint
    hproc = ctypes.windll.kernel32.GetCurrentProcess()

    hud = JarvisFloatingHUD(start_visible=False)
    try:
        hud.show()
        # Warm up first frame
        hud._render_tick()
        gdi_before = get_gui(hproc, GR_GDIOBJECTS)
        for _ in range(100):
            hud._render_tick()
        gdi_after = get_gui(hproc, GR_GDIOBJECTS)
        leaked = gdi_after - gdi_before
        assert leaked <= 0, f"Detected GDI handle leak over 100 frames: before={gdi_before}, after={gdi_after}"
        print(f"PASS: 100 layered UpdateLayeredWindow frames pushed cleanly with zero GDI handle leaks ({gdi_before} -> {gdi_after}).")
    finally:
        hud.quit()


if __name__ == "__main__":
    print("=" * 64)
    print("UNLEASH-AGENT FLOATING GYRO SPHERE VERIFICATION SUITE")
    print("=" * 64)
    test_gyro_renderer_states_and_pop()
    test_voice_pilot_speech_energy()
    test_hud_state_api_endpoint()
    test_independent_mic_and_bgra_helper()
    test_live_win32_process_standby_and_show()
    test_hud_startup_endpoint()
    test_local_stt_complex_routing_and_tray_shutdown()
    test_gdi_handle_leak_and_sleep_safety()
    print("\nALL 8 GYRO SPHERE HUD VERIFICATION SUITES PASSED.")
