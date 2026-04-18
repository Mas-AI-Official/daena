"""Voice WebSocket endpoint.

Phase I.4: gives the frontend VoiceConsolePage a streaming channel
into the ConversationSession. Clients post text "audio" (browser
already transcribed via Web Speech API in Phase 1) or raw bytes
(when faster-whisper is installed), the server returns transcript +
assistant reply + synthesized audio (or a browser-directive payload).

Protocol
--------
Client -> Server: {"type": "turn", "audio": "<text or base64 bytes>",
                    "audio_kind": "text" | "bytes",
                    "language": "en", "voice": "default"}
Server -> Client: {"type": "turn_result", ... TurnResult fields}
Server -> Client: {"type": "error", "reason": "..."}
Server -> Client: {"type": "pong"}  for health pings.

Every turn routes through :class:`ConversationSession`, which
already applies the governance tier gate. High-tier replies come back
with ``status=awaiting_approval`` and an ``approval_id``; the Sidebar
badge and InlineApprovalBanner pick them up within one poll tick.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.services.voice.conversation_session import (
    ConversationSession,
    TurnResult,
    VoiceRiskTier,
)
from app.services.voice.stt_pipeline import STTPipeline
from app.services.voice.tts_pipeline import TTSPipeline

logger = get_logger(__name__)

router = APIRouter()


async def _echo_chat_turn(text: str) -> str:
    """Fallback chat-turn function.

    The real implementation will delegate to the 10-stage orchestrator.
    Wiring that in here touches the hot path; this module instead
    accepts a ``chat_turn`` factory from the request path so the
    orchestrator integration lands as a separate, scoped change.

    For now we return a safe acknowledgement so the voice pipeline
    end-to-end test works without the orchestrator plumbing.
    """
    return (
        f"I heard: '{text.strip()[:200]}'. The voice pipeline is live and "
        "governed. Ask me to prospect, draft, or run a security engagement."
    )


@router.websocket("/voice/ws/{session_id}")
async def voice_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """Streaming voice channel for a chat session."""
    await websocket.accept()
    logger.info("voice_ws.connected", session_id=session_id)

    stt = STTPipeline()
    tts = TTSPipeline()
    session = ConversationSession(
        stt=stt, tts=tts, chat_turn=_echo_chat_turn,
    )

    try:
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get("type", "turn")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type != "turn":
                await websocket.send_json({
                    "type": "error",
                    "reason": f"Unknown message type {msg_type!r}",
                })
                continue

            audio_kind = payload.get("audio_kind", "text")
            audio_raw = payload.get("audio", "")
            if audio_kind == "bytes":
                try:
                    audio: bytes | str = base64.b64decode(audio_raw)
                except Exception:
                    await websocket.send_json({
                        "type": "error",
                        "reason": "audio payload is not valid base64",
                    })
                    continue
            else:
                audio = str(audio_raw)

            result: TurnResult = await session.handle_turn(
                audio,
                language=payload.get("language", "en"),
                voice=payload.get("voice", "default"),
            )
            await websocket.send_json({
                "type": "turn_result",
                "status": result.status,
                "transcript": result.transcript,
                "reply_text": result.reply_text,
                "audio_b64": base64.b64encode(result.audio).decode() if result.audio else "",
                "audio_format": result.audio_format,
                "tier": result.tier.value if isinstance(result.tier, VoiceRiskTier) else str(result.tier),
                "approval_id": result.approval_id,
                "reason": result.reason,
                "metadata": result.metadata,
            })

    except WebSocketDisconnect:
        logger.info("voice_ws.disconnected", session_id=session_id)
    except Exception as exc:
        logger.warning("voice_ws.error", session_id=session_id, error=str(exc))
        try:
            await websocket.send_json({"type": "error", "reason": str(exc)})
        except Exception:
            pass
