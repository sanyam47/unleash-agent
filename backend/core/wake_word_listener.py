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
_MIC_ENERGY = 0.0
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()
_VAD_MODEL = None
_VAD_LOCK = threading.Lock()


def _get_silero_vad_model():
    """Lazy-loads bundled offline Silero VAD ONNX model cleanly with zero downloads."""
    global _VAD_MODEL
    if _VAD_MODEL is not None:
        return _VAD_MODEL
    with _VAD_LOCK:
        if _VAD_MODEL is not None:
            return _VAD_MODEL
        try:
            from faster_whisper.vad import get_vad_model
            _VAD_MODEL = get_vad_model()
        except Exception as e:
            print(f"[WakeWord VAD Notice]: Silero VAD unavailable ({e}).")
            _VAD_MODEL = False
    return _VAD_MODEL if _VAD_MODEL is not False else None


def has_human_speech(samples_f32) -> bool:
    """Returns True only if Silero VAD detects genuine human speech in 16kHz float32 samples."""
    if samples_f32 is None or len(samples_f32) < 1600:
        return False
    vad_model = _get_silero_vad_model()
    if vad_model is None:
        return True  # Fail-open cleanly if VAD library unavailable
    try:
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        opts = VadOptions(threshold=0.45, min_speech_duration_ms=140, min_silence_duration_ms=120)
        segments = get_speech_timestamps(samples_f32, opts)
        return bool(segments)
    except Exception:
        return True


def _update_mic_energy_from_pcm(pcm_bytes: bytes) -> float:
    """Computes normalized live mic amplitude [0.0..1.0] for Gyro Sphere HUD visualization."""
    global _MIC_ENERGY
    try:
        import numpy as np
        arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        if len(arr) == 0:
            return _MIC_ENERGY
        arr = arr - float(np.mean(arr))
        rms = float(np.sqrt(np.mean(arr * arr))) / 32768.0
        # Map conversational laptop mic RMS (~0.005..0.043) onto crisp [0.0..1.0] so Listening pops clearly
        instant = max(0.0, min(1.0, (rms - 0.005) / 0.038))
        if instant >= _MIC_ENERGY:
            _MIC_ENERGY = 0.65 * instant + 0.35 * _MIC_ENERGY
        else:
            _MIC_ENERGY = 0.25 * instant + 0.75 * _MIC_ENERGY
    except Exception:
        pass
    return round(_MIC_ENERGY, 4)


