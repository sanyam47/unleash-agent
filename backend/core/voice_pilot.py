"""
Voice Pilot - Multi-Tier Voice & Speech Engine.

Enables:
1. Flexible synthesis modes:
   - "work": Low-latency Neural Mode (instant, responsive edge neural synthesis).
   - "cinema": Resonant Studio Mode (deep, high-dynamic-range acoustic profile).
   - Offline fallback: If internet is down or disabled, automatically uses native Windows SAPI.
2. Direct speaker playback via Windows native winmm.dll (mciSendStringW).
3. Speech-to-Text transcription via multi-modal AI / local Whisper.
4. Persistent configuration saved in backend/data/voice_profiles/voice_config.json.
"""

import os
import sys
import time
import json
import asyncio
import ctypes
import queue
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Paths (Absolute resolution to prevent C:\coding pollution)
BASE_DIR = Path(__file__).resolve().parent.parent
VOICE_DIR = BASE_DIR / "data" / "voice_profiles"
VOICE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = VOICE_DIR / "voice_config.json"
AUDIO_CACHE_DIR = VOICE_DIR / "cache"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Phase 7: Serialized Speech Queue (Ensures two Jarvis voices never talk over each other)
_SPEECH_QUEUE = queue.Queue()
_SPEECH_WORKER_STARTED = False
_SPEECH_LOCK = threading.RLock()
_STOP_REQUESTED = threading.Event()
_IS_SPEAKING = False


def is_speaking() -> bool:
    """Returns True if Jarvis is currently outputting audio via system speakers."""
    global _IS_SPEAKING
    return _IS_SPEAKING or not _SPEECH_QUEUE.empty()


def _speech_queue_worker():
    """Background worker that serializes voice utterances politely without overlapping audio."""
    global _IS_SPEAKING
    winmm = ctypes.windll.winmm
    while True:
        try:
            item = _SPEECH_QUEUE.get()
            if item is None:
                break
            if _STOP_REQUESTED.is_set():
                _SPEECH_QUEUE.task_done()
                continue

            _IS_SPEAKING = True
            audio_path = item.get("audio_path")
            if audio_path and os.path.exists(audio_path):
                abs_path = os.path.abspath(audio_path)
                alias = f"jarvis_{int(time.time() * 1000)}"
                file_type = "mpegvideo" if abs_path.lower().endswith(".mp3") else "waveaudio"
                winmm.mciSendStringW(f'open "{abs_path}" type {file_type} alias {alias}', None, 0, None)
                # Play with 'wait' so it completes before starting the next queued audio
                winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
                winmm.mciSendStringW(f"close {alias}", None, 0, None)
                time.sleep(0.12)  # Natural conversational spacing
            _SPEECH_QUEUE.task_done()
            if _SPEECH_QUEUE.empty():
                _IS_SPEAKING = False
        except Exception as e:
            _IS_SPEAKING = False
            print(f"[Voice Pilot] Queue playback notice: {e}")


def _ensure_speech_worker():
    global _SPEECH_WORKER_STARTED
    with _SPEECH_LOCK:
        if not _SPEECH_WORKER_STARTED:
            t = threading.Thread(target=_speech_queue_worker, daemon=True)
            t.start()
            _SPEECH_WORKER_STARTED = True

VOICES_DIR = VOICE_DIR.parent / "voices"
VOICES_DIR.mkdir(parents=True, exist_ok=True)

AVAILABLE_INTERNET_VOICES = [
    {"id": "en-US-GuyNeural", "name": "🇺🇸 US English - Male (Guy Neural) — Recommended Default", "gender": "male", "lang": "en-US"},
    {"id": "en-US-JennyNeural", "name": "🇺🇸 US English - Female (Jenny Neural)", "gender": "female", "lang": "en-US"},
    {"id": "en-GB-RyanNeural", "name": "🇬🇧 British English - Male (Ryan Neural)", "gender": "male", "lang": "en-GB"},
    {"id": "en-IE-EmilyNeural", "name": "🇮🇪 Irish English - Female (Emily Neural)", "gender": "female", "lang": "en-IE"},
    {"id": "en-AU-WilliamNeural", "name": "🇦🇺 Australian English - Male (William Neural)", "gender": "male", "lang": "en-AU"},
    {"id": "en-US-BrianNeural", "name": "🇺🇸 US English - Authoritative Male (Brian Neural)", "gender": "male", "lang": "en-US"},
    {"id": "en-IN-PrabhatNeural", "name": "🇮🇳 Indian English - Male (Prabhat Neural)", "gender": "male", "lang": "en-IN"},
    {"id": "none", "name": "🚫 None / Null (Pure Offline Mode — No Internet Audio)", "gender": "none", "lang": "offline"}
]

