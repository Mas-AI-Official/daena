"""Neural TTS API -- streams natural voices via Microsoft Edge TTS.

Replaces the browser-native SpeechSynthesis fallback when the frontend
wants real neural voice output without an API key. Edge-TTS rides the
same Microsoft CDN Edge browser uses for its "read aloud" feature; it
is free, requires no authentication, and ships ~300 distinct voices
across 80+ locales.

Key endpoints:

    POST /tts/speak
        Body: {"text": "...", "voice": "en-US-AriaNeural", "rate": "+0%"}
        Returns: audio/mpeg (MP3) stream, ~50-200ms first-byte latency.

    GET /tts/voices
        Returns: JSON list of available voice descriptors, filtered to
        English by default (``locale=en`` param opt-out).

    GET /tts/defaults
        Returns: the recommended default voice for conversational use
        (currently en-US-AriaNeural -- natural, warm, moderate pace).

BACKGROUND PATH OK -- these endpoints do not block the scan hot path.
Edge-TTS opens a WebSocket to edge.microsoft.com per request; the
streaming response is proxied straight to the caller so we never
buffer the full audio in memory.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Recommended defaults
# ---------------------------------------------------------------------------
# Picked by ear for "Jarvis-tier" natural conversation:
#   AriaNeural   -- warm female, moderate pace, great for assistant
#   JennyNeural  -- friendly female, slightly brighter than Aria
#   GuyNeural    -- male, grounded, no artifacts
#   DavisNeural  -- expressive male, tunable with styles
#   EmmaNeural   -- natural female with more emotion range
#
# Use a style-aware voice via the ``style`` param for occasional
# excitement / whispering; defaults to "general".

DEFAULT_VOICE = "en-US-AriaNeural"
RECOMMENDED_VOICES: list[dict[str, str]] = [
    {"short_name": "en-US-AriaNeural",   "gender": "Female", "label": "Aria (warm, balanced)"},
    {"short_name": "en-US-JennyNeural",  "gender": "Female", "label": "Jenny (friendly)"},
    {"short_name": "en-US-EmmaNeural",   "gender": "Female", "label": "Emma (expressive)"},
    {"short_name": "en-US-GuyNeural",    "gender": "Male",   "label": "Guy (grounded)"},
    {"short_name": "en-US-DavisNeural",  "gender": "Male",   "label": "Davis (expressive)"},
    {"short_name": "en-US-BrianNeural",  "gender": "Male",   "label": "Brian (neutral)"},
    {"short_name": "en-GB-SoniaNeural",  "gender": "Female", "label": "Sonia (UK)"},
    {"short_name": "en-GB-RyanNeural",   "gender": "Male",   "label": "Ryan (UK)"},
    {"short_name": "en-AU-NatashaNeural","gender": "Female", "label": "Natasha (AU)"},
]


class TtsRequest(BaseModel):
    """Request body for POST /tts/speak."""
    text: str = Field(..., min_length=1, max_length=8000)
    voice: str = Field(default=DEFAULT_VOICE)
    # Rate / pitch / volume tokens accepted by edge-tts SSML prosody.
    # Examples: "+10%", "-15%", "medium".
    rate: str = Field(default="+0%")
    pitch: str = Field(default="+0Hz")
    volume: str = Field(default="+0%")


@router.get("/defaults", dependencies=[Depends(get_current_user)])
async def tts_defaults() -> dict[str, Any]:
    """Return the recommended default voice + a short shortlist the UI
    can render without fetching the full ~300-voice catalog."""
    return {
        "default": DEFAULT_VOICE,
        "recommended": RECOMMENDED_VOICES,
    }


@router.get("/voices", dependencies=[Depends(get_current_user)])
async def list_voices(
    locale: str = Query(default="en", min_length=0, max_length=12),
) -> list[dict[str, Any]]:
    """Return every voice Edge-TTS knows about. Filtered to locales
    starting with ``locale`` (default: all English). Pass ``locale=`` to
    get everything. Each entry has ``ShortName``, ``Gender``, ``Locale``,
    and a list of supported SSML style tags when available.
    """
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"edge-tts not installed in backend venv: {exc}",
        )

    try:
        voices = await edge_tts.list_voices()
    except Exception as exc:  # noqa: BLE001
        logger.warning("tts.list_voices_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Upstream fetch failed: {exc}")

    prefix = locale.lower()
    out: list[dict[str, Any]] = []
    for v in voices:
        loc = (v.get("Locale") or "").lower()
        if prefix and not loc.startswith(prefix):
            continue
        out.append({
            "short_name": v.get("ShortName", ""),
            "gender": v.get("Gender", ""),
            "locale": v.get("Locale", ""),
            "friendly_name": v.get("FriendlyName", ""),
            "styles": v.get("VoiceTag", {}).get("VoicePersonalities", []) if isinstance(v.get("VoiceTag"), dict) else [],
        })
    return out


@router.post("/speak", dependencies=[Depends(get_current_user)])
async def speak(body: TtsRequest) -> StreamingResponse:
    """Stream neural-voice MP3 audio for ``text`` via Edge-TTS.

    No buffering on our side: we forward Edge-TTS's streamed chunks
    directly to the caller so first-byte latency stays around
    150-300ms on a warm network.

    Returns 502 when Edge-TTS is unreachable (network blocked,
    Microsoft CDN outage); 400 on obviously-bad input so the caller
    can fall back to browser SpeechSynthesis without ambiguity.
    """
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"edge-tts not installed: {exc}",
        )

    # edge-tts rejects some unicode control chars outright; strip them.
    clean = "".join(ch for ch in body.text if ch.isprintable() or ch in "\n\r\t")
    if not clean.strip():
        raise HTTPException(status_code=400, detail="Empty text after sanitization")

    logger.info(
        "tts.speak",
        voice=body.voice, chars=len(clean),
        rate=body.rate, pitch=body.pitch,
    )

    async def _streamer():
        try:
            communicate = edge_tts.Communicate(
                text=clean,
                voice=body.voice,
                rate=body.rate,
                pitch=body.pitch,
                volume=body.volume,
            )
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    yield chunk["data"]
        except Exception as exc:  # noqa: BLE001
            logger.warning("tts.stream_failed", error=str(exc))
            # Cannot raise HTTPException mid-stream; just end the stream.
            # The client will get a truncated MP3 and fall back to
            # browser TTS per its own retry logic.
            return

    return StreamingResponse(
        _streamer(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            # Let the frontend know which voice actually rendered this.
            "X-Daena-TTS-Voice": body.voice,
        },
    )
