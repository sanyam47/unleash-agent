"""
Voice API Router for Jarvis Voice & Speech Engine.
Endpoints for voice mode switching (Work vs Cinema), speech synthesis, and audio transcription.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from pathlib import Path

from backend.core.voice_pilot import (
    get_voice_mode, set_voice_mode, synthesize_speech,
    speak_aloud, transcribe_speech, load_voice_config,
    update_voice_config, stop_speaking, speak_pipelined_async,
    is_speaking, AVAILABLE_INTERNET_VOICES, AVAILABLE_FALLBACK_VOICES,
    get_installed_sapi_voices, get_custom_local_voices
)

router = APIRouter()


class VoiceModeRequest(BaseModel):
    mode: str = Field(..., description="'work' (low-latency neural) or 'cinema' (deep resonant studio)")


class SpeakRequest(BaseModel):
    text: str = Field(..., description="Text for speech synthesis")
    mode: Optional[str] = Field(default=None, description="Optional override: 'work' or 'cinema'")
    voice: Optional[str] = Field(default=None, description="Optional explicit voice ID, e.g. 'en-US-GuyNeural' or 'none'")
    fallback_voice: Optional[str] = Field(default=None, description="Optional fallback voice ID, e.g. 'male', 'female', 'default', 'none'")
    model: Optional[str] = Field(default=None, description="Optional active model name to resolve baked persona voice")
    play_on_host: bool = Field(default=False, description="Whether to also play directly through host speakers")
    pipelined: bool = Field(default=True, description="Enable sentence-pipelined speech synthesis for sub-second playback")


class TestVoiceRequest(BaseModel):
    voice: Optional[str] = Field("en-US-GuyNeural", description="Voice ID to test or 'none'")
    fallback_voice: Optional[str] = Field("default", description="Fallback voice ID")
    text: Optional[str] = Field("Systems online and calibrated, ready for your directive.", description="Test phrase to synthesize")
    play_on_host: bool = Field(True, description="Play directly through host speakers")


@router.get("/available_voices")
def get_available_voices() -> Dict[str, Any]:
    """Lists available cloud neural voices, local Windows SAPI voices, and downloaded local voice models."""
    return {
        "status": "success",
        "internet_voices": AVAILABLE_INTERNET_VOICES,
        "fallback_voices": AVAILABLE_FALLBACK_VOICES,
        "installed_sapi_voices": get_installed_sapi_voices(),
        "custom_local_voices": get_custom_local_voices()
    }


@router.post("/upload_custom_voice")
async def upload_custom_voice(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Uploads a custom voice model/sample (.onnx, .bin, .pt, .wav, .mp3)
    directly into backend/data/voices/ for local synthesis and offline playback.
    """
    import os
    from backend.core.voice_pilot import VOICES_DIR, get_custom_local_voices

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    safe_name = os.path.basename(file.filename)
    allowed_exts = {".onnx", ".bin", ".pt", ".wav", ".mp3"}
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(allowed_exts))}"
        )

    dest_path = VOICES_DIR / safe_name
    content = await file.read()
    dest_path.write_bytes(content)

    return {
        "status": "success",
        "filename": safe_name,
        "path": str(dest_path),
        "custom_local_voices": get_custom_local_voices()
    }


@router.post("/test_voice")
def test_voice_endpoint(req: TestVoiceRequest) -> Dict[str, Any]:
    """Synthesizes a short test sample to audition a voice."""
    sample_text = req.text or "Systems online and calibrated, ready for your directive."
    if req.play_on_host:
        res = speak_aloud(sample_text, voice=req.voice, fallback_voice=req.fallback_voice)
        audio_p = res.get("audio_path") if isinstance(res, dict) else None
        audio_url = f"/api/voice/audio/{Path(audio_p).name}" if audio_p else None
        return {"status": "success", "result": res, "audio_url": audio_url}

    synth = synthesize_speech(sample_text, voice=req.voice, fallback_voice=req.fallback_voice)
    if not synth.get("success"):
        raise HTTPException(status_code=500, detail=synth.get("error", "Test synthesis failed"))
    audio_p = synth.get("audio_path")
    if audio_p:
        synth["audio_url"] = f"/api/voice/audio/{Path(audio_p).name}"
    synth["status"] = "success"
    return synth


@router.get("/mode")
def get_current_mode() -> Dict[str, Any]:
    """Gets the active voice mode."""
    cfg = load_voice_config()
    mode = cfg.get("mode", "work")
    desc = "⚡ Low-Latency Mode (Fast, responsive neural voice)" if mode == "work" else "🎬 Resonant Studio Mode (Deep timbre acoustic voice)"
    return {
        "status": "success",
        "mode": mode,
        "description": desc,
        "config": cfg
    }


@router.post("/mode")
def update_voice_mode(req: VoiceModeRequest) -> Dict[str, Any]:
    """Switches the active voice mode between 'work' and 'cinema'."""
    res = set_voice_mode(req.mode)
    return res


