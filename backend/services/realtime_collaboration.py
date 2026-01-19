"""
Real-Time Collaboration Service for Daena

Provides:
- Live agent activity tracking
- Real-time memory updates
- Collaborative decision-making
- Agent status broadcasting
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum

from backend.services.websocket_service import websocket_manager

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    """Types of agent activities."""
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    MEMORY_WRITE = "memory_write"
    MEMORY_READ = "memory_read"
    COUNCIL_DEBATE = "council_debate"
    COUNCIL_SYNTHESIS = "council_synthesis"
    DECISION_MADE = "decision_made"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    MESSAGE_SENT = "message_sent"
    COLLABORATION_STARTED = "collaboration_started"
    COLLABORATION_ENDED = "collaboration_ended"


@dataclass
class AgentActivity:
    """Record of an agent activity."""
    activity_id: str
    agent_id: str
    department: str
    activity_type: str
    timestamp: float
    metadata: Dict[str, Any]
    related_agents: List[str]
    status: str  # "active", "completed", "failed"


@dataclass
class CollaborationSession:
    """A collaboration session between agents."""
    session_id: str
    participants: List[str]
    started_at: float
    ended_at: Optional[float]
    activities: List[str]  # Activity IDs
    decision_points: List[Dict[str, Any]]


class RealTimeCollaborationService:
    """
    Service for real-time collaboration features.
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize real-time collaboration service.
        
        Args:
            max_history: Maximum number of activities to keep in history
        """
        self.max_history = max_history
        
        # Activity tracking
        self.activities: deque = deque(maxlen=max_history)
        self.active_activities: Dict[str, AgentActivity] = {}
        
        # Agent status tracking
        self.agent_status: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "status": "idle",
            "current_activity": None,
            "last_activity": None,
            "collaboration_sessions": []
        })
        
        # Collaboration sessions
        self.collaboration_sessions: Dict[str, CollaborationSession] = {}
        
        # Memory update tracking
        self.recent_memory_updates: deque = deque(maxlen=100)
        
        # Subscriptions (which clients want which updates)
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # client_id -> activity_types
        
        # Start background task for broadcasting
        self._broadcast_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the collaboration service."""
        if not self._running:
            self._running = True
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())
            logger.info("Real-time collaboration service started")
    
    async def stop(self):
        """Stop the collaboration service."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
        logger.info("Real-time collaboration service stopped")
    
    async def _broadcast_loop(self):
        """Background task to broadcast updates."""
        while self._running:
            try:
                # Broadcast agent status updates every 2 seconds
                await self._broadcast_agent_status()
                
                # Broadcast memory updates
                await self._broadcast_memory_updates()
                
                await asyncio.sleep(2)  # Update every 2 seconds
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error
    
    async def _broadcast_agent_status(self):
        """Broadcast agent status updates."""
        status_summary = {
            "type": "agent_status_update",
            "timestamp": datetime.now().isoformat(),
            "agents": {}
        }
        
        for agent_id, status in self.agent_status.items():
            status_summary["agents"][agent_id] = {
                "status": status["status"],
                "current_activity": status["current_activity"],
                "last_activity": status["last_activity"]
            }
        
        # Broadcast to all connected clients
        await websocket_manager.broadcast_to_all(status_summary)
    
    async def _broadcast_memory_updates(self):
        """Broadcast recent memory updates."""
        if not self.recent_memory_updates:
            return
        
        # Get recent updates (last 10)
        recent = list(self.recent_memory_updates)[-10:]
        
        if recent:
            message = {
                "type": "memory_updates",
                "timestamp": datetime.now().isoformat(),
                "updates": recent
            }
            await websocket_manager.broadcast_to_all(message)
    
    def record_activity(
        self,
        agent_id: str,
        department: str,
        activity_type: ActivityType,
        metadata: Optional[Dict[str, Any]] = None,
        related_agents: Optional[List[str]] = None
    ) -> str:
        """
        Record an agent activity.
        
        Returns:
            Activity ID
        """
        activity_id = f"act_{int(time.time() * 1000)}_{agent_id}"
        
        activity = AgentActivity(
            activity_id=activity_id,
            agent_id=agent_id,
            department=department,
            activity_type=activity_type.value,
            timestamp=time.time(),
            metadata=metadata or {},
            related_agents=related_agents or [],
            status="active"
        )
        
        self.activities.append(activity)
        self.active_activities[activity_id] = activity
        
        # Update agent status
        self.agent_status[agent_id]["status"] = "active"
        self.agent_status[agent_id]["current_activity"] = activity_id
        self.agent_status[agent_id]["last_activity"] = activity_id
        
        # Broadcast activity
        asyncio.create_task(self._broadcast_activity(activity))
        
        return activity_id
    
    async def _broadcast_activity(self, activity: AgentActivity):
        """Broadcast an activity to connected clients."""
        message = {
            "type": "agent_activity",
            "activity": asdict(activity),
            "timestamp": datetime.now().isoformat()
        }
        await websocket_manager.broadcast_to_all(message)
    
    def complete_activity(self, activity_id: str, success: bool = True):
        """Mark an activity as completed."""
        if activity_id in self.active_activities:
            activity = self.active_activities[activity_id]
            activity.status = "completed" if success else "failed"
            
            # Update agent status
            agent_id = activity.agent_id
            if self.agent_status[agent_id]["current_activity"] == activity_id:
                self.agent_status[agent_id]["status"] = "idle"
                self.agent_status[agent_id]["current_activity"] = None
            
            # Remove from active
            del self.active_activities[activity_id]
            
            # Broadcast completion
            asyncio.create_task(self._broadcast_activity_completion(activity_id, success))
    
    async def _broadcast_activity_completion(self, activity_id: str, success: bool):
        """Broadcast activity completion."""
        message = {
            "type": "activity_completed",
            "activity_id": activity_id,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        await websocket_manager.broadcast_to_all(message)
    
    def record_memory_update(
        self,
        operation: str,
        item_id: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a memory update."""
        update = {
            "operation": operation,  # "write", "read", "delete"
            "item_id": item_id,
            "agent_id": agent_id,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        self.recent_memory_updates.append(update)
        
        # Broadcast immediately
        asyncio.create_task(self._broadcast_memory_update(update))
    
    async def _broadcast_memory_update(self, update: Dict[str, Any]):
        """Broadcast a memory update."""
        message = {
            "type": "memory_update",
            "update": update,
            "timestamp": datetime.now().isoformat()
        }
        await websocket_manager.broadcast_to_all(message)
    
    def start_collaboration_session(
        self,
        participants: List[str],
        session_type: str = "general"
    ) -> str:
        """Start a collaboration session."""
        session_id = f"collab_{int(time.time() * 1000)}"
        
        session = CollaborationSession(
            session_id=session_id,
            participants=participants,
            started_at=time.time(),
            ended_at=None,
            activities=[],
            decision_points=[]
        )
        
        self.collaboration_sessions[session_id] = session
        
        # Update agent statuses
        for agent_id in participants:
            if agent_id in self.agent_status:
                self.agent_status[agent_id]["collaboration_sessions"].append(session_id)
        
        # Broadcast session start
        asyncio.create_task(self._broadcast_collaboration_start(session))
        
        return session_id
    
    async def _broadcast_collaboration_start(self, session: CollaborationSession):
        """Broadcast collaboration session start."""
        message = {
            "type": "collaboration_started",
            "session": {
                "session_id": session.session_id,
                "participants": session.participants,
                "started_at": datetime.fromtimestamp(session.started_at).isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        await websocket_manager.broadcast_to_all(message)
    
    def end_collaboration_session(self, session_id: str):
        """End a collaboration session."""
        if session_id in self.collaboration_sessions:
            session = self.collaboration_sessions[session_id]
            session.ended_at = time.time()
            
            # Update agent statuses
            for agent_id in session.participants:
                if agent_id in self.agent_status:
                    sessions = self.agent_status[agent_id]["collaboration_sessions"]
                    if session_id in sessions:
                        sessions.remove(session_id)
            
            # Broadcast session end
            asyncio.create_task(self._broadcast_collaboration_end(session_id))
    
    async def _broadcast_collaboration_end(self, session_id: str):
        """Broadcast collaboration session end."""
        message = {
            "type": "collaboration_ended",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        await websocket_manager.broadcast_to_all(message)
    
    def get_agent_activity_feed(self, agent_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get activity feed for an agent or all agents."""
        activities = list(self.activities)
        
        if agent_id:
            activities = [a for a in activities if a.agent_id == agent_id]
        
        # Sort by timestamp (newest first)
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit
        activities = activities[:limit]
        
        return [asdict(a) for a in activities]
    
    def get_active_collaborations(self) -> List[Dict[str, Any]]:
        """Get all active collaboration sessions."""
        active = [
            session for session in self.collaboration_sessions.values()
            if session.ended_at is None
        ]
        
        return [
            {
                "session_id": s.session_id,
                "participants": s.participants,
                "started_at": datetime.fromtimestamp(s.started_at).isoformat(),
                "activity_count": len(s.activities),
                "decision_count": len(s.decision_points)
            }
            for s in active
        ]
    
    def get_agent_status_summary(self) -> Dict[str, Any]:
        """Get summary of all agent statuses."""
        return {
            "total_agents": len(self.agent_status),
            "active_agents": len([s for s in self.agent_status.values() if s["status"] == "active"]),
            "idle_agents": len([s for s in self.agent_status.values() if s["status"] == "idle"]),
            "active_activities": len(self.active_activities),
            "active_collaborations": len(self.get_active_collaborations()),
            "agents": {
                agent_id: {
                    "status": status["status"],
                    "current_activity": status["current_activity"],
                    "collaboration_count": len(status["collaboration_sessions"])
                }
                for agent_id, status in self.agent_status.items()
            }
        }


# Global instance
realtime_collaboration_service = RealTimeCollaborationService()

