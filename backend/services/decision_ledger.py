"""
Decision Ledger - Auditable Decision Trail for Daena

Records all decisions made during autonomous project execution:
- Who did what (department, agent, council)
- Why (reasoning, council synthesis)
- Evidence used
- Timestamps
- Outcomes

This is the audit trail required for governance and compliance.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import uuid

logger = logging.getLogger(__name__)


@dataclass
class LedgerEntry:
    """A single entry in the decision ledger"""
    entry_id: str
    project_id: str
    action: str
    actor_type: str  # department, agent, council, daena, founder
    actor_id: str
    evidence: List[str] = field(default_factory=list)
    reasoning: Optional[str] = None
    outcome: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DecisionLedger:
    """
    Immutable decision ledger for audit trail.
    
    All entries are append-only and cannot be modified once written.
    """
    
    def __init__(self):
        # In-memory ledger (would be backed by append-only DB in production)
        self._entries: List[LedgerEntry] = []
        self._project_index: Dict[str, List[str]] = {}  # project_id -> entry_ids
    
    async def write_entry(self, entry_data: Dict[str, Any]) -> LedgerEntry:
        """
        Write an entry to the decision ledger.
        
        This is append-only - entries cannot be modified.
        """
        entry_id = f"ledger-{uuid.uuid4().hex[:12]}"
        
        entry = LedgerEntry(
            entry_id=entry_id,
            project_id=entry_data.get("project_id", "unknown"),
            action=entry_data.get("action", entry_data.get("title", "unknown_action")),
            actor_type=self._determine_actor_type(entry_data),
            actor_id=self._determine_actor_id(entry_data),
            evidence=entry_data.get("evidence", []),
            reasoning=entry_data.get("council_recommendation", entry_data.get("reasoning")),
            outcome=entry_data.get("outcome", "recorded"),
            metadata=self._extract_metadata(entry_data),
            timestamp=datetime.utcnow()
        )
        
        self._entries.append(entry)
        
        # Index by project
        if entry.project_id not in self._project_index:
            self._project_index[entry.project_id] = []
        self._project_index[entry.project_id].append(entry_id)
        
        # Persist to database
        await self._persist_to_db(entry)
        
        # Publish event
        await self._publish_event(entry)
        
        logger.info(f"📜 Ledger entry written: {entry_id} | {entry.action} by {entry.actor_type}:{entry.actor_id}")
        
        return entry
    
    def _determine_actor_type(self, data: Dict[str, Any]) -> str:
        """Determine actor type from entry data"""
        if data.get("council_recommendation"):
            return "council"
        if data.get("departments_involved"):
            return "department"
        if data.get("agents_involved"):
            return "agent"
        return "daena"
    
    def _determine_actor_id(self, data: Dict[str, Any]) -> str:
        """Determine specific actor from entry data"""
        if data.get("departments_involved"):
            return ",".join(data["departments_involved"][:3])
        if data.get("agents_involved"):
            return ",".join(data["agents_involved"][:3])
        return "daena_autonomous"
    
    def _extract_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from entry data"""
        return {
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at"),
            "tasks_completed": data.get("tasks_completed"),
            "facts_verified": data.get("facts_verified"),
            "deliverables_produced": data.get("deliverables_produced"),
            "qa_passed": data.get("qa_passed")
        }
    
    async def _persist_to_db(self, entry: LedgerEntry):
        """Persist entry to database"""
        try:
            from backend.database import SessionLocal, Decision
            
            db = SessionLocal()
            try:
                decision = Decision(
                    decision_id=entry.entry_id,
                    title=entry.action,
                    description=entry.reasoning or "",
                    decision_type="autonomous_execution",
                    priority="normal",
                    impact_level="project",
                    related_departments=entry.metadata.get("departments_involved", []),
                    related_agents=entry.metadata.get("agents_involved", []),
                    status="implemented",
                    created_by=f"{entry.actor_type}:{entry.actor_id}",
                    implemented_at=datetime.utcnow()
                )
                db.add(decision)
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist ledger entry: {e}")
                db.rollback()
            finally:
                db.close()
        except ImportError:
            logger.debug("Database not available for ledger persistence")
    
    async def _publish_event(self, entry: LedgerEntry):
        """Publish ledger event for UI sync"""
        try:
            from backend.services.event_bus import event_bus
            await event_bus.publish(
                "ledger.written",
                "ledger",
                entry.entry_id,
                {
                    "entry_id": entry.entry_id,
                    "project_id": entry.project_id,
                    "action": entry.action,
                    "actor": f"{entry.actor_type}:{entry.actor_id}",
                    "outcome": entry.outcome,
                    "timestamp": entry.timestamp.isoformat()
                }
            )
        except Exception as e:
            logger.debug(f"Failed to publish ledger event: {e}")
    
    # =========================================================================
    # READ OPERATIONS
    # =========================================================================
    
    def get_project_ledger(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all ledger entries for a project"""
        entry_ids = self._project_index.get(project_id, [])
        entries = [e for e in self._entries if e.entry_id in entry_ids]
        
        return [self._entry_to_dict(e) for e in entries]
    
    def get_all_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent ledger entries"""
        entries = sorted(self._entries, key=lambda e: e.timestamp, reverse=True)[:limit]
        return [self._entry_to_dict(e) for e in entries]
    
    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific ledger entry"""
        for entry in self._entries:
            if entry.entry_id == entry_id:
                return self._entry_to_dict(entry)
        return None
    
    def _entry_to_dict(self, entry: LedgerEntry) -> Dict[str, Any]:
        """Convert entry to dictionary"""
        return {
            "entry_id": entry.entry_id,
            "project_id": entry.project_id,
            "action": entry.action,
            "actor_type": entry.actor_type,
            "actor_id": entry.actor_id,
            "evidence": entry.evidence,
            "reasoning": entry.reasoning,
            "outcome": entry.outcome,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp.isoformat()
        }
    
    # =========================================================================
    # QUERY OPERATIONS
    # =========================================================================
    
    def query_by_actor(self, actor_type: str, actor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query entries by actor"""
        entries = [
            e for e in self._entries
            if e.actor_type == actor_type and (actor_id is None or e.actor_id == actor_id)
        ]
        return [self._entry_to_dict(e) for e in entries]
    
    def query_by_date_range(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Query entries by date range"""
        entries = [
            e for e in self._entries
            if start <= e.timestamp <= end
        ]
        return [self._entry_to_dict(e) for e in entries]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get ledger statistics"""
        return {
            "total_entries": len(self._entries),
            "projects_tracked": len(self._project_index),
            "by_actor_type": self._count_by_actor_type(),
            "recent_24h": len([e for e in self._entries if (datetime.utcnow() - e.timestamp).total_seconds() < 86400])
        }
    
    def _count_by_actor_type(self) -> Dict[str, int]:
        """Count entries by actor type"""
        counts = {}
        for entry in self._entries:
            counts[entry.actor_type] = counts.get(entry.actor_type, 0) + 1
        return counts


# Global singleton
decision_ledger = DecisionLedger()
