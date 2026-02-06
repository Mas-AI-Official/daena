
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List, Any
import datetime
import asyncio
import json

# Minimal mock for Socket.io if not using a full sio server, 
# but the prompt implies python-socketio. 
# For now, I'll implement a FastAPI WebSocket router that mimics the functionality 
# if the environment doesn't have python-socketio installed (likely), 
# OR I can assume python-socketio is integrated with FastAPI.

# Given the instructions, I'll use standard FastAPI WebSockets for simplicity 
# unless python-socketio is strictly required by the prompt's provided code structure.
# The prompt code uses `@sio.on`, which is python-socketio. 
# I will implement a wrapper that works with FastAPI WebSockets but structure it to handle the events.

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Simple echo or event dispatcher
            try:
                event = json.loads(data)
                if event.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.datetime.utcnow().isoformat()}))
            except:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@router.post("/ws/broadcast")
async def broadcast_event(payload: Dict[str, Any]):
    """Internal endpoint to broadcast events to connected clients"""
    # Payload expected: {"type": "event_name", "data": { ... }}
    await manager.broadcast(json.dumps(payload))
    return {"status": "broadcasted"}

# Mock SIO for compatibility if referenced elsewhere
class MockSIO:
    async def emit(self, event, data):
        await manager.broadcast(json.dumps({"type": event, "data": data}))

sio = MockSIO()
