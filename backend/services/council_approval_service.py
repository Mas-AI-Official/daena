"""
Council Approval Service for High-Impact Decisions.

Implements approval workflow for council decisions that require human review:
- Financial decisions (resource allocation, spending, contracts)
- Security actions (policy changes, access modifications)
- Data actions (deletions, modifications)
- Reputation-sensitive actions (external communications)
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.database import SessionLocal, Decision
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DecisionImpact(Enum):
    """Decision impact levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"  # Low-impact decisions auto-approved
    EXPIRED = "expired"


class CouncilApprovalService:
    """
    Service for managing council decision approvals.
    
    High-impact decisions require approval before being committed.
    Low/medium-impact decisions can be auto-approved if confidence is high.
    """
    
    # Keywords that indicate high-impact decisions
    HIGH_IMPACT_KEYWORDS = {
        "financial": ["allocate", "spend", "budget", "contract", "payment", "invoice", "expense", "cost", "price", "revenue"],
        "security": ["access", "permission", "policy", "security", "auth", "password", "token", "key", "encryption", "disable"],
        "data": ["delete", "remove", "modify", "update", "change", "edit", "corrupt", "backup", "restore", "migrate"],
        "reputation": ["publish", "announce", "communicate", "send", "email", "message", "press", "media", "social"]
    }
    
    # Financial thresholds (in USD)
    FINANCIAL_THRESHOLD_HIGH = 10000.0
    FINANCIAL_THRESHOLD_MEDIUM = 1000.0
    
    def __init__(self):
        """Initialize the approval service."""
        self.auto_approve_low_impact = True
        self.auto_approve_high_confidence = 0.9  # Auto-approve if confidence > 0.9
        self.require_approval_for_high = True
        self.require_approval_for_critical = True
        
    def assess_impact(
        self,
        action_text: str,
        department: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DecisionImpact:
        """
        Assess the impact level of a council decision.
        
        Args:
            action_text: The action text from the council decision
            department: Department making the decision
            confidence: Confidence score (0.0-1.0)
            metadata: Additional metadata (e.g., financial_amount, data_scope)
            
        Returns:
            DecisionImpact level
        """
        action_lower = action_text.lower()
        metadata = metadata or {}
        
        # Check for critical indicators
        critical_indicators = [
            "delete all", "remove all", "disable security", "bypass auth",
            "allocate unlimited", "approve contract", "public announcement"
        ]
        if any(indicator in action_lower for indicator in critical_indicators):
            return DecisionImpact.CRITICAL
        
        # Check financial impact
        financial_amount = metadata.get("financial_amount", 0.0)
        if financial_amount >= self.FINANCIAL_THRESHOLD_HIGH:
            return DecisionImpact.HIGH
        elif financial_amount >= self.FINANCIAL_THRESHOLD_MEDIUM:
            return DecisionImpact.MEDIUM
        
        # Check for high-impact keywords
        high_impact_count = 0
        for category, keywords in self.HIGH_IMPACT_KEYWORDS.items():
            if any(keyword in action_lower for keyword in keywords):
                high_impact_count += 1
                if category == "financial" or category == "security":
                    # Financial and security actions are always high-impact
                    return DecisionImpact.HIGH
        
        # Multiple high-impact categories = HIGH
        if high_impact_count >= 2:
            return DecisionImpact.HIGH
        
        # Single high-impact category = MEDIUM
        if high_impact_count >= 1:
            return DecisionImpact.MEDIUM
        
        # Low confidence decisions are MEDIUM impact
        if confidence < 0.7:
            return DecisionImpact.MEDIUM
        
        # Security and Finance departments default to MEDIUM
        if department in ["security", "finance"]:
            return DecisionImpact.MEDIUM
        
        # Default to LOW
        return DecisionImpact.LOW
    
    def requires_approval(
        self,
        impact: DecisionImpact,
        confidence: float,
        department: str
    ) -> bool:
        """
        Determine if a decision requires approval.
        
        Args:
            impact: Impact level
            confidence: Confidence score
            department: Department making the decision
            
        Returns:
            True if approval is required, False otherwise
        """
        # Critical always requires approval
        if impact == DecisionImpact.CRITICAL:
            return True
        
        # High impact requires approval (unless auto-approve is disabled for high)
        if impact == DecisionImpact.HIGH:
            return self.require_approval_for_high
        
        # Medium impact requires approval if confidence is low
        if impact == DecisionImpact.MEDIUM:
            return confidence < 0.8
        
        # Low impact auto-approved (unless auto-approve is disabled)
        if impact == DecisionImpact.LOW:
            return not self.auto_approve_low_impact
        
        return False
    
    def create_approval_request(
        self,
        decision_id: str,
        department: str,
        topic: str,
        action_text: str,
        impact: DecisionImpact,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Decision:
        """
        Create an approval request in the database.
        
        Args:
            decision_id: Unique decision identifier
            department: Department making the decision
            topic: Decision topic
            action_text: The action to be approved
            impact: Impact level
            confidence: Confidence score
            metadata: Additional metadata
            tenant_id: Tenant identifier
            project_id: Project identifier
            
        Returns:
            Decision object
        """
        metadata = metadata or {}
        
        # Determine decision type from metadata or impact
        decision_type = metadata.get("decision_type") or self._infer_decision_type(action_text, impact)
        
        # Create decision record
        decision = Decision(
            decision_id=decision_id,
            title=f"Council Decision: {topic[:100]}",
            description=action_text,
            decision_type=decision_type,
            impact=impact.value,
            reasoning=f"Council decision from {department} department. Confidence: {confidence:.2f}",
            agents_involved=metadata.get("agents_involved", 0),
            departments_affected=[department],
            risk_assessment=self._generate_risk_assessment(impact, confidence, action_text),
            metrics_impact=metadata.get("metrics_impact", {}),
            related_projects=[project_id] if project_id else [],
            status=ApprovalStatus.PENDING.value,
            created_at=datetime.utcnow(),
            created_by=f"council_{department}"
        )
        
        # Save to database
        try:
            session = SessionLocal()
            try:
                session.add(decision)
                session.commit()
                logger.info(f"Approval request created: {decision_id} (impact: {impact.value})")
                return decision
            except Exception as e:
                session.rollback()
                logger.error(f"Error creating approval request: {e}")
                raise
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Database error creating approval request: {e}")
            # Return decision object even if DB save fails (will be retried)
            return decision
    
    def check_approval_status(
        self,
        decision_id: str
    ) -> Optional[ApprovalStatus]:
        """
        Check the approval status of a decision.
        
        Args:
            decision_id: Decision identifier
            
        Returns:
            ApprovalStatus or None if not found
        """
        try:
            session = SessionLocal()
            try:
                decision = session.query(Decision).filter(Decision.decision_id == decision_id).first()
                if decision:
                    return ApprovalStatus(decision.status)
                return None
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error checking approval status: {e}")
            return None
    
    def auto_approve_decision(
        self,
        decision_id: str,
        reason: str = "Auto-approved: Low impact or high confidence"
    ) -> bool:
        """
        Auto-approve a decision (for low-impact or high-confidence decisions).
        
        Args:
            decision_id: Decision identifier
            reason: Reason for auto-approval
            
        Returns:
            True if approved, False otherwise
        """
        try:
            session = SessionLocal()
            try:
                decision = session.query(Decision).filter(Decision.decision_id == decision_id).first()
                if decision:
                    decision.status = ApprovalStatus.AUTO_APPROVED.value
                    decision.reasoning = f"{decision.reasoning}\n\n{reason}"
                    decision.implemented_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Decision auto-approved: {decision_id}")
                    return True
                return False
            except Exception as e:
                session.rollback()
                logger.error(f"Error auto-approving decision: {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Database error auto-approving decision: {e}")
            return False
    
    def _infer_decision_type(
        self,
        action_text: str,
        impact: DecisionImpact
    ) -> str:
        """Infer decision type from action text and impact."""
        action_lower = action_text.lower()
        
        if any(kw in action_lower for kw in self.HIGH_IMPACT_KEYWORDS["financial"]):
            return "financial_decision"
        elif any(kw in action_lower for kw in self.HIGH_IMPACT_KEYWORDS["security"]):
            return "security_action"
        elif any(kw in action_lower for kw in self.HIGH_IMPACT_KEYWORDS["data"]):
            return "data_action"
        elif any(kw in action_lower for kw in self.HIGH_IMPACT_KEYWORDS["reputation"]):
            return "external_communication"
        else:
            return "general_decision"
    
    def _generate_risk_assessment(
        self,
        impact: DecisionImpact,
        confidence: float,
        action_text: str
    ) -> str:
        """Generate risk assessment text."""
        risk_levels = {
            DecisionImpact.CRITICAL: "CRITICAL",
            DecisionImpact.HIGH: "HIGH",
            DecisionImpact.MEDIUM: "MEDIUM",
            DecisionImpact.LOW: "LOW"
        }
        
        risk_level = risk_levels.get(impact, "UNKNOWN")
        confidence_level = "HIGH" if confidence >= 0.8 else "MEDIUM" if confidence >= 0.6 else "LOW"
        
        return f"Risk Level: {risk_level}\nConfidence: {confidence_level} ({confidence:.2f})\nAction: {action_text[:200]}"


# Global instance
council_approval_service = CouncilApprovalService()

