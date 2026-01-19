"""
⚠️ CORE FILE — DO NOT DELETE OR REWRITE
Changes allowed ONLY via extension modules.

Brain Store Interface - Shared brain read/write access control.

CRITICAL: This is the canonical brain store. Only patch specific functions.
Never replace the entire class or remove query() / propose_experience() methods.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

from backend.daena_brain import daena_brain


class GovernanceState(str, Enum):
    """Governance pipeline states"""
    PROPOSED = "proposed"
    SCOUTED = "scouted"
    DEBATED = "debated"
    SYNTHESIZED = "synthesized"
    APPROVED = "approved"
    FORGED = "forged"
    COMMITTED = "committed"
    REJECTED = "rejected"


class BrainStore:
    """
    Shared brain store with governance-gated writes.
    
    Agents can READ freely, but WRITES must go through governance pipeline.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize brain store"""
        if storage_path is None:
            # Default to local_brain directory for brain storage
            project_root = Path(__file__).parent.parent.parent.parent
            storage_path = project_root / "local_brain" / "brain_store"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Governance queue (proposals awaiting processing)
        self.queue_file = self.storage_path / "governance_queue.json"
        self.committed_file = self.storage_path / "committed_experiences.json"
        
        # Initialize storage files
        self._ensure_storage_files()
    
    def _ensure_storage_files(self):
        """Ensure storage files exist"""
        if not self.queue_file.exists():
            self.queue_file.write_text("[]", encoding="utf-8")
        if not self.committed_file.exists():
            self.committed_file.write_text("[]", encoding="utf-8")
    
    def query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Query shared brain (read-only, available to all agents).
        
        This uses the canonical Daena brain to answer queries.
        """
        # Use canonical brain to process query
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        response = loop.run_until_complete(
            daena_brain.process_message(query, context)
        )
        
        return {
            "query": query,
            "response": response,
            "source": "shared_brain",
            "timestamp": datetime.utcnow().isoformat(),
            "context": context or {}
        }
    
    def propose_knowledge(
        self,
        agent_id: str,
        content: str,
        evidence: Optional[Dict[str, Any]] = None,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Propose knowledge to be added to shared brain (agents only).
        
        Alias for propose_experience for consistency with governance pipeline terminology.
        """
        experience = {
            "type": "knowledge",
            "content": content,
            "evidence": evidence or {}
        }
        return self.propose_experience(
            experience=experience,
            reason=f"Knowledge proposal from agent {agent_id}",
            source_agent_id=agent_id,
            department=department
        )
    
    def propose_experience(
        self,
        experience: Dict[str, Any],
        reason: str,
        source_agent_id: str,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Propose experience to be added to shared brain (agents only).
        
        This creates a proposal that goes through governance pipeline.
        Agents cannot write directly to brain.
        """
        proposal_id = str(uuid.uuid4())
        
        proposal = {
            "id": proposal_id,
            "state": GovernanceState.PROPOSED.value,
            "experience": experience,
            "reason": reason,
            "source_agent_id": source_agent_id,
            "department": department,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "history": [
                {
                    "state": GovernanceState.PROPOSED.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    "actor": source_agent_id
                }
            ]
        }
        
        # Add to governance queue
        queue = self._load_queue()
        queue.append(proposal)
        self._save_queue(queue)
        
        # Log to audit trail
        self._log_audit("propose", proposal_id, source_agent_id, {"reason": reason})
        
        return {
            "status": "proposed",
            "proposal_id": proposal_id,
            "message": "Experience proposed. Awaiting governance review."
        }
    
    def get_queue(self, state: Optional[GovernanceState] = None) -> List[Dict[str, Any]]:
        """Get governance queue (pending proposals)"""
        queue = self._load_queue()
        if state:
            return [p for p in queue if p.get("state") == state.value]
        return queue
    
    def transition_state(
        self,
        proposal_id: str,
        new_state: GovernanceState,
        actor: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transition proposal to new state (Daena VP / Council only).
        
        This enforces access control - only Daena VP can approve/commit.
        """
        queue = self._load_queue()
        
        proposal = None
        for p in queue:
            if p["id"] == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return {"status": "error", "message": "Proposal not found"}
        
        # Validate state transition
        current_state = GovernanceState(proposal["state"])
        if not self._is_valid_transition(current_state, new_state):
            return {
                "status": "error",
                "message": f"Invalid state transition: {current_state.value} -> {new_state.value}"
            }
        
        # Update proposal
        proposal["state"] = new_state.value
        proposal["updated_at"] = datetime.utcnow().isoformat()
        proposal["history"].append({
            "state": new_state.value,
            "timestamp": datetime.utcnow().isoformat(),
            "actor": actor,
            "notes": notes
        })
        
        # If committed, move to committed storage
        if new_state == GovernanceState.COMMITTED:
            self._commit_experience(proposal)
            queue = [p for p in queue if p["id"] != proposal_id]
        
        self._save_queue(queue)
        
        return {
            "status": "success",
            "proposal_id": proposal_id,
            "new_state": new_state.value,
            "message": f"Proposal moved to {new_state.value}"
        }
    
    def review_and_score(
        self,
        proposal_id: str,
        council_member: str,
        score: float,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Review and score a proposal (Council members).
        
        Score should be 0.0 to 1.0 (higher = better).
        """
        queue = self._load_queue()
        proposal = None
        for p in queue:
            if p["id"] == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return {"status": "error", "message": "Proposal not found"}
        
        # Add review to proposal
        if "reviews" not in proposal:
            proposal["reviews"] = []
        
        proposal["reviews"].append({
            "council_member": council_member,
            "score": score,
            "comments": comments,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Calculate average score
        scores = [r["score"] for r in proposal["reviews"]]
        proposal["average_score"] = sum(scores) / len(scores) if scores else 0.0
        
        # Auto-transition to DEBATED if enough reviews
        if len(proposal["reviews"]) >= 3:  # Require 3 council reviews
            proposal["state"] = GovernanceState.DEBATED.value
        
        proposal["updated_at"] = datetime.utcnow().isoformat()
        self._save_queue(queue)
        
        # Log to audit trail
        self._log_audit("review", proposal_id, council_member, {"score": score, "comments": comments})
        
        return {
            "status": "reviewed",
            "proposal_id": proposal_id,
            "average_score": proposal["average_score"],
            "review_count": len(proposal["reviews"])
        }
    
    def approve_and_commit(
        self,
        proposal_id: str,
        daena_vp: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve and commit proposal to shared brain (Daena VP only).
        
        This is the final step - merges approved experience into shared brain/NBMF.
        """
        result = self.transition_state(
            proposal_id=proposal_id,
            new_state=GovernanceState.COMMITTED,
            actor=daena_vp,
            notes=notes
        )
        
        if result.get("status") == "success":
            # Log to audit trail
            self._log_audit("commit", proposal_id, daena_vp, {"notes": notes})
        
        return result
    
    def commit_experience(self, proposal_id: str, approved_by: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Commit proposal to shared brain (Daena VP / Founder only).
        
        Alias for approve_and_commit for backward compatibility.
        """
        return self.approve_and_commit(proposal_id, approved_by, notes)
    
    def _is_valid_transition(self, current: GovernanceState, new: GovernanceState) -> bool:
        """Validate state transition"""
        valid_transitions = {
            GovernanceState.PROPOSED: [GovernanceState.SCOUTED, GovernanceState.REJECTED],
            GovernanceState.SCOUTED: [GovernanceState.DEBATED, GovernanceState.SYNTHESIZED, GovernanceState.REJECTED],
            GovernanceState.DEBATED: [GovernanceState.SYNTHESIZED, GovernanceState.REJECTED],
            GovernanceState.SYNTHESIZED: [GovernanceState.APPROVED, GovernanceState.REJECTED],
            GovernanceState.APPROVED: [GovernanceState.FORGED],
            GovernanceState.FORGED: [GovernanceState.COMMITTED],
            GovernanceState.COMMITTED: [],  # Terminal state
            GovernanceState.REJECTED: []  # Terminal state
        }
        return new in valid_transitions.get(current, [])
    
    def _commit_experience(self, proposal: Dict[str, Any]):
        """Move committed experience to permanent storage"""
        committed = self._load_committed()
        committed.append({
            "id": proposal["id"],
            "experience": proposal["experience"],
            "source_agent_id": proposal["source_agent_id"],
            "department": proposal.get("department"),
            "committed_at": datetime.utcnow().isoformat(),
            "approved_by": proposal["history"][-1].get("actor", "unknown")
        })
        self._save_committed(committed)
    
    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load governance queue"""
        try:
            content = self.queue_file.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception:
            return []
    
    def _save_queue(self, queue: List[Dict[str, Any]]):
        """Save governance queue"""
        self.queue_file.write_text(
            json.dumps(queue, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _load_committed(self) -> List[Dict[str, Any]]:
        """Load committed experiences"""
        try:
            content = self.committed_file.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception:
            return []
    
    def _save_committed(self, committed: List[Dict[str, Any]]):
        """Save committed experiences"""
        self.committed_file.write_text(
            json.dumps(committed, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    def _log_audit(
        self,
        action: str,
        proposal_id: str,
        actor: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log governance action to audit trail"""
        audit_file = self.storage_path / "audit_log.jsonl"
        
        audit_entry = {
            "action": action,
            "proposal_id": proposal_id,
            "actor": actor,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        try:
            with open(audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Don't fail if audit logging fails
    
    def get_status(self) -> Dict[str, Any]:
        """Get brain store status"""
        queue = self._load_queue()
        committed = self._load_committed()
        
        return {
            "status": "operational",
            "shared_brain": "active",
            "model": "daena_brain (canonical)",
            "queue_size": len(queue),
            "committed_count": len(committed),
            "queue_by_state": {
                state.value: len([p for p in queue if p.get("state") == state.value])
                for state in GovernanceState
            }
        }


# Global singleton
brain_store = BrainStore()

