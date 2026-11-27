"""
Native Background Wake Word Listener - Phase 5 / OS Level

Listens in the background for "Hey Jarvis", "Jarvis", or configured wake words.
When detected:
1. Plays the Arc Reactor activation prompt chime or speaks "At your service, Sir."
2. Captures user voice command.
3. Transcribes and executes via dispatch_jarvis_executive_action.
4. Speaks back the response using cultured British speech.
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.voice_pilot import speak_aloud, is_speaking, stop_speaking, get_duplex_state
from backend.core.jarvis_executive import dispatch_jarvis_executive_action, send_desktop_notification

CONFIG_PATH = PROJECT_ROOT / "backend" / "data" / "voice_profiles" / "voice_config.json"

_LISTENER_THREAD: Optional[threading.Thread] = None
_STOP_EVENT = threading.Event()
_IS_LISTENING = False
_DUPLEX_STATE = "IDLE"  # "IDLE", "LISTENING", "THINKING", "SPEAKING"
_LAST_BARGE_IN: Optional[Dict[str, Any]] = None
_BARGE_IN_COUNT = 0
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()


def _get_local_whisper_model():
    """Lazy-loads lightweight offline CPU INT8 Whisper model only when voice recognition runs."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL
        try:
            from faster_whisper import WhisperModel
            # Prefer locally cached multilingual 'tiny' / 'tiny.en' cleanly without blocking offline
            try:
                _WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8", local_files_only=True)
                print("[WakeWord STT]: Local cached faster-whisper (tiny, int8 CPU) loaded.")
            except Exception:
                _WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
                print("[WakeWord STT]: Local offline faster-whisper (tiny, int8 CPU) loaded.")
        except Exception as e:
            print(f"[WakeWord STT]: Local faster-whisper unavailable ({e}).")
            _WHISPER_MODEL = False
    return _WHISPER_MODEL if _WHISPER_MODEL is not False else None


def transcribe_audio_local_or_cloud(recognizer, audio) -> str:
    """
    Privacy-aware hybrid speech recognition:
    1. Prefers local offline faster-whisper (CPU int8, zero cloud dependency).
    2. Falls back to Google Web Speech only when NOT in air_gapped mode and local STT is unavailable.
    """
    model = _get_local_whisper_model()
    if model is not None:
        try:
            import numpy as np
            pcm_bytes = audio.get_raw_data(convert_rate=16000, convert_width=2)
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            if len(samples) > 1600:
                segments, _ = model.transcribe(
                    samples,
                    language="en",
                    beam_size=1,
                    vad_filter=True,
                    initial_prompt="Hey Jarvis, Jarvis, Friday, Unleash",
                )
                text = " ".join(seg.text.strip() for seg in segments if seg.text).strip()
                if text:
                    return text
        except Exception as e:
            print(f"[WakeWord Local STT Notice]: {e}")

    # Cloud fallback only when privacy mode permits external calls
    try:
        from backend.core.privacy_mode import is_frontier_allowed
        if not is_frontier_allowed():
            return ""
    except Exception:
        pass

    try:
        return (recognizer.recognize_google(audio) or "").strip()
    except Exception:
        return ""


def get_duplex_listener_status() -> Dict[str, Any]:
    """Returns the real-time duplex state machine and telemetry."""
    global _IS_LISTENING, _DUPLEX_STATE, _LAST_BARGE_IN, _BARGE_IN_COUNT
    duplex_audio = get_duplex_state()
    thread_alive = bool(_LISTENER_THREAD and _LISTENER_THREAD.is_alive())
    listening_now = bool(_IS_LISTENING and thread_alive)
    current_state = "SPEAKING" if duplex_audio["is_speaking"] else _DUPLEX_STATE
    return {
        "status": "success",
        "is_listening": listening_now,
        "is_speaking": duplex_audio["is_speaking"],
        "speech_energy": duplex_audio.get("speech_energy", 0.0),
        "duplex_state": current_state,
        "active_playback_alias": duplex_audio.get("active_alias"),
        "barge_in_count": _BARGE_IN_COUNT,
        "last_barge_in": _LAST_BARGE_IN,
        "last_cutoff_ms": duplex_audio.get("last_cutoff_ms", 0.0),
        "barge_in_enabled": True
    }


