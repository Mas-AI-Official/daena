"""
Event Bus for Real-Time WebSocket Broadcasting
Publishes events to all connected clients and logs to EventLog table
"""
from typing import Set, Dict, Any
from fastapi import WebSocket
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

class EventBus:
    """Central event bus for real-time updates"""
    
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        """Add a WebSocket connection (assumes already accepted)"""
        # NOTE: Do NOT call websocket.accept() here - caller already accepted
        async with self._lock:
            self.connections.add(websocket)
        logger.info(f"EventBus: WebSocket added. Total connections: {len(self.connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            self.connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.connections)}")
    
    async def publish(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        log_to_db: bool = True
    ):
        """
        Publish an event to all connected WebSocket clients
        
        Args:
            event_type: Type of event (e.g., "agent.created", "task.progress")
            entity_type: Type of entity (e.g., "agent", "task", "department")
            entity_id: ID of the entity
            payload: Event data payload
            log_to_db: Whether to log this event to EventLog table
        """
        event = {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Log to database
        if log_to_db:
            try:
                from backend.database import SessionLocal, EventLog
                db = SessionLocal()
                log_entry = EventLog(
                    event_type=event_type,
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                    payload_json=payload
                )
                db.add(log_entry)
                db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Failed to log event: {e}")
        
        # Broadcast to all connected clients
        disconnected = set()
        async with self._lock:
            for ws in self.connections:
                try:
                    await ws.send_json(event)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    disconnected.add(ws)
            
            # Remove disconnected sockets
            self.connections -= disconnected
        
        logger.debug(f"Published event: {event_type} -> {len(self.connections)} clients")
    
    async def publish_agent_event(self, event_type: str, agent_id: str, data: Dict):
        """Convenience method for agent events"""
        await self.publish(event_type, "agent", agent_id, data)
    
    async def publish_task_event(self, event_type: str, task_id: str, data: Dict):
        """Convenience method for task events"""
        await self.publish(event_type, "task", task_id, data)
    
    async def publish_department_event(self, event_type: str, dept_id: str, data: Dict):
        """Convenience method for department events"""
        await self.publish(event_type, "department", dept_id, data)
    
    async def publish_chat_event(self, event_type: str, session_id: str, data: Dict):
        """Convenience method for chat events"""
        await self.publish(event_type, "chat", session_id, data)
    
    async def publish_brain_status(self, connected: bool, model: str = None):
        """Publish brain/LLM status update"""
        await self.publish(
            "brain.status",
            "system",
            "brain",
            {"connected": connected, "model": model}
        )
    
    async def publish_system_reset(self):
        """Publish system reset event - UI should refresh"""
        await self.publish(
            "system.reset",
            "system",
            "all",
            {"action": "reset", "message": "System reset to defaults"}
        )
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.connections)


# Global singleton instance
event_bus = EventBus()


# Convenience function for publishing events
async def publish_event(
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: Dict[str, Any]
):
    """Publish an event via the global event bus"""
    await event_bus.publish(event_type, entity_type, entity_id, payload)
