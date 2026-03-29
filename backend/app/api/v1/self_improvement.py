"""Self-improvement API endpoints.

Run audits, view suggestions, and apply improvements.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user

router = APIRouter()


def _get_auditor():
    from app.services.self_improvement.self_audit import SelfAudit

    if not hasattr(_get_auditor, "_instance"):
        _get_auditor._instance = SelfAudit()
    return _get_auditor._instance


@router.get("/audit")
async def run_audit(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Run a full self-audit."""
    auditor = _get_auditor()
    results = await auditor.full_audit()
    return {
        "success": True,
        "data": {k: v.to_dict() for k, v in results.items()},
    }


@router.get("/audit/last")
async def last_audit(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get the last audit results."""
    auditor = _get_auditor()
    return {"success": True, "data": auditor.get_last_audit()}


@router.get("/suggestions")
async def list_suggestions(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all improvement suggestions from the last audit."""
    auditor = _get_auditor()
    return {"success": True, "data": auditor.get_all_suggestions()}