class _MeteredAudioStream:
    """Lightweight transparent proxy over sr.Microphone stream updating real-time mic_energy."""

    def __init__(self, inner_stream):
        self._inner = inner_stream

    def read(self, size: int) -> bytes:
        data = self._inner.read(size)
        if data:
            _update_mic_energy_from_pcm(data)
        return data

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _get_local_whisper_model():
    """Lazy-loads offline CPU INT8 Whisper model (prefers cached 'base', falls back to 'tiny')."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL
        try:
            from faster_whisper import WhisperModel
            preferred = os.environ.get("UNLEASH_WHISPER_MODEL", "base").strip() or "base"
            candidates = [preferred] if preferred == "tiny" else [preferred, "tiny"]
            cpu_threads = min(4, max(1, os.cpu_count() or 2))

            for model_name in candidates:
                try:
                    _WHISPER_MODEL = WhisperModel(
                        model_name,
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=cpu_threads,
                        local_files_only=True,
                    )
                    print(f"[WakeWord STT]: Local cached faster-whisper ({model_name}, int8 CPU) loaded.")
                    break
                except Exception:
                    continue

            if _WHISPER_MODEL is None:
                _WHISPER_MODEL = WhisperModel(
                    preferred,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=cpu_threads,
                )
                print(f"[WakeWord STT]: Local offline faster-whisper ({preferred}, int8 CPU) loaded.")
        except Exception as e:
            print(f"[WakeWord STT]: Local faster-whisper unavailable ({e}).")
            _WHISPER_MODEL = False
    return _WHISPER_MODEL if _WHISPER_MODEL is not False else None


def _condition_pcm_for_whisper(samples):
    """Removes DC offset, normalizes low mic gain, and pads brief boundary silence."""
    import numpy as np
    if len(samples) == 0:
        return samples
    # Remove microphone DC bias
    samples = samples - float(np.mean(samples))
    # Gently normalize quiet laptop mic gain without clipping
    peak = float(np.max(np.abs(samples)))
    if 0.005 < peak < 0.75:
        gain = min(0.75 / peak, 8.0)
        samples = np.clip(samples * gain, -1.0, 1.0)
    # Pad 150ms silence on both sides so initial/final consonants aren't clipped
    pad = np.zeros(2400, dtype=np.float32)
    return np.concatenate((pad, samples, pad))


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
            if len(samples) > 1200:
                samples = samples - float(np.mean(samples))
                # Reject ambient room hum/noise cleanly via bundled Silero VAD before running Whisper
                if not has_human_speech(samples):
                    return ""
                samples = _condition_pcm_for_whisper(samples)
                segments, _ = model.transcribe(
                    samples,
                    language="en",
                    beam_size=3,
                    temperature=0.0,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.55,
                    log_prob_threshold=-0.85,
                    hotwords="Jarvis",
                )
                text = " ".join(
                    seg.text.strip()
                    for seg in segments
                    if seg.text and getattr(seg, "no_speech_prob", 0.0) < 0.65
                ).strip()
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
    global _IS_LISTENING, _DUPLEX_STATE, _LAST_BARGE_IN, _BARGE_IN_COUNT, _MIC_ENERGY
    duplex_audio = get_duplex_state()
    thread_alive = bool(_LISTENER_THREAD and _LISTENER_THREAD.is_alive())
    listening_now = bool(_IS_LISTENING and thread_alive)
    current_state = "SPEAKING" if duplex_audio["is_speaking"] else _DUPLEX_STATE
    return {
        "status": "success",
        "is_listening": listening_now,
        "is_speaking": duplex_audio["is_speaking"],
        "speech_energy": duplex_audio.get("speech_energy", 0.0),
        "mic_energy": round(float(_MIC_ENERGY), 4) if listening_now else 0.0,
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
    defaults = ["hey jarvis", "hi jarvis", "hello jarvis", "ok jarvis", "okay jarvis", "jarvis"]
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return [w.strip().lower() for w in cfg.get("wake_words", defaults) if w.strip()]
    except Exception:
        pass
    return defaults


def match_wake_word(transcribed_text: str, wake_words: Optional[list] = None) -> tuple[Optional[str], str]:
    """
    Normalizes punctuation and matches configured wake words anchored near utterance start
    (tolerance: up to 2 leading filler words) so casual mid-sentence words never false-trigger.
    Returns `(matched_word, trailing_command)`.
    """
    import re
    clean_words = re.sub(r"[^\w\s]", " ", (transcribed_text or "").lower())
    clean_words = re.sub(r"\s+", " ", clean_words).strip()
    if not clean_words:
        return None, ""

    candidates = [w.strip().lower() for w in (wake_words or load_wake_words()) if w and w.strip()]
    # Only include phonetic spellings of 'jarvis' if 'jarvis' is actually an active wake word
    if any("jarvis" in w for w in candidates):
        for alias in ("hey jarvis", "jarvis", "jarvus", "jervis", "jarvish"):
            if alias not in candidates:
                candidates.append(alias)
    # Match multi-word wake phrases before single words so 'hey' doesn't linger in command_part
    candidates.sort(key=lambda s: len(s), reverse=True)

    for w in candidates:
        norm_w = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", w.lower())).strip()
        if not norm_w:
            continue
        m = re.search(rf"\b{re.escape(norm_w)}\b", clean_words)
        if m:
            prefix = clean_words[:m.start()].strip()
            # Anchor near utterance start: ignore casual mid-sentence mentions (>2 words before wake word)
            if prefix and len(prefix.split()) > 2:
                continue
            trailing = clean_words[m.end():].strip()
            # Strip repeated wake-word echo (e.g. "hey jarvis, jarvis," -> "")
            echoes = tuple(sorted(set(candidates), key=len, reverse=True))
            changed = True
            while changed and trailing:
                changed = False
                for echo in echoes:
                    norm_e = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", echo)).strip()
                    if norm_e and (trailing == norm_e or trailing.startswith(norm_e + " ")):
                        trailing = trailing[len(norm_e):].strip()
                        changed = True
                        break
            return norm_w, trailing
    return None, ""


def is_valid_barge_in_text(transcribed_text: str, wake_words: Optional[list] = None) -> tuple[bool, str]:
    """
    Guards against acoustic speaker self-echo cutting off Jarvis's own voice:
    Only interrupts active playback on explicit stop directives or addressed wake phrases.
    Returns `(should_interrupt, directive_text)`.
    """
    import re
    clean = re.sub(r"[^\w\s]", " ", (transcribed_text or "").lower())
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return False, ""

    stop_keywords = ("stop", "quiet", "shut up", "pause", "never mind", "cancel", "hold on", "silence", "wait")
    for kw in stop_keywords:
        if clean == kw or clean.startswith(kw + " "):
            return True, clean

    matched_w, trailing = match_wake_word(clean, wake_words=wake_words)
    if matched_w:
        return True, (trailing or clean)

    return False, ""


def listen_for_wake_words(
    on_wake_callback: Optional[Callable[[str], None]] = None,
    stop_event: Optional[threading.Event] = None
):
    """
    Continuous background loop that listens to the default Windows microphone
    for configured wake words with minimal CPU footprint.
    """
    global _IS_LISTENING, _DUPLEX_STATE, _BARGE_IN_COUNT, _LAST_BARGE_IN
    try:
        import speech_recognition as sr
    except ImportError:
        print("[WakeWord]: speech_recognition not installed. Wake-word listener disabled.")
        return

    # Pre-warm local Whisper & Silero VAD cleanly while opening mic so first trigger has zero cold delay
    threading.Thread(target=_get_local_whisper_model, daemon=True).start()
    threading.Thread(target=_get_silero_vad_model, daemon=True).start()

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 160
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.72
    recognizer.non_speaking_duration = 0.45

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"[WakeWord]: Failed to initialize microphone: {e}")
        return

    wake_words = load_wake_words()
    print(f"[WakeWord]: Native OS Background Listener Online. Active Wake Words: {wake_words}")
    _IS_LISTENING = True
    _DUPLEX_STATE = "LISTENING"

    try:
        with mic as source:
            if getattr(source, "stream", None) is not None:
                source.stream = _MeteredAudioStream(source.stream)
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.35)
                recognizer.energy_threshold = min(420.0, max(165.0, float(recognizer.energy_threshold)))
                print(f"[WakeWord]: Mic calibrated (energy_threshold={recognizer.energy_threshold:.1f})")
            except Exception:
                pass

            while stop_event is None or not stop_event.is_set():
                # ================================================================
                # DUPLEX BARGE-IN PROTOCOL:
                # When Jarvis is speaking, monitor ONLY for explicit stop or wake-word
                # commands at elevated threshold so laptop speaker echo never cuts off reply.
                # ================================================================
                if is_speaking():
                    _DUPLEX_STATE = "SPEAKING"
                    saved_thresh = float(recognizer.energy_threshold)
                    saved_dyn = bool(recognizer.dynamic_energy_threshold)
                    try:
                        recognizer.dynamic_energy_threshold = False
                        recognizer.energy_threshold = max(saved_thresh * 2.2, 420.0)
                        barge_audio = recognizer.listen(source, timeout=0.6, phrase_time_limit=2.5)
                        interrupted_text = transcribe_audio_local_or_cloud(recognizer, barge_audio)

                        should_cut, directive = is_valid_barge_in_text(interrupted_text, wake_words)
                        if should_cut:
                            cutoff_ms = stop_speaking()
                            _BARGE_IN_COUNT += 1
                            _LAST_BARGE_IN = {
                                "timestamp": time.time(),
                                "reason": "speech_activity",
                                "cutoff_ms": cutoff_ms
                            }
                            _DUPLEX_STATE = "LISTENING"
                            print(f"[Duplex Barge-In Activated]: Detected verified interruption '{interrupted_text}' ({cutoff_ms:.2f}ms cutoff). Audio halted.")

                            stop_keywords = ["stop", "quiet", "shut up", "pause", "never mind", "cancel", "hold on", "silence", "wait"]
                            is_pure_stop = any(directive == kw or directive.startswith(kw + " ") for kw in stop_keywords)
                            if is_pure_stop or not directive:
                                print(f"[Duplex Barge-In]: User requested silence ('{interrupted_text}'). Standing by.")
                                _DUPLEX_STATE = "LISTENING"
                                continue

                            # User interrupted with an addressed new instruction
                            print(f"[Duplex Barge-In Executing]: Routing new directive: '{directive}'")
                            fast_reply = None
                            try:
                                from backend.core.fast_path_router import try_fast_path_os_dispatch
                                fast_res = try_fast_path_os_dispatch(directive)
                                if fast_res is not None:
                                    fast_reply = fast_res.get("reply")
                            except Exception:
                                pass

                            if fast_reply:
                                _DUPLEX_STATE = "SPEAKING"
                                speak_aloud(fast_reply)
                            else:
                                _DUPLEX_STATE = "THINKING"
                                res = dispatch_jarvis_executive_action(directive)
                                reply = (res or {}).get("reply", "Standing by.")
                                _DUPLEX_STATE = "SPEAKING"
                                speak_aloud(reply)
                        continue
                    except sr.WaitTimeoutError:
                        # Assistant still speaking, user hasn't spoken yet
                        continue
                    except Exception:
                        time.sleep(0.1)
                        continue
                    finally:
                        recognizer.energy_threshold = saved_thresh
                        recognizer.dynamic_energy_threshold = saved_dyn

                # ================================================================
                # STANDALONE WAKE-WORD DETECTION PROTOCOL:
                # ================================================================
                # Prevent dynamic drift from calibrating threshold above normal speaking volume
                recognizer.energy_threshold = min(360.0, max(165.0, float(recognizer.energy_threshold)))
                _DUPLEX_STATE = "LISTENING"
                try:
                    audio = recognizer.listen(source, timeout=2.5, phrase_time_limit=6.0)
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    time.sleep(0.3)
                    continue

                if stop_event is not None and stop_event.is_set():
                    break

                # Transcribe phrase locally/lightweight
                try:
                    text = transcribe_audio_local_or_cloud(recognizer, audio).lower().strip()
                    if not text:
                        continue

                    print(f"[WakeWord Heard]: '{text}'")

                    matched_word, command_part = match_wake_word(text, wake_words)
                    if matched_word:
                        print(f"[WakeWord Detected]: Matched '{matched_word}'! Command: '{command_part}'")
                        _DUPLEX_STATE = "LISTENING"

                        if on_wake_callback:
                            on_wake_callback(command_part)
                        else:
                            handle_wake_activation(command_part, recognizer, source)

                        _DUPLEX_STATE = "LISTENING"

                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    time.sleep(1.0)
                except Exception:
                    time.sleep(0.3)
    finally:
        global _MIC_ENERGY
        _IS_LISTENING = False
        _DUPLEX_STATE = "IDLE"
        _MIC_ENERGY = 0.0
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


def dispatch_complex_background_task(text: str) -> str:
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
            print(f"[WakeWord Replying]: '{reply[:120]}'")
            speak_aloud(reply)
        finally:
            _DUPLEX_STATE = "IDLE"

    if initial_command and len(initial_command) > 2:
        # User spoke the directive in the same breath
        print(f"[WakeWord Processing Direct Command]: '{initial_command}'")
        _execute_directive(initial_command)
        return

    # Acknowledge and prompt user cleanly without clipping
    _DUPLEX_STATE = "SPEAKING"
    speak_aloud("Listening.")
    deadline = time.monotonic() + 2.0
    while is_speaking() and time.monotonic() < deadline:
        time.sleep(0.05)

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
