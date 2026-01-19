"""
Knowledge Distillation API Endpoints.
Provides access to experience vector extraction and cross-tenant knowledge sharing.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from memory_service.knowledge_distillation import knowledge_distiller, ExperienceVector
from backend.routes.monitoring import verify_monitoring_auth
from starlette.requests import Request

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge-distillation"])
logger = logging.getLogger(__name__)


@router.post("/distill")
async def distill_experience(
    request: Request,
    data_items: List[Dict[str, Any]] = Body(...),
    tenant_id: Optional[str] = Query(None),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Distill experience vectors from tenant data.
    
    Pipeline: Trust → Quarantine → Distill → Approve → Publish
    
    Args:
        data_items: List of data items to analyze
        tenant_id: Tenant ID (optional, extracted from request if not provided)
    
    Returns:
        List of extracted experience vectors
    """
    filter_tenant = tenant_id or getattr(request.state, 'tenant_id', None)
    
    if len(data_items) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 data items required for pattern extraction"
        )
    
    vectors = knowledge_distiller.extract_patterns(
        data_items=data_items,
        tenant_id=filter_tenant
    )
    
    # Store vectors
    stored_ids = []
    for vector in vectors:
        vector_id = knowledge_distiller.store_vector(vector)
        stored_ids.append(vector_id)
    
    return {
        "success": True,
        "vectors_extracted": len(vectors),
        "vector_ids": stored_ids,
        "vectors": [v.to_dict() for v in vectors]
    }


@router.post("/approve/{vector_id}")
async def approve_pattern(
    request: Request,
    vector_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Approve a pattern for publishing (governance filter).
    
    Args:
        vector_id: Experience vector ID to approve
    
    Returns:
        Approval status
    """
    approved = knowledge_distiller.approve_pattern(vector_id)
    
    if not approved:
        raise HTTPException(
            status_code=400,
            detail=f"Pattern {vector_id} does not meet approval criteria"
        )
    
    return {
        "success": True,
        "vector_id": vector_id,
        "approved": True,
        "message": "Pattern approved for publishing"
    }


@router.post("/publish/{vector_id}")
async def publish_pattern(
    request: Request,
    vector_id: str,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Publish an approved pattern (make available for cross-tenant use).
    
    Args:
        vector_id: Experience vector ID to publish
    
    Returns:
        Published pattern
    """
    published = knowledge_distiller.publish_pattern(vector_id)
    
    if not published:
        raise HTTPException(
            status_code=400,
            detail=f"Pattern {vector_id} could not be published (not approved or not found)"
        )
    
    return {
        "success": True,
        "vector_id": vector_id,
        "pattern": published.to_dict(),
        "message": "Pattern published successfully"
    }


@router.get("/patterns")
async def get_patterns(
    request: Request,
    pattern_type: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get published patterns (cross-tenant experience vectors).
    
    Args:
        pattern_type: Filter by pattern type (optional)
        min_confidence: Minimum confidence threshold (optional)
    
    Returns:
        List of published patterns
    """
    patterns = knowledge_distiller.get_patterns(
        pattern_type=pattern_type,
        min_confidence=min_confidence
    )
    
    return {
        "success": True,
        "count": len(patterns),
        "patterns": [p.to_dict() for p in patterns]
    }


@router.get("/stats")
async def get_distillation_stats(
    request: Request,
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get knowledge distillation statistics.
    
    Returns:
        Statistics about extracted patterns
    """
    all_patterns = knowledge_distiller.get_patterns()
    
    by_type = {}
    total_confidence = 0.0
    
    for pattern in all_patterns:
        pattern_type = pattern.pattern_type
        if pattern_type not in by_type:
            by_type[pattern_type] = 0
        by_type[pattern_type] += 1
        total_confidence += pattern.confidence
    
    avg_confidence = total_confidence / len(all_patterns) if all_patterns else 0.0
    
    return {
        "success": True,
        "total_patterns": len(all_patterns),
        "by_type": by_type,
        "average_confidence": avg_confidence,
        "min_confidence": knowledge_distiller.min_confidence,
        "min_sources": knowledge_distiller.min_sources
    }


@router.post("/search")
async def search_similar_patterns(
    request: Request,
    query_features: Dict[str, float] = Body(...),
    pattern_type: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Search for similar patterns based on feature vector.
    
    Args:
        query_features: Feature vector to search for
        pattern_type: Filter by pattern type (optional)
        top_k: Number of results to return
        similarity_threshold: Minimum similarity score
        
    Returns:
        List of similar patterns with similarity scores
    """
    similar = knowledge_distiller.find_similar_patterns(
        query_features=query_features,
        pattern_type=pattern_type,
        top_k=top_k,
        similarity_threshold=similarity_threshold
    )
    
    return {
        "success": True,
        "count": len(similar),
        "patterns": [
            {
                "pattern": pattern.to_dict(),
                "similarity_score": float(score)
            }
            for pattern, score in similar
        ]
    }


@router.post("/recommend")
async def recommend_patterns(
    request: Request,
    context: Dict[str, Any] = Body(...),
    pattern_type: Optional[str] = Query(None),
    top_k: int = Query(3, ge=1, le=10),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Get pattern recommendations based on context.
    
    Args:
        context: Context information (features, metadata, etc.)
        pattern_type: Filter by pattern type (optional)
        top_k: Number of recommendations
        
    Returns:
        List of recommended patterns
    """
    recommendations = knowledge_distiller.recommend_patterns(
        context=context,
        pattern_type=pattern_type,
        top_k=top_k
    )
    
    return {
        "success": True,
        "count": len(recommendations),
        "recommendations": [
            {
                "pattern": pattern.to_dict(),
                "relevance_score": float(score)
            }
            for pattern, score in recommendations
        ]
    }


@router.post("/auto-publish")
async def auto_publish_patterns(
    request: Request,
    min_confidence: float = Query(0.9, ge=0.0, le=1.0),
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """
    Automatically publish high-confidence patterns.
    
    Args:
        min_confidence: Minimum confidence for auto-publishing
        
    Returns:
        Number of patterns auto-published
    """
    published_count = knowledge_distiller.auto_publish_high_confidence_patterns(
        min_confidence=min_confidence
    )
    
    return {
        "success": True,
        "published_count": published_count,
        "min_confidence": min_confidence,
        "message": f"Auto-published {published_count} high-confidence patterns"
    }




