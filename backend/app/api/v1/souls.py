"""Soul Maker API -- department Mind personas + proposal review.

Public endpoints (any authenticated user):
    GET  /souls                      -- list all 10 Department Minds with metadata
    GET  /souls/{department}         -- full soul body + metadata for one Mind
    GET  /souls/proposals            -- list pending proposals

Founder-only endpoints (require FOUNDER tier):
    POST /souls/{department}/refine  -- kick off a 3-pass refinement
    POST /souls/refine-all           -- refine every Mind in parallel
    POST /souls/proposals/{id}/approve
    POST /souls/proposals/{id}/reject

Promotion rule: only ``approve_proposal`` writes the live soul file.
No refiner, heartbeat, or background job may overwrite a soul.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.logging import get_logger
from app.services.soul_engine import SoulEngine, _load_department_soul, _normalize_department
from app.services.soul_maker import (
    approve_proposal,
    get_proposal,
    list_proposals,
    refine_department_soul,
    reject_proposal,
)
from app.services.soul_maker.refinement import refine_all_departments

logger = get_logger(__name__)

router = APIRouter()


# ── Response shapes ────────────────────────────────────────────────


class SoulSummary(BaseModel):
    """One Department Mind in the gallery view."""

    slug: str
    name: str | None = None
    department: str | None = None
    runtime_preference: str | None = None
    voice: str | None = None
    accent_color: str | None = None
    temperature: float | None = None


class SoulDetail(SoulSummary):
    """Full soul record with body text for the detail view."""

    body: str
    fallback_runtimes: list[str] = Field(default_factory=list)
    tools_enabled: list[str] = Field(default_factory=list)
    version: str | None = None


class RefineRequest(BaseModel):
    use_research: bool = True
    persist_proposal: bool = True


class DecisionRequest(BaseModel):
    notes: str | None = Field(None, max_length=4000)


# ── Public reads ──────────────────────────────────────────────────


@router.get("/souls", response_model=list[SoulSummary])
async def list_souls(user: CurrentUser = Depends(get_current_user)) -> list[SoulSummary]:
    """List all available Department Minds with summary metadata.

    Used by the frontend Minds gallery page and the chat model/mind
    switcher. Returns empty list when no department souls are present.
    """
    _ = user  # authenticated gate; content is non-sensitive
    items: list[SoulSummary] = []
    for dept in SoulEngine.list_departments():
        items.append(
            SoulSummary(
                slug=dept.get("slug", ""),
                name=dept.get("name"),
                department=dept.get("department"),
                runtime_preference=dept.get("runtime_preference"),
                voice=dept.get("voice"),
                accent_color=dept.get("accent_color"),
                temperature=_coerce_float(dept.get("temperature")),
            ),
        )
    return items


@router.get("/souls/proposals")
async def list_soul_proposals(
    user: CurrentUser = Depends(get_current_user),
    slug: str | None = Query(None, description="Filter by department slug"),
    status: str | None = Query("pending", description="pending | approved | rejected | all"),
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """List soul refinement proposals awaiting founder review."""
    _ = user
    effective_status = None if (status in (None, "", "all")) else status
    return list_proposals(slug=slug, status=effective_status, limit=limit)


@router.get("/souls/{department}", response_model=SoulDetail)
async def get_soul(
    department: str,
    user: CurrentUser = Depends(get_current_user),
) -> SoulDetail:
    """Fetch the full soul body + metadata for one Department Mind."""
    _ = user
    slug = _normalize_department(department)
    if not slug:
        raise HTTPException(status_code=404, detail=f"Unknown department: {department}")
    meta, body = _load_department_soul(slug)
    if not body:
        raise HTTPException(status_code=404, detail=f"Soul body empty for {slug}")
    return SoulDetail(
        slug=slug,
        name=meta.get("name"),
        department=meta.get("department"),
        runtime_preference=meta.get("runtime_preference"),
        voice=meta.get("voice"),
        accent_color=meta.get("accent_color"),
        temperature=_coerce_float(meta.get("temperature")),
        fallback_runtimes=_coerce_list(meta.get("fallback_runtimes")),
        tools_enabled=_coerce_list(meta.get("tools_enabled")),
        version=meta.get("version"),
        body=body,
    )


# ── Founder-gated actions ─────────────────────────────────────────


@router.post("/souls/{department}/refine")
async def refine_soul(
    department: str,
    payload: RefineRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Run a 3-pass refinement for one Department Mind.

    Produces a pending proposal (never overwrites the live file). Returns
    the refinement verdict + confidence + proposal id. The founder must
    then call ``/souls/proposals/{id}/approve`` to promote it.
    """
    _ = user
    opts = payload or RefineRequest()
    slug = _normalize_department(department)
    if not slug:
        raise HTTPException(status_code=404, detail=f"Unknown department: {department}")
    result = await refine_department_soul(
        slug,
        use_research=opts.use_research,
        persist_proposal=opts.persist_proposal,
    )
    return {
        "slug": result.department_slug,
        "verdict": result.verdict,
        "confidence": result.confidence,
        "error": result.error,
        "gap_count": len(result.gap_report.get("missing_expertise_frames") or []),
        "evidence_sources": len(result.evidence_sources),
        "improvement_notes": result.improvement_notes,
    }


@router.post("/souls/refine-all")
async def refine_all(
    payload: RefineRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> list[dict[str, Any]]:
    """Refine every Department Mind in parallel (weekly heartbeat use).

    Heavy operation -- respects the shared refinement semaphore
    (MAX_CONCURRENT_REFINEMENTS=3) so concurrent calls don't explode
    token spend. Returns per-department verdicts.
    """
    _ = user
    opts = payload or RefineRequest()
    results = await refine_all_departments(use_research=opts.use_research)
    return [
        {
            "slug": r.department_slug,
            "verdict": r.verdict,
            "confidence": r.confidence,
            "error": r.error,
        }
        for r in results
    ]


@router.post("/souls/proposals/{proposal_id}/approve")
async def approve_soul_proposal(
    proposal_id: str,
    payload: DecisionRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Promote a pending proposal to the live soul file.

    This is the ONLY path that writes ``backend/app/soul/departments/<slug>.md``.
    """
    notes = payload.notes if payload else None
    decided_by = getattr(user, "email", None) or getattr(user, "id", None) or "FOUNDER"
    rec = approve_proposal(proposal_id, decided_by=str(decided_by), notes=notes)
    if rec is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return rec


@router.post("/souls/proposals/{proposal_id}/reject")
async def reject_soul_proposal(
    proposal_id: str,
    payload: DecisionRequest | None = None,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Reject a pending proposal. Never touches the live soul file."""
    notes = payload.notes if payload else None
    decided_by = getattr(user, "email", None) or getattr(user, "id", None) or "FOUNDER"
    rec = reject_proposal(proposal_id, decided_by=str(decided_by), notes=notes)
    if rec is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return rec


@router.get("/souls/proposals/{proposal_id}")
async def get_soul_proposal(
    proposal_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Fetch a single proposal (with full diff bodies)."""
    _ = user
    rec = get_proposal(proposal_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return rec


# ── small parsing helpers ──────────────────────────────────────────


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        return [x.strip() for x in value.strip("[]").split(",") if x.strip()]
    return []
