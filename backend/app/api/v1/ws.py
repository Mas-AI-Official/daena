"""WebSocket endpoint for real-time chat streaming.

Provides a WebSocket connection per chat session for streaming
LLM responses back to the client in real-time.

Protocol:
  Client → Server: {"type": "message", "content": "user text"}
  Server → Client: {"type": "chunk", "content": "partial response"}
  Server → Client: {"type": "done", "message_id": "uuid"}
  Server → Client: {"type": "error", "message": "description"}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.websocket import ConnectionManager

logger = get_logger(__name__)

router = APIRouter()

# Singleton connection manager — shared across all WebSocket endpoints
manager = ConnectionManager()


async def _get_manager() -> ConnectionManager:
    """Dependency: return the global ConnectionManager instance."""
    return manager


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    mgr: ConnectionManager = Depends(_get_manager),
) -> None:
    """WebSocket endpoint for streaming chat within a session.

    Currently a skeleton: accepts connections, echoes messages,
    and handles disconnections. LLM integration will be added
    in Phase 5 when the model router is built.

    Args:
        websocket: The WebSocket connection.
        session_id: Chat session UUID from URL path.
        mgr: Injected ConnectionManager.
    """
    await mgr.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                await mgr.send_json(
                    session_id,
                    websocket,
                    {"type": "pong"},
                )
            elif msg_type == "message":
                # Phase 5 will route through LLM pipeline here.
                # For now: acknowledge receipt.
                await mgr.send_json(
                    session_id,
                    websocket,
                    {
                        "type": "ack",
                        "content": "Message received. LLM routing not yet active.",
                        "session_id": session_id,
                    },
                )
            else:
                await mgr.send_json(
                    session_id,
                    websocket,
                    {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    },
                )
    except WebSocketDisconnect:
        mgr.disconnect(session_id, websocket)
        logger.info("ws_client_disconnected", session_id=session_id)
    except Exception:
        mgr.disconnect(session_id, websocket)
        logger.exception("ws_unexpected_error", session_id=session_id)
