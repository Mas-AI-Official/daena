"""
WebSocket Routes for Real-Time Updates
"""
from datetime import datetime
import asyncio
import logging
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.websocket_manager import websocket_manager, emit_chat_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _websocket_auth_required() -> bool:
    """True if WebSocket connections should require token (EXECUTION_TOKEN or WS_AUTH_ENABLED)."""
    try:
        from backend.config.settings import settings
        if getattr(settings, "ws_auth_enabled", False):
            return bool(settings.execution_token)
        return False
    except Exception:
        return False


def _validate_websocket_token(websocket: WebSocket) -> bool:
    """Validate token from query param ?token= or Cookie daena_execution_token. Returns True if valid or auth not required."""
    try:
        from backend.config.settings import settings
        if not _websocket_auth_required() or not settings.execution_token:
            return True
        token = websocket.query_params.get("token") or websocket.cookies.get("daena_execution_token")
        if token and token == settings.execution_token:
            return True
        return False
    except Exception:
        return False


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """Unified events WebSocket endpoint - connects to event bus for all real-time updates
    
    This endpoint receives all events from the unified event bus:
    - chat.message (department, executive, agent chats)
    - agent.progress (agent activity updates)
    - task.updated (task progress)
    - council.updated (council changes)
    - brain.status (brain connection status)
    - system.reset (system resets)
    """
    from backend.services.event_bus import event_bus
    import asyncio

    if _websocket_auth_required() and not _validate_websocket_token(websocket):
        await websocket.close(code=4403)
        return

    await websocket.accept()
    await event_bus.connect(websocket)
    
    # Heartbeat task
    async def heartbeat(ws):
        try:
            while True:
                await asyncio.sleep(25)
                # Check if open? Fastapi doesn't expose easy check without trying to send
                try:
                    await ws.send_json({"event_type": "ping", "timestamp": datetime.utcnow().isoformat()})
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
            
    heartbeat_task = asyncio.create_task(heartbeat(websocket))
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle client messages if needed
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "event_type": "pong",
                        "timestamp": message.get("timestamp")
                    })
                elif message.get("type") == "pong":
                    # Client responded to our ping
                    pass
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {data}")
    except WebSocketDisconnect:
        heartbeat_task.cancel()
        await event_bus.disconnect(websocket)
    except Exception as e:
        heartbeat_task.cancel()
        logger.error(f"WebSocket error: {e}")
        await event_bus.disconnect(websocket)



@router.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """Chat-specific WebSocket endpoint for a session"""
    connection_id = f"chat_{session_id}"
    await websocket_manager.connect(websocket, connection_id, {"session_id": session_id})
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle client messages (e.g., typing indicators, read receipts)
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message(websocket, {
                        "event_type": "pong",
                        "timestamp": message.get("timestamp")
                    })
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {data}")
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket_manager.disconnect(websocket, connection_id)


@router.websocket("/ws/council")
async def websocket_council(websocket: WebSocket):
    """Council/Governance WebSocket endpoint"""
    connection_id = "council"
    await websocket_manager.connect(websocket, connection_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message(websocket, {
                        "event_type": "pong",
                        "timestamp": message.get("timestamp")
                    })
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {data}")
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket_manager.disconnect(websocket, connection_id)


@router.websocket("/ws/agent/{agent_id}")
async def websocket_agent(websocket: WebSocket, agent_id: str):
    """Agent-specific WebSocket endpoint"""
    connection_id = f"agent_{agent_id}"
    await websocket_manager.connect(websocket, connection_id, {"agent_id": agent_id})
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket_manager.send_personal_message(websocket, {
                        "event_type": "pong",
                        "timestamp": message.get("timestamp")
                    })
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from WebSocket: {data}")
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket_manager.disconnect(websocket, connection_id)


@router.get("/api/v1/websocket/metrics")
async def get_websocket_metrics():
    """Get WebSocket connection and event metrics"""
    from backend.core.websocket_metrics import websocket_metrics
    return websocket_metrics.get_stats()


@router.get("/api/v1/websocket/events/recent")
async def get_recent_events(limit: int = 50):
    """Get recent WebSocket events"""
    from backend.core.websocket_metrics import websocket_metrics
    return {
        "events": websocket_metrics.get_recent_events(limit),
        "count": len(websocket_metrics.get_recent_events(limit))
    }


@router.get("/api/v1/websocket/errors/recent")
async def get_recent_errors(limit: int = 50):
    """Get recent WebSocket errors"""
    from backend.core.websocket_metrics import websocket_metrics
    return {
        "errors": websocket_metrics.get_recent_errors(limit),
        "count": len(websocket_metrics.get_recent_errors(limit))
    }
