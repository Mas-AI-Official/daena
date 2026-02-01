"""
Package Auditor API Routes

Supply-chain governance — every package install must be audited.
Catches CVEs, typosquatting, malicious packages, and suspicious behavior.

Audit Loop:
  REQUEST → QUEUE → STATIC ANALYSIS → CVE SCAN → SANDBOX INSTALL
  → BEHAVIORAL CHECK → DECISION → PENDING_APPROVAL → APPROVED/REJECTED
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/packages", tags=["packages"])


def get_auditor():
    """Get the package auditor singleton."""
    from backend.services.package_auditor import get_package_auditor
    return get_package_auditor()


# ============================================
# Package Audit Requests
# ============================================

@router.post("/audit")
async def request_audit(
    package_name: str = Body(...),
    version: str = Body(default="latest"),
    manager: str = Body(default="npm"),
    requested_by: str = Body(default="daena")
) -> Dict[str, Any]:
    """
    Queue a package for security audit.
    
    Returns an audit ID that can be used to check status.
    
    Supported managers: npm, pip, yarn, cargo
    """
    auditor = get_auditor()
    result = auditor.request_install(package_name, version, manager, requested_by)
    return result


@router.post("/audit/{record_id}/run")
async def run_audit(record_id: str) -> Dict[str, Any]:
    """
    Run the full audit pipeline for a queued package.
    
    Stages:
    1. Static analysis (known threats, typosquatting)
    2. CVE check (known vulnerabilities)
    3. Sandbox install (isolated test)
    4. Behavioral check (suspicious patterns)
    5. Risk assessment → auto-approve, auto-reject, or pending
    """
    auditor = get_auditor()
    result = auditor.run_audit(record_id)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.get("/audit/{record_id}")
async def get_audit_status(record_id: str) -> Dict[str, Any]:
    """Get the status and details of an audit."""
    auditor = get_auditor()
    record = auditor.get_record(record_id)
    
    if not record:
        raise HTTPException(404, f"Audit record not found: {record_id}")
    
    return record


# ============================================
# Governance Actions
# ============================================

@router.post("/audit/{record_id}/approve")
async def approve_package(
    record_id: str,
    approver: str = Body(default="founder"),
    notes: str = Body(default="")
) -> Dict[str, Any]:
    """Approve a pending package install."""
    auditor = get_auditor()
    result = auditor.approve(record_id, approver, notes)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/audit/{record_id}/reject")
async def reject_package(
    record_id: str,
    reason: str = Body(...),
    rejector: str = Body(default="founder")
) -> Dict[str, Any]:
    """Reject a pending package install."""
    auditor = get_auditor()
    result = auditor.reject(record_id, reason, rejector)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/audit/{record_id}/install")
async def execute_install(record_id: str) -> Dict[str, Any]:
    """
    Execute the actual package install (only if APPROVED).
    
    Returns the command that should be run.
    """
    auditor = get_auditor()
    result = auditor.execute_install(record_id)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


# ============================================
# Listing & Stats
# ============================================

@router.get("/")
async def list_audits(status: Optional[str] = None) -> Dict[str, Any]:
    """
    List all audit records.
    
    Filter by status: queued, scanning, pending_approval, approved, rejected, installed
    """
    auditor = get_auditor()
    records = auditor.list_records(status_filter=status)
    return {
        "count": len(records),
        "records": records
    }


@router.get("/pending")
async def list_pending() -> Dict[str, Any]:
    """List packages pending approval (for governance dashboard)."""
    auditor = get_auditor()
    records = auditor.list_records(status_filter="pending_approval")
    return {
        "count": len(records),
        "records": records
    }


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get package audit statistics."""
    auditor = get_auditor()
    return auditor.get_stats()


@router.get("/log")
async def get_audit_log(limit: int = 50) -> Dict[str, Any]:
    """Get recent audit events (for real-time dashboard feed)."""
    auditor = get_auditor()
    events = auditor.get_audit_log(limit=limit)
    return {
        "count": len(events),
        "events": events
    }


# ============================================
# Quick Audit (Request + Run in one call)
# ============================================

@router.post("/quick-audit")
async def quick_audit(
    package_name: str = Body(...),
    version: str = Body(default="latest"),
    manager: str = Body(default="npm"),
    requested_by: str = Body(default="founder")
) -> Dict[str, Any]:
    """
    Request and immediately run an audit in one call.
    
    Useful for quick package checks.
    """
    auditor = get_auditor()
    
    # Queue it
    request_result = auditor.request_install(package_name, version, manager, requested_by)
    record_id = request_result.get("id")
    
    if not record_id:
        raise HTTPException(500, "Failed to create audit record")
    
    # Run the audit
    audit_result = auditor.run_audit(record_id)
    
    return audit_result


# ============================================
# Threat Intelligence
# ============================================

@router.get("/threats/known-malicious")
async def list_known_malicious() -> Dict[str, Any]:
    """List known malicious packages in our threat database."""
    from backend.services.package_auditor import KNOWN_MALICIOUS
    return {
        "count": len(KNOWN_MALICIOUS),
        "packages": sorted(list(KNOWN_MALICIOUS))
    }


@router.get("/threats/popular-packages")
async def list_popular_packages() -> Dict[str, Any]:
    """List popular packages on our whitelist."""
    from backend.services.package_auditor import POPULAR_PACKAGES
    return {
        "count": len(POPULAR_PACKAGES),
        "packages": sorted(list(POPULAR_PACKAGES))
    }


@router.post("/threats/check-typosquat")
async def check_typosquat(
    package_name: str = Body(...)
) -> Dict[str, Any]:
    """
    Check if a package name looks like a typosquat of a popular package.
    
    Returns potential matches with edit distance.
    """
    from backend.services.package_auditor import POPULAR_PACKAGES
    
    name = package_name.lower()
    matches = []
    
    for popular in POPULAR_PACKAGES:
        if name == popular:
            continue
        
        # Levenshtein distance check
        dist = _edit_distance(name, popular)
        if dist <= 2:
            matches.append({
                "similar_to": popular,
                "edit_distance": dist,
                "warning": f"'{name}' looks like a typosquat of '{popular}'"
            })
    
    return {
        "package": package_name,
        "is_suspicious": len(matches) > 0,
        "matches": matches
    }


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if len(b) == 0:
        return len(a)
    prev_row = range(len(b) + 1)
    for i, ca in enumerate(a):
        curr_row = [i + 1]
        for j, cb in enumerate(b):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (ca != cb)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


# ============================================
# Health
# ============================================

@router.get("/health")
async def package_auditor_health() -> Dict[str, Any]:
    """Health check for package auditor."""
    auditor = get_auditor()
    stats = auditor.get_stats()
    
    return {
        "status": "healthy",
        "total_audits": stats.get("total_audits", 0),
        "pending_approval": stats.get("pending_approval", 0),
        "rejected": stats.get("rejected", 0)
    }
