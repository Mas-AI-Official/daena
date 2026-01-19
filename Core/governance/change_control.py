"""
Change Control System
Manages proposals, testing, and Founder approval for HARD-CODE policy changes.

LAW 4 — FOUNDER ABSOLUTE OVERRIDE:
Any HARD-CODE change requires explicit Founder (Masoud) approval.
Daena may propose changes but cannot apply them unilaterally.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


class ChangeProposalStatus(str, Enum):
    """Status of a change proposal"""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    ROLLED_BACK = "rolled_back"


class ChangeProposal(BaseModel):
    """A proposal to change HARD-CODE policy or T3 memory"""
    id: str
    title: str
    description: str
    what_changes: str  # What is being changed
    why_changes: str  # Rationale
    impact_analysis: str  # Impact on system
    risks: List[str]  # Known risks
    rollback_plan: str  # How to undo
    evaluation_criteria: List[str]  # How to measure success
    proposed_by: str  # Agent/user who proposed
    proposed_at: datetime
    status: ChangeProposalStatus
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    test_results: Dict[str, Any] = {}
    implementation_notes: Optional[str] = None


class ChangeControlSystem:
    """
    Change Control System - Governance for HARD-CODE changes
    
    Workflow:
    1. Proposal → Impact analysis → Test → Founder Approval
    2. If approved, apply change
    3. If not approved, keep as proposal only
    """
    
    FOUNDER_ID = "masoud"  # Only Masoud can approve T3+ changes
    
    def __init__(self):
        """Initialize change control system"""
        self.proposals: Dict[str, ChangeProposal] = {}
        self.hard_code_policies: Dict[str, str] = self._initialize_hard_policies()
        logger.info("✅ Change Control System initialized")
    
    def _initialize_hard_policies(self) -> Dict[str, str]:
        """Initialize HARD-CODE policies that require approval to change"""
        return {
            "LAW_1_REALITY_FIRST": "No claim enters durable memory without verification",
            "LAW_2_EXECUTION_OVER_AESTHETICS": "Prefer actions, artifacts, code over motivational text",
            "LAW_3_NO_COSPLAY": "Agents do not roleplay celebrities - use DCPs",
            "LAW_4_FOUNDER_OVERRIDE": "Any HARD-CODE change requires Founder approval",
            "LAW_5_MEMORY_SANCTITY": "NBMF tiers: T0-T4 with strict write permissions",
            "LAW_6_ROUTER_AWARENESS": "Every agent adapts prompts to target model",
            "LAW_7_SCOUT_VERIFY_SYNTHESIZE": "Raw data never goes directly to synthesis",
            "LAW_8_SAFE_IMPROVEMENT": "Upgrades require testing, metrics, and logging",
            "LAW_9_LOW_LATENCY": "Prefer short, modular messages"
        }
    
    def create_proposal(
        self,
        title: str,
        description: str,
        what_changes: str,
        why_changes: str,
        impact_analysis: str,
        risks: List[str],
        rollback_plan: str,
        evaluation_criteria: List[str],
        proposed_by: str
    ) -> ChangeProposal:
        """
        Create a new change proposal
        
        Args:
            title: Short title
            description: Detailed description
            what_changes: What is being modified
            why_changes: Rationale
            impact_analysis: Expected impact
            risks: Known risks
            rollback_plan: How to undo
            evaluation_criteria: Success metrics
            proposed_by: Who is proposing (e.g., "daena", "masoud")
        
        Returns:
            ChangeProposal
        """
        proposal = ChangeProposal(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            what_changes=what_changes,
            why_changes=why_changes,
            impact_analysis=impact_analysis,
            risks=risks,
            rollback_plan=rollback_plan,
            evaluation_criteria=evaluation_criteria,
            proposed_by=proposed_by,
            proposed_at=datetime.now(),
            status=ChangeProposalStatus.DRAFT
        )
        
        self.proposals[proposal.id] = proposal
        logger.info(f"📝 Created change proposal: {title}")
        
        return proposal
    
    def submit_for_approval(self, proposal_id: str) -> bool:
        """
        Submit proposal for Founder approval
        
        Args:
            proposal_id: ID of the proposal
        
        Returns:
            True if submitted, False if not found or invalid
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            logger.warning(f"Proposal {proposal_id} not found")
            return False
        
        if proposal.status != ChangeProposalStatus.DRAFT:
            logger.warning(f"Proposal {proposal_id} is not in DRAFT status")
            return False
        
        # Check required fields
        if not proposal.rollback_plan:
            logger.warning("Rollback plan is required")
            return False
        
        if not proposal.evaluation_criteria:
            logger.warning("Evaluation criteria required")
            return False
        
        proposal.status = ChangeProposalStatus.PENDING_APPROVAL
        logger.info(f"📤 Submitted proposal for approval: {proposal.title}")
        
        return True
    
    def approve(
        self,
        proposal_id: str,
        approver: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Approve a change proposal (Founder only)
        
        Args:
            proposal_id: ID of proposal to approve
            approver: Must be FOUNDER_ID
            notes: Optional approval notes
        
        Returns:
            True if approved, False if denied
        """
        # Check approver is Founder
        if approver.lower() != self.FOUNDER_ID:
            logger.warning(f"❌ Only Founder can approve changes, not: {approver}")
            return False
        
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            logger.warning(f"Proposal {proposal_id} not found")
            return False
        
        if proposal.status != ChangeProposalStatus.PENDING_APPROVAL:
            logger.warning(f"Proposal {proposal_id} is not pending approval")
            return False
        
        # Approve
        proposal.status = ChangeProposalStatus.APPROVED
        proposal.approved_by = approver
        proposal.approved_at = datetime.now()
        if notes:
            proposal.implementation_notes = notes
        
        logger.info(f"✅ APPROVED by Founder: {proposal.title}")
        
        return True
    
    def reject(
        self,
        proposal_id: str,
        rejector: str,
        reason: str
    ) -> bool:
        """
        Reject a change proposal
        
        Args:
            proposal_id: ID of proposal to reject
            rejector: Who is rejecting
            reason: Reason for rejection
        
        Returns:
            True if rejected, False if not found
        """
        if rejector.lower() != self.FOUNDER_ID:
            logger.warning(f"Only Founder can reject changes, not: {rejector}")
            return False
        
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        proposal.status = ChangeProposalStatus.REJECTED
        proposal.implementation_notes = f"REJECTED: {reason}"
        
        logger.info(f"❌ REJECTED by Founder: {proposal.title} - {reason}")
        
        return True
    
    def implement(
        self,
        proposal_id: str,
        test_results: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark proposal as implemented (after approval)
        
        Args:
            proposal_id: ID of approved proposal
            test_results: Results of testing
        
        Returns:
            True if marked implemented, False otherwise
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        if proposal.status != ChangeProposalStatus.APPROVED:
            logger.warning(f"Cannot implement non-approved proposal: {proposal.title}")
            return False
        
        proposal.status = ChangeProposalStatus.IMPLEMENTED
        if test_results:
            proposal.test_results = test_results
        
        logger.info(f"✅ IMPLEMENTED: {proposal.title}")
        
        return True
    
    def rollback(
        self,
        proposal_id: str,
        reason: str
    ) -> bool:
        """
        Rollback an implemented change
        
        Args:
            proposal_id: ID of implemented proposal
            reason: Reason for rollback
        
        Returns:
            True if rolled back, False otherwise
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        if proposal.status != ChangeProposalStatus.IMPLEMENTED:
            logger.warning(f"Cannot rollback non-implemented proposal")
            return False
        
        proposal.status = ChangeProposalStatus.ROLLED_BACK
        proposal.implementation_notes = f"ROLLED BACK: {reason}"
        
        logger.warning(f"⏪ ROLLED BACK: {proposal.title} - {reason}")
        
        return True
    
    def get_pending_approvals(self) -> List[ChangeProposal]:
        """Get all proposals pending Founder approval"""
        return [
            p for p in self.proposals.values()
            if p.status == ChangeProposalStatus.PENDING_APPROVAL
        ]
    
    def get_proposal(self, proposal_id: str) -> Optional[ChangeProposal]:
        """Get a specific proposal"""
        return self.proposals.get(proposal_id)
    
    def list_all_proposals(
        self,
        status_filter: Optional[ChangeProposalStatus] = None
    ) -> List[ChangeProposal]:
        """
        List all proposals, optionally filtered by status
        
        Args:
            status_filter: Optional status to filter by
        
        Returns:
            List of proposals
        """
        if status_filter:
            return [
                p for p in self.proposals.values()
                if p.status == status_filter
            ]
        return list(self.proposals.values())
    
    def get_hard_policies(self) -> Dict[str, str]:
        """Get all HARD-CODE policies"""
        return self.hard_code_policies.copy()
    
    def check_policy_compliance(
        self,
        proposed_change: str
    ) -> Dict[str, Any]:
        """
        Check if a proposed change violates any HARD-CODE policies
        
        Args:
            proposed_change: Description of the proposed change
        
        Returns:
            Compliance check results
        """
        violations = []
        
        # Check for policy keywords
        change_lower = proposed_change.lower()
        
        for policy_id, policy_text in self.hard_code_policies.items():
            # Simple keyword matching (in production, use NLP)
            if any(keyword in change_lower for keyword in ["without verification", "skip verify", "bypass"]):
                if policy_id == "LAW_1_REALITY_FIRST":
                    violations.append({
                        "policy": policy_id,
                        "reason": "Change may bypass verification requirement"
                    })
        
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "requires_approval": True  # All HARD-CODE changes require approval
        }


# Global instance
change_control = ChangeControlSystem()
