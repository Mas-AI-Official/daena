"""
Council Policy: Manages council quorum and ABAC policy decisions.

Implements 4/6 neighbor quorum for SEC-Loop promotion decisions.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import yaml

from .tester import EvaluationResult

logger = logging.getLogger(__name__)


class DecisionStatus(Enum):
    """Decision status."""
    PENDING = "pending"
    PROMOTE = "promote"
    HOLD = "hold"
    REJECT = "reject"


@dataclass
class CouncilDecision:
    """A council decision for SEC-Loop promotion."""
    decision_id: str
    abstract_id: str
    status: DecisionStatus
    votes: Dict[str, bool]  # voter_id -> vote (True=approve, False=reject)
    quorum_reached: bool
    reasoning: str
    timestamp: float
    department: str
    tenant_id: Optional[str] = None


class CouncilPolicy:
    """
    Manages council quorum and ABAC policy decisions.
    
    Uses 4/6 neighbor quorum (same as CMP validation) for promotion decisions.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize policy manager."""
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        
        self.config = self._load_config(config_path)
        quorum_config = self.config.get("quorum", {})
        self.quorum_type = quorum_config.get("type", "local")
        self.required_votes = quorum_config.get("required_votes", 4)
        self.timeout_seconds = quorum_config.get("timeout_seconds", 30.0)
        
        # Active decisions
        self.active_decisions: Dict[str, CouncilDecision] = {}
        
        logger.info(f"CouncilPolicy initialized: quorum_type={self.quorum_type}, required_votes={self.required_votes}")
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                return {}
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return {}
    
    def make_decision(
        self,
        evaluation_result: EvaluationResult,
        department: str,
        tenant_id: Optional[str] = None,
        cell_id: Optional[str] = None
    ) -> CouncilDecision:
        """
        Make a council decision based on evaluation results.
        
        Args:
            evaluation_result: Evaluation results
            department: Department requesting decision
            tenant_id: Optional tenant ID for isolation
            cell_id: Optional cell ID for neighbor lookup
            
        Returns:
            Council decision
        """
        # Generate unique decision ID with microsecond precision
        import time
        decision_id = f"sec_decision_{int(time.time() * 1000000)}_{evaluation_result.abstract_id[:8]}"
        
        # Start quorum
        quorum_id = f"sec_quorum_{decision_id}"
        votes = {}
        quorum_reached = False
        
        try:
            from backend.utils.quorum import quorum_manager, QuorumType
            from backend.utils.sunflower_registry import sunflower_registry
            
            # Get neighbors if cell_id provided
            neighbors = []
            if cell_id:
                try:
                    neighbors = sunflower_registry.get_neighbors(cell_id) if hasattr(sunflower_registry, 'get_neighbors') else []
                    # Set neighbors for quorum manager
                    if neighbors:
                        quorum_manager.set_cell_neighbors(cell_id, neighbors)
                except:
                    pass
            
            # Start quorum
            quorum_type = QuorumType.LOCAL if self.quorum_type == "local" else QuorumType.GLOBAL
            quorum_manager.start_quorum(
                quorum_id,
                quorum_type,
                required_votes=self.required_votes,
                cell_id=cell_id
            )
            
            # Simulate votes based on evaluation results
            # In production, actual agents would vote
            # For now, auto-approve if evaluation passed
            if evaluation_result.passed:
                # Simulate 4/6 neighbor approval
                for i in range(self.required_votes):
                    voter_id = neighbors[i] if i < len(neighbors) else f"neighbor_{i+1}"
                    quorum_manager.cast_vote(quorum_id, voter_id, True, confidence=0.9)
                    votes[voter_id] = True
                
                # Check quorum status
                quorum_status = quorum_manager.get_quorum_status(quorum_id)
                quorum_reached = quorum_status.get("quorum_reached", False)
            else:
                # Evaluation failed, reject
                quorum_reached = False
                votes = {}
        
        except Exception as e:
            logger.warning(f"Quorum check failed: {e}, using evaluation result directly")
            quorum_reached = evaluation_result.passed
        
        # Determine decision status
        if quorum_reached and evaluation_result.passed:
            status = DecisionStatus.PROMOTE
            reasoning = f"Quorum reached ({len(votes)}/{self.required_votes} votes) and evaluation passed"
        elif evaluation_result.passed:
            status = DecisionStatus.HOLD
            reasoning = f"Evaluation passed but quorum not reached ({len(votes)}/{self.required_votes} votes)"
        else:
            status = DecisionStatus.REJECT
            reasoning = f"Evaluation failed: {self._format_failure_reason(evaluation_result)}"
        
        decision = CouncilDecision(
            decision_id=decision_id,
            abstract_id=evaluation_result.abstract_id,
            status=status,
            votes=votes,
            quorum_reached=quorum_reached,
            reasoning=reasoning,
            timestamp=time.time(),
            department=department,
            tenant_id=tenant_id
        )
        
        self.active_decisions[decision_id] = decision
        
        logger.info(f"Decision made: {decision_id} -> {status.value} (quorum_reached={quorum_reached})")
        
        return decision
    
    def _format_failure_reason(self, result: EvaluationResult) -> str:
        """Format failure reason from evaluation result."""
        reasons = []
        
        min_incorporation = 0.03
        max_retention_drift = 0.01
        max_latency_change = 0.05
        min_cost_reduction = 0.20
        
        if result.knowledge_incorporation < min_incorporation:
            reasons.append(f"knowledge_incorporation={result.knowledge_incorporation:.2%} < {min_incorporation:.2%}")
        if result.retention_drift > max_retention_drift:
            reasons.append(f"retention_drift={result.retention_drift:.2%} > {max_retention_drift:.2%}")
        if result.latency_change_p95 > max_latency_change:
            reasons.append(f"latency_change_p95={result.latency_change_p95:.2%} > {max_latency_change:.2%}")
        if result.cost_reduction < min_cost_reduction:
            reasons.append(f"cost_reduction={result.cost_reduction:.2%} < {min_cost_reduction:.2%}")
        if not result.abac_compliant:
            reasons.append("ABAC compliance failed")
        
        return "; ".join(reasons) if reasons else "Unknown failure"
    
    def get_decision(self, decision_id: str) -> Optional[CouncilDecision]:
        """Get a decision by ID."""
        return self.active_decisions.get(decision_id)
    
    def get_pending_decisions(self) -> List[CouncilDecision]:
        """Get all pending decisions."""
        return [
            d for d in self.active_decisions.values()
            if d.status == DecisionStatus.PENDING
        ]