@router.get("/config")
def get_voice_and_wake_config() -> Dict[str, Any]:
    """Gets the complete voice and wake word configuration."""
    cfg = load_voice_config()
    return {"status": "success", "config": cfg}


@router.post("/config")
def set_voice_and_wake_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Updates voice and wake word configuration and syncs native OS background listener."""
    cfg = update_voice_config(updates)
    if "wake_word_enabled" in updates:
        try:
            from backend.core.wake_word_listener import (
                start_native_wake_word_daemon,
                stop_native_wake_word_daemon
            )
            if updates["wake_word_enabled"]:
                start_native_wake_word_daemon(in_background=True)
            else:
                stop_native_wake_word_daemon()
        except Exception as e:
            print(f"[Voice Router] Sync wake-word daemon notice: {e}")
    return {"status": "success", "config": cfg}


@router.post("/toggle_mic")
def toggle_microphone_endpoint(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Direct unified toggle for microphone listening:
    Controls both host Windows native wake-word listener thread and configuration state.
    """
    from backend.core.wake_word_listener import (
        start_native_wake_word_daemon,
        stop_native_wake_word_daemon,
        get_duplex_listener_status
    )

    req_active = None
    if payload and "active" in payload:
        req_active = bool(payload["active"])

    current_cfg = load_voice_config()
    current_enabled = current_cfg.get("wake_word_enabled", True)
    new_state = req_active if req_active is not None else not current_enabled

    cfg = update_voice_config({"wake_word_enabled": new_state})
    if new_state:
        start_native_wake_word_daemon(in_background=True)
    else:
        stop_native_wake_word_daemon()

    status = get_duplex_listener_status()
    status["wake_word_enabled"] = new_state
    return {
        "status": "success",
        "mic_active": new_state,
        "listener_status": status,
        "message": f"Workstation microphone listening {'activated' if new_state else 'completely deactivated'}."
    }


@router.post("/stop")
def stop_voice_playback():
    """Barge-in endpoint: instantly stops active audio playback on host speakers in <15ms."""
    cutoff_ms = stop_speaking()
    return {
        "status": "success",
        "cutoff_ms": cutoff_ms,
        "message": f"Voice playback halted in {cutoff_ms:.2f}ms."
    }


@router.get("/duplex_status")
def get_duplex_voice_status() -> Dict[str, Any]:
    """Returns complete real-time duplex hands-free voice status, playback state, and barge-in telemetry."""
    try:
        from backend.core.wake_word_listener import get_duplex_listener_status
        return get_duplex_listener_status()
    except Exception as e:
        from backend.core.voice_pilot import get_duplex_state
        return {
            "status": "success",
            "audio": get_duplex_state(),
            "detail": str(e)
        }


@router.post("/barge_in")
def trigger_duplex_barge_in(reason: Optional[str] = "api_request") -> Dict[str, Any]:
    """Trigger real-time speech barge-in via API (halts audio in <15ms and shifts to listening)."""
    try:
        from backend.core.wake_word_listener import trigger_manual_barge_in
        return trigger_manual_barge_in(reason=reason or "api_request")
    except Exception:
        cutoff_ms = stop_speaking()
        return {
            "status": "success",
            "cutoff_ms": cutoff_ms,
            "message": f"Barge-in triggered; audio stopped in {cutoff_ms:.2f}ms."
        }


@router.get("/status")
def get_voice_playback_status() -> Dict[str, Any]:
    """Returns active speech and audio queue state for duplex coordination."""
    return {
        "status": "success",
        "is_speaking": is_speaking()
    }


@router.post("/speak")
def generate_speech(req: SpeakRequest):
    """Synthesizes speech and returns the audio file (or plays through speakers)."""
    if req.play_on_host:
        if req.pipelined:
            speak_pipelined_async(req.text, mode=req.mode, voice=req.voice, fallback_voice=req.fallback_voice, model=req.model)
            return {"status": "success", "pipelined": True}
        res = speak_aloud(req.text, mode=req.mode, voice=req.voice, fallback_voice=req.fallback_voice, model=req.model)
        return res

    synth = synthesize_speech(req.text, mode=req.mode, voice=req.voice, fallback_voice=req.fallback_voice, model=req.model)
    if not synth.get("success"):
        raise HTTPException(status_code=500, detail=synth.get("error", "Speech synthesis failed"))

    media_type = "audio/mpeg" if synth.get("format") == "mp3" else "audio/wav"
    return FileResponse(
        path=synth["audio_path"],
        media_type=media_type,
        filename=f"jarvis_speech.{synth.get('format', 'mp3')}"
    )


@router.post("/transcribe")
async def transcribe_audio_file(file: UploadFile = File(...)):
    """Transcribes an uploaded microphone audio recording into text."""
    audio_bytes = await file.read()
    mime = file.content_type or "audio/mp3"
    res = transcribe_speech(audio_bytes, mime_type=mime)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Transcription failed"))
    return res
