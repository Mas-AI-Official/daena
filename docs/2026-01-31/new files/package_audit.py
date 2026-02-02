"""
Package Audit API Routes — /api/v1/packages/*

Governance gate for all package installs.
Every install request goes through: queue → audit → approve/reject → install.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.package_auditor import get_package_auditor

router = APIRouter(prefix="/api/v1/packages", tags=["package_audit"])


# ─── REQUEST MODELS ────────────────────────────────────────────────

class InstallRequest(BaseModel):
    package_name: str = Field(..., description="Package name (e.g. 'lodash', 'pandas')")
    version: str = Field(..., description="Version (e.g. '4.17.21', 'latest')")
    manager: str = Field(..., description="Package manager: npm|pip|yarn|cargo")
    requested_by: str = Field(default="daena", description="Agent or user requesting the install")


class ApproveRequest(BaseModel):
    approver: str = Field(default="founder")
    notes: str = Field(default="")


class RejectRequest(BaseModel):
    reason: str = Field(..., description="Why the install was rejected")
    rejector: str = Field(default="founder")


# ─── ROUTES ────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check."""
    auditor = get_package_auditor()
    stats = auditor.get_stats()
    return {"status": "healthy", "total_audits": stats["total_audits"]}


@router.get("/stats")
async def get_stats():
    """Dashboard statistics — counts by status, manager, risk level."""
    auditor = get_package_auditor()
    return auditor.get_stats()


@router.get("/log")
async def get_audit_log(limit: int = 50):
    """
    Real-time audit event log.
    Frontend polls this (or gets WS push) to show the live audit feed.
    """
    auditor = get_package_auditor()
    return {"events": auditor.get_audit_log(limit=limit)}


@router.get("/records")
async def list_records(status: Optional[str] = None):
    """List all audit records, optionally filtered by status."""
    auditor = get_package_auditor()
    return {
        "records": auditor.list_records(status_filter=status),
        "count": len(auditor.list_records(status_filter=status))
    }


@router.get("/records/{record_id}")
async def get_record(record_id: str):
    """Get a single audit record by ID."""
    auditor = get_package_auditor()
    record = auditor.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Audit record {record_id} not found")
    return record


@router.post("/request-install")
async def request_install(payload: InstallRequest):
    """
    Entry point: request a package install.
    Returns immediately with an audit record ID.
    Then call /audit/{id} to run the full audit pipeline.
    """
    auditor = get_package_auditor()
    result = auditor.request_install(
        package_name=payload.package_name,
        version=payload.version,
        manager=payload.manager,
        requested_by=payload.requested_by
    )
    return result


@router.post("/audit/{record_id}")
async def run_audit(record_id: str):
    """
    Run the full audit pipeline on a queued package.
    Stages: static_analysis → cve_check → sandbox_install → behavioral_check → decision
    Returns the complete audit record with all findings.
    """
    auditor = get_package_auditor()
    result = auditor.run_audit(record_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/approve/{record_id}")
async def approve_install(record_id: str, payload: ApproveRequest):
    """Approve a pending package install (Founder action)."""
    auditor = get_package_auditor()
    result = auditor.approve(record_id, payload.approver, payload.notes)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/reject/{record_id}")
async def reject_install(record_id: str, payload: RejectRequest):
    """Reject a pending package install."""
    auditor = get_package_auditor()
    result = auditor.reject(record_id, payload.reason, payload.rejector)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/install/{record_id}")
async def execute_install(record_id: str):
    """
    Execute the actual install (only if APPROVED).
    Returns the install command to run.
    """
    auditor = get_package_auditor()
    result = auditor.execute_install(record_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
