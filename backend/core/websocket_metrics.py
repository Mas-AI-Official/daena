"""
WebSocket Metrics and Monitoring
Tracks connection metrics, event rates, and errors
"""
import time
from typing import Dict, List
from collections import deque
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class WebSocketMetrics:
    """Tracks WebSocket connection and event metrics"""
    
    def __init__(self, max_history=1000):
        self.max_history = max_history
        self.connections = {}  # connection_id -> connection_info
        self.events = deque(maxlen=max_history)  # Event history
        self.errors = deque(maxlen=max_history)  # Error history
        self.start_time = time.time()
        
        # Counters
        self.total_connections = 0
        self.total_disconnections = 0
        self.total_events_emitted = 0
        self.total_errors = 0
        self.total_messages_sent = 0
        self.total_messages_received = 0
    
    def record_connection(self, connection_id: str, metadata: Dict = None):
        """Record a new connection"""
        self.connections[connection_id] = {
            "id": connection_id,
            "connected_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "events_sent": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0
        }
        self.total_connections += 1
        self.record_event("connection", {"connection_id": connection_id, "action": "connected"})
    
    def record_disconnection(self, connection_id: str):
        """Record a disconnection"""
        if connection_id in self.connections:
            del self.connections[connection_id]
        self.total_disconnections += 1
        self.record_event("connection", {"connection_id": connection_id, "action": "disconnected"})
    
    def record_event(self, event_type: str, payload: Dict):
        """Record an event emission"""
        event = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
            "connection_id": payload.get("connection_id")
        }
        self.events.append(event)
        self.total_events_emitted += 1
        
        # Update connection stats if applicable
        connection_id = payload.get("connection_id")
        if connection_id and connection_id in self.connections:
            self.connections[connection_id]["events_sent"] += 1
    
    def record_message_sent(self, connection_id: str):
        """Record a message sent"""
        self.total_messages_sent += 1
        if connection_id in self.connections:
            self.connections[connection_id]["messages_sent"] += 1
    
    def record_message_received(self, connection_id: str):
        """Record a message received"""
        self.total_messages_received += 1
        if connection_id in self.connections:
            self.connections[connection_id]["messages_received"] += 1
    
    def record_error(self, connection_id: str, error: str, details: Dict = None):
        """Record an error"""
        error_record = {
            "connection_id": connection_id,
            "error": error,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.errors.append(error_record)
        self.total_errors += 1
        
        if connection_id in self.connections:
            self.connections[connection_id]["errors"] += 1
    
    def get_stats(self) -> Dict:
        """Get current statistics"""
        uptime = time.time() - self.start_time
        
        # Calculate event rates
        events_per_minute = (self.total_events_emitted / uptime * 60) if uptime > 0 else 0
        errors_per_minute = (self.total_errors / uptime * 60) if uptime > 0 else 0
        
        # Recent events (last 60 seconds)
        now = time.time()
        recent_events = [
            e for e in self.events
            if (now - datetime.fromisoformat(e["timestamp"]).timestamp()) < 60
        ]
        
        return {
            "uptime_seconds": uptime,
            "uptime_formatted": self._format_uptime(uptime),
            "active_connections": len(self.connections),
            "total_connections": self.total_connections,
            "total_disconnections": self.total_disconnections,
            "total_events_emitted": self.total_events_emitted,
            "total_messages_sent": self.total_messages_sent,
            "total_messages_received": self.total_messages_received,
            "total_errors": self.total_errors,
            "events_per_minute": round(events_per_minute, 2),
            "errors_per_minute": round(errors_per_minute, 2),
            "recent_events_count": len(recent_events),
            "connections": list(self.connections.values())
        }
    
    def get_recent_events(self, limit: int = 50) -> List[Dict]:
        """Get recent events"""
        return list(self.events)[-limit:]
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Get recent errors"""
        return list(self.errors)[-limit:]
    
    def get_connection_stats(self, connection_id: str) -> Dict:
        """Get stats for a specific connection"""
        if connection_id in self.connections:
            return self.connections[connection_id]
        return None
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def reset(self):
        """Reset all metrics (for testing)"""
        self.connections.clear()
        self.events.clear()
        self.errors.clear()
        self.start_time = time.time()
        self.total_connections = 0
        self.total_disconnections = 0
        self.total_events_emitted = 0
        self.total_errors = 0
        self.total_messages_sent = 0
        self.total_messages_received = 0


# Global metrics instance
websocket_metrics = WebSocketMetrics()



