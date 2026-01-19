"""
TrustManager v2 with Enterprise-DNA Immune system integration.
Consumes Immune events to adjust trust thresholds, force quorum, or quarantine.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from memory_service.trust_manager import TrustManager, TrustAssessment
from backend.models.enterprise_dna import ThreatLevel, ImmuneAction

logger = logging.getLogger(__name__)


class TrustManagerV2(TrustManager):
    """
    Enhanced TrustManager that integrates with DNA Immune system.
    
    Features:
    - Adjusts trust thresholds based on Immune events
    - Forces quorum requirements when threats detected
    - Enforces quarantine based on Immune recommendations
    - Tracks threat history per tenant
    """
    
    def __init__(
        self,
        *,
        min_consensus: int = 2,
        max_halluc_score: float = 0.35,
        promote_threshold: float = 0.35,
        divergence_threshold: float = 0.3,
        critical_abort_thresholds: Optional[Dict[str, float]] = None,
        immune_integration: bool = True,
    ) -> None:
        super().__init__(
            min_consensus=min_consensus,
            max_halluc_score=max_halluc_score,
            promote_threshold=promote_threshold,
            divergence_threshold=divergence_threshold,
            critical_abort_thresholds=critical_abort_thresholds
        )
        
        self.immune_integration = immune_integration
        self.tenant_threat_history: Dict[str, List[Dict[str, Any]]] = {}
        self.tenant_quarantine_flags: Dict[str, bool] = {}
        self.tenant_quorum_requirements: Dict[str, int] = {}  # tenant_id -> min_consensus
        self.tenant_trust_adjustments: Dict[str, float] = {}  # tenant_id -> adjustment (-1.0 to 1.0)
        
        # Load recent Immune events if available
        if immune_integration:
            self._load_recent_immune_events()
    
    def _load_recent_immune_events(self):
        """Load recent Immune events and apply to TrustManager state."""
        try:
            from backend.services.enterprise_dna_service import get_dna_service
            
            dna_service = get_dna_service()
            if not dna_service:
                return
            
            # Load events for all tenants (in production, would iterate over active tenants)
            # For now, we'll load on-demand when needed
            logger.debug("Immune event loading available (on-demand)")
        except ImportError:
            logger.warning("DNA service not available for Immune event loading")
    
    def apply_immune_event(
        self,
        tenant_id: str,
        quarantine_required: bool,
        quorum_required: bool,
        trust_score_adjustment: float,
        threat_level: Optional[ThreatLevel] = None
    ):
        """
        Apply an Immune event to adjust TrustManager behavior.
        
        Args:
            tenant_id: Tenant identifier
            quarantine_required: Whether to force quarantine
            quorum_required: Whether to require quorum
            trust_score_adjustment: Trust score adjustment (-1.0 to 1.0)
            threat_level: Threat severity level
        """
        # Record threat in history
        if tenant_id not in self.tenant_threat_history:
            self.tenant_threat_history[tenant_id] = []
        
        self.tenant_threat_history[tenant_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "quarantine_required": quarantine_required,
            "quorum_required": quorum_required,
            "trust_score_adjustment": trust_score_adjustment,
            "threat_level": threat_level.value if threat_level else None
        })
        
        # Keep only last 100 events per tenant
        if len(self.tenant_threat_history[tenant_id]) > 100:
            self.tenant_threat_history[tenant_id] = self.tenant_threat_history[tenant_id][-100:]
        
        # Apply quarantine flag
        if quarantine_required:
            self.tenant_quarantine_flags[tenant_id] = True
            logger.warning(f"Tenant {tenant_id} quarantined by Immune system")
        
        # Apply quorum requirement
        if quorum_required:
            # Increase minimum consensus requirement
            current_quorum = self.tenant_quorum_requirements.get(tenant_id, self.min_consensus)
            self.tenant_quorum_requirements[tenant_id] = max(current_quorum, self.min_consensus + 1)
            logger.info(f"Tenant {tenant_id} requires quorum: {self.tenant_quorum_requirements[tenant_id]} consensus")
        
        # Apply trust score adjustment
        current_adjustment = self.tenant_trust_adjustments.get(tenant_id, 0.0)
        new_adjustment = max(-1.0, min(1.0, current_adjustment + trust_score_adjustment))
        self.tenant_trust_adjustments[tenant_id] = new_adjustment
        
        if abs(trust_score_adjustment) > 0.1:
            logger.info(f"Tenant {tenant_id} trust adjustment: {new_adjustment:.2f}")
    
    def is_quarantined(self, tenant_id: str) -> bool:
        """Check if tenant is quarantined."""
        return self.tenant_quarantine_flags.get(tenant_id, False)
    
    def requires_quorum(self, tenant_id: str) -> bool:
        """Check if tenant requires quorum."""
        return tenant_id in self.tenant_quorum_requirements
    
    def get_required_consensus(self, tenant_id: str) -> int:
        """Get required consensus count for tenant (may be higher than default)."""
        return self.tenant_quorum_requirements.get(tenant_id, self.min_consensus)
    
    def get_trust_adjustment(self, tenant_id: str) -> float:
        """Get trust score adjustment for tenant."""
        return self.tenant_trust_adjustments.get(tenant_id, 0.0)
    
    def assess_with_immune(
        self,
        cls: str,
        candidate: Any,
        tenant_id: Optional[str] = None,
        reference: Optional[Any] = None,
        *,
        hallucination_scores: Optional[List[float]] = None,
        related_texts: Optional[List[str]] = None,
    ) -> TrustAssessment:
        """
        Assess trust with Immune system integration.
        
        If tenant is quarantined, automatically fails assessment.
        If tenant requires quorum, increases consensus requirement.
        Applies trust score adjustments from Immune events.
        """
        # Check quarantine
        if tenant_id and self.is_quarantined(tenant_id):
            logger.warning(f"Assessment blocked: tenant {tenant_id} is quarantined")
            return TrustAssessment(
                cls=cls,
                score=0.0,
                divergence=1.0,
                consensus=0.0,
                safety=0.0,
                issues=["quarantined_by_immune_system"],
                details={"tenant_id": tenant_id, "quarantined": True},
                promote=False
            )
        
        # Get base assessment
        assessment = self.assess(
            cls=cls,
            candidate=candidate,
            reference=reference,
            hallucination_scores=hallucination_scores,
            related_texts=related_texts
        )
        
        # Apply trust adjustment if tenant has Immune events
        if tenant_id:
            adjustment = self.get_trust_adjustment(tenant_id)
            if abs(adjustment) > 0.01:
                # Adjust score (clamp to 0.0-1.0)
                original_score = assessment.score
                assessment.score = max(0.0, min(1.0, assessment.score + adjustment))
                logger.debug(f"Trust score adjusted for {tenant_id}: {original_score:.3f} -> {assessment.score:.3f} (adjustment: {adjustment:+.3f})")
            
            # Check quorum requirement
            if self.requires_quorum(tenant_id):
                required_consensus = self.get_required_consensus(tenant_id)
                # If we don't have enough consensus, don't promote
                if assessment.consensus < (required_consensus / (required_consensus + 1)):
                    assessment.promote = False
                    assessment.issues.append("insufficient_quorum")
                    assessment.details["quorum_required"] = required_consensus
                    assessment.details["current_consensus"] = assessment.consensus
        
        return assessment
    
    def should_promote_with_immune(
        self,
        value: Any,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Check if promotion should occur, considering Immune system state.
        
        Args:
            value: TrustAssessment or float trust score
            tenant_id: Optional tenant identifier
        
        Returns:
            True if promotion should occur
        """
        # Check quarantine first
        if tenant_id and self.is_quarantined(tenant_id):
            return False
        
        # Get base promotion decision
        should_promote = self.should_promote(value)
        
        if not should_promote:
            return False
        
        # Apply trust adjustment
        if tenant_id:
            adjustment = self.get_trust_adjustment(tenant_id)
            if isinstance(value, TrustAssessment):
                adjusted_score = max(0.0, min(1.0, value.score + adjustment))
                should_promote = adjusted_score >= self.promote_threshold
            elif isinstance(value, (int, float)):
                adjusted_score = max(0.0, min(1.0, value + adjustment))
                should_promote = adjusted_score >= self.promote_threshold
        
        return should_promote
    
    def clear_quarantine(self, tenant_id: str):
        """Clear quarantine flag for tenant (manual override)."""
        if tenant_id in self.tenant_quarantine_flags:
            del self.tenant_quarantine_flags[tenant_id]
            logger.info(f"Quarantine cleared for tenant {tenant_id}")
    
    def clear_quorum_requirement(self, tenant_id: str):
        """Clear quorum requirement for tenant."""
        if tenant_id in self.tenant_quorum_requirements:
            del self.tenant_quorum_requirements[tenant_id]
            logger.info(f"Quorum requirement cleared for tenant {tenant_id}")
    
    def reset_trust_adjustment(self, tenant_id: str):
        """Reset trust adjustment for tenant."""
        if tenant_id in self.tenant_trust_adjustments:
            del self.tenant_trust_adjustments[tenant_id]
            logger.info(f"Trust adjustment reset for tenant {tenant_id}")
    
    def get_tenant_status(self, tenant_id: str) -> Dict[str, Any]:
        """Get current Immune system status for tenant."""
        recent_threats = self.tenant_threat_history.get(tenant_id, [])
        recent_count = len([t for t in recent_threats 
                           if (datetime.utcnow() - datetime.fromisoformat(t["timestamp"])).total_seconds() < 86400])
        
        return {
            "tenant_id": tenant_id,
            "quarantined": self.is_quarantined(tenant_id),
            "quorum_required": self.requires_quorum(tenant_id),
            "required_consensus": self.get_required_consensus(tenant_id),
            "trust_adjustment": self.get_trust_adjustment(tenant_id),
            "recent_threats_24h": recent_count,
            "total_threats": len(recent_threats)
        }


# Global instance (can replace TrustManager)
_trust_manager_v2: Optional[TrustManagerV2] = None


def get_trust_manager_v2() -> TrustManagerV2:
    """Get or create global TrustManagerV2 instance."""
    global _trust_manager_v2
    if _trust_manager_v2 is None:
        _trust_manager_v2 = TrustManagerV2()
    return _trust_manager_v2

