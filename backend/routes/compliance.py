"""
Compliance and Verification API Routes.

Provides endpoints for manifest verification and compliance reporting.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pathlib import Path

from backend.routes.monitoring import verify_monitoring_auth
from Tools.verify_manifests_comprehensive import (
    verify_manifest_chain,
    check_cloud_kms_integration,
    generate_compliance_report
)

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


@router.get("/manifests/verify")
async def verify_manifests(
    manifest_dir: str = ".kms/manifests",
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """Verify key rotation manifest chain."""
    try:
        results = verify_manifest_chain(Path(manifest_dir))
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.get("/manifests/compliance")
async def get_compliance_report(
    manifest_dir: str = ".kms/manifests",
    _: bool = Depends(verify_monitoring_auth)
) -> Dict[str, Any]:
    """Get comprehensive compliance report for manifests."""
    try:
        report = generate_compliance_report(Path(manifest_dir))
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/kms/status")
async def get_kms_status(_: bool = Depends(verify_monitoring_auth)) -> Dict[str, Any]:
    """Check cloud KMS integration status."""
    try:
        status = check_cloud_kms_integration()
        return {
            "success": True,
            "status": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

