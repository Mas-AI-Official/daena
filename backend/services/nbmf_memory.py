"""
NBMF Memory Service - Tiered Memory System for Daena

Implements NBMF (Neural-Based Memory Framework) with 5 tiers:
- T0 Ephemeral: Current session only, auto-expires
- T1 Working: Survives session, expires in 24h
- T2 Project-stable: Persists for project duration
- T3 Institutional: Founder-approved permanent defaults
- T4 Founder-private: Encrypted, only Founder access

Enforced by Edna (Enterprise Data & Knowledge Authority).
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class MemoryTier(str, Enum):
    """NBMF Memory Tiers"""
    T0_EPHEMERAL = "T0"       # Session only
    T1_WORKING = "T1"         # 24h TTL
    T2_PROJECT = "T2"         # Project duration
    T3_INSTITUTIONAL = "T3"   # Permanent (Founder approved)
    T4_FOUNDER_PRIVATE = "T4" # Encrypted, Founder only


@dataclass
class MemoryEntry:
    """A memory entry in the NBMF system"""
    memory_id: str
    tier: MemoryTier
    key: str
    value: Any
    context: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    project_id: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class NBMFMemory:
    """
    NBMF Tiered Memory System
    
    Manages memory across 5 tiers with automatic expiration,
    promotion/demotion, and Founder approval workflow.
    """
    
    def __init__(self):
        # In-memory storage by tier (would be backed by DB in production)
        self._memory: Dict[MemoryTier, Dict[str, MemoryEntry]] = {
            tier: {} for tier in MemoryTier
        }
        self._session_id: Optional[str] = None
    
    def set_session(self, session_id: str):
        """Set current session for T0 memory scope"""
        # Clear old T0 memory when session changes
        if self._session_id and self._session_id != session_id:
            self._memory[MemoryTier.T0_EPHEMERAL] = {}
        self._session_id = session_id
    
    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================
    
    def write(
        self,
        key: str,
        value: Any,
        tier: MemoryTier = MemoryTier.T0_EPHEMERAL,
        context: Optional[Dict[str, Any]] = None,
        source: str = "system",
        project_id: Optional[str] = None
    ) -> MemoryEntry:
        """
        Write to memory at specified tier.
        
        T3/T4 writes are held as pending until Founder approves.
        """
        import uuid
        
        memory_id = f"mem-{uuid.uuid4().hex[:8]}"
        
        # Calculate expiration
        expires_at = self._calculate_expiration(tier, project_id)
        
        entry = MemoryEntry(
            memory_id=memory_id,
            tier=tier,
            key=key,
            value=value,
            context=context or {},
            source=source,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            project_id=project_id
        )
        
        # T3 and T4 require Founder approval - store as pending
        if tier in [MemoryTier.T3_INSTITUTIONAL, MemoryTier.T4_FOUNDER_PRIVATE]:
            entry = self._queue_for_approval(entry)
        else:
            self._memory[tier][key] = entry
        
        logger.info(f"📝 NBMF Write: {tier.value}/{key} (expires: {expires_at})")
        
        # Publish event for UI sync
        self._publish_memory_event("nbmf.memory_write_proposed", entry)
        
        return entry
    
    def _calculate_expiration(self, tier: MemoryTier, project_id: Optional[str] = None) -> Optional[datetime]:
        """Calculate expiration time based on tier"""
        now = datetime.utcnow()
        
        if tier == MemoryTier.T0_EPHEMERAL:
            return now + timedelta(hours=1)  # Session-scoped, 1h max
        elif tier == MemoryTier.T1_WORKING:
            return now + timedelta(hours=24)
        elif tier == MemoryTier.T2_PROJECT:
            return now + timedelta(days=30)  # 30 days or until project ends
        elif tier in [MemoryTier.T3_INSTITUTIONAL, MemoryTier.T4_FOUNDER_PRIVATE]:
            return None  # Permanent
        
        return now + timedelta(hours=1)  # Default
    
    def _queue_for_approval(self, entry: MemoryEntry) -> MemoryEntry:
        """Queue T3/T4 memory for Founder approval"""
        # Store in pending state
        pending_key = f"_pending_{entry.key}"
        self._memory[entry.tier][pending_key] = entry
        
        # Log for Founder Panel
        try:
            from backend.services.learning_service import learning_service
            learning_service.log_learning(
                learned_by="nbmf",
                category="knowledge",
                summary=f"Memory write pending approval: {entry.key}",
                details={
                    "tier": entry.tier.value,
                    "key": entry.key,
                    "value": str(entry.value)[:200],
                    "requires_approval": True
                }
            )
        except Exception as e:
            logger.warning(f"Failed to log pending approval: {e}")
        
        return entry
    
    # =========================================================================
    # READ OPERATIONS
    # =========================================================================
    
    def read(
        self,
        key: str,
        tier: Optional[MemoryTier] = None,
        default: Any = None
    ) -> Any:
        """
        Read from memory.
        
        If tier not specified, searches from T0 up to T3 (T4 requires explicit access).
        """
        search_tiers = [tier] if tier else [
            MemoryTier.T0_EPHEMERAL,
            MemoryTier.T1_WORKING,
            MemoryTier.T2_PROJECT,
            MemoryTier.T3_INSTITUTIONAL
        ]
        
        for t in search_tiers:
            if key in self._memory[t]:
                entry = self._memory[t][key]
                
                # Check expiration
                if entry.expires_at and entry.expires_at < datetime.utcnow():
                    del self._memory[t][key]
                    continue
                
                # Update access stats
                entry.access_count += 1
                entry.last_accessed = datetime.utcnow()
                
                return entry.value
        
        return default
    
    def read_all(self, tier: MemoryTier) -> Dict[str, Any]:
        """Read all entries from a tier"""
        self._cleanup_expired(tier)
        return {
            key: entry.value 
            for key, entry in self._memory[tier].items()
            if not key.startswith("_pending_")
        }
    
    def _cleanup_expired(self, tier: MemoryTier):
        """Remove expired entries from tier"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._memory[tier].items()
            if entry.expires_at and entry.expires_at < now
        ]
        for key in expired_keys:
            del self._memory[tier][key]
    
    # =========================================================================
    # TIER MANAGEMENT
    # =========================================================================
    
    def promote(self, key: str, from_tier: MemoryTier, to_tier: MemoryTier) -> bool:
        """Promote memory to higher tier (requires approval for T3+)"""
        if key not in self._memory[from_tier]:
            return False
        
        entry = self._memory[from_tier][key]
        del self._memory[from_tier][key]
        
        entry.tier = to_tier
        entry.expires_at = self._calculate_expiration(to_tier)
        
        if to_tier in [MemoryTier.T3_INSTITUTIONAL, MemoryTier.T4_FOUNDER_PRIVATE]:
            self._queue_for_approval(entry)
        else:
            self._memory[to_tier][key] = entry
        
        logger.info(f"📊 NBMF Promote: {key} from {from_tier.value} to {to_tier.value}")
        return True
    
    def approve(self, key: str, tier: MemoryTier, approved_by: str = "founder") -> bool:
        """Approve pending T3/T4 memory (Founder only)"""
        pending_key = f"_pending_{key}"
        
        if pending_key not in self._memory[tier]:
            return False
        
        entry = self._memory[tier][pending_key]
        del self._memory[tier][pending_key]
        
        entry.approved_by = approved_by
        entry.approved_at = datetime.utcnow()
        
        self._memory[tier][key] = entry
        
        logger.info(f"✅ NBMF Approved: {tier.value}/{key} by {approved_by}")
        self._publish_memory_event("nbmf.memory_write_applied", entry)
        
        return True
    
    def reject(self, key: str, tier: MemoryTier) -> bool:
        """Reject pending T3/T4 memory"""
        pending_key = f"_pending_{key}"
        
        if pending_key in self._memory[tier]:
            del self._memory[tier][pending_key]
            logger.info(f"❌ NBMF Rejected: {tier.value}/{key}")
            return True
        return False
    
    # =========================================================================
    # PROJECT SCOPING
    # =========================================================================
    
    def clear_project_memory(self, project_id: str):
        """Clear all T2 memory for a completed project"""
        keys_to_remove = []
        for key, entry in self._memory[MemoryTier.T2_PROJECT].items():
            if entry.project_id == project_id:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._memory[MemoryTier.T2_PROJECT][key]
        
        logger.info(f"🧹 NBMF: Cleared {len(keys_to_remove)} entries for project {project_id}")
    
    def get_project_memory(self, project_id: str) -> Dict[str, Any]:
        """Get all memory for a project"""
        return {
            key: entry.value
            for key, entry in self._memory[MemoryTier.T2_PROJECT].items()
            if entry.project_id == project_id
        }
    
    # =========================================================================
    # UTILS
    # =========================================================================
    
    def _publish_memory_event(self, event_type: str, entry: MemoryEntry):
        """Publish memory event for UI sync"""
        try:
            import asyncio
            from backend.services.event_bus import event_bus
            
            asyncio.create_task(event_bus.publish(
                event_type,
                "nbmf",
                entry.memory_id,
                {
                    "memory_id": entry.memory_id,
                    "tier": entry.tier.value,
                    "key": entry.key,
                    "source": entry.source,
                    "requires_approval": entry.tier in [MemoryTier.T3_INSTITUTIONAL, MemoryTier.T4_FOUNDER_PRIVATE] and not entry.approved_by
                }
            ))
        except Exception as e:
            logger.debug(f"Failed to publish memory event: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        stats = {}
        for tier in MemoryTier:
            entries = self._memory[tier]
            pending = sum(1 for k in entries if k.startswith("_pending_"))
            stats[tier.value] = {
                "count": len(entries) - pending,
                "pending": pending
            }
        return stats
    
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get all pending T3/T4 approvals"""
        pending = []
        for tier in [MemoryTier.T3_INSTITUTIONAL, MemoryTier.T4_FOUNDER_PRIVATE]:
            for key, entry in self._memory[tier].items():
                if key.startswith("_pending_"):
                    pending.append({
                        "memory_id": entry.memory_id,
                        "tier": tier.value,
                        "key": entry.key,
                        "value": str(entry.value)[:200],
                        "source": entry.source,
                        "created_at": entry.created_at.isoformat()
                    })
        return pending


# Global singleton
nbmf_memory = NBMFMemory()


# Convenience functions
def remember(key: str, value: Any, tier: str = "T1", **kwargs) -> MemoryEntry:
    """Quick write to memory"""
    tier_enum = MemoryTier(tier) if isinstance(tier, str) else tier
    return nbmf_memory.write(key, value, tier_enum, **kwargs)


def recall(key: str, default: Any = None) -> Any:
    """Quick read from memory"""
    return nbmf_memory.read(key, default=default)
