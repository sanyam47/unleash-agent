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
from typing import Optional, Callable

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.voice_pilot import speak_aloud, is_speaking
from backend.core.jarvis_executive import dispatch_jarvis_executive_action, send_desktop_notification

CONFIG_PATH = PROJECT_ROOT / "backend" / "data" / "voice_profiles" / "voice_config.json"

_LISTENER_THREAD: Optional[threading.Thread] = None
_STOP_EVENT = threading.Event()
_IS_LISTENING = False


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
            # If Jarvis is currently speaking out loud, pause microphone listening to prevent hearing himself
            if is_speaking():
                time.sleep(0.3)
                continue

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
                    
                    # Extract any trailing command user said in the same breath (e.g. "Hey Jarvis open VS Code")
                    command_part = text.split(matched_word, 1)[-1].strip()
                    
                    if on_wake_callback:
                        on_wake_callback(command_part)
                    else:
                        handle_wake_activation(command_part, recognizer, source)

            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                # Offline fallback or brief connection hiccup
                time.sleep(1.0)
            except Exception as e:
                time.sleep(0.5)

    _IS_LISTENING = False
    print("[WakeWord]: Background Listener stopped.")


def handle_wake_activation(initial_command: str, recognizer, source):
    """Handles prompt playback and command execution when wake word fires."""
    send_desktop_notification("Voice Assistant Active", "Listening for your directive...")
    
    if initial_command and len(initial_command) > 2:
        # User spoke the directive in the same breath
        print(f"[WakeWord Processing Direct Command]: '{initial_command}'")
        res = dispatch_jarvis_executive_action(initial_command)
        reply = res.get("reply", "Command executed.")
        speak_aloud(reply)
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
            res = dispatch_jarvis_executive_action(cmd_text)
            reply = res.get("reply", "Done.")
            speak_aloud(reply)
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
