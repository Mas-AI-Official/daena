"""WebSocket connection manager for real-time chat streaming.

Manages active WebSocket connections per chat session.
Multiple connections per session are supported (e.g. multiple browser tabs).
Includes server-side heartbeat to detect and prune stale connections.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

logger = get_logger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 30


class ConnectionManager:
    """Manage WebSocket connections grouped by chat session ID.

    Includes a background heartbeat task that periodically pings all
    connected clients to detect and remove stale connections.

    Usage::

        manager = ConnectionManager()

        # In WebSocket endpoint:
        await manager.connect(session_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()
                # process data...
                await manager.broadcast(session_id, response)
        except WebSocketDisconnect:
            manager.disconnect(session_id, websocket)
    """

    def __init__(self) -> None:
        """Initialize with empty connection registry."""
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection.

        Starts the heartbeat background task on the first connection.
        """
        await websocket.accept()
        self._connections[session_id].append(websocket)
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(
            "ws_connected",
            session_id=session_id,
            active_connections=len(self._connections[session_id]),
        )

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        conns = self._connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._connections.pop(session_id, None)
        logger.info(
            "ws_disconnected",
            session_id=session_id,
            remaining_connections=len(self._connections.get(session_id, [])),
        )

    async def send_json(
        self, session_id: str, websocket: WebSocket, data: dict
    ) -> None:
        """Send JSON to a specific connection within a session."""
        try:
            await websocket.send_json(data)
        except Exception:
            logger.warning("ws_send_failed", session_id=session_id)
            self.disconnect(session_id, websocket)

    async def broadcast(self, session_id: str, data: dict) -> None:
        """Send JSON to all connections for a session.

        Failed connections are automatically cleaned up.
        """
        conns = list(self._connections.get(session_id, []))
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning("ws_broadcast_send_failed", session_id=session_id)
                self.disconnect(session_id, ws)

    def get_active_sessions(self) -> list[str]:
        """Return list of session IDs with active connections."""
        return list(self._connections.keys())

    def get_connection_count(self, session_id: str) -> int:
        """Return number of active connections for a session."""
        return len(self._connections.get(session_id, []))

    async def _heartbeat_loop(self) -> None:
        """Background task: ping all connections every HEARTBEAT_INTERVAL_SECONDS.

        Sends a JSON ping to each connected client. If the send fails
        (client crashed, network dropped), the connection is pruned.
        Stops automatically when no connections remain.
        """
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            total = sum(len(v) for v in self._connections.values())
            if total == 0:
                logger.debug("heartbeat_stopped", reason="no connections")
                return

            pruned = 0
            for session_id in list(self._connections.keys()):
                for ws in list(self._connections.get(session_id, [])):
                    if ws.client_state != WebSocketState.CONNECTED:
                        self.disconnect(session_id, ws)
                        pruned += 1
                        continue
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        self.disconnect(session_id, ws)
                        pruned += 1

            if pruned:
                logger.info("heartbeat_pruned", stale_connections=pruned)

    async def shutdown(self) -> None:
        """Cancel heartbeat and close all connections. Call on app shutdown."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        for session_id in list(self._connections.keys()):
            for ws in list(self._connections.get(session_id, [])):
                try:  # noqa: SIM105
                    await ws.close()
                except Exception:
                    pass
            self._connections.pop(session_id, None)
        logger.info("ws_manager_shutdown")
