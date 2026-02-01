"""
Data Integrity Shield API Routes

Provides endpoints for:
- Viewing tracked sources and trust scores
- Managing flagged content
- Reviewing manipulation attempts
- Real-time alerts via WebSocket
"""

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

from backend.services.integrity_shield import (
    get_integrity_shield,
    verify_external_data,
    VerificationResult,
    TrustLevel
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrity", tags=["integrity"])


# ============================================
# Pydantic Models
# ============================================

class VerifyRequest(BaseModel):
    content: str = Field(..., description="Content to verify")
    source: str = Field(..., description="Source URL or identifier")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class ReviewFlagRequest(BaseModel):
    accept: bool = Field(..., description="Whether to accept the flagged content")
    reviewer: str = Field(default="founder", description="Who is reviewing")


class UnblockRequest(BaseModel):
    domain: str = Field(..., description="Domain to unblock")
    approver: str = Field(default="founder", description="Who is approving the unblock")


# ============================================
# Source Endpoints
# ============================================

@router.get("/sources")
async def list_sources(
    trust_level: Optional[str] = Query(None, description="Filter by trust level"),
    limit: int = Query(100, ge=1, le=500)
) -> Dict[str, Any]:
    """
    List all tracked sources with their trust scores.
    
    Returns sources sorted by trust score (highest first).
    """
    shield = get_integrity_shield()
    sources = shield.trust_ledger.get_all_sources()
    
    # Filter by trust level if specified
    if trust_level:
        try:
            level = TrustLevel(trust_level.lower())
            sources = [s for s in sources if s.trust_level == level]
        except ValueError:
            raise HTTPException(400, f"Invalid trust level: {trust_level}")
    
    # Sort by trust score
    sources = sorted(sources, key=lambda s: s.trust_score, reverse=True)[:limit]
    
    return {
        "count": len(sources),
        "sources": [
            {
                "source_id": s.source_id,
                "domain": s.domain,
                "trust_score": round(s.trust_score, 1),
                "trust_level": s.trust_level.value,
                "times_verified": s.times_verified,
                "times_flagged": s.times_flagged,
                "first_seen": s.first_seen,
                "last_seen": s.last_seen
            }
            for s in sources
        ]
    }


@router.get("/sources/{source_id}")
async def get_source(source_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific source."""
    shield = get_integrity_shield()
    
    for source in shield.trust_ledger.get_all_sources():
        if source.source_id == source_id:
            return {
                "source_id": source.source_id,
                "domain": source.domain,
                "trust_score": round(source.trust_score, 1),
                "trust_level": source.trust_level.value,
                "times_verified": source.times_verified,
                "times_flagged": source.times_flagged,
                "times_blocked": source.times_blocked,
                "first_seen": source.first_seen,
                "last_seen": source.last_seen,
                "metadata": source.metadata
            }
    
    raise HTTPException(404, f"Source not found: {source_id}")


@router.get("/sources/blocked")
async def get_blocked_sources() -> Dict[str, Any]:
    """Get all blocked sources (trust score < 30)."""
    shield = get_integrity_shield()
    blocked = shield.get_blocked_sources()
    
    return {
        "count": len(blocked),
        "sources": [
            {
                "source_id": s.source_id,
                "domain": s.domain,
                "trust_score": round(s.trust_score, 1),
                "times_blocked": s.times_blocked,
                "last_seen": s.last_seen
            }
            for s in blocked
        ]
    }


@router.post("/sources/unblock")
async def unblock_source(request: UnblockRequest) -> Dict[str, Any]:
    """Manually unblock a source (requires founder approval)."""
    shield = get_integrity_shield()
    
    success = shield.unblock_source(request.domain, request.approver)
    if success:
        return {
            "success": True,
            "message": f"Source {request.domain} unblocked by {request.approver}"
        }
    
    return {
        "success": False,
        "message": "Source was not blocked or could not be unblocked"
    }


# ============================================
# Flag Endpoints
# ============================================

@router.get("/flags")
async def get_flags(
    reviewed: Optional[bool] = Query(None, description="Filter by reviewed status"),
    limit: int = Query(50, ge=1, le=200)
) -> Dict[str, Any]:
    """Get flagged content items."""
    shield = get_integrity_shield()
    
    if reviewed is None:
        flags = shield.active_flags[-limit:]
    elif reviewed:
        flags = [f for f in shield.active_flags if f.get("reviewed", False)][-limit:]
    else:
        flags = shield.get_active_flags()[-limit:]
    
    return {
        "count": len(flags),
        "flags": flags
    }


@router.post("/flags/{flag_id}/review")
async def review_flag(flag_id: int, request: ReviewFlagRequest) -> Dict[str, Any]:
    """Review and resolve a flagged content item."""
    shield = get_integrity_shield()
    
    success = shield.review_flag(flag_id, request.accept, request.reviewer)
    if success:
        action = "accepted" if request.accept else "rejected"
        return {
            "success": True,
            "message": f"Flag {flag_id} {action} by {request.reviewer}"
        }
    
    raise HTTPException(404, f"Flag not found: {flag_id}")


# ============================================
# Manipulation Attempts Log
# ============================================

@router.get("/attempts")
async def get_manipulation_attempts(
    limit: int = Query(50, ge=1, le=200)
) -> Dict[str, Any]:
    """Get log of detected manipulation/injection attempts."""
    shield = get_integrity_shield()
    attempts = shield.get_injection_log(limit)
    
    return {
        "count": len(attempts),
        "attempts": attempts
    }


# ============================================
# Verification Endpoint
# ============================================

@router.post("/verify")
async def verify_content(request: VerifyRequest) -> Dict[str, Any]:
    """
    Verify external data before it reaches Daena.
    
    This is the main entry point for the Data Integrity Shield.
    All external data should pass through this endpoint.
    """
    shield = get_integrity_shield()
    
    try:
        report = shield.verify_data(
            content=request.content,
            source=request.source,
            metadata=request.metadata
        )
        
        return {
            "result": report.result.value,
            "passed": report.result == VerificationResult.PASSED,
            "trust_score": round(report.trust_score, 1),
            "flags": report.flags,
            "manipulation_score": round(report.manipulation_score, 1),
            "recommendations": report.recommendations,
            "source": {
                "domain": report.source_info.domain if report.source_info else request.source,
                "trust_level": report.source_info.trust_level.value if report.source_info else "unknown"
            }
        }
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(500, f"Verification failed: {str(e)}")


@router.post("/strip")
async def strip_malicious_content(
    content: str = Body(..., embed=True)
) -> Dict[str, Any]:
    """Strip detected malicious patterns from content."""
    shield = get_integrity_shield()
    
    cleaned = shield.strip_malicious_content(content)
    modified = cleaned != content
    
    return {
        "cleaned_content": cleaned,
        "modified": modified,
        "original_length": len(content),
        "cleaned_length": len(cleaned)
    }


# ============================================
# Dashboard Stats
# ============================================

@router.get("/stats")
async def get_integrity_stats() -> Dict[str, Any]:
    """
    Get comprehensive integrity shield statistics.
    
    This powers the Trust & Safety dashboard tab.
    """
    shield = get_integrity_shield()
    stats = shield.get_dashboard_stats()
    
    return {
        "summary": {
            "total_verifications": stats["verification"]["total"],
            "passed": stats["verification"].get("passed", 0),
            "blocked": stats["verification"].get("blocked", 0),
            "active_flags": stats["active_flags"],
            "injection_attempts": stats["injection_attempts"]
        },
        "trust_ledger": stats["trust_ledger"],
        "verification": stats["verification"]
    }


@router.get("/health")
async def integrity_health() -> Dict[str, Any]:
    """Health check for the integrity shield."""
    try:
        shield = get_integrity_shield()
        stats = shield.trust_ledger.get_stats()
        
        return {
            "status": "healthy",
            "tracked_sources": stats.get("total", 0),
            "active_flags": len(shield.get_active_flags())
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e)
        }
