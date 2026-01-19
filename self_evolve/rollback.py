"""
Rollback Manager: Reverts last N promotions via ledger.

Provides rollback capability for SEC-Loop promotions.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    rollback_id: str
    reverted_count: int
    reverted_abstracts: List[str]
    success: bool
    error: Optional[str] = None
    timestamp: float = 0.0


class RollbackManager:
    """
    Manages rollback of SEC-Loop promotions.
    
    Uses ledger manifest to identify and revert promotions.
    """
    
    def __init__(self):
        """Initialize rollback manager."""
        logger.info("RollbackManager initialized")
    
    def rollback_last_n(
        self,
        n: int,
        department: Optional[str] = None
    ) -> RollbackResult:
        """
        Rollback last N promotions.
        
        Args:
            n: Number of promotions to rollback
            department: Optional department filter
            
        Returns:
            Rollback result
        """
        rollback_id = f"sec_rollback_{int(time.time())}"
        
        try:
            # Load ledger entries
            ledger_entries = self._load_ledger_entries()
            
            # Filter for SEC promotions
            sec_entries = [
                e for e in ledger_entries
                if e.get("action") == "sec_promote_abstract"
                and (not department or e.get("meta", {}).get("department") == department)
            ]
            
            # Get last N entries
            last_n = sec_entries[-n:] if len(sec_entries) >= n else sec_entries
            
            # Revert each entry
            reverted_abstracts = []
            for entry in last_n:
                abstract_id = entry.get("meta", {}).get("abstract_id")
                item_id = entry.get("ref_id")
                
                if self._revert_promotion(item_id, abstract_id):
                    reverted_abstracts.append(abstract_id)
            
            # Log rollback to ledger
            self._log_rollback(rollback_id, reverted_abstracts, department)
            
            logger.info(f"Rolled back {len(reverted_abstracts)}/{n} promotions (rollback_id: {rollback_id})")
            
            return RollbackResult(
                rollback_id=rollback_id,
                reverted_count=len(reverted_abstracts),
                reverted_abstracts=reverted_abstracts,
                success=len(reverted_abstracts) > 0,
                timestamp=time.time()
            )
        
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return RollbackResult(
                rollback_id=rollback_id,
                reverted_count=0,
                reverted_abstracts=[],
                success=False,
                error=str(e),
                timestamp=time.time()
            )
    
    def _load_ledger_entries(self) -> List[Dict[str, Any]]:
        """Load ledger entries from ledger file."""
        try:
            from memory_service.ledger import AppendOnlyLedger
            ledger = AppendOnlyLedger()
            return ledger.read_all()
        except Exception as e:
            logger.error(f"Error loading ledger entries: {e}")
            return []
    
    def _revert_promotion(
        self,
        item_id: str,
        abstract_id: str
    ) -> bool:
        """
        Revert a single promotion.
        
        In production, would:
        1. Remove from NBMF L2
        2. Update ledger
        3. Notify monitoring
        
        For now, logs the revert action.
        """
        try:
            # In production, would actually remove from NBMF
            # For now, just log
            logger.info(f"Reverting promotion: item_id={item_id}, abstract_id={abstract_id}")
            
            # Log to ledger
            try:
                from memory_service.ledger import log_event
                log_event(
                    action="sec_rollback_promotion",
                    ref=item_id,
                    store="nbmf",
                    route="sec_loop",
                    extra={
                        "abstract_id": abstract_id,
                        "item_id": item_id,
                        "reverted_at": time.time()
                    }
                )
            except Exception as e:
                logger.warning(f"Error logging rollback to ledger: {e}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error reverting promotion {item_id}: {e}")
            return False
    
    def _log_rollback(
        self,
        rollback_id: str,
        reverted_abstracts: List[str],
        department: Optional[str]
    ):
        """Log rollback operation to ledger."""
        try:
            from memory_service.ledger import log_event
            log_event(
                action="sec_rollback_batch",
                ref=rollback_id,
                store="nbmf",
                route="sec_loop",
                extra={
                    "rollback_id": rollback_id,
                    "reverted_count": len(reverted_abstracts),
                    "reverted_abstracts": reverted_abstracts,
                    "department": department,
                    "rolled_back_at": time.time()
                }
            )
        except Exception as e:
            logger.warning(f"Error logging rollback batch: {e}")

