"""
Abstract Applier: Promotes approved abstracts to NBMF L2.

Writes abstracts to NBMF with full ledger audit trail.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time

from .revisor import NBMFAbstract
from .policy import CouncilDecision, DecisionStatus
from . import metrics as sec_metrics

logger = logging.getLogger(__name__)


@dataclass
class PromotionResult:
    """Result of promoting an abstract."""
    abstract_id: str
    promoted: bool
    item_id: Optional[str] = None
    txid: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = 0.0


class AbstractApplier:
    """
    Promotes approved abstracts to NBMF L2.
    
    Ensures:
    - Base models remain immutable (unless explicitly scheduled)
    - Full ledger audit trail
    - Tenant/project isolation
    """
    
    def __init__(self):
        """Initialize applier."""
        self.router = None
        self._init_router()
        logger.info("AbstractApplier initialized")
    
    def _init_router(self):
        """Initialize memory router."""
        try:
            from memory_service.router import MemoryRouter
            self.router = MemoryRouter()
        except Exception as e:
            logger.error(f"Error initializing memory router: {e}")
            self.router = None
    
    def promote(
        self,
        abstract: NBMFAbstract,
        decision: CouncilDecision
    ) -> PromotionResult:
        """
        Promote an approved abstract to NBMF L2.
        
        Args:
            abstract: NBMF abstract to promote
            decision: Council decision approving promotion
            
        Returns:
            Promotion result
        """
        if decision.status != DecisionStatus.PROMOTE:
            return PromotionResult(
                abstract_id=abstract.abstract_id,
                promoted=False,
                error=f"Decision status is {decision.status.value}, not PROMOTE"
            )
        
        if not self.router:
            return PromotionResult(
                abstract_id=abstract.abstract_id,
                promoted=False,
                error="Memory router not initialized"
            )
        
        try:
            # Prepare item ID
            item_id = abstract.abstract_id
            if abstract.tenant_id:
                item_id = f"{abstract.tenant_id}:{item_id}"
            
            # Prepare payload
            payload = {
                "content": abstract.content,
                "embedding": abstract.embedding,
                "metadata": abstract.metadata,
                "source": "sec_loop",
                "promoted_at": time.time(),
                "decision_id": decision.decision_id
            }
            
            # Prepare metadata
            meta = {
                "department": decision.department,
                "tenant_id": abstract.tenant_id,
                "project_id": abstract.project_id,
                "source": "sec_loop",
                "decision_id": decision.decision_id,
                "quorum_reached": decision.quorum_reached,
                "votes_count": len(decision.votes),
                "promoted_at": time.time()
            }
            
            # Write to NBMF L2
            result = self.router.write_nbmf_only(
                item_id,
                "sec_abstract",
                payload,
                meta
            )
            
            # Get transaction ID
            txid = result.get("txid") if isinstance(result, dict) else None
            
            # Log to ledger
            try:
                from memory_service.ledger import log_event
                log_event(
                    action="sec_promote_abstract",
                    ref=item_id,
                    store="nbmf",
                    route="sec_loop",
                    extra={
                        "abstract_id": abstract.abstract_id,
                        "decision_id": decision.decision_id,
                        "department": decision.department,
                        "txid": txid
                    }
                )
            except Exception as e:
                logger.warning(f"Error logging to ledger: {e}")
            
            logger.info(f"Promoted abstract {abstract.abstract_id} to NBMF L2 (item_id: {item_id}, txid: {txid})")
            
            # Record promotion metric
            sec_metrics.record_promotion(decision.department, "success")
            
            return PromotionResult(
                abstract_id=abstract.abstract_id,
                promoted=True,
                item_id=item_id,
                txid=txid,
                timestamp=time.time()
            )
        
        except Exception as e:
            logger.error(f"Error promoting abstract {abstract.abstract_id}: {e}")
            return PromotionResult(
                abstract_id=abstract.abstract_id,
                promoted=False,
                error=str(e),
                timestamp=time.time()
            )
    
    def batch_promote(
        self,
        abstracts: List[NBMFAbstract],
        decisions: List[CouncilDecision]
    ) -> List[PromotionResult]:
        """
        Promote multiple approved abstracts.
        
        Args:
            abstracts: List of abstracts to promote
            decisions: List of corresponding decisions
            
        Returns:
            List of promotion results
        """
        results = []
        
        # Create decision map
        decision_map = {d.abstract_id: d for d in decisions}
        
        for abstract in abstracts:
            decision = decision_map.get(abstract.abstract_id)
            if not decision:
                results.append(PromotionResult(
                    abstract_id=abstract.abstract_id,
                    promoted=False,
                    error="No decision found for abstract"
                ))
                continue
            
            result = self.promote(abstract, decision)
            results.append(result)
        
        promoted_count = sum(1 for r in results if r.promoted)
        logger.info(f"Promoted {promoted_count}/{len(abstracts)} abstracts")
        
        return results

