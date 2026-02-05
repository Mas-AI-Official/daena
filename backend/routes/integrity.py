from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from backend.services.integrity_shield import get_integrity_shield, VerificationReport, SourceInfo
from backend.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/integrity", tags=["Integrity Shield"])

class VerifyRequest(BaseModel):
    content: str
    source: str
    metadata: Optional[Dict[str, Any]] = None

class ReviewRequest(BaseModel):
    accept: bool
    reviewer: str = "founder"  # Default, but verified against token

@router.post("/verify", response_model=Dict[str, Any])
async def verify_content(
    request: VerifyRequest,
    current_user: dict = Depends(get_current_user)  # Require auth for verification
):
    """
    Verify content using Daena's Data Integrity Shield.
    Requires valid authentication.
    """
    shield = get_integrity_shield()
    report = shield.verify_data(request.content, request.source, request.metadata)
    
    # Audit log (implicit via shield logging, but could add explicit audit here)
    return report.to_dict()

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get Integrity Shield statistics."""
    shield = get_integrity_shield()
    return shield.get_dashboard_stats()

@router.get("/flags")
async def get_active_flags(current_user: dict = Depends(get_current_user)):
    """Get active verification flags requiring review."""
    shield = get_integrity_shield()
    return shield.get_active_flags()

@router.post("/flags/{flag_id}/review")
async def review_flag(
    flag_id: int, 
    request: ReviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Review and resolve a verification flag.
    RESTRICTED: Only Founder can approve/reject flags.
    """
    if current_user.get("role") != "founder":
         raise HTTPException(status_code=403, detail="Only Founder can review flags")

    shield = get_integrity_shield()
    success = shield.review_flag(flag_id, request.accept, current_user.get("sub", "founder"))
    if not success:
        raise HTTPException(status_code=404, detail="Flag not found")
    return {"success": True}

@router.get("/sources/blocked")
async def get_blocked_sources(current_user: dict = Depends(get_current_user)):
    """Get list of blocked data sources."""
    shield = get_integrity_shield()
    return [s.__dict__ for s in shield.get_blocked_sources()]

@router.post("/sources/{domain}/unblock")
async def unblock_source(
    domain: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually unblock a data source.
    RESTRICTED: Only Founder can unblock sources.
    """
    if current_user.get("role") != "founder":
         raise HTTPException(status_code=403, detail="Only Founder can unblock sources")

    shield = get_integrity_shield()
    success = shield.unblock_source(domain, approver=current_user.get("sub", "founder"))
    if not success:
        raise HTTPException(status_code=400, detail="Source not blocked or unblock failed")
    return {"success": True}

@router.get("/logs/injection")
async def get_injection_logs(
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get logs of detected prompt injection attempts."""
    shield = get_integrity_shield()
    return shield.get_injection_log(limit)
