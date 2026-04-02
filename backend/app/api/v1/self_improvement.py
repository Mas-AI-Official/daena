"""Self-improvement API endpoints.

Run audits, view suggestions, apply improvements, and track learning.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_current_user

router = APIRouter()


def _get_auditor():
    from app.services.self_improvement.self_audit import SelfAudit

    if not hasattr(_get_auditor, "_instance"):
        _get_auditor._instance = SelfAudit()
    return _get_auditor._instance


def _get_learning_service():
    from app.services.learning_service import LearningService

    if not hasattr(_get_learning_service, "_instance"):
        _get_learning_service._instance = LearningService()
    return _get_learning_service._instance


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


# ── Learning endpoints ────────────────────────────────────────


@router.get("/learning/stats")
async def learning_stats(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get overall learning statistics."""
    service = _get_learning_service()
    return {"success": True, "data": service.get_stats()}


@router.get("/learning/session/{session_id}")
async def learning_session_summary(
    session_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get learning summary for a specific session."""
    service = _get_learning_service()
    return {"success": True, "data": service.get_session_summary(session_id)}


@router.get("/learning/suggestions")
async def learning_suggestions(
    agent: str = Query(..., description="Agent name"),
    operation: str = Query(..., description="Operation name"),
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get improvement suggestions for a specific agent operation."""
    service = _get_learning_service()
    return {"success": True, "data": service.get_suggestions(agent, operation)}


@router.post("/learning/extract-skills/{session_id}")
async def extract_session_skills(
    session_id: str,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Extract reusable skills from a session's action history."""
    service = _get_learning_service()
    skills = await service.extract_skills_from_session(session_id)
    return {"success": True, "data": skills}


class FeedbackRequest(BaseModel):
    action_id: str
    feedback: str  # "good" | "bad"


@router.post("/learning/feedback")
async def record_feedback(
    body: FeedbackRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Record user feedback on an action outcome."""
    service = _get_learning_service()
    await service.track_user_feedback(body.action_id, body.feedback)
    return {"success": True}
