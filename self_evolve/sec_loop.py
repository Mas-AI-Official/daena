"""
SEC-Loop: Main orchestrator for Council-Gated Self-Evolving Cycle.

Coordinates all phases: SELECT → REWRITE → TEST → DECIDE → APPLY
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time

from .selector import DataSelector, CandidateSlice
from .revisor import AbstractRevisor, NBMFAbstract
from .tester import EvaluationTester, EvaluationResult
from .policy import CouncilPolicy, CouncilDecision, DecisionStatus
from .apply import AbstractApplier, PromotionResult
from .rollback import RollbackManager
from . import metrics as sec_metrics

logger = logging.getLogger(__name__)


@dataclass
class SECLoopResult:
    """Result of a SEC-Loop cycle."""
    cycle_id: str
    department: str
    candidates_selected: int
    abstracts_created: int
    abstracts_evaluated: int
    decisions_made: int
    abstracts_promoted: int
    abstracts_rejected: int
    duration_sec: float
    success: bool
    errors: List[str]


class SECLoop:
    """
    Main orchestrator for SEC-Loop.
    
    Coordinates:
    1. SELECT: Data slice selection
    2. REWRITE: NBMF abstract creation
    3. TEST: Gated evaluations
    4. DECIDE: Council quorum + ABAC policy
    5. APPLY: NBMF L2 promotion
    """
    
    def __init__(self):
        """Initialize SEC-Loop."""
        self.selector = DataSelector()
        self.revisor = AbstractRevisor()
        self.tester = EvaluationTester()
        self.policy = CouncilPolicy()
        self.applier = AbstractApplier()
        self.rollback = RollbackManager()
        
        logger.info("SEC-Loop initialized")
    
    def run_cycle(
        self,
        department: str,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None,
        cell_id: Optional[str] = None
    ) -> SECLoopResult:
        """
        Run a complete SEC-Loop cycle.
        
        Args:
            department: Department requesting cycle
            tenant_id: Optional tenant ID for isolation
            project_id: Optional project ID for scoping
            cell_id: Optional cell ID for neighbor lookup
            
        Returns:
            SEC-Loop result
        """
        cycle_id = f"sec_cycle_{int(time.time())}_{department}"
        cycle_start = time.time()
        errors = []
        
        logger.info(f"Starting SEC-Loop cycle: {cycle_id} (department: {department})")
        
        try:
            # 1. SELECT: Data slice selection
            candidates = self.selector.select_candidates(department, tenant_id, project_id)
            if not candidates:
                logger.warning(f"No candidates selected for {department}")
                return SECLoopResult(
                    cycle_id=cycle_id,
                    department=department,
                    candidates_selected=0,
                    abstracts_created=0,
                    abstracts_evaluated=0,
                    decisions_made=0,
                    abstracts_promoted=0,
                    abstracts_rejected=0,
                    duration_sec=time.time() - cycle_start,
                    success=False,
                    errors=["No candidates selected"]
                )
            
            # 2. REWRITE: NBMF abstract creation
            abstracts = self.revisor.batch_create_abstracts(candidates, sanitize=True)
            
            # 3. TEST: Gated evaluations
            eval_results = self.tester.batch_evaluate(abstracts, department, tenant_id)
            
            # 4. DECIDE: Council quorum + ABAC policy
            decisions = []
            for eval_result in eval_results:
                try:
                    decision = self.policy.make_decision(eval_result, department, tenant_id, cell_id)
                    decisions.append(decision)
                except Exception as e:
                    logger.error(f"Error making decision for {eval_result.abstract_id}: {e}")
                    errors.append(f"Decision error for {eval_result.abstract_id}: {e}")
                    continue
            
            # 5. APPLY: NBMF L2 promotion (only for PROMOTE decisions)
            promote_decisions = [d for d in decisions if d.status == DecisionStatus.PROMOTE]
            promote_abstracts = [
                a for a, d in zip(abstracts, decisions)
                if d.status == DecisionStatus.PROMOTE
            ]
            
            promotion_results = []
            if promote_abstracts and promote_decisions:
                promotion_results = self.applier.batch_promote(promote_abstracts, promote_decisions)
            
            # Count results
            promoted_count = sum(1 for r in promotion_results if r.promoted)
            rejected_count = sum(1 for d in decisions if d.status == DecisionStatus.REJECT)
            
            duration = time.time() - cycle_start
            
            # Record metrics
            for result in eval_results:
                sec_metrics.record_retention_delta(department, result.retention_drift)
                sec_metrics.record_knowledge_incorporation(department, result.knowledge_incorporation)
            
            for decision in decisions:
                if decision.status == DecisionStatus.PROMOTE:
                    sec_metrics.record_promotion(department, "success")
                elif decision.status == DecisionStatus.REJECT:
                    sec_metrics.record_rejection(department, "evaluation_failed")
            
            sec_metrics.record_cycle(department, "completed", duration)
            
            logger.info(f"SEC-Loop cycle complete: {cycle_id} (promoted: {promoted_count}, rejected: {rejected_count})")
            
            return SECLoopResult(
                cycle_id=cycle_id,
                department=department,
                candidates_selected=len(candidates),
                abstracts_created=len(abstracts),
                abstracts_evaluated=len(eval_results),
                decisions_made=len(decisions),
                abstracts_promoted=promoted_count,
                abstracts_rejected=rejected_count,
                duration_sec=duration,
                success=promoted_count > 0,
                errors=errors
            )
        
        except Exception as e:
            logger.error(f"Error in SEC-Loop cycle {cycle_id}: {e}")
            return SECLoopResult(
                cycle_id=cycle_id,
                department=department,
                candidates_selected=0,
                abstracts_created=0,
                abstracts_evaluated=0,
                decisions_made=0,
                abstracts_promoted=0,
                abstracts_rejected=0,
                duration_sec=time.time() - cycle_start,
                success=False,
                errors=[str(e)]
            )


# Global instance
sec_loop = SECLoop()

