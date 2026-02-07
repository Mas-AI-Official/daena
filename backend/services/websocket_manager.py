"""
WebSocket Manager - Centralized real-time communication
"""
from typing import Dict, List, Set, Any
from fastapi import WebSocket
import json
import asyncio

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str):
        await websocket.accept()

        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        self.active_connections[client_id].append(websocket)

        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)

        print(f"[WS] Client {client_id} connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, client_id: str, user_id: str):
        if client_id in self.active_connections:
            if websocket in self.active_connections[client_id]:
                self.active_connections[client_id].remove(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]

        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)

        print(f"[WS] Client {client_id} disconnected")

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Send message to all connections for a user"""
        if user_id in self.user_connections:
            disconnected = []
            for connection in self.user_connections[user_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)

            # Clean up disconnected
            for conn in disconnected:
                self.user_connections[user_id].discard(conn)

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast to all connected clients"""
        for user_id in list(self.user_connections.keys()):
            await self.broadcast_to_user(user_id, message)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message to specific websocket"""
        try:
            await websocket.send_json(message)
        except:
            pass

_manager = None

def get_websocket_manager() -> WebSocketManager:
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager
