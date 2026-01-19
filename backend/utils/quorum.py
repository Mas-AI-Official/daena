"""
Quorum Calculation for Hex-Mesh Communication.

Implements quorum logic for consensus:
- Local quorum: 4/6 neighbors required
- Global quorum: CMP fallback required
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class QuorumType(Enum):
    """Type of quorum."""
    LOCAL = "local"  # 4/6 neighbors
    GLOBAL = "global"  # CMP fallback
    RING = "ring"  # Ring-level consensus
    RADIAL = "radial"  # Radial arm consensus


@dataclass
class QuorumVote:
    """A vote in a quorum."""
    voter_id: str
    vote: bool  # True = approve, False = reject
    confidence: float = 1.0
    timestamp: float = None
    
    def __post_init__(self):
        import time
        if self.timestamp is None:
            self.timestamp = time.time()


class QuorumManager:
    """
    Manages quorum calculations for consensus decisions.
    
    Quorum rules:
    - Local: 4/6 neighbors must approve
    - Global: CMP fallback required
    - Ring: Majority of ring members
    - Radial: Majority of radial arm
    """
    
    def __init__(self):
        self.active_quorums: Dict[str, Dict[str, QuorumVote]] = {}
        self.quorum_history: List[Dict[str, any]] = []
        self.max_history = 1000
        self.cell_neighbors: Dict[str, Set[str]] = {}  # cell_id -> set of neighbor_ids
        
    def set_cell_neighbors(self, cell_id: str, neighbors: List[str]) -> None:
        """Set neighbors for a cell (for LOCAL quorum validation)."""
        self.cell_neighbors[cell_id] = set(neighbors)
        logger.debug(f"Set {len(neighbors)} neighbors for cell {cell_id}")
    
    def get_cell_neighbors(self, cell_id: str) -> Set[str]:
        """Get neighbors for a cell."""
        return self.cell_neighbors.get(cell_id, set())
    
    def start_quorum(
        self,
        quorum_id: str,
        quorum_type: QuorumType,
        required_votes: Optional[int] = None,
        timeout_seconds: float = 30.0,
        cell_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Start a new quorum.
        
        Args:
            quorum_id: Unique identifier for this quorum
            quorum_type: Type of quorum (LOCAL, GLOBAL, RING, RADIAL)
            required_votes: Override default required votes
            timeout_seconds: Timeout for quorum completion
            cell_id: Cell ID for LOCAL quorum (to track neighbors)
        """
        # Calculate default required votes based on type
        if required_votes is None:
            if quorum_type == QuorumType.LOCAL:
                required_votes = 4  # 4/6 neighbors
            elif quorum_type == QuorumType.GLOBAL:
                required_votes = 1  # CMP fallback (single vote)
            elif quorum_type == QuorumType.RING:
                required_votes = 3  # Majority of ring (simplified)
            elif quorum_type == QuorumType.RADIAL:
                required_votes = 2  # Majority of radial arm (simplified)
            else:
                required_votes = 1
        
        import time
        self.active_quorums[quorum_id] = {
            "quorum_type": quorum_type,
            "required_votes": required_votes,
            "timeout": timeout_seconds,
            "votes": {},
            "start_time": time.time(),
            "cell_id": cell_id,  # Store cell_id for neighbor validation
            "neighbors": self.get_cell_neighbors(cell_id) if cell_id else set()
        }
        
        neighbor_count = len(self.active_quorums[quorum_id]["neighbors"])
        logger.info(f"Started quorum {quorum_id} ({quorum_type.value}), requires {required_votes} votes, cell={cell_id}, neighbors={neighbor_count}")
        
        return {
            "quorum_id": quorum_id,
            "quorum_type": quorum_type.value,
            "required_votes": required_votes,
            "timeout": timeout_seconds,
            "cell_id": cell_id,
            "neighbor_count": neighbor_count
        }
    
    def cast_vote(
        self,
        quorum_id: str,
        voter_id: str,
        vote: bool,
        confidence: float = 1.0
    ) -> Dict[str, any]:
        """
        Cast a vote in a quorum.
        
        Returns:
            Dict with quorum status and whether quorum is reached
        """
        if quorum_id not in self.active_quorums:
            return {
                "error": "Quorum not found",
                "quorum_id": quorum_id
            }
        
        quorum = self.active_quorums[quorum_id]
        
        # Check timeout
        import time
        elapsed = time.time() - quorum["start_time"]
        if elapsed > quorum["timeout"]:
            return {
                "error": "Quorum timeout",
                "quorum_id": quorum_id,
                "elapsed": elapsed
            }
        
        # For LOCAL quorum, validate that voter is a neighbor
        if quorum["quorum_type"] == QuorumType.LOCAL:
            neighbors = quorum.get("neighbors", set())
            if neighbors and voter_id not in neighbors:
                logger.warning(f"Vote from non-neighbor {voter_id} in LOCAL quorum {quorum_id} (neighbors: {neighbors})")
                # Still record vote but mark as invalid for quorum calculation
                # In strict mode, we might reject this vote
        
        # Record vote
        quorum["votes"][voter_id] = QuorumVote(
            voter_id=voter_id,
            vote=vote,
            confidence=confidence
        )
        
        # Check if quorum is reached
        # For LOCAL quorum, only count votes from neighbors
        if quorum["quorum_type"] == QuorumType.LOCAL:
            neighbors = quorum.get("neighbors", set())
            if neighbors:
                # Only count votes from neighbors
                neighbor_votes = {vid: v for vid, v in quorum["votes"].items() if vid in neighbors}
                approve_votes = sum(1 for v in neighbor_votes.values() if v.vote)
                reject_votes = sum(1 for v in neighbor_votes.values() if not v.vote)
                total_votes = len(neighbor_votes)
            else:
                # No neighbors set, count all votes (fallback)
                approve_votes = sum(1 for v in quorum["votes"].values() if v.vote)
                reject_votes = sum(1 for v in quorum["votes"].values() if not v.vote)
                total_votes = len(quorum["votes"])
        else:
            # For other quorum types, count all votes
            approve_votes = sum(1 for v in quorum["votes"].values() if v.vote)
            reject_votes = sum(1 for v in quorum["votes"].values() if not v.vote)
            total_votes = len(quorum["votes"])
        
        required = quorum["required_votes"]
        
        quorum_reached = approve_votes >= required
        
        result = {
            "quorum_id": quorum_id,
            "voter_id": voter_id,
            "vote": vote,
            "total_votes": total_votes,
            "approve_votes": approve_votes,
            "reject_votes": reject_votes,
            "required_votes": required,
            "quorum_reached": quorum_reached,
            "consensus": approve_votes > reject_votes if total_votes > 0 else False,
            "is_neighbor": voter_id in quorum.get("neighbors", set()) if quorum["quorum_type"] == QuorumType.LOCAL else True
        }
        
        if quorum_reached:
            # Close quorum and move to history
            self._close_quorum(quorum_id, result)
        
        logger.info(f"Vote cast in quorum {quorum_id}: {vote} by {voter_id}, quorum_reached={quorum_reached}")
        
        return result
    
    def get_quorum_status(self, quorum_id: str) -> Dict[str, any]:
        """Get current status of a quorum."""
        if quorum_id not in self.active_quorums:
            return {"error": "Quorum not found", "quorum_id": quorum_id}
        
        quorum = self.active_quorums[quorum_id]
        votes = quorum["votes"]
        
        # For LOCAL quorum, only count neighbor votes
        if quorum["quorum_type"] == QuorumType.LOCAL:
            neighbors = quorum.get("neighbors", set())
            if neighbors:
                neighbor_votes = {vid: v for vid, v in votes.items() if vid in neighbors}
                approve_votes = sum(1 for v in neighbor_votes.values() if v.vote)
                reject_votes = sum(1 for v in neighbor_votes.values() if not v.vote)
                total_votes = len(neighbor_votes)
                valid_voters = list(neighbor_votes.keys())
                invalid_voters = [vid for vid in votes.keys() if vid not in neighbors]
            else:
                approve_votes = sum(1 for v in votes.values() if v.vote)
                reject_votes = sum(1 for v in votes.values() if not v.vote)
                total_votes = len(votes)
                valid_voters = list(votes.keys())
                invalid_voters = []
        else:
            approve_votes = sum(1 for v in votes.values() if v.vote)
            reject_votes = sum(1 for v in votes.values() if not v.vote)
            total_votes = len(votes)
            valid_voters = list(votes.keys())
            invalid_voters = []
        
        import time
        elapsed = time.time() - quorum["start_time"]
        
        return {
            "quorum_id": quorum_id,
            "quorum_type": quorum["quorum_type"].value,
            "cell_id": quorum.get("cell_id"),
            "neighbor_count": len(quorum.get("neighbors", set())),
            "total_votes": total_votes,
            "approve_votes": approve_votes,
            "reject_votes": reject_votes,
            "required_votes": quorum["required_votes"],
            "quorum_reached": approve_votes >= quorum["required_votes"],
            "elapsed_seconds": elapsed,
            "timeout_seconds": quorum["timeout"],
            "valid_voters": valid_voters,
            "invalid_voters": invalid_voters if quorum["quorum_type"] == QuorumType.LOCAL else []
        }
    
    def _close_quorum(self, quorum_id: str, result: Dict[str, any]) -> None:
        """Close a quorum and move to history."""
        if quorum_id not in self.active_quorums:
            return
        
        quorum = self.active_quorums.pop(quorum_id)
        
        history_entry = {
            "quorum_id": quorum_id,
            "quorum_type": quorum["quorum_type"].value,
            "result": result,
            "votes": {voter_id: {"vote": vote.vote, "confidence": vote.confidence} 
                     for voter_id, vote in quorum["votes"].items()},
            "closed_at": result.get("timestamp", None) or __import__("time").time()
        }
        
        self.quorum_history.append(history_entry)
        if len(self.quorum_history) > self.max_history:
            self.quorum_history.pop(0)
        
        logger.info(f"Closed quorum {quorum_id}, result: {result.get('quorum_reached', False)}")
    
    def get_history(self, limit: int = 100) -> List[Dict[str, any]]:
        """Get quorum history."""
        return self.quorum_history[-limit:] if self.quorum_history else []
    
    def get_stats(self) -> Dict[str, any]:
        """Get quorum statistics."""
        total_quorums = len(self.quorum_history)
        successful_quorums = sum(1 for q in self.quorum_history if q.get("result", {}).get("quorum_reached", False))
        
        return {
            "active_quorums": len(self.active_quorums),
            "total_quorums": total_quorums,
            "successful_quorums": successful_quorums,
            "success_rate": successful_quorums / total_quorums if total_quorums > 0 else 0.0
        }


# Global instance
quorum_manager = QuorumManager()