AVAILABLE_FALLBACK_VOICES = [
    {"id": "default", "name": "💻 Windows Default Local System Voice"},
    {"id": "male", "name": "💻 Windows SAPI Male (Microsoft David)"},
    {"id": "female", "name": "💻 Windows SAPI Female (Microsoft Zira)"},
    {"id": "none", "name": "🚫 None (Silent when offline / network drops)"}
]

DEFAULT_CONFIG = {
    "mode": "work",  # "work" (fast) or "cinema" (authoritative profile)
    "work_voice": "en-US-GuyNeural",
    "work_pitch": "-0Hz",
    "work_rate": "+0%",
    "cinema_voice": "en-US-BrianNeural",
    "cinema_pitch": "-3Hz",
    "cinema_rate": "-2%",
    "default_internet_voice": "en-US-GuyNeural",
    "default_fallback_voice": "default",
    "auto_speak_replies": True,
    "wake_word_enabled": True,
    "wake_words": ["assistant", "hey assistant"],
    "wake_sound": True,
    "auto_submit_speech": True
}


def get_installed_sapi_voices() -> List[Dict[str, str]]:
    """Scans and returns all offline Windows SAPI voices installed on this PC."""
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        voices = speaker.GetVoices()
        res = []
        for i in range(voices.Count):
            desc = voices.Item(i).GetDescription()
            res.append({"id": f"sapi_{i}", "name": desc, "description": desc})
        return res
    except Exception:
        return []


def get_custom_local_voices() -> List[Dict[str, str]]:
    """Scans backend/data/voices/ for any downloaded .onnx or custom voice model files."""
    custom = []
    if VOICES_DIR.exists():
        for f in VOICES_DIR.glob("*.*"):
            if f.suffix.lower() in (".onnx", ".bin", ".pt", ".wav", ".mp3") and not f.name.startswith("README"):
                custom.append({
                    "id": f.name,
                    "name": f"📁 Local Model: {f.name}",
                    "path": str(f.resolve())
                })
    return custom


def get_model_voice_profile(model_name: Optional[str] = None) -> Tuple[str, str]:
    """
    Resolves the internet voice and fallback voice for a given model:
    1. If model has a baked persona config in backend/data/personas/<model>/persona_config.json, use it.
    2. If model name suggests Jarvis/cyber-specialist, default to Ryan British.
    3. Otherwise, use global default_internet_voice and default_fallback_voice.
    """
    cfg = load_voice_config()
    def_internet = cfg.get("default_internet_voice", "en-US-GuyNeural")
    def_fallback = cfg.get("default_fallback_voice", "default")

    if not model_name:
        return def_internet, def_fallback

    clean_model = model_name.lower().split(":")[0].strip()

    # Check baked personas directory
    personas_dir = BASE_DIR / "data" / "personas"
    if personas_dir.exists():
        # Try direct or normalized directory
        for p_dir in personas_dir.iterdir():
            if p_dir.is_dir() and (p_dir.name.lower() == clean_model or clean_model.startswith(p_dir.name.lower())):
                p_cfg_file = p_dir / "persona_config.json"
                if p_cfg_file.exists():
                    try:
                        p_data = json.loads(p_cfg_file.read_text(encoding="utf-8"))
                        i_v = p_data.get("internet_voice")
                        f_v = p_data.get("fallback_voice")
                        return (i_v if i_v is not None else def_internet), (f_v or def_fallback)
                    except Exception:
                        pass

    return def_internet, def_fallback


