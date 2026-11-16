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
    """Updates voice and wake word configuration."""
    cfg = update_voice_config(updates)
    return {"status": "success", "config": cfg}


@router.post("/stop")
def stop_voice_playback():
    """Barge-in endpoint: instantly stops active audio playback on host speakers."""
    stop_speaking()
    return {"status": "success", "message": "Voice playback halted."}


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
