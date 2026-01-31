"""
Quarantine Module - Isolates misbehaving agents and manages recovery

Implements Charter Section G: Quarantine & Containment
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("qa_guardian.quarantine")


class QuarantineState(Enum):
    """Quarantine state machine states"""
    ACTIVE = "active"           # Normal operation
    SUSPECTED = "suspected"     # Under observation (2+ incidents in 30 min)
    QUARANTINED = "quarantined" # Fully isolated
    RECOVERING = "recovering"   # Postmortem complete, testing
    RESTORED = "restored"       # Back to normal


class QuarantineLevel(Enum):
    """Quarantine action levels"""
    DISABLE = "disable"   # Agent stopped, no new tasks
    LIMIT = "limit"       # Reduced permissions, read-only
    REDIRECT = "redirect" # Tasks routed to backup agent
    ISOLATE = "isolate"   # Network access restricted


@dataclass
class IncidentRecord:
    """Record of an incident for tracking"""
    incident_id: str
    agent_id: str
    severity: str
    timestamp: datetime


@dataclass
class QuarantineEntry:
    """A quarantine entry for an agent"""
    agent_id: str
    department: Optional[str]
    state: QuarantineState
    level: QuarantineLevel
    reason: str
    incident_ids: List[str]
    backup_agent: Optional[str] = None
    quarantined_at: Optional[datetime] = None
    suspected_at: Optional[datetime] = None
    restored_at: Optional[datetime] = None
    postmortem_approved: bool = False
    fix_verified: bool = False
    founder_approved: bool = False


class QuarantineManager:
    """
    Manages agent quarantine state and transitions.
    
    Quarantine Triggers (from Charter):
    - 3+ incidents within 1 hour from same source
    - Single P0/P1 incident from agent behavior
    - Resource exhaustion
    - Security violation
    - Infinite loop detection
    - Manual trigger by founder
    """
    
    INCIDENT_THRESHOLD = 3
    INCIDENT_WINDOW_MINUTES = 60
    SUSPECTED_THRESHOLD = 2
    SUSPECTED_WINDOW_MINUTES = 30
    
    def __init__(self):
        self.entries: Dict[str, QuarantineEntry] = {}
        self.incident_history: List[IncidentRecord] = []
    
    def record_incident(
        self,
        incident_id: str,
        agent_id: str,
        severity: str
    ) -> Optional[QuarantineEntry]:
        """
        Record an incident and check if quarantine is needed.
        
        Returns QuarantineEntry if agent is quarantined, None otherwise.
        """
        record = IncidentRecord(
            incident_id=incident_id,
            agent_id=agent_id,
            severity=severity,
            timestamp=datetime.utcnow()
        )
        self.incident_history.append(record)
        
        # Prune old records
        cutoff = datetime.utcnow() - timedelta(minutes=self.INCIDENT_WINDOW_MINUTES)
        self.incident_history = [r for r in self.incident_history if r.timestamp > cutoff]
        
        # Check for P0/P1 - immediate quarantine
        if severity in ["P0", "P1"]:
            return self.quarantine_agent(
                agent_id=agent_id,
                reason=f"Critical incident: {severity}",
                incident_ids=[incident_id],
                level=QuarantineLevel.DISABLE
            )
        
        # Count recent incidents for this agent
        recent = self._get_agent_incidents(agent_id)
        
        # Check thresholds
        if len(recent) >= self.INCIDENT_THRESHOLD:
            return self.quarantine_agent(
                agent_id=agent_id,
                reason="Repeated failures (threshold exceeded)",
                incident_ids=[r.incident_id for r in recent],
                level=QuarantineLevel.REDIRECT
            )
        
        elif len(recent) >= self.SUSPECTED_THRESHOLD:
            return self.suspect_agent(
                agent_id=agent_id,
                incident_ids=[r.incident_id for r in recent]
            )
        
        return None
    
    def _get_agent_incidents(self, agent_id: str) -> List[IncidentRecord]:
        """Get recent incidents for an agent"""
        cutoff = datetime.utcnow() - timedelta(minutes=self.INCIDENT_WINDOW_MINUTES)
        return [
            r for r in self.incident_history
            if r.agent_id == agent_id and r.timestamp > cutoff
        ]
    
    def suspect_agent(
        self,
        agent_id: str,
        incident_ids: List[str]
    ) -> QuarantineEntry:
        """Put agent under observation"""
        entry = self.entries.get(agent_id)
        
        if entry and entry.state == QuarantineState.QUARANTINED:
            # Already quarantined, don't downgrade
            return entry
        
        entry = QuarantineEntry(
            agent_id=agent_id,
            department=None,  # TODO: Look up
            state=QuarantineState.SUSPECTED,
            level=QuarantineLevel.LIMIT,
            reason="Under observation",
            incident_ids=incident_ids,
            suspected_at=datetime.utcnow()
        )
        
        self.entries[agent_id] = entry
        logger.warning(f"Agent {agent_id} is now SUSPECTED")
        
        self._audit_log("agent_suspected", {
            "agent_id": agent_id,
            "incident_ids": incident_ids
        })
        
        return entry
    
    def quarantine_agent(
        self,
        agent_id: str,
        reason: str,
        incident_ids: List[str],
        level: QuarantineLevel = QuarantineLevel.DISABLE
    ) -> QuarantineEntry:
        """Quarantine an agent"""
        entry = QuarantineEntry(
            agent_id=agent_id,
            department=None,  # TODO: Look up
            state=QuarantineState.QUARANTINED,
            level=level,
            reason=reason,
            incident_ids=incident_ids,
            quarantined_at=datetime.utcnow(),
            backup_agent=self._find_backup_agent(agent_id)
        )
        
        self.entries[agent_id] = entry
        logger.error(f"Agent {agent_id} QUARANTINED: {reason}")
        
        self._audit_log("agent_quarantined", {
            "agent_id": agent_id,
            "reason": reason,
            "level": level.value,
            "incident_ids": incident_ids,
            "backup_agent": entry.backup_agent
        })
        
        # TODO: Actually disable the agent
        # TODO: Reroute tasks to backup agent
        # TODO: Notify founder
        
        return entry
    
    def begin_recovery(self, agent_id: str) -> Optional[QuarantineEntry]:
        """Begin recovery process after postmortem"""
        entry = self.entries.get(agent_id)
        if not entry:
            return None
        
        if entry.state != QuarantineState.QUARANTINED:
            return entry
        
        entry.state = QuarantineState.RECOVERING
        entry.postmortem_approved = True
        
        self._audit_log("recovery_started", {"agent_id": agent_id})
        
        return entry
    
    def restore_agent(
        self,
        agent_id: str,
        founder_approved: bool = False
    ) -> Optional[QuarantineEntry]:
        """Restore an agent from quarantine (requires founder approval)"""
        entry = self.entries.get(agent_id)
        if not entry:
            return None
        
        if not founder_approved:
            logger.warning(f"Cannot restore {agent_id} without founder approval")
            return entry
        
        entry.state = QuarantineState.RESTORED
        entry.founder_approved = True
        entry.restored_at = datetime.utcnow()
        
        logger.info(f"Agent {agent_id} RESTORED")
        
        self._audit_log("agent_restored", {
            "agent_id": agent_id,
            "founder_approved": founder_approved
        })
        
        # TODO: Re-enable the agent
        # TODO: Start enhanced monitoring
        
        return entry
    
    def _find_backup_agent(self, agent_id: str) -> Optional[str]:
        """Find a backup agent in the same department"""
        # TODO: Implement actual backup agent lookup
        return None
    
    def get_quarantine_status(self, agent_id: str) -> Optional[QuarantineEntry]:
        """Get current quarantine status for an agent"""
        return self.entries.get(agent_id)
    
    def get_all_quarantined(self) -> List[QuarantineEntry]:
        """Get all quarantined agents"""
        return [
            e for e in self.entries.values()
            if e.state == QuarantineState.QUARANTINED
        ]
    
    def get_all_suspected(self) -> List[QuarantineEntry]:
        """Get all suspected agents"""
        return [
            e for e in self.entries.values()
            if e.state == QuarantineState.SUSPECTED
        ]
    
    def _audit_log(self, action: str, details: dict):
        """Log action to audit trail"""
        import json
        from pathlib import Path
        
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "qa_guardian_quarantine.jsonl"
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            **details
        }
        
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# Singleton instance
_quarantine_manager: Optional[QuarantineManager] = None

def get_quarantine_manager() -> QuarantineManager:
    """Get or create the singleton quarantine manager"""
    global _quarantine_manager
    if _quarantine_manager is None:
        _quarantine_manager = QuarantineManager()
    return _quarantine_manager