def load_voice_config() -> Dict[str, Any]:
    """Loads voice configuration or creates default."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    save_voice_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def get_voice_config() -> Dict[str, Any]:
    """Alias for load_voice_config to support backwards compatibility."""
    return load_voice_config()


def save_voice_config(config: Dict[str, Any]):
    """Saves voice configuration to disk."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Voice Pilot] Failed to save config: {e}")


def update_voice_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates arbitrary voice and wake word configuration settings."""
    cfg = load_voice_config()
    cfg.update(updates)
    save_voice_config(cfg)
    return cfg


def get_voice_mode() -> str:
    """Returns the current voice mode ('work' or 'cinema')."""
    return load_voice_config().get("mode", "work")


def set_voice_mode(mode: str) -> Dict[str, Any]:
    """Switches between 'work' and 'cinema' mode."""
    clean_mode = str(mode).strip().lower()
    if clean_mode not in ("work", "cinema"):
        if any(w in clean_mode for w in ("movie", "bettany", "film")):
            clean_mode = "cinema"
        else:
            clean_mode = "work"

    cfg = load_voice_config()
    cfg["mode"] = clean_mode
    save_voice_config(cfg)

    desc = "⚡ Low-Latency Mode (Fast Neural)" if clean_mode == "work" else "🎬 Resonant Studio Mode (Deep Dynamic Range)"
    return {
        "success": True,
        "mode": clean_mode,
        "description": desc,
        "message": f"Voice mode set to {desc}"
    }


def _synthesize_edge_tts_sync(text: str, voice: str, pitch: str = "+0Hz", rate: str = "+0%", output_file: str = "", timeout_sec: float = 6.5) -> bool:
    """Synthesizes speech using edge-tts synchronously with network timeout."""
    try:
        import edge_tts

        async def _run():
            comm = edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
            await asyncio.wait_for(comm.save(output_file), timeout=timeout_sec)

        asyncio.run(_run())
        return os.path.exists(output_file) and os.path.getsize(output_file) > 100
    except Exception as e:
        print(f"[Voice Pilot] edge-tts error (or timeout): {e}")
        return False


def _synthesize_sapi_fallback(text: str, output_wav: str, voice_hint: str = "default") -> bool:
    """Offline fallback: Windows SAPI5 supporting male, female, default, or none."""
    hint = str(voice_hint or "default").strip().lower()
    if hint in ("none", "null", "false"):
        return False

    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        voices = speaker.GetVoices()
        chosen = None

        if hint == "female":
            for i in range(voices.Count):
                desc = voices.Item(i).GetDescription()
                if any(f in desc for f in ("Zira", "Hazel", "Female", "Eva")):
                    chosen = voices.Item(i)
                    break
        elif hint in ("male", "work", "cinema"):
            for i in range(voices.Count):
                desc = voices.Item(i).GetDescription()
                if any(m in desc for m in ("David", "George", "Mark", "Male", "Guy")):
                    chosen = voices.Item(i)
                    break

        if chosen:
            speaker.Voice = chosen

        # Save to WAV file
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(output_wav, 3, False)  # 3 = SSFMCreateForWrite
        speaker.AudioOutputStream = stream
        speaker.Speak(text)
        stream.Close()
        return os.path.exists(output_wav) and os.path.getsize(output_wav) > 100
    except Exception as e:
        print(f"[Voice Pilot] SAPI fallback error: {e}")
        return False


def clean_phonetics_for_speech(text: str) -> str:
    """
    Normalizes technical terms and punctuation for natural British TTS delivery:
    - Replaces 'RAM' / 'R.A.M.' with 'ram' so TTS doesn't spell it out as letters 'R - A - M'.
    - Replaces underscores in identifiers (e.g. language_server -> language server, python_language -> python language)
      so TTS never reads out the literal word 'underscore'.
    - Cleans markdown symbols and bullet points.
    """
    import re
    s = str(text or "").strip()
    if not s:
        return ""
    # 1. RAM pronunciation: 'ram' instead of 'R.A.M.' or spelled out
    s = re.sub(r'\bR\.?\s*A\.?\s*M\.?', 'ram', s)
    # 2. Underscores in process/code names (language_server -> language server)
    s = re.sub(r'([a-zA-Z0-9])_([a-zA-Z0-9])', r'\1 \2', s)
    # 3. Strip code blocks and markdown markers
    s = re.sub(r'```[\s\S]*?```', '', s)
    s = re.sub(r'[*#`_~]', '', s)
    # 4. Clean extra spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def synthesize_with_piper(text: str, output_path: str, model_filename: Optional[str] = "jarvis-medium.onnx") -> bool:
    """Synthesizes speech using local Piper ONNX model without any external piper.exe binary."""
    try:
        import wave
        import piper

        model_candidates = [
            VOICES_DIR / (model_filename or "jarvis-medium.onnx"),
            Path.home() / "Downloads" / (model_filename or "jarvis-medium.onnx")
        ]
        target_model = None
        for cand in model_candidates:
            if cand.exists():
                target_model = cand
                break

        if not target_model:
            print(f"[Voice Pilot] Piper model '{model_filename}' not found in voices dir or Downloads.")
            return False

        config_path = str(target_model) + ".json"
        if not os.path.exists(config_path):
            config_path = str(target_model.with_suffix(".onnx.json"))

        voice = piper.PiperVoice.load(str(target_model), config_path=config_path if os.path.exists(config_path) else None)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with wave.open(output_path, "wb") as wf:
            voice.synthesize_wav(text, wf)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 100
    except Exception as e:
        print(f"[Voice Pilot] Piper ONNX synthesis exception: {e}")
        return False


def synthesize_speech(
    text: str,
    mode: Optional[str] = None,
    voice: Optional[str] = None,
    fallback_voice: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synthesizes speech for the given text.
    Handles 'work' (instant) and 'cinema' (movie clone profile) with smart fallback and persistent MD5 cache.
    Supports per-model custom voice bindings and pure offline mode (voice='none').
    """
    clean_text = clean_phonetics_for_speech(text)
    if not clean_text:
        return {"success": False, "error": "No text provided to synthesize."}

    cfg = load_voice_config()
    active_mode = (mode or cfg.get("mode", "work")).lower().strip()
    if active_mode not in ("work", "cinema"):
        active_mode = "work"

    # Resolve target voice and fallback:
    # 1. Explicit arguments
    # 2. Per-model persona profile (if model provided)
    # 3. Global config defaults
    model_internet_v, model_fallback_v = get_model_voice_profile(model)
    target_voice = voice if voice is not None else model_internet_v
    target_fallback = fallback_voice if fallback_voice is not None else model_fallback_v

    import hashlib
    cache_key = hashlib.md5(f"{clean_text}_{active_mode}_{target_voice}_{target_fallback}".encode("utf-8")).hexdigest()
    out_mp3 = str(AUDIO_CACHE_DIR / f"speech_{cache_key}.mp3")
    out_wav = str(AUDIO_CACHE_DIR / f"speech_{cache_key}.wav")

    # Instant hit on previously cached speech
    if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 100:
        return {
            "success": True,
            "audio_path": out_mp3,
            "mode": active_mode,
            "voice": target_voice,
            "cached": True,
            "format": "mp3"
        }
    if os.path.exists(out_wav) and os.path.getsize(out_wav) > 100:
        return {
            "success": True,
            "audio_path": out_wav,
            "mode": active_mode,
            "voice": f"Windows SAPI ({target_fallback})",
            "cached": True,
            "format": "wav"
        }

    # Case 0: Target voice is a custom Piper ONNX model or requested locally
    if target_voice and (str(target_voice).endswith(".onnx") or "jarvis-medium" in str(target_voice)):
        piper_ok = synthesize_with_piper(clean_text, out_wav, model_filename=str(target_voice))
        if piper_ok:
            return {
                "success": True,
                "audio_path": out_wav,
                "mode": active_mode,
                "voice": f"Piper ONNX ({target_voice})",
                "format": "wav"
            }

    # Case 1: Internet voice is explicitly None / Null / Offline-only or Fallback is Piper ONNX
    if str(target_voice).lower() in ("none", "null", "offline", "") or "jarvis-medium" in str(target_fallback):
        if str(target_fallback).endswith(".onnx") or "jarvis-medium" in str(target_fallback):
            piper_ok = synthesize_with_piper(clean_text, out_wav, model_filename=str(target_fallback))
            if piper_ok:
                return {
                    "success": True,
                    "audio_path": out_wav,
                    "mode": active_mode,
                    "voice": f"Piper ONNX Offline ({target_fallback})",
                    "format": "wav",
                    "offline": True
                }

        if str(target_fallback).lower() in ("none", "null"):
            return {"success": False, "error": "Both internet voice and offline fallback are disabled."}
        sapi_ok = _synthesize_sapi_fallback(clean_text, out_wav, voice_hint=target_fallback)
        if sapi_ok:
            return {
                "success": True,
                "audio_path": out_wav,
                "mode": active_mode,
                "voice": f"Windows SAPI Offline ({target_fallback})",
                "format": "wav",
                "offline": True
            }
        return {"success": False, "error": "Offline SAPI speech synthesis failed."}

    # Case 2: Neural Internet Voice with Offline Fallback
    pitch = cfg.get(f"{active_mode}_pitch", "-2Hz" if active_mode == "work" else "-5Hz")
    rate = cfg.get(f"{active_mode}_rate", "+0%" if active_mode == "work" else "-2%")
    success = _synthesize_edge_tts_sync(clean_text, target_voice, pitch=pitch, rate=rate, output_file=out_mp3)

    if not success:
        # Fallback to local offline Windows SAPI
        if str(target_fallback).lower() not in ("none", "null"):
            print(f"[Voice Pilot] Neural stream failed, falling back to SAPI ({target_fallback})...")
            sapi_ok = _synthesize_sapi_fallback(clean_text, out_wav, voice_hint=target_fallback)
            if sapi_ok:
                return {
                    "success": True,
                    "audio_path": out_wav,
                    "mode": active_mode,
                    "voice": f"Windows SAPI Fallback ({target_fallback})",
                    "fallback": True,
                    "format": "wav"
                }

    if success:
        return {
            "success": True,
            "audio_path": out_mp3,
            "mode": active_mode,
            "voice": target_voice,
            "fallback": False,
            "format": "mp3"
        }

    return {"success": False, "error": "Speech synthesis failed across both cloud neural and local offline engines."}


