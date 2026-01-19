"""
Experience Pipeline API Endpoints.

Endpoints for the experience-without-data pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, List, Optional, Any

from backend.routes.monitoring import verify_monitoring_auth
from memory_service.experience_pipeline import (
    experience_pipeline,
    SharedPattern,
    PatternStatus,
    PatternType
)

router = APIRouter(prefix="/api/v1/experience", tags=["experience"])


class DistillPatternRequest(BaseModel):
    """Request to distill a pattern from tenant data."""
    tenant_id: str
    task_data: Dict[str, Any]
    pattern_type: str = "decision_pattern"  # decision_pattern, success_pattern, etc.


class AdoptPatternRequest(BaseModel):
    """Request to adopt a pattern."""
    pattern_id: str
    target_tenant_id: str
    context: Optional[Dict[str, Any]] = None


class RevokePatternRequest(BaseModel):
    """Request to revoke a pattern."""
    pattern_id: str
    reason: str
    revoke_dependents: bool = True


@router.post("/distill")
async def distill_pattern(
    request: DistillPatternRequest,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Distill a pattern from tenant A's task data.
    
    Returns:
        Pattern ID and cryptographic pointers (no tenant data)
    """
    try:
        pattern_type = PatternType(request.pattern_type)
        shared_pattern, pointers = experience_pipeline.distill_pattern_from_tenant(
            tenant_id=request.tenant_id,
            task_data=request.task_data,
            pattern_type=pattern_type
        )
        
        if not shared_pattern:
            raise HTTPException(status_code=400, detail="Failed to distill pattern")
        
        # Auto-approve if confidence is high enough
        approved = experience_pipeline.approve_pattern(shared_pattern)
        
        return {
            "success": True,
            "pattern_id": shared_pattern.pattern_id,
            "confidence_score": shared_pattern.confidence_score,
            "contamination_score": shared_pattern.contamination_score,
            "status": shared_pattern.status.value,
            "approved": approved,
            "pointers": [
                {
                    "evidence_hash": p.evidence_hash,
                    "evidence_location": p.evidence_location,
                    "timestamp": p.timestamp
                }
                for p in pointers
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error distilling pattern: {str(e)}")


@router.post("/adopt")
async def adopt_pattern(
    request: AdoptPatternRequest,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Gate adoption of a pattern for tenant B.
    
    Checks:
    - Confidence threshold
    - Contamination scan
    - Red-team probe
    - Human approval (if required)
    """
    try:
        allowed, reason, gate_result = experience_pipeline.gate_adoption(
            pattern_id=request.pattern_id,
            target_tenant_id=request.target_tenant_id,
            context=request.context
        )
        
        if not allowed:
            return {
                "success": False,
                "allowed": False,
                "reason": reason,
                "gate_result": gate_result
            }
        
        # Get pattern details (without source pointers for security)
        pattern = experience_pipeline.get_pattern_by_id(request.pattern_id)
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")
        
        return {
            "success": True,
            "allowed": True,
            "pattern_id": pattern.pattern_id,
            "pattern_type": pattern.pattern_type.value,
            "confidence": pattern.confidence_score,
            "contamination": pattern.contamination_score,
            "adoption_count": pattern.adoption_count,
            "gate_result": gate_result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adopting pattern: {str(e)}")


@router.post("/revoke")
async def revoke_pattern(
    request: RevokePatternRequest,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Kill-switch: Revoke a pattern globally.
    
    This immediately removes the pattern from the shared pool
    and optionally revokes dependent patterns.
    """
    try:
        revoked = experience_pipeline.revoke_pattern(
            pattern_id=request.pattern_id,
            reason=request.reason,
            revoke_dependents=request.revoke_dependents
        )
        
        if not revoked:
            raise HTTPException(status_code=404, detail="Pattern not found")
        
        return {
            "success": True,
            "pattern_id": request.pattern_id,
            "revoked": True,
            "reason": request.reason,
            "revoke_dependents": request.revoke_dependents
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error revoking pattern: {str(e)}")


@router.get("/recommendations")
async def get_recommendations(
    tenant_id: str,
    limit: int = 10,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get pattern recommendations for a tenant.
    
    Returns patterns that pass adoption gating.
    """
    try:
        recommendations = experience_pipeline.get_pattern_recommendations(
            tenant_id=tenant_id,
            limit=limit
        )
        
        return {
            "success": True,
            "tenant_id": tenant_id,
            "recommendations": [
                {
                    "pattern_id": p.pattern_id,
                    "pattern_type": p.pattern_type.value,
                    "confidence": p.confidence_score,
                    "contamination": p.contamination_score,
                    "adoption_count": p.adoption_count,
                    "success_rate": p.success_rate
                }
                for p in recommendations
            ],
            "count": len(recommendations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recommendations: {str(e)}")


@router.get("/patterns")
async def list_patterns(
    status: Optional[str] = None,
    limit: int = 100,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    List patterns in the shared pool.
    
    Args:
        status: Filter by status (approved, pending, revoked, etc.)
        limit: Maximum number of patterns to return
    """
    try:
        if status:
            patterns = [
                p for p in experience_pipeline.shared_pool.values()
                if p.status.value == status
            ]
        else:
            patterns = experience_pipeline.list_approved_patterns(limit=limit)
        
        return {
            "success": True,
            "patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "pattern_type": p.pattern_type.value,
                    "confidence": p.confidence_score,
                    "contamination": p.contamination_score,
                    "status": p.status.value,
                    "adoption_count": p.adoption_count,
                    "success_rate": p.success_rate,
                    "created_at": p.created_at
                }
                for p in patterns[:limit]
            ],
            "count": len(patterns)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing patterns: {str(e)}")


@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get details of a specific pattern.
    
    Note: Source pointers are not included for security.
    """
    try:
        pattern = experience_pipeline.get_pattern_by_id(pattern_id)
        
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")
        
        return {
            "success": True,
            "pattern": {
                "pattern_id": pattern.pattern_id,
                "pattern_type": pattern.pattern_type.value,
                "confidence": pattern.confidence_score,
                "contamination": pattern.contamination_score,
                "status": pattern.status.value,
                "adoption_count": pattern.adoption_count,
                "success_rate": pattern.success_rate,
                "created_at": pattern.created_at,
                "approved_at": pattern.approved_at,
                "metadata": pattern.metadata,
                # Source pointers excluded for security
                "source_pointer_count": len(pattern.source_pointers)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting pattern: {str(e)}")

