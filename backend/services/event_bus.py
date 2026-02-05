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
        self._event_queue: List[Dict[str, Any]] = []
        self._batch_task: Optional[asyncio.Task] = None
        self._batch_interval = 0.25  # 250ms batch window (Issue 13 Fix)
    
    async def connect(self, websocket: WebSocket):
        """Add a WebSocket connection (assumes already accepted)"""
        # NOTE: Do NOT call websocket.accept() here - caller already accepted
        async with self._lock:
            self.connections.add(websocket)
            # Start batch task if not running
            if not self._batch_task or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._flush_batch_loop())
        logger.info(f"EventBus: WebSocket added. Total connections: {len(self.connections)}")

    async def _flush_batch_loop(self):
        """Background task to flush batched events"""
        while True:
            await asyncio.sleep(self._batch_interval)
            if not self._event_queue:
                continue
                
            async with self._lock:
                batch = self._event_queue.copy()
                self._event_queue.clear()
            
            if not batch:
                continue
                
            # If only one event, send normally
            # If multiple, send as a batch event
            message = {
                "event_type": "batch",
                "events": batch,
                "timestamp": datetime.utcnow().isoformat()
            } if len(batch) > 1 else batch[0]
            
            # Broadcast
            disconnected = set()
            async with self._lock:
                for ws in self.connections:
                    try:
                        await ws.send_json(message)
                    except Exception:
                        disconnected.add(ws)
                self.connections -= disconnected

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            self.connections.discard(websocket)
            if not self.connections and self._batch_task:
                self._batch_task.cancel()
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
        Publish an event (batched) to all connected WebSocket clients
        """
        event = {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Log to database (immediate)
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
        
        # Queue for batching
        async with self._lock:
            self._event_queue.append(event)
            # Ensure task is running
            if (not self._batch_task or self._batch_task.done()) and self.connections:
                self._batch_task = asyncio.create_task(self._flush_batch_loop())
    
    async def broadcast(self, event_type: str, data: Dict[str, Any] = None, message: str = ""):
        """
        Simple broadcast for Control Plane: sends { type, timestamp, data, message }.
        Frontend handleWSEvent can route by event_type (e.g. governance_pipeline, skill_created).
        """
        payload = dict(data or {})
        payload["message"] = message or event_type
        await self.publish(
            event_type,
            entity_type="system",
            entity_id=payload.get("pipeline_id", payload.get("id", event_type)),
            payload=payload,
            log_to_db=True
        )
    
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
