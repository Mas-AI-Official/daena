"""WebSocket endpoint for DaenaBot bridge connections.

DaenaBot is a local daemon users install on their machine. It connects
to this endpoint via WebSocket, receives tool_call messages, executes
them locally, and sends results back.

Architecture:
    Cloud Daena (this server) <--WebSocket--> DaenaBot (user's machine)

Protocol:
    DaenaBot -> Server: {"type": "handshake", "capabilities": [...], ...}
    Server -> DaenaBot: {"type": "tool_call", "call_id": "...", "tool": "...", "params": {...}}
    DaenaBot -> Server: {"type": "tool_result", "call_id": "...", "result": {...}}
    Server -> DaenaBot: {"type": "ping"}
    DaenaBot -> Server: {"type": "pong"}
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class BridgeConnection:
    """Represents a single DaenaBot bridge connection."""

    def __init__(
        self,
        ws: WebSocket,
        user_id: UUID,
        tenant_id: UUID,
    ) -> None:
        self.ws = ws
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.connected_at = time.time()
        self.capabilities: list[str] = []
        self.platform: str = "unknown"
        self.machine: str = "unknown"
        self.version: str = "0.0.0"
        self.system_info: dict[str, Any] = {}
        self._pending_calls: dict[str, asyncio.Future] = {}

    async def send_tool_call(
        self,
        tool: str,
        params: dict[str, Any],
        governance_tier: int = 0,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Send a tool call to DaenaBot and wait for the result."""
        call_id = str(uuid4())
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_calls[call_id] = future

        await self.ws.send_json({
            "type": "tool_call",
            "call_id": call_id,
            "tool": tool,
            "params": params,
            "governance_tier": governance_tier,
        })

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self._pending_calls.pop(call_id, None)
            return {"success": False, "error": f"Tool call timed out after {timeout}s"}

    def handle_result(self, call_id: str, result: dict[str, Any]) -> None:
        """Handle a tool result from DaenaBot."""
        future = self._pending_calls.pop(call_id, None)
        if future and not future.done():
            future.set_result(result)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "user_id": str(self.user_id),
            "connected_at": self.connected_at,
            "capabilities": self.capabilities,
            "platform": self.platform,
            "machine": self.machine,
            "version": self.version,
            "system_info": self.system_info,
            "uptime_seconds": int(time.time() - self.connected_at),
        }


class BridgeManager:
    """Manages all active DaenaBot bridge connections.

    One bridge per user (last connection wins).
    """

    def __init__(self) -> None:
        self._connections: dict[str, BridgeConnection] = {}  # user_id -> connection

    def register(self, conn: BridgeConnection) -> None:
        """Register a new bridge connection."""
        key = str(conn.user_id)
        self._connections[key] = conn
        logger.info(
            "bridge.connected",
            user_id=key,
            platform=conn.platform,
            machine=conn.machine,
        )

    def unregister(self, user_id: str | UUID) -> None:
        """Remove a bridge connection."""
        key = str(user_id)
        self._connections.pop(key, None)
        logger.info("bridge.disconnected", user_id=key)

    def get(self, user_id: str | UUID) -> BridgeConnection | None:
        """Get bridge connection for a user."""
        return self._connections.get(str(user_id))

    def is_connected(self, user_id: str | UUID) -> bool:
        """Check if a user has an active bridge."""
        return str(user_id) in self._connections

    def list_all(self) -> list[dict[str, Any]]:
        """List all active bridges."""
        return [conn.to_dict() for conn in self._connections.values()]


# Singleton bridge manager
bridge_manager = BridgeManager()


def get_bridge_manager() -> BridgeManager:
    """Get the global bridge manager instance."""
    return bridge_manager


@router.websocket("/ws/bridge")
async def websocket_bridge(websocket: WebSocket) -> None:
    """WebSocket endpoint for DaenaBot bridge connections.

    Auth: Bearer token in headers or query param.
    """
    # Extract auth token
    auth_header = websocket.headers.get("authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = websocket.query_params.get("token", "")

    if not token:
        await websocket.close(code=4001, reason="Missing auth token")
        return

    # Validate token and get user
    try:
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload.get("tenant_id", payload.get("tid", "")))
    except Exception as exc:
        await websocket.close(code=4003, reason=f"Invalid token: {exc}")
        return

    await websocket.accept()

    conn = BridgeConnection(websocket, user_id, tenant_id)

    try:
        # Wait for handshake
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        handshake = json.loads(raw)

        if handshake.get("type") == "handshake":
            conn.capabilities = handshake.get("capabilities", [])
            conn.platform = handshake.get("platform", "unknown")
            conn.machine = handshake.get("machine", "unknown")
            conn.version = handshake.get("version", "0.0.0")
            conn.system_info = handshake.get("system_info", {})

        bridge_manager.register(conn)

        # Send welcome
        await websocket.send_json({
            "type": "welcome",
            "message": "DaenaBot connected. Ready for tool calls.",
            "server_version": "3.7.1",
        })

        # Listen for messages
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "tool_result":
                call_id = data.get("call_id", "")
                result = data.get("result", {})
                conn.handle_result(call_id, result)

            elif msg_type == "pong":
                pass  # Keepalive response

            elif msg_type == "handshake":
                # Re-handshake (capability update)
                conn.capabilities = data.get("capabilities", conn.capabilities)

            else:
                logger.debug("bridge.unknown_message", type=msg_type)

    except WebSocketDisconnect:
        logger.info("bridge.client_disconnected", user_id=str(user_id))
    except asyncio.TimeoutError:
        logger.warning("bridge.handshake_timeout", user_id=str(user_id))
    except Exception:
        logger.exception("bridge.error", user_id=str(user_id))
    finally:
        bridge_manager.unregister(user_id)


@router.get("/bridge/status")
async def bridge_status() -> dict:
    """Check if any DaenaBot bridges are connected (admin/debug)."""
    return {
        "success": True,
        "data": {
            "active_bridges": len(bridge_manager._connections),
            "bridges": bridge_manager.list_all(),
        },
    }
