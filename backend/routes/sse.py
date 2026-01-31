"""
SSE Fallback - Server-Sent Events fallback for real-time updates

Part B: Real-time sync between backend and frontend.
Provides SSE fallback when WebSocket is not available.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["SSE"])


# ═══════════════════════════════════════════════════════════════════════
# Event Queue for SSE
# ═══════════════════════════════════════════════════════════════════════

class SSEEventQueue:
    """Queue for SSE events - mirrors the WebSocket event bus"""
    
    def __init__(self, max_size: int = 100):
        self.events: list = []
        self.max_size = max_size
        self.subscribers: set = set()
        self._lock = asyncio.Lock()
    
    async def add_event(self, event: Dict[str, Any]):
        """Add an event to the queue"""
        async with self._lock:
            self.events.append(event)
            if len(self.events) > self.max_size:
                self.events = self.events[-self.max_size:]
        
        # Notify all subscribers
        for callback in self.subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"SSE callback error: {e}")
    
    def get_recent(self, count: int = 50) -> list:
        """Get recent events"""
        return self.events[-count:]


# Global event queue
sse_queue = SSEEventQueue()


# ═══════════════════════════════════════════════════════════════════════
# SSE Event Generator
# ═══════════════════════════════════════════════════════════════════════

async def event_generator(request: Request) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for a client.
    
    Format: data: {json}\n\n
    """
    # Track this connection
    event_queue: asyncio.Queue = asyncio.Queue()
    
    async def on_event(event: Dict[str, Any]):
        await event_queue.put(event)
    
    sse_queue.subscribers.add(on_event)
    
    try:
        # Send initial connection event
        yield f"data: {json.dumps({'event_type': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
        
        # Keep connection alive and send events
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            try:
                # Wait for event with timeout (for keepalive)
                event = await asyncio.wait_for(event_queue.get(), timeout=30)
                yield f"data: {json.dumps(event, default=str)}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive
                yield f": keepalive\n\n"
    
    finally:
        sse_queue.subscribers.discard(on_event)
        logger.info("SSE client disconnected")


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

@router.get("/events")
async def sse_events(request: Request):
    """
    SSE endpoint for real-time events.
    
    Fallback for WebSocket /ws/events.
    Receives all events from the unified event bus.
    
    Event types:
    - chat.message
    - agent.progress
    - task.updated
    - council.updated
    - incident.created
    - brain.status
    - system.reset
    """
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/status")
async def sse_status():
    """Get SSE connection status"""
    return {
        "subscribers": len(sse_queue.subscribers),
        "events_in_queue": len(sse_queue.events),
        "timestamp": datetime.utcnow().isoformat()
    }


# ═══════════════════════════════════════════════════════════════════════
# Integration with Event Bus
# ═══════════════════════════════════════════════════════════════════════

async def publish_to_sse(event: Dict[str, Any]):
    """
    Publish an event to SSE queue.
    
    Call this from the main event bus to mirror events to SSE.
    """
    await sse_queue.add_event(event)


def integrate_with_event_bus():
    """
    Hook into the main event bus to mirror events to SSE.
    
    Call this at startup.
    """
    try:
        from backend.services.event_bus import event_bus
        
        # Store original publish method
        original_publish = event_bus.publish
        
        # Wrap to also publish to SSE
        async def wrapped_publish(
            event_type: str,
            entity_type: str,
            entity_id: str,
            payload: Dict[str, Any],
            log_to_db: bool = True
        ):
            # Call original
            await original_publish(event_type, entity_type, entity_id, payload, log_to_db)
            
            # Also publish to SSE
            await publish_to_sse({
                "event_type": event_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        event_bus.publish = wrapped_publish
        logger.info("SSE integrated with event bus")
        
    except Exception as e:
        logger.warning(f"Could not integrate SSE with event bus: {e}")
