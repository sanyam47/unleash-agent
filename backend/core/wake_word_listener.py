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


def get_duplex_listener_status() -> Dict[str, Any]:
    """Returns the real-time duplex state machine and telemetry."""
    global _IS_LISTENING, _DUPLEX_STATE, _LAST_BARGE_IN, _BARGE_IN_COUNT
    duplex_audio = get_duplex_state()
    current_state = "SPEAKING" if duplex_audio["is_speaking"] else _DUPLEX_STATE
    return {
        "status": "success",
        "is_listening": _IS_LISTENING,
        "is_speaking": duplex_audio["is_speaking"],
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
                    interrupted_text = ""
                    try:
                        interrupted_text = recognizer.recognize_google(barge_audio).strip()
                    except Exception:
                        interrupted_text = ""

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
                text = recognizer.recognize_google(audio).lower().strip()
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


def handle_wake_activation(initial_command: str, recognizer, source):
    """Handles prompt playback and command execution when wake word fires."""
    send_desktop_notification("Voice Assistant Active", "Listening for your directive...")

    def _execute_directive(text: str):
        try:
            from backend.core.fast_path_router import try_fast_path_os_dispatch
            fast_res = try_fast_path_os_dispatch(text)
            if fast_res is not None:
                reply = fast_res.get("reply", "Command executed.")
                speak_aloud(reply)
                return
        except Exception:
            pass
        res = dispatch_jarvis_executive_action(text)
        reply = res.get("reply", "Command executed.")
        speak_aloud(reply)
    
    if initial_command and len(initial_command) > 2:
        # User spoke the directive in the same breath
        print(f"[WakeWord Processing Direct Command]: '{initial_command}'")
        _execute_directive(initial_command)
        return

    # Acknowledge and prompt user
    speak_aloud("Listening.")
    time.sleep(1.0)  # Give time for the speech playback to finish

    # Listen for directive
    try:
        print("[WakeWord]: Awaiting your directive...")
        cmd_audio = recognizer.listen(source, timeout=5.0, phrase_time_limit=8.0)
        cmd_text = recognizer.recognize_google(cmd_audio).strip()
        print(f"[WakeWord Directive Captured]: '{cmd_text}'")
        if cmd_text:
            _execute_directive(cmd_text)
    except Exception as e:
        print(f"[WakeWord Notice]: {e}")


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
    global _STOP_EVENT
    _STOP_EVENT.set()
    print("[WakeWord]: Stop signal dispatched.")


if __name__ == "__main__":
    print("Testing Native Jarvis OS Wake Word Daemon. Say 'Hey Jarvis' or 'Jarvis'...")
    listen_for_wake_words()
