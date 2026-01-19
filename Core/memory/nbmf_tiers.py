"""
NBMF Memory Tier System (Nuanced Behavior Memory Framework)
5-tier memory architecture with write permissions and verification gates.

LAW 5 — MEMORY SANCTITY (NBMF):
- T0 Ephemeral (session)
- T1 Working (task)
- T2 Project-Stable (verified)
- T3 Institutional Defaults (Founder-approved only)
- T4 Founder-Private (Founder only)
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import json
import logging

logger = logging.getLogger(__name__)


class MemoryTier(str, Enum):
    """Memory tier levels with increasing persistence and restrictions"""
    T0_EPHEMERAL = "T0_EPHEMERAL"       # Session scratch, auto-expire
    T1_WORKING = "T1_WORKING"           # Task notes, temporary decisions
    T2_PROJECT = "T2_PROJECT"           # Stable facts, requires verification
    T3_INSTITUTIONAL = "T3_INSTITUTIONAL"  # Policies, defaults, Founder approval required
    T4_FOUNDER_PRIVATE = "T4_FOUNDER_PRIVATE"  # Masoud only


class MemoryPermission(BaseModel):
    """Write permissions per agent role"""
    agent_type: str
    can_write_t0: bool = True
    can_write_t1: bool = False
    can_write_t2: bool = False
    can_write_t3: bool = False
    can_write_t4: bool = False
    can_promote_to_t2: bool = False  # Requires verification


class MemoryEntry(BaseModel):
    """A single memory entry in the NBMF system"""
    id: str
    tier: MemoryTier
    content: str
    metadata: Dict[str, Any] = {}
    source: str  # Which agent/user created this
    created_at: datetime
    expires_at: Optional[datetime] = None
    verified: bool = False
    verification_score: Optional[float] = None
    tags: List[str] = []
    evidence: List[str] = []  # Supporting evidence/citations


class NBMFTierSystem:
    """
    NBMF Memory Tier System
    Manages tiered memory with write permissions and verification gates
    """
    
    # Default retention periods
    RETENTION_PERIODS = {
        MemoryTier.T0_EPHEMERAL: timedelta(hours=1),
        MemoryTier.T1_WORKING: timedelta(days=7),
        MemoryTier.T2_PROJECT: timedelta(days=365),
        MemoryTier.T3_INSTITUTIONAL: None,  # Permanent
        MemoryTier.T4_FOUNDER_PRIVATE: None,  # Permanent
    }
    
    def __init__(self):
        """Initialize NBMF tier system"""
        self.permissions = self._initialize_permissions()
        self.memory_store: Dict[MemoryTier, List[MemoryEntry]] = {
            tier: [] for tier in MemoryTier
        }
        logger.info("✅ NBMF Tier System initialized")
    
    def _initialize_permissions(self) -> Dict[str, MemoryPermission]:
        """Set up default write permissions per agent type"""
        return {
            "scout": MemoryPermission(
                agent_type="scout",
                can_write_t0=True,
                can_write_t1=True,
                can_write_t2=False,
                can_write_t3=False,
                can_write_t4=False,
                can_promote_to_t2=False
            ),
            "verifier": MemoryPermission(
                agent_type="verifier",
                can_write_t0=True,
                can_write_t1=True,
                can_write_t2=False,
                can_write_t3=False,
                can_write_t4=False,
                can_promote_to_t2=True  # Verifier can promote to T2
            ),
            "daena": MemoryPermission(
                agent_type="daena",
                can_write_t0=True,
                can_write_t1=True,
                can_write_t2=False,
                can_write_t3=False,  # Can propose but not apply
                can_write_t4=False,
                can_promote_to_t2=False
            ),
            "founder": MemoryPermission(
                agent_type="founder",
                can_write_t0=True,
                can_write_t1=True,
                can_write_t2=True,
                can_write_t3=True,
                can_write_t4=True,
                can_promote_to_t2=True
            )
        }
    
    def can_write(self, agent_type: str, tier: MemoryTier) -> bool:
        """Check if agent has write permission for tier"""
        perm = self.permissions.get(agent_type.lower())
        if not perm:
            return False
        
        tier_permissions = {
            MemoryTier.T0_EPHEMERAL: perm.can_write_t0,
            MemoryTier.T1_WORKING: perm.can_write_t1,
            MemoryTier.T2_PROJECT: perm.can_write_t2,
            MemoryTier.T3_INSTITUTIONAL: perm.can_write_t3,
            MemoryTier.T4_FOUNDER_PRIVATE: perm.can_write_t4,
        }
        
        return tier_permissions.get(tier, False)
    
    def store(
        self,
        tier: MemoryTier,
        content: str,
        source: str,
        metadata: Dict[str, Any] = None,
        verified: bool = False,
        verification_score: Optional[float] = None,
        tags: List[str] = None,
        evidence: List[str] = None
    ) -> Optional[MemoryEntry]:
        """
        Store a memory entry in the specified tier
        
        Args:
            tier: Memory tier to store in
            content: The content to store
            source: Agent/user who created this
            metadata: Additional metadata
            verified: Whether this has been verified
            verification_score: Verification confidence (0-100)
            tags: Tags for categorization
            evidence: Supporting evidence/citations
        
        Returns:
            MemoryEntry if successful, None if permission denied
        """
        # Check permissions
        agent_type = source.split("_")[0]  # Extract agent type from source
        if not self.can_write(agent_type, tier):
            logger.warning(f"❌ Permission denied: {source} cannot write to {tier}")
            return None
        
        # Calculate expiration
        retention = self.RETENTION_PERIODS.get(tier)
        expires_at = datetime.now() + retention if retention else None
        
        # Create entry
        entry = MemoryEntry(
            id=f"{tier.value}_{datetime.now().timestamp()}",
            tier=tier,
            content=content,
            metadata=metadata or {},
            source=source,
            created_at=datetime.now(),
            expires_at=expires_at,
            verified=verified,
            verification_score=verification_score,
            tags=tags or [],
            evidence=evidence or []
        )
        
        # Store
        self.memory_store[tier].append(entry)
        logger.info(f"✅ Stored memory in {tier}: {content[:50]}...")
        
        return entry
    
    def promote_to_t2(
        self,
        entry_id: str,
        agent_type: str,
        verification_score: float,
        evidence: List[str]
    ) -> bool:
        """
        Promote a T0/T1 entry to T2 (requires verification)
        
        Args:
            entry_id: ID of the entry to promote
            agent_type: Agent requesting promotion (must be verifier or founder)
            verification_score: Verification confidence (0-100)
            evidence: Supporting evidence
        
        Returns:
            True if promoted, False if denied
        """
        # Check permissions
        perm = self.permissions.get(agent_type.lower())
        if not perm or not perm.can_promote_to_t2:
            logger.warning(f"❌ Permission denied: {agent_type} cannot promote to T2")
            return False
        
        # Find entry in T0 or T1
        entry = None
        source_tier = None
        for tier in [MemoryTier.T0_EPHEMERAL, MemoryTier.T1_WORKING]:
            for e in self.memory_store[tier]:
                if e.id == entry_id:
                    entry = e
                    source_tier = tier
                    break
            if entry:
                break
        
        if not entry:
            logger.warning(f"❌ Entry {entry_id} not found in T0/T1")
            return False
        
        # Remove from source tier
        self.memory_store[source_tier].remove(entry)
        
        # Update entry
        entry.tier = MemoryTier.T2_PROJECT
        entry.verified = True
        entry.verification_score = verification_score
        entry.evidence = evidence
        entry.expires_at = datetime.now() + self.RETENTION_PERIODS[MemoryTier.T2_PROJECT]
        
        # Add to T2
        self.memory_store[MemoryTier.T2_PROJECT].append(entry)
        
        logger.info(f"✅ Promoted {entry_id} from {source_tier} to T2 (score: {verification_score})")
        return True
    
    def retrieve(
        self,
        tier: Optional[MemoryTier] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """
        Retrieve memory entries
        
        Args:
            tier: Filter by tier (None = all tiers)
            tags: Filter by tags
            limit: Maximum entries to return
        
        Returns:
            List of memory entries
        """
        results = []
        
        tiers_to_search = [tier] if tier else list(MemoryTier)
        
        for t in tiers_to_search:
            for entry in self.memory_store[t]:
                # Check expiration
                if entry.expires_at and entry.expires_at < datetime.now():
                    continue
                
                # Filter by tags
                if tags and not any(tag in entry.tags for tag in tags):
                    continue
                
                results.append(entry)
                
                if len(results) >= limit:
                    return results
        
        return results
    
    def cleanup_expired(self) -> int:
        """Remove expired entries from T0 and T1"""
        removed_count = 0
        now = datetime.now()
        
        for tier in [MemoryTier.T0_EPHEMERAL, MemoryTier.T1_WORKING]:
            original_count = len(self.memory_store[tier])
            self.memory_store[tier] = [
                e for e in self.memory_store[tier]
                if not e.expires_at or e.expires_at > now
            ]
            removed = original_count - len(self.memory_store[tier])
            removed_count += removed
            
            if removed > 0:
                logger.info(f"🧹 Cleaned up {removed} expired entries from {tier}")
        
        return removed_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory tier statistics"""
        return {
            "tiers": {
                tier.value: {
                    "count": len(self.memory_store[tier]),
                    "verified_count": sum(1 for e in self.memory_store[tier] if e.verified),
                    "retention": str(self.RETENTION_PERIODS[tier]) if self.RETENTION_PERIODS[tier] else "permanent"
                }
                for tier in MemoryTier
            },
            "total_entries": sum(len(entries) for entries in self.memory_store.values()),
            "last_cleanup": datetime.now().isoformat()
        }


# Global instance
nbmf_system = NBMFTierSystem()
