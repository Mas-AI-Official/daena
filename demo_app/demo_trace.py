"""
Demo Trace Logger - Timeline Display for AI Tinkerers Demo

Captures and stores trace events for the demo UI timeline:
- Route decision logging
- Council role outputs
- Merge summary
- Memory/log write confirmation
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TraceEvent:
    """Single trace event in the timeline."""
    event_id: str
    event_type: str  # route, council_security, council_reliability, council_product, merge, memory
    timestamp: str
    duration_ms: int
    data: Dict[str, Any]
    status: str  # pending, success, error


@dataclass
class DemoTrace:
    """Complete trace for a demo request."""
    trace_id: str
    session_id: str
    prompt: str
    created_at: str
    events: List[TraceEvent]
    total_duration_ms: int
    status: str  # running, completed, failed


class DemoTraceLogger:
    """Logger for demo trace events."""
    
    def __init__(self):
        self.active_traces: Dict[str, DemoTrace] = {}
        self.completed_traces: Dict[str, DemoTrace] = {}
        self._max_completed = 50  # Keep last 50 traces
    
    def start_trace(self, prompt: str, session_id: Optional[str] = None) -> str:
        """Start a new trace for a demo request."""
        trace_id = str(uuid.uuid4())[:8]
        session_id = session_id or str(uuid.uuid4())[:8]
        
        trace = DemoTrace(
            trace_id=trace_id,
            session_id=session_id,
            prompt=prompt,
            created_at=datetime.utcnow().isoformat(),
            events=[],
            total_duration_ms=0,
            status="running"
        )
        
        self.active_traces[trace_id] = trace
        logger.info(f"Started demo trace: {trace_id}")
        return trace_id
    
    def add_event(
        self,
        trace_id: str,
        event_type: str,
        data: Dict[str, Any],
        duration_ms: int = 0,
        status: str = "success"
    ) -> Optional[str]:
        """Add an event to an active trace."""
        trace = self.active_traces.get(trace_id)
        if not trace:
            logger.warning(f"Trace not found: {trace_id}")
            return None
        
        event_id = f"{event_type}_{len(trace.events)}"
        event = TraceEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow().isoformat(),
            duration_ms=duration_ms,
            data=data,
            status=status
        )
        
        trace.events.append(event)
        trace.total_duration_ms += duration_ms
        
        logger.debug(f"Trace {trace_id}: {event_type} ({duration_ms}ms)")
        return event_id
    
    def add_route_event(
        self,
        trace_id: str,
        model_name: str,
        provider: str,
        reason: str,
        latency_ms: int,
        cost_usd: float
    ) -> Optional[str]:
        """Add routing decision event."""
        return self.add_event(
            trace_id=trace_id,
            event_type="route",
            data={
                "model_name": model_name,
                "provider": provider,
                "reason": reason,
                "cost_usd": cost_usd,
                "icon": "🔀",
                "label": "Router Decision"
            },
            duration_ms=latency_ms
        )
    
    def add_council_event(
        self,
        trace_id: str,
        role: str,
        vote: str,
        confidence: float,
        critiques: List[str],
        duration_ms: int
    ) -> Optional[str]:
        """Add council role evaluation event."""
        icons = {"security": "🔒", "reliability": "⚙️", "product": "📊"}
        colors = {"security": "#ef4444", "reliability": "#3b82f6", "product": "#10b981"}
        
        return self.add_event(
            trace_id=trace_id,
            event_type=f"council_{role}",
            data={
                "role": role,
                "vote": vote,
                "confidence": confidence,
                "critiques": critiques,
                "icon": icons.get(role, "👤"),
                "color": colors.get(role, "#6b7280"),
                "label": f"{role.title()} Review"
            },
            duration_ms=duration_ms
        )
    
    def add_merge_event(
        self,
        trace_id: str,
        final_decision: str,
        consensus_confidence: float,
        conflicts: List[str],
        duration_ms: int
    ) -> Optional[str]:
        """Add council merge decision event."""
        return self.add_event(
            trace_id=trace_id,
            event_type="merge",
            data={
                "final_decision": final_decision,
                "consensus_confidence": consensus_confidence,
                "conflicts": conflicts,
                "icon": "🔗",
                "label": "Council Merge"
            },
            duration_ms=duration_ms
        )
    
    def add_memory_event(
        self,
        trace_id: str,
        memory_tier: str,
        bytes_written: int,
        duration_ms: int
    ) -> Optional[str]:
        """Add memory/log write event."""
        return self.add_event(
            trace_id=trace_id,
            event_type="memory",
            data={
                "memory_tier": memory_tier,
                "bytes_written": bytes_written,
                "icon": "💾",
                "label": "Memory Write"
            },
            duration_ms=duration_ms
        )
    
    def complete_trace(self, trace_id: str, status: str = "completed") -> Optional[DemoTrace]:
        """Complete an active trace and move to completed."""
        trace = self.active_traces.pop(trace_id, None)
        if not trace:
            return None
        
        trace.status = status
        self.completed_traces[trace_id] = trace
        
        # Prune old traces
        if len(self.completed_traces) > self._max_completed:
            oldest_id = list(self.completed_traces.keys())[0]
            del self.completed_traces[oldest_id]
        
        logger.info(f"Completed demo trace: {trace_id} ({trace.total_duration_ms}ms)")
        return trace
    
    def get_trace(self, trace_id: str) -> Optional[DemoTrace]:
        """Get a trace by ID (active or completed)."""
        return self.active_traces.get(trace_id) or self.completed_traces.get(trace_id)
    
    def trace_to_dict(self, trace: DemoTrace) -> Dict[str, Any]:
        """Convert trace to JSON-serializable dict."""
        return {
            "trace_id": trace.trace_id,
            "session_id": trace.session_id,
            "prompt": trace.prompt,
            "created_at": trace.created_at,
            "status": trace.status,
            "total_duration_ms": trace.total_duration_ms,
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "duration_ms": e.duration_ms,
                    "status": e.status,
                    **e.data
                }
                for e in trace.events
            ]
        }


# Global singleton
demo_trace_logger = DemoTraceLogger()
