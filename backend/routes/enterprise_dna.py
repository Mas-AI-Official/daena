"""
Enterprise-DNA API routes.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from backend.services.enterprise_dna_service import get_dna_service, EnterpriseDNAService
from backend.models.enterprise_dna import (
    Genome, Epigenome, LineageRecord, ThreatSignal, ImmuneEvent,
    ThreatLevel, ImmuneAction
)
# NO-AUTH baseline: do not require auth to access DNA endpoints in local mode.

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dna", tags=["enterprise-dna"])


# ------------------------------------------------------------------
# Epigenome endpoints
# ------------------------------------------------------------------

@router.get("/{tenant_id}")
async def get_epigenome(
    tenant_id: str,
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)  # Uncomment when auth is ready
):
    """Get epigenome for a tenant."""
    epigenome = dna_service.get_epigenome(tenant_id)
    if not epigenome:
        raise HTTPException(status_code=404, detail=f"Epigenome not found for tenant {tenant_id}")
    return epigenome.to_dict()


@router.put("/{tenant_id}")
async def update_epigenome(
    tenant_id: str,
    epigenome_data: Dict[str, Any],
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """Update or create epigenome for a tenant."""
    try:
        # Get existing or create new
        existing = dna_service.get_epigenome(tenant_id)
        if existing:
            # Update existing
            for key, value in epigenome_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            epigenome = existing
        else:
            # Create new
            epigenome_data["tenant_id"] = tenant_id
            epigenome = Epigenome.from_dict(epigenome_data)
        
        if dna_service.save_epigenome(epigenome):
            return {"status": "success", "epigenome": epigenome.to_dict()}
        else:
            raise HTTPException(status_code=500, detail="Failed to save epigenome")
    except Exception as e:
        logger.error(f"Error updating epigenome for {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Genome endpoints
# ------------------------------------------------------------------

@router.get("/{tenant_id}/genome")
async def get_effective_genome(
    tenant_id: str,
    department: Optional[str] = Query(None, description="Filter by department"),
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """
    Get effective capabilities (Genome + Epigenome) for a tenant.
    Returns capabilities per department/agent with policy constraints applied.
    """
    try:
        capabilities = dna_service.get_effective_capabilities(tenant_id, department)
        return capabilities
    except Exception as e:
        logger.error(f"Error getting effective genome for {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/genome/{agent_id}")
async def get_agent_genome(
    tenant_id: str,
    agent_id: str,
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """Get genome for a specific agent."""
    genome = dna_service.get_genome(agent_id)
    if not genome:
        raise HTTPException(status_code=404, detail=f"Genome not found for agent {agent_id}")
    return genome.to_dict()


@router.post("/{tenant_id}/genome")
async def create_or_update_genome(
    tenant_id: str,
    genome_data: Dict[str, Any],
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """Create or update genome for an agent."""
    try:
        genome = Genome.from_dict(genome_data)
        if dna_service.save_genome(genome):
            return {"status": "success", "genome": genome.to_dict()}
        else:
            raise HTTPException(status_code=500, detail="Failed to save genome")
    except Exception as e:
        logger.error(f"Error saving genome: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Lineage endpoints
# ------------------------------------------------------------------

@router.get("/{tenant_id}/lineage/{object_id}")
async def get_lineage_chain(
    tenant_id: str,
    object_id: str,
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """
    Get lineage chain for an object with Merkle proofs.
    Returns full promotion history with cryptographic hashes.
    """
    try:
        chain = dna_service.get_lineage_chain(object_id)
        if not chain:
            raise HTTPException(status_code=404, detail=f"Lineage not found for object {object_id}")
        
        # Build Merkle proof chain
        merkle_proofs = []
        for i, record in enumerate(chain):
            proof = {
                "record": record.to_dict(),
                "merkle_parent": record.merkle_parent,
                "merkle_root": record.merkle_root,
                "nbmf_ledger_txid": record.nbmf_ledger_txid,
                "index": i
            }
            merkle_proofs.append(proof)
        
        return {
            "object_id": object_id,
            "tenant_id": tenant_id,
            "chain_length": len(chain),
            "lineage_chain": merkle_proofs
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lineage for {object_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/lineage/by-txid/{txid}")
async def get_lineage_by_txid(
    tenant_id: str,
    txid: str,
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """Get lineage record by NBMF ledger transaction ID."""
    try:
        lineage = dna_service.get_lineage_by_txid(txid)
        if not lineage:
            raise HTTPException(status_code=404, detail=f"Lineage not found for txid {txid}")
        return lineage.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lineage by txid {txid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Immune system endpoints
# ------------------------------------------------------------------

@router.post("/{tenant_id}/immune/event")
async def record_immune_event(
    tenant_id: str,
    event_data: Dict[str, Any],
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """
    Record an immune event (threat signal intake).
    Feeds into TrustManager for quarantine/quorum decisions.
    
    Can also accept text input for automatic prompt injection detection.
    """
    try:
        # Check if this is a text input for prompt injection detection
        if "text" in event_data and "source" in event_data:
            from backend.services.prompt_injection_detector import get_prompt_injection_detector
            detector = get_prompt_injection_detector()
            
            threat_signal = detector.create_threat_signal(
                text=event_data["text"],
                tenant_id=tenant_id,
                source=event_data["source"],
                context=event_data.get("context", {})
            )
            
            # Create immune event from detected threat
            event = dna_service.record_immune_event(
                tenant_id=tenant_id,
                threat_signals=[threat_signal],
                trust_score_adjustment=-threat_signal.score * 0.5,  # Adjust trust based on severity
                quarantine_required=threat_signal.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL],
                quorum_required=threat_signal.threat_level == ThreatLevel.CRITICAL,
                rollback_required=False
            )
            
            if event:
                # Feed to TrustManagerV2
                try:
                    from memory_service.trust_manager_v2 import get_trust_manager_v2
                    trust_manager = get_trust_manager_v2()
                    trust_manager.apply_immune_event(
                        tenant_id=tenant_id,
                        quarantine_required=event.quarantine_required,
                        quorum_required=event.quorum_required,
                        trust_score_adjustment=event.trust_score_adjustment,
                        threat_level=threat_signal.threat_level
                    )
                except ImportError:
                    pass
                
                return {
                    "status": "success",
                    "event": event.to_dict(),
                    "detection": {
                        "type": "prompt_injection",
                        "score": threat_signal.score,
                        "threat_level": threat_signal.threat_level.value,
                        "patterns": threat_signal.details.get("detected_patterns", [])
                    }
                }
        
        # Parse threat signals (manual input)
        threat_signals = []
        for signal_data in event_data.get("threat_signals", []):
            threat_signals.append(ThreatSignal.from_dict(signal_data))
        
        # Create immune event
        event = dna_service.record_immune_event(
            tenant_id=tenant_id,
            threat_signals=threat_signals,
            trust_score_adjustment=event_data.get("trust_score_adjustment", 0.0),
            quarantine_required=event_data.get("quarantine_required", False),
            quorum_required=event_data.get("quorum_required", False),
            rollback_required=event_data.get("rollback_required", False)
        )
        
        if not event:
            raise HTTPException(status_code=500, detail="Failed to record immune event")
        
        # Feed to TrustManagerV2 (if available)
        try:
            from memory_service.trust_manager_v2 import get_trust_manager_v2
            trust_manager = get_trust_manager_v2()
            
            # Get threat level from signals
            threat_level = None
            if threat_signals:
                max_level = max(s.threat_level for s in threat_signals)
                threat_level = max_level
            
            # Apply immune event to TrustManager
            trust_manager.apply_immune_event(
                tenant_id=tenant_id,
                quarantine_required=event.quarantine_required,
                quorum_required=event.quorum_required,
                trust_score_adjustment=event.trust_score_adjustment,
                threat_level=threat_level
            )
            
            logger.info(f"Immune event applied to TrustManagerV2 for tenant {tenant_id}")
        except ImportError:
            logger.warning("TrustManagerV2 not available for immune event processing")
        
        # Record Prometheus metrics
        try:
            from memory_service.dna_metrics import (
                record_immune_event, record_quarantine, record_quorum
            )
            for signal in threat_signals:
                record_immune_event(
                    tenant_id=tenant_id,
                    threat_type=signal.threat_type,
                    threat_level=signal.threat_level.value
                )
            if event.quarantine_required:
                record_quarantine(tenant_id=tenant_id, reason="immune_event")
            if event.quorum_required:
                record_quorum(tenant_id=tenant_id)
        except ImportError:
            pass  # Metrics not available
        
        return {
            "status": "success",
            "event": event.to_dict(),
            "actions_taken": {
                "quarantine": event.quarantine_required,
                "quorum": event.quorum_required,
                "rollback": event.rollback_required
            }
        }
    except Exception as e:
        logger.error(f"Error recording immune event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}/immune/events")
async def get_immune_events(
    tenant_id: str,
    limit: int = Query(100, ge=1, le=1000),
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """Get recent immune events for a tenant."""
    try:
        events = dna_service.get_immune_events(tenant_id, limit=limit)
        return {
            "tenant_id": tenant_id,
            "count": len(events),
            "events": [event.to_dict() for event in events]
        }
    except Exception as e:
        logger.error(f"Error getting immune events for {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Health/Status endpoints
# ------------------------------------------------------------------

@router.get("/{tenant_id}/health")
async def get_dna_health(
    tenant_id: str,
    dna_service: EnterpriseDNAService = Depends(get_dna_service),
    # current_user = Depends(get_current_user)
):
    """
    Get DNA health status for a tenant.
    Returns policy state, last rotation, anomalies in last 24h.
    """
    try:
        epigenome = dna_service.get_epigenome(tenant_id)
        if not epigenome:
            return {
                "tenant_id": tenant_id,
                "status": "not_configured",
                "epigenome_exists": False
            }
        
        # Get recent immune events (last 24h)
        events = dna_service.get_immune_events(tenant_id, limit=100)
        now = datetime.utcnow()
        recent_events = [
            e for e in events
            if (now - e.created_at).total_seconds() < 86400  # 24 hours
        ]
        
        # Count anomalies
        anomalies = sum(
            1 for event in recent_events
            for signal in event.threat_signals
            if signal.threat_type == "anomaly" and signal.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        )
        
        is_healthy = anomalies == 0
        
        # Update Prometheus metrics
        try:
            from memory_service.dna_metrics import update_health_status, update_anomalies_24h
            update_health_status(tenant_id, is_healthy)
            update_anomalies_24h(tenant_id, anomalies)
        except ImportError:
            pass  # Metrics not available
        
        health_data = {
            "tenant_id": tenant_id,
            "status": "healthy" if is_healthy else "degraded",
            "epigenome_exists": True,
            "last_rotation": epigenome.updated_at.isoformat(),
            "anomalies_last_24h": anomalies,
            "recent_immune_events": len(recent_events),
            "feature_flags": len(epigenome.feature_flags),
            "jurisdictions": len(epigenome.jurisdictions)
        }
        
        # Emit real-time event for frontend
        try:
            from backend.routes.events import emit_dna_health_update
            emit_dna_health_update(tenant_id, health_data)
        except ImportError:
            pass  # Events system not available
        
        return health_data
    except Exception as e:
        logger.error(f"Error getting DNA health for {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

