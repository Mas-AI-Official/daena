"""
Poisoning Filters for Council Rounds and NBMF.

Implements defenses against:
- Message poisoning (duplicate/spam messages)
- Reputation-based filtering
- Source trust ledger
- Quarantine queue for suspicious content
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class MessageReputation:
    """Reputation score for a message source."""
    source_id: str
    reputation_score: float  # 0.0 to 1.0
    total_messages: int
    accepted_messages: int
    rejected_messages: int
    last_seen: datetime
    trust_level: str  # "trusted", "neutral", "suspicious", "blocked"
    
    def update_reputation(self, accepted: bool):
        """Update reputation based on acceptance."""
        self.total_messages += 1
        if accepted:
            self.accepted_messages += 1
        else:
            self.rejected_messages += 1
        
        # Calculate reputation score
        if self.total_messages > 0:
            self.reputation_score = self.accepted_messages / self.total_messages
        else:
            self.reputation_score = 0.5  # Neutral
        
        # Update trust level
        if self.reputation_score >= 0.8:
            self.trust_level = "trusted"
        elif self.reputation_score >= 0.5:
            self.trust_level = "neutral"
        elif self.reputation_score >= 0.3:
            self.trust_level = "suspicious"
        else:
            self.trust_level = "blocked"
        
        self.last_seen = datetime.utcnow()


class SimHashDeduplicator:
    """SimHash-based near-duplicate detection."""
    
    def __init__(self, hash_bits: int = 64):
        self.hash_bits = hash_bits
        self.seen_hashes: Set[int] = set()
        self.hash_to_source: Dict[int, List[str]] = defaultdict(list)
    
    def compute_simhash(self, content: str) -> int:
        """
        Compute SimHash for content.
        
        Simplified version - in production, use proper SimHash algorithm.
        """
        # Simple hash-based approach (replace with proper SimHash)
        content_hash = hashlib.md5(content.encode()).hexdigest()
        # Convert to integer (first 16 chars = 64 bits)
        return int(content_hash[:16], 16)
    
    def is_duplicate(self, content: str, threshold: float = 0.9) -> Tuple[bool, Optional[int]]:
        """
        Check if content is a near-duplicate.
        
        Args:
            content: Content to check
            threshold: Similarity threshold (0.0 to 1.0)
        
        Returns:
            (is_duplicate, matching_hash)
        """
        content_hash = self.compute_simhash(content)
        
        # Check exact match
        if content_hash in self.seen_hashes:
            return True, content_hash
        
        # For near-duplicate detection, would need proper SimHash with hamming distance
        # For now, just check exact matches
        return False, None
    
    def register_content(self, content: str, source_id: str):
        """Register content as seen."""
        content_hash = self.compute_simhash(content)
        self.seen_hashes.add(content_hash)
        self.hash_to_source[content_hash].append(source_id)


class PoisoningFilter:
    """
    Main poisoning filter that combines all defenses.
    """
    
    def __init__(self):
        self.simhash = SimHashDeduplicator()
        self.reputations: Dict[str, MessageReputation] = {}
        self.quarantine_queue: List[Dict[str, Any]] = []
        self.trust_ledger: List[Dict[str, Any]] = []
        self.min_reputation = 0.5  # Minimum reputation to accept message
        self.quarantine_duration = timedelta(hours=24)  # Quarantine for 24 hours
    
    def get_reputation(self, source_id: str) -> MessageReputation:
        """Get or create reputation for source."""
        if source_id not in self.reputations:
            self.reputations[source_id] = MessageReputation(
                source_id=source_id,
                reputation_score=0.5,  # Start neutral
                total_messages=0,
                accepted_messages=0,
                rejected_messages=0,
                last_seen=datetime.utcnow(),
                trust_level="neutral"
            )
        return self.reputations[source_id]
    
    def check_message(
        self,
        content: str,
        source_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if message should be accepted.
        
        Args:
            content: Message content
            source_id: Source identifier
            metadata: Optional metadata
        
        Returns:
            (accepted, reason, filter_result)
        """
        filter_result = {
            "simhash_check": None,
            "reputation_check": None,
            "quarantine_check": None,
            "final_decision": None
        }
        
        # 1. SimHash deduplication
        is_duplicate, matching_hash = self.simhash.is_duplicate(content)
        filter_result["simhash_check"] = {
            "is_duplicate": is_duplicate,
            "matching_hash": matching_hash
        }
        
        if is_duplicate:
            return False, "Duplicate content detected", filter_result
        
        # 2. Reputation check
        reputation = self.get_reputation(source_id)
        filter_result["reputation_check"] = {
            "reputation_score": reputation.reputation_score,
            "trust_level": reputation.trust_level,
            "total_messages": reputation.total_messages
        }
        
        if reputation.trust_level == "blocked":
            return False, f"Source blocked (reputation: {reputation.reputation_score:.2f})", filter_result
        
        if reputation.reputation_score < self.min_reputation:
            # Add to quarantine queue
            self.quarantine_queue.append({
                "content": content,
                "source_id": source_id,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow(),
                "reason": "Low reputation"
            })
            filter_result["quarantine_check"] = {
                "quarantined": True,
                "reason": "Low reputation"
            }
            return False, f"Quarantined due to low reputation ({reputation.reputation_score:.2f})", filter_result
        
        # 3. Register content
        self.simhash.register_content(content, source_id)
        
        # 4. Update reputation (will be updated after message is processed)
        # For now, mark as accepted
        reputation.update_reputation(accepted=True)
        
        # 5. Log to trust ledger
        self.trust_ledger.append({
            "source_id": source_id,
            "content_hash": self.simhash.compute_simhash(content),
            "accepted": True,
            "reputation_score": reputation.reputation_score,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        
        filter_result["final_decision"] = "accepted"
        return True, "Message accepted", filter_result
    
    def reject_message(self, source_id: str, reason: str):
        """Mark a message as rejected and update reputation."""
        reputation = self.get_reputation(source_id)
        reputation.update_reputation(accepted=False)
        
        # Log to trust ledger
        self.trust_ledger.append({
            "source_id": source_id,
            "accepted": False,
            "reason": reason,
            "reputation_score": reputation.reputation_score,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
    
    def get_quarantine_queue(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get items in quarantine queue."""
        # Filter expired items
        now = datetime.utcnow()
        self.quarantine_queue = [
            item for item in self.quarantine_queue
            if now - item["timestamp"] < self.quarantine_duration
        ]
        return self.quarantine_queue[:limit]
    
    def release_from_quarantine(self, content_hash: int) -> bool:
        """Release item from quarantine (if manually approved)."""
        removed = False
        for item in self.quarantine_queue[:]:
            item_hash = self.simhash.compute_simhash(item["content"])
            if item_hash == content_hash:
                self.quarantine_queue.remove(item)
                removed = True
                # Update reputation positively
                reputation = self.get_reputation(item["source_id"])
                reputation.update_reputation(accepted=True)
        return removed


# Global instance
poisoning_filter = PoisoningFilter()

