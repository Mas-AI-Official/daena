"""
DNA integration hooks for NBMF promotion pipeline.
Records lineage on L2Q→L2→L3 promotions.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_dna_service = None


def get_dna_service():
    """Get DNA service instance (lazy import)."""
    global _dna_service
    if _dna_service is None:
        try:
            from backend.services.enterprise_dna_service import get_dna_service as _get_service
            _dna_service = _get_service()
        except ImportError as e:
            logger.warning(f"DNA service not available: {e}")
            return None
    return _dna_service


def record_promotion_lineage(
    object_id: str,
    tenant_id: str,
    promotion_from: str,
    promotion_to: str,
    promoted_by: str,
    nbmf_ledger_txid: str,
    merkle_parent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Record a lineage entry for an NBMF promotion.
    
    Args:
        object_id: Memory object identifier
        tenant_id: Tenant identifier
        promotion_from: Source tier (L2Q, L2, L3)
        promotion_to: Destination tier (L2, L3)
        promoted_by: Agent ID or system identifier
        nbmf_ledger_txid: NBMF ledger transaction ID
        merkle_parent: Parent lineage hash (for chain)
        metadata: Additional metadata
    
    Returns:
        Lineage record hash if successful, None otherwise
    """
    try:
        dna_service = get_dna_service()
        if not dna_service:
            logger.debug("DNA service not available, skipping lineage recording")
            return None
        
        lineage = dna_service.record_lineage(
            object_id=object_id,
            tenant_id=tenant_id,
            promotion_from=promotion_from,
            promotion_to=promotion_to,
            promoted_by=promoted_by,
            nbmf_ledger_txid=nbmf_ledger_txid,
            merkle_parent=merkle_parent,
            metadata=metadata or {}
        )
        
        if lineage:
            lineage_hash = lineage.compute_hash()
            logger.info(f"Recorded DNA lineage for {object_id}: {promotion_from}→{promotion_to} (txid: {nbmf_ledger_txid})")
            
            # Record Prometheus metric
            try:
                from memory_service.dna_metrics import record_lineage_promotion
                record_lineage_promotion(promotion_from, promotion_to, tenant_id)
            except ImportError:
                pass  # Metrics not available
            
            # Emit real-time event for frontend
            try:
                from backend.routes.events import emit
                emit("dna_lineage_promotion", {
                    "object_id": object_id,
                    "tenant_id": tenant_id,
                    "promotion_from": promotion_from,
                    "promotion_to": promotion_to,
                    "txid": nbmf_ledger_txid
                })
            except ImportError:
                pass  # Events system not available
            
            return lineage_hash
        else:
            logger.warning(f"Failed to record DNA lineage for {object_id}")
            return None
    except Exception as e:
        logger.error(f"Error recording DNA lineage: {e}", exc_info=True)
        return None


def hook_l2q_to_l2_promotion(
    item_id: str,
    cls: str,
    tenant_id: str,
    nbmf_ledger_txid: str,
    promoted_by: str = "system",
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Hook to call when promoting from L2Q to L2.
    Records lineage and returns lineage hash.
    """
    return record_promotion_lineage(
        object_id=item_id,
        tenant_id=tenant_id,
        promotion_from="L2Q",
        promotion_to="L2",
        promoted_by=promoted_by,
        nbmf_ledger_txid=nbmf_ledger_txid,
        merkle_parent=None,  # First promotion, no parent
        metadata=metadata or {}
    )


def hook_l2_to_l3_promotion(
    item_id: str,
    cls: str,
    tenant_id: str,
    nbmf_ledger_txid: str,
    previous_lineage_hash: Optional[str] = None,
    promoted_by: str = "system",
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Hook to call when promoting from L2 to L3 (aging).
    Records lineage with parent hash for chain.
    """
    return record_promotion_lineage(
        object_id=item_id,
        tenant_id=tenant_id,
        promotion_from="L2",
        promotion_to="L3",
        promoted_by=promoted_by,
        nbmf_ledger_txid=nbmf_ledger_txid,
        merkle_parent=previous_lineage_hash,
        metadata=metadata or {}
    )


def hook_l3_to_l2_promotion(
    item_id: str,
    cls: str,
    tenant_id: str,
    nbmf_ledger_txid: str,
    previous_lineage_hash: Optional[str] = None,
    promoted_by: str = "system",
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Hook to call when promoting from L3 back to L2 (hot record promotion).
    Records lineage with parent hash.
    """
    return record_promotion_lineage(
        object_id=item_id,
        tenant_id=tenant_id,
        promotion_from="L3",
        promotion_to="L2",
        promoted_by=promoted_by,
        nbmf_ledger_txid=nbmf_ledger_txid,
        merkle_parent=previous_lineage_hash,
        metadata=metadata or {}
    )

