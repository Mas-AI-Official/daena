"""
WebSocket Manager for Real-Time Updates
Handles WebSocket connections and broadcasts events to connected clients
"""
import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from backend.core.websocket_metrics import websocket_metrics

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, metadata: Dict = None):
        """Accept a WebSocket connection"""
        await websocket.accept()
        
        if connection_id not in self.active_connections:
            self.active_connections[connection_id] = []
        
        self.active_connections[connection_id].append(websocket)
        self.connection_metadata[websocket] = metadata or {}
        
        # Record metrics
        websocket_metrics.record_connection(connection_id, metadata)
        
        logger.info(f"WebSocket connected: {connection_id} (total: {len(self.active_connections[connection_id])})")
        
        # Send welcome message
        await self.send_personal_message(websocket, {
            "event_type": "connection",
            "status": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def disconnect(self, websocket: WebSocket, connection_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            if websocket in self.active_connections[connection_id]:
                self.active_connections[connection_id].remove(websocket)
            
            # Clean up empty connection groups
            if not self.active_connections[connection_id]:
                del self.active_connections[connection_id]
        
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        # Record metrics
        websocket_metrics.record_disconnection(connection_id)
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_personal_message(self, websocket: WebSocket, message: Dict):
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
            # Find connection_id for metrics
            connection_id = None
            for cid, conns in self.active_connections.items():
                if websocket in conns:
                    connection_id = cid
                    break
            if connection_id:
                websocket_metrics.record_message_sent(connection_id)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            # Record error
            connection_id = None
            for cid, conns in self.active_connections.items():
                if websocket in conns:
                    connection_id = cid
                    break
            if connection_id:
                websocket_metrics.record_error(connection_id, str(e))
    
    async def broadcast_to_group(self, connection_id: str, message: Dict):
        """Broadcast a message to all connections in a group"""
        if connection_id not in self.active_connections:
            return
        
        disconnected = []
        for websocket in self.active_connections[connection_id]:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Error broadcasting to {connection_id}: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected websockets
        for ws in disconnected:
            await self.disconnect(ws, connection_id)
    
    async def broadcast_to_all(self, message: Dict):
        """Broadcast a message to all connected clients"""
        for connection_id in list(self.active_connections.keys()):
            await self.broadcast_to_group(connection_id, message)
    
    async def emit_event(self, event_type: str, payload: Dict, connection_id: str = None):
        """Emit an event to specific group or all clients"""
        message = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Record metrics
        websocket_metrics.record_event(event_type, {**payload, "connection_id": connection_id})
        
        if connection_id:
            await self.broadcast_to_group(connection_id, message)
        else:
            await self.broadcast_to_all(message)
    
    async def publish_event(self, event_type: str, entity_type: str, entity_id: str, payload: Dict, created_by: str = "system"):
        """
        Publish an event: write to EventLog and broadcast via WebSocket
        This is the single source of truth for all system events
        """
        from backend.database import SessionLocal, EventLog
        from typing import Optional
        
        # Write to EventLog
        db = SessionLocal()
        event_id = None
        try:
            event = EventLog(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload_json=payload,
                created_by=created_by
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            event_id = event.id
        except Exception as e:
            logger.error(f"Failed to write event to EventLog: {e}")
            db.rollback()
        finally:
            db.close()
        
        # Broadcast via WebSocket
        message = {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_id": event_id,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Broadcast to all connections
        for connection_id in list(self.active_connections.keys()):
            await self.broadcast_to_group(connection_id, message)
        
        return event_id
    
    def get_connection_count(self, connection_id: str = None) -> int:
        """Get the number of active connections"""
        if connection_id:
            return len(self.active_connections.get(connection_id, []))
        return sum(len(conns) for conns in self.active_connections.values())
    
    def get_active_groups(self) -> List[str]:
        """Get list of active connection groups"""
        return list(self.active_connections.keys())


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


# Event emitter functions for use throughout the application
async def emit_chat_message(session_id: str, sender: str, content: str, metadata: Dict = None):
    """
    Emit a chat message event - writes to EventLog and broadcasts via WebSocket
    """
    payload = {
        "session_id": session_id,
        "sender": sender,
        "content": content,
        "metadata": metadata or {}
    }
    
    # Use publish_event to write to EventLog and broadcast
    await websocket_manager.publish_event(
        event_type="chat.message",
        entity_type="chat",
        entity_id=session_id,
        payload=payload,
        created_by=sender
    )


async def emit_session_created(session_id: str, title: str, category: str = None):
    """Emit a session created event"""
    await websocket_manager.emit_event("session.created", {
        "session_id": session_id,
        "title": title,
        "category": category
    })


async def emit_session_updated(session_id: str, updates: Dict):
    """Emit a session updated event"""
    await websocket_manager.emit_event("session.updated", {
        "session_id": session_id,
        "updates": updates
    }, connection_id=f"chat_{session_id}")


async def emit_agent_activity(agent_id: str, activity: Dict):
    """Emit an agent activity event"""
    await websocket_manager.emit_event("agent.activity", {
        "agent_id": agent_id,
        "activity": activity
    }, connection_id=f"agent_{agent_id}")


async def emit_brain_status(status: Dict):
    """Emit brain status update"""
    await websocket_manager.emit_event("brain.status", {
        "status": status
    })


async def emit_task_update(task_id: str, status: str, progress: Dict = None):
    """Emit a task update event"""
    await websocket_manager.emit_event("task.update", {
        "task_id": task_id,
        "status": status,
        "progress": progress or {}
    })

