"""Neural TTS API -- F5-TTS local voice clone first, Edge-TTS fallback.

Provider chain (Daena house default; overridable per request via ``provider``):
  1. F5-TTS local  -- voice-cloned neural TTS from the F5-TTS microservice that
     runs in its OWN venv, reached over HTTP at $F5_TTS_URL (default
     http://127.0.0.1:9101). Best quality + Daena's cloned voice, but heavier
     latency (GPU ~10-30s, CPU slower) and only available while that service runs.
  2. Edge-TTS      -- Microsoft neural voices, in-process, ~150-300ms, no key,
     no clone. Reliable fallback. Always tried when F5 is unavailable in "auto".
  3. ElevenLabs    -- CLIENT-SIDE only (VoiceProvider, needs a key).
  4. Browser       -- CLIENT-SIDE speechSynthesis, always-available last resort.

The backend serves stages 1-2 ("auto" = F5 then Edge). Stages 3-4 are the
frontend's job: when /tts/speak returns a non-2xx, VoiceProvider falls through
to ElevenLabs then the browser synth. So the full four-stage chain is preserved
end-to-end without the backend ever pretending it can do ElevenLabs/browser.

Endpoints (ALL require auth; /tts/speak + /tts/voices are rate-limited via
app/middleware/rate_limit.py):

    POST /tts/speak
        Body: {"text": "...", "provider": "auto|f5|edge", "voice": "...", "speed": 1.0}
        Returns: audio/mpeg. Response header X-Daena-TTS-Provider names what
        actually rendered ("f5" or "edge") so the UI never fakes the source.
    GET /tts/voices      -- Edge voice catalog (English by default).
    GET /tts/defaults    -- default Edge voice + HONEST provider availability
                            (probes the live F5 service so the UI never shows a
                            fake "F5 ready" badge).

F5-TTS service HTTP contract (contentops-core/services/f5_tts/server.py, separate
repo + venv; Daena only talks to it over HTTP, never imports it):
    POST {F5_TTS_URL}/synthesize {"text","reference_wav"?,"ref_text"?,"speed"?}
        -> 200 audio/mpeg | 400/500 {"error": "..."}
    GET  {F5_TTS_URL}/health
        -> {model, model_loaded, cuda_available, device,
            default_reference, default_reference_exists, ...}

BACKGROUND PATH OK -- these endpoints never block the scan hot path.
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# F5-TTS bridge config (env-wrapped; NO hardcoded personal paths)
# ---------------------------------------------------------------------------
# The F5-TTS voice-clone microservice runs in its own venv and is reached over
# HTTP. Default to localhost:9101 (the service's own default port). The clone
# REFERENCE wav is the F5 service's concern (its $F5_VOICE_REF); Daena only
# overrides it when F5_TTS_REFERENCE_WAV is explicitly set in the environment,
# so no personal path is ever baked into Daena's source.


def _f5_base_url() -> str:
    """Base URL of the F5-TTS microservice (env F5_TTS_URL, default :9101)."""
    return os.environ.get("F5_TTS_URL", "http://127.0.0.1:9101").rstrip("/")


def _f5_reference_wav() -> str | None:
    """Optional clone-reference override. Unset -> let the F5 service use its
    own $F5_VOICE_REF default (keeps Daena free of hardcoded wav paths)."""
    ref = os.environ.get("F5_TTS_REFERENCE_WAV", "").strip()
    return ref or None


# Health probe stays short so a down/absent F5 service fails fast to Edge.
# Synthesis is long because F5 on CPU can take tens of seconds for long text.
F5_PROBE_TIMEOUT_S = float(os.environ.get("F5_TTS_PROBE_TIMEOUT_S", "2.0"))
F5_SYNTH_TIMEOUT_S = float(os.environ.get("F5_TTS_TIMEOUT_S", "120"))


# ---------------------------------------------------------------------------
# Edge recommended defaults (unchanged)
# ---------------------------------------------------------------------------
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

Provider = Literal["auto", "f5", "edge", "elevenlabs", "browser"]


class TtsRequest(BaseModel):
    """Request body for POST /tts/speak."""
    text: str = Field(..., min_length=1, max_length=8000)
    # Provider preference. "auto" (default) = F5-TTS then Edge-TTS.
    provider: Provider = Field(default="auto")
    # Edge-TTS voice + SSML prosody (ignored by F5).
    voice: str = Field(default=DEFAULT_VOICE)
    rate: str = Field(default="+0%")
    pitch: str = Field(default="+0Hz")
    volume: str = Field(default="+0%")
    # F5-TTS speech speed (ignored by Edge).
    speed: float = Field(default=1.0, ge=0.5, le=1.5)


# ---------------------------------------------------------------------------
# F5-TTS HTTP helpers (monkeypatchable in tests)
# ---------------------------------------------------------------------------


async def _f5_probe() -> dict[str, Any]:
    """GET the F5 service /health. Returns {available, reason, health}.

    Never raises: a down/absent service resolves to available=False with a
    human-readable reason so callers can fall back without a stack trace.
    """
    base = _f5_base_url()
    try:
        async with httpx.AsyncClient(timeout=F5_PROBE_TIMEOUT_S) as client:
            r = await client.get(f"{base}/health")
        if r.status_code != 200:
            return {"available": False, "reason": f"health HTTP {r.status_code}", "health": None}
        return {"available": True, "reason": "ok", "health": r.json()}
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "reason": f"service unreachable at {base} ({type(exc).__name__})",
            "health": None,
        }


async def _f5_synthesize(text: str, speed: float) -> bytes | None:
    """POST the F5 service /synthesize. Returns MP3 bytes, or None on any
    failure (logged, never raised, never leaks a trace to the caller)."""
    base = _f5_base_url()
    payload: dict[str, Any] = {"text": text, "speed": speed}
    ref = _f5_reference_wav()
    if ref:
        payload["reference_wav"] = ref
    try:
        async with httpx.AsyncClient(timeout=F5_SYNTH_TIMEOUT_S) as client:
            r = await client.post(f"{base}/synthesize", json=payload)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.startswith("audio"):
            data = r.content
            if data and len(data) > 100:
                return data
            logger.warning("tts.f5_empty_audio", bytes=(len(data) if data else 0))
            return None
        logger.warning("tts.f5_synth_failed", status=r.status_code, ctype=ctype)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("tts.f5_synth_error", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Edge-TTS helpers (extracted so the audio path is monkeypatchable in tests)
# ---------------------------------------------------------------------------


def _edge_available() -> bool:
    """True iff edge-tts is importable in the backend venv."""
    try:
        import edge_tts  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


async def _edge_stream_iter(text: str, voice: str, rate: str, pitch: str, volume: str):
    """Yield Edge-TTS MP3 chunks. An upstream failure mid-stream ends the
    stream quietly (client falls back); it never leaks a trace to the caller."""
    try:
        import edge_tts  # type: ignore

        communicate = edge_tts.Communicate(
            text=text, voice=voice, rate=rate, pitch=pitch, volume=volume,
        )
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                yield chunk["data"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("tts.edge_stream_failed", error=str(exc))
        return


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/defaults", dependencies=[Depends(get_current_user)])
async def tts_defaults() -> dict[str, Any]:
    """Recommended Edge voice + HONEST, live provider availability.

    Probes the F5 service so the frontend can show the real active provider and
    a truthful reason when F5 is unavailable (never a fake "F5 ready" badge).
    """
    probe = await _f5_probe()
    edge_ok = _edge_available()
    health = probe.get("health") or {}

    if probe["available"]:
        active = "f5"
    elif edge_ok:
        active = "edge"
    else:
        active = "none"

    return {
        "default": DEFAULT_VOICE,
        "recommended": RECOMMENDED_VOICES,
        "tts": {
            "preferred_provider": "f5",
            "default_provider": "auto",
            "fallback_chain": ["f5", "edge", "elevenlabs", "browser"],
            "active_provider": active,
            "providers": {
                "f5": {
                    "available": probe["available"],
                    "reason": probe["reason"],
                    "url": _f5_base_url(),
                    "device": health.get("device"),
                    "model_loaded": health.get("model_loaded"),
                    "reference_exists": health.get("default_reference_exists"),
                },
                "edge": {
                    "available": edge_ok,
                    "reason": "edge-tts importable" if edge_ok
                    else "edge-tts not installed in backend venv",
                },
                "elevenlabs": {
                    "available": None,
                    "reason": "client-side (VoiceProvider, needs daena:elevenlabs_key)",
                },
                "browser": {
                    "available": None,
                    "reason": "client-side speechSynthesis fallback",
                },
            },
        },
    }


@router.get("/voices", dependencies=[Depends(get_current_user)])
async def list_voices(
    locale: str = Query(default="en", min_length=0, max_length=12),
) -> list[dict[str, Any]]:
    """Return every Edge-TTS voice, filtered to locales starting with ``locale``
    (default: all English). Pass ``locale=`` for everything."""
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
            "styles": v.get("VoiceTag", {}).get("VoicePersonalities", [])
            if isinstance(v.get("VoiceTag"), dict) else [],
        })
    return out


@router.post("/speak", dependencies=[Depends(get_current_user)])
async def speak(body: TtsRequest) -> Response:
    """Synthesize speech for ``text`` using the provider chain.

    "auto" (default): F5-TTS local voice clone first, then Edge-TTS. "f5" or
    "edge" force a single provider. ElevenLabs/browser are client-side and are
    rejected here with a clear message. The X-Daena-TTS-Provider response header
    names what actually rendered. Failures are logged and degrade gracefully;
    stack traces are never returned to the caller.
    """
    # edge-tts rejects some unicode control chars; strip them up front.
    clean = "".join(ch for ch in body.text if ch.isprintable() or ch in "\n\r\t")
    if not clean.strip():
        raise HTTPException(status_code=400, detail="Empty text after sanitization")

    provider = body.provider
    if provider in ("elevenlabs", "browser"):
        raise HTTPException(
            status_code=400,
            detail=f"provider '{provider}' is rendered client-side; "
                   f"backend serves 'auto', 'f5', or 'edge'",
        )

    # Stage 1: F5-TTS (preferred) for auto|f5. Probe first so a down service
    # fails fast to Edge instead of eating the long synthesis timeout.
    if provider in ("auto", "f5"):
        probe = await _f5_probe()
        if probe["available"]:
            audio = await _f5_synthesize(clean, body.speed)
            if audio:
                logger.info("tts.speak", provider="f5", chars=len(clean))
                return Response(
                    content=audio,
                    media_type="audio/mpeg",
                    headers={
                        "Cache-Control": "no-cache, no-store",
                        "X-Daena-TTS-Provider": "f5",
                    },
                )
            if provider == "f5":
                raise HTTPException(
                    status_code=502,
                    detail="F5-TTS synthesis failed; see backend logs",
                )
            logger.info("tts.f5_fallback_to_edge", reason="synth_failed")
        elif provider == "f5":
            raise HTTPException(
                status_code=502,
                detail=f"F5-TTS unavailable: {probe['reason']}",
            )
        else:
            logger.info("tts.f5_fallback_to_edge", reason=probe["reason"])

    # Stage 2: Edge-TTS (auto fallback, or explicit edge).
    if not _edge_available():
        raise HTTPException(
            status_code=503,
            detail="edge-tts not installed in backend venv"
                   + (" and F5-TTS unavailable" if provider == "auto" else ""),
        )

    logger.info("tts.speak", provider="edge", voice=body.voice, chars=len(clean))
    return StreamingResponse(
        _edge_stream_iter(clean, body.voice, body.rate, body.pitch, body.volume),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "X-Daena-TTS-Voice": body.voice,
            "X-Daena-TTS-Provider": "edge",
        },
    )