def play_audio_file(audio_path: str, serialize: bool = True) -> Dict[str, Any]:
    """Plays an audio file directly through the system speakers with serial queue support."""
    global _IS_SPEAKING
    if not os.path.exists(audio_path):
        return {"success": False, "error": f"Audio file not found: {audio_path}"}

    abs_path = os.path.abspath(audio_path)
    if serialize:
        _IS_SPEAKING = True
        _ensure_speech_worker()
        _SPEECH_QUEUE.put({"audio_path": abs_path})
        return {
            "success": True,
            "audio_path": abs_path,
            "message": f"Queued audio via serialized speaker queue ({os.path.basename(abs_path)})"
        }

    alias = f"jarvis_{int(time.time() * 1000)}"
    winmm = ctypes.windll.winmm
    file_type = "mpegvideo" if abs_path.lower().endswith(".mp3") else "waveaudio"
    res_open = winmm.mciSendStringW(f'open "{abs_path}" type {file_type} alias {alias}', None, 0, None)
    if res_open != 0:
        return {"success": False, "error": f"Failed to open audio: winmm code {res_open}"}

    _IS_SPEAKING = True
    res_play = winmm.mciSendStringW(f"play {alias}", None, 0, None)
    return {
        "success": res_play == 0,
        "audio_path": abs_path,
        "message": f"Playing audio via system speakers ({os.path.basename(abs_path)})"
    }