def trigger_manual_barge_in(reason: str = "manual_api") -> Dict[str, Any]:
    """Manually triggers real-time barge-in, cutting off assistant speech in <15ms."""
    global _DUPLEX_STATE, _LAST_BARGE_IN, _BARGE_IN_COUNT
    cutoff_ms = stop_speaking()
    _DUPLEX_STATE = "LISTENING"
    _BARGE_IN_COUNT += 1
    _LAST_BARGE_IN = {
        "timestamp": time.time(),
        "reason": reason,
        "cutoff_ms": cutoff_ms
    }
    print(f"[Duplex Barge-In Triggered]: Speech playback halted in {cutoff_ms:.2f}ms (Reason: {reason})")
    return {
        "status": "success",
        "cutoff_ms": cutoff_ms,
        "duplex_state": _DUPLEX_STATE,
        "message": f"Barge-in executed successfully in {cutoff_ms:.2f}ms."
    }


def load_wake_words() -> list:
    """Reads configured wake words from voice_config.json."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return [w.strip().lower() for w in cfg.get("wake_words", ["hey jarvis", "jarvis"]) if w.strip()]
    except Exception:
        pass
    return ["hey jarvis", "jarvis"]


def listen_for_wake_words(
    on_wake_callback: Optional[Callable[[str], None]] = None,
    stop_event: Optional[threading.Event] = None
):
    """
    Continuous background loop that listens to the default Windows microphone
    for configured wake words with minimal CPU footprint.
    """
    global _IS_LISTENING
    try:
        import speech_recognition as sr
    except ImportError:
        print("[WakeWord]: speech_recognition not installed. Wake-word listener disabled.")
        return

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"[WakeWord]: Failed to initialize microphone: {e}")
        return

    wake_words = load_wake_words()
    print(f"[WakeWord]: Native OS Background Listener Online. Active Wake Words: {wake_words}")
    _IS_LISTENING = True

    with mic as source:
        try:
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
        except Exception:
            pass

        while stop_event is None or not stop_event.is_set():
            # ================================================================
            # DUPLEX BARGE-IN PROTOCOL:
            # When Jarvis is speaking, monitor for user interruption.
            # Speech activity instantly triggers stop_speaking() in <15ms.
            # ================================================================
            if is_speaking():
                _DUPLEX_STATE = "SPEAKING"
                try:
                    # Short slice to detect user vocal interruption
                    barge_audio = recognizer.listen(source, timeout=0.6, phrase_time_limit=2.5)
                    # Transcribe FIRST before cutting off speech to prevent acoustic self-echo from cutting off assistant speech!
                    interrupted_text = transcribe_audio_local_or_cloud(recognizer, barge_audio)

                    # Only cut off if user actually spoke recognized words (prevents background noise / speaker echo from cutting off speech)
                    if interrupted_text and len(interrupted_text) > 1:
                        cutoff_ms = stop_speaking()
                        _BARGE_IN_COUNT += 1
                        _LAST_BARGE_IN = {
                            "timestamp": time.time(),
                            "reason": "speech_activity",
                            "cutoff_ms": cutoff_ms
                        }
                        _DUPLEX_STATE = "LISTENING"
                        print(f"[Duplex Barge-In Activated]: Detected verified voice interruption '{interrupted_text}' ({cutoff_ms:.2f}ms cutoff). Audio halted.")

                        lower_text = interrupted_text.lower()
                        stop_keywords = ["stop", "quiet", "shut up", "pause", "never mind", "cancel", "hold on", "silence", "wait"]
                        is_pure_stop = any(lower_text == kw or lower_text.startswith(kw) for kw in stop_keywords)
                        if is_pure_stop:
                            print(f"[Duplex Barge-In]: User requested silence ('{interrupted_text}'). Standing by.")
                            _DUPLEX_STATE = "IDLE"
                            continue

                        # User interrupted with a new instruction or question
                        print(f"[Duplex Barge-In Executing]: Routing new directive: '{interrupted_text}'")
                        fast_reply = None
                        try:
                            from backend.core.fast_path_router import try_fast_path_os_dispatch
                            fast_res = try_fast_path_os_dispatch(interrupted_text)
                            if fast_res is not None:
                                fast_reply = fast_res.get("reply")
                        except Exception:
                            pass

                        if fast_reply:
                            _DUPLEX_STATE = "SPEAKING"
                            speak_aloud(fast_reply)
                        else:
                            _DUPLEX_STATE = "THINKING"
                            res = dispatch_jarvis_executive_action(interrupted_text)
                            reply = res.get("reply", "Standing by.")
                            _DUPLEX_STATE = "SPEAKING"
                            speak_aloud(reply)
                    _DUPLEX_STATE = "IDLE"
                    continue
                except sr.WaitTimeoutError:
                    # Assistant still speaking, user hasn't spoken yet
                    continue
                except Exception:
                    time.sleep(0.1)
                    continue

            # ================================================================
            # IDLE WAKE-WORD DETECTION PROTOCOL:
            # ================================================================
            _DUPLEX_STATE = "IDLE"
            try:
                audio = recognizer.listen(source, timeout=3.0, phrase_time_limit=5.0)
            except sr.WaitTimeoutError:
                continue
            except Exception:
                time.sleep(0.5)
                continue

            if stop_event is not None and stop_event.is_set():
                break

            # Transcribe phrase locally/lightweight
            try:
                text = transcribe_audio_local_or_cloud(recognizer, audio).lower().strip()
                if not text:
                    continue

                print(f"[WakeWord Heard]: '{text}'")

                # Check if speech contains any of our wake words
                matched_word = None
                for w in wake_words:
                    if w in text:
                        matched_word = w
                        break

                if matched_word:
                    print(f"[WakeWord Detected]: Matched trigger phrase '{matched_word}'!")
                    _DUPLEX_STATE = "LISTENING"

                    # Extract any trailing command user said in the same breath (e.g. "Hey Jarvis open VS Code")
                    command_part = text.split(matched_word, 1)[-1].strip()

                    if on_wake_callback:
                        on_wake_callback(command_part)
                    else:
                        handle_wake_activation(command_part, recognizer, source)

                    _DUPLEX_STATE = "IDLE"

            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                time.sleep(1.0)
            except Exception as e:
                time.sleep(0.5)

    _IS_LISTENING = False
    print("[WakeWord]: Background Listener stopped.")


def _fallback_voice_reply(text: str) -> str:
    """Routes general conversational voice queries through privacy-aware LLM when executive actions don't match."""
    try:
        from backend.core.privacy_mode import is_frontier_allowed
        if is_frontier_allowed():
            from backend.core.gemini_client import gemini_available, _call_gemini
            if gemini_available():
                ans = _call_gemini(
                    f"Answer concisely in 1-2 natural spoken sentences for a desktop voice assistant:\nUser: {text}"
                )
                if ans and ans.strip():
                    return ans.strip()
    except Exception:
        pass
    try:
        import urllib.request
        payload = json.dumps({
            "model": "jarvis-qlora:latest",
            "messages": [
                {"role": "system", "content": "Answer concisely in 1-2 natural spoken sentences with no markdown."},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": 140},
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = (data.get("message") or {}).get("content", "").strip()
            if content:
                return content
    except Exception:
        pass
    return "Directive noted, though my reasoning engine is currently offline."


def _is_complex_task_prompt(text: str) -> bool:
    """Detects multi-step coding, research, file, or build directives suitable for background ReAct execution."""
    import re
    p = (text or "").lower().strip()
    if len(p.split()) < 3:
        return False
    return bool(re.search(
        r"\b(build|create|write|fix|debug|refactor|research|analyze|summarize|generate|implement|script|website|app|project|search\s+for|find\s+all|inspect\s+files)\b",
        p,
    ))


def _dispatch_complex_background_task(text: str) -> str:
    """Runs multi-step agentic tasks asynchronously with live daemon progress tracking."""
    task_id = None
    try:
        from backend.core.task_daemon import spawn_daemon_task, _update_task_row
        t_rec = spawn_daemon_task(
            title=text[:72],
            description=text,
            steps=["Planning directive", "Executing agentic workflow", "Summarizing result"],
        )
        task_id = t_rec.get("task_id") if isinstance(t_rec, dict) else None
    except Exception:
        _update_task_row = None

    def _runner():
        global _DUPLEX_STATE
        try:
            from backend.core.agent_engine import run_agentic_react_loop
            model_name = "jarvis-qlora:latest"
            try:
                from backend.core.privacy_mode import is_frontier_allowed
                if is_frontier_allowed():
                    from backend.core.gemini_client import gemini_available
                    if gemini_available():
                        model_name = "gemini-3.5-flash"
            except Exception:
                pass

            res = run_agentic_react_loop(model=model_name, user_prompt=text, max_steps=12)
            summary = ""
            if isinstance(res, dict):
                summary = (res.get("reply") or res.get("final_answer") or "").strip()
            if task_id and _update_task_row is not None:
                _update_task_row(task_id, status="completed", progress=100.0, current_step="Complete")
            if summary:
                short_summary = summary[:240].replace("`", "")
                _DUPLEX_STATE = "SPEAKING"
                speak_aloud(short_summary)
        except Exception as e:
            print(f"[WakeWord Complex Task Error]: {e}")
            if task_id and _update_task_row is not None:
                _update_task_row(task_id, status="failed", current_step=str(e)[:80])
        finally:
            _DUPLEX_STATE = "IDLE"

    threading.Thread(target=_runner, daemon=True, name="JarvisVoiceComplexTask").start()
    return "On it. Running that task in the background now."


def handle_wake_activation(initial_command: str, recognizer, source):
    """Handles prompt playback and command execution when wake word fires."""
    global _DUPLEX_STATE
    send_desktop_notification("Voice Assistant Active", "Listening for your directive...")

    def _execute_directive(text: str):
        global _DUPLEX_STATE
        _DUPLEX_STATE = "THINKING"
        reply = ""
        try:
            from backend.core.fast_path_router import try_fast_path_os_dispatch
            fast_res = try_fast_path_os_dispatch(text)
            if isinstance(fast_res, dict) and fast_res.get("reply"):
                reply = fast_res["reply"]
        except Exception:
            pass

        if not reply and _is_complex_task_prompt(text):
            reply = _dispatch_complex_background_task(text)

        if not reply:
            try:
                res = dispatch_jarvis_executive_action(text)
                if isinstance(res, dict) and res.get("reply"):
                    reply = res["reply"]
            except Exception as e:
                print(f"[WakeWord Directive Error]: {e}")

        if not reply:
            reply = _fallback_voice_reply(text)

        _DUPLEX_STATE = "SPEAKING"
        try:
            speak_aloud(reply)
        finally:
            _DUPLEX_STATE = "IDLE"

    if initial_command and len(initial_command) > 2:
        # User spoke the directive in the same breath
        print(f"[WakeWord Processing Direct Command]: '{initial_command}'")
        _execute_directive(initial_command)
        return

    # Acknowledge and prompt user
    _DUPLEX_STATE = "SPEAKING"
    speak_aloud("Listening.")
    time.sleep(0.9)  # Give time for the short prompt playback to settle

    # Listen for directive
    _DUPLEX_STATE = "LISTENING"
    try:
        print("[WakeWord]: Awaiting your directive...")
        cmd_audio = recognizer.listen(source, timeout=5.0, phrase_time_limit=8.0)
        cmd_text = transcribe_audio_local_or_cloud(recognizer, cmd_audio)
        print(f"[WakeWord Directive Captured]: '{cmd_text}'")
        if cmd_text:
            _execute_directive(cmd_text)
    except Exception as e:
        print(f"[WakeWord Notice]: {e}")
    finally:
        _DUPLEX_STATE = "IDLE"


def start_native_wake_word_daemon(in_background: bool = True):
    """Starts the native OS wake-word listener thread."""
    global _LISTENER_THREAD, _STOP_EVENT
    if _LISTENER_THREAD and _LISTENER_THREAD.is_alive():
        print("[WakeWord]: Daemon is already running.")
        return

    _STOP_EVENT.clear()
    _LISTENER_THREAD = threading.Thread(
        target=listen_for_wake_words,
        kwargs={"stop_event": _STOP_EVENT},
        daemon=True,
        name="JarvisNativeWakeWordThread"
    )
    _LISTENER_THREAD.start()
    print("[WakeWord]: Native Windows Wake Word Thread dispatched.")


def stop_native_wake_word_daemon():
    """Stops the native OS wake-word listener thread."""
    global _STOP_EVENT, _IS_LISTENING, _DUPLEX_STATE
    _STOP_EVENT.set()
    _IS_LISTENING = False
    if _DUPLEX_STATE == "LISTENING":
        _DUPLEX_STATE = "IDLE"
    print("[WakeWord]: Stop signal dispatched.")


if __name__ == "__main__":
    print("Testing Native Jarvis OS Wake Word Daemon. Say 'Hey Jarvis' or 'Jarvis'...")
    listen_for_wake_words()