def split_sentences_for_pipeline(text: str) -> list:
    """Splits response text into natural conversational sentence chunks for progressive voice streaming."""
    import re
    clean = re.sub(r'```[\s\S]*?```', ' [code omitted] ', text or '')
    clean = re.sub(r'[*_#`]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    parts = re.split(r'(?<=[.!?])\s+', clean)
    sentences = [p.strip() for p in parts if len(p.strip()) > 2]
    return sentences if sentences else [clean] if clean else []


_LAST_CUTOFF_MS: float = 0.0


def get_duplex_state() -> Dict[str, Any]:
    """Returns real-time duplex voice playback & barge-in readiness state."""
    return {
        "is_speaking": is_speaking(),
        "last_cutoff_ms": _LAST_CUTOFF_MS,
        "barge_in_ready": True,
    }


def stop_speaking() -> float:
    """Immediately stops all active audio playback and flushes the queue (Duplex Barge-in)."""
    global _IS_SPEAKING, _LAST_CUTOFF_MS
    t0 = time.perf_counter()
    _STOP_REQUESTED.set()
    _IS_SPEAKING = False
    if os.name == "nt":
        try:
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW("close all", None, 0, None)
        except Exception:
            pass
    with _SPEECH_LOCK:
        while not _SPEECH_QUEUE.empty():
            try:
                _SPEECH_QUEUE.get_nowait()
                _SPEECH_QUEUE.task_done()
            except Exception:
                break
    threading.Timer(0.3, _STOP_REQUESTED.clear).start()
    cutoff_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    _LAST_CUTOFF_MS = cutoff_ms
    return cutoff_ms


def speak_pipelined_async(
    text: str,
    mode: Optional[str] = None,
    voice: Optional[str] = None,
    fallback_voice: Optional[str] = None,
    model: Optional[str] = None
):
    """
    Seamless full-utterance voice synthesis with fast fallback:
    Generates single unified audio track and queues for playback.
    """
    global _IS_SPEAKING
    clean_text = str(text or "").strip()
    if not clean_text:
        return

    _IS_SPEAKING = True

    def _worker():
        global _IS_SPEAKING
        try:
            res = synthesize_speech(clean_text, mode=mode, voice=voice, fallback_voice=fallback_voice, model=model)
            if res.get("success") and res.get("audio_path"):
                play_audio_file(res["audio_path"], serialize=True)
            else:
                _IS_SPEAKING = False
        except Exception as e:
            print(f"[Speech Generation Error]: {e}")
            _IS_SPEAKING = False

    threading.Thread(target=_worker, daemon=True).start()


def speak_aloud(
    text: str,
    mode: Optional[str] = None,
    voice: Optional[str] = None,
    fallback_voice: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """Synthesizes speech and immediately plays it through the user's speakers."""
    synth = synthesize_speech(text, mode=mode, voice=voice, fallback_voice=fallback_voice, model=model)
    if not synth.get("success"):
        return synth

    audio_path = synth["audio_path"]
    play_res = play_audio_file(audio_path)
    return {
        "success": play_res.get("success", False),
        "text": text,
        "mode": synth.get("mode"),
        "voice": synth.get("voice"),
        "fallback": synth.get("fallback", False),
        "audio_path": audio_path,
        "message": f"Spoke aloud: '{text[:60]}...'" if len(text) > 60 else f"Spoke aloud: '{text}'"
    }


def transcribe_speech(audio_bytes: bytes, mime_type: str = "audio/mp3") -> Dict[str, Any]:
    """Transcribes user voice audio into text using multi-modal AI."""
    if not audio_bytes or len(audio_bytes) < 100:
        return {"success": False, "error": "Audio recording was empty or too short."}

    # Tier 1: Fast Gemini Multi-Modal Speech Recognition
    try:
        from backend.core.gemini_client import gemini_available, _get_client
        if gemini_available():
            client = _get_client()
            from google.genai import types
            part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            models = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.0-flash"]
            for m in models:
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents=[part, "Transcribe this audio recording verbatim. Output ONLY the transcribed words with zero commentary."]
                    )
                    txt = (resp.text or "").strip()
                    if txt:
                        return {"success": True, "text": txt, "engine": f"Cloud Gemini ({m})"}
                except Exception:
                    continue
    except Exception as e:
        pass

    return {"success": False, "error": "Speech transcription was unavailable."}
