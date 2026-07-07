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


class VpMind(SoulSummary):
    """Daena's pinned VP-tier Mind -- distinct from the 10 department peers.

    Carries the extra ``tier``/``pinned``/``role`` fields the department
    shape lacks, so the frontend can render her as the gold Vice President
    card rather than an eleventh department. Served by GET /souls/vp.
    """

    tier: str | None = None
    pinned: bool = False
    role: str | None = None
    fallback_runtimes: list[str] = Field(default_factory=list)
    tools_enabled: list[str] = Field(default_factory=list)


class RefineRequest(BaseModel):
    use_research: bool = True
    persist_proposal: bool = True


class DecisionRequest(BaseModel):
    notes: str | None = Field(None, max_length=4000)


class SoulProposalOut(BaseModel):
    """One soul refinement proposal, shaped for the frontend contract.

    The store persists proposals with internal keys (id / slug /
    original_body / decision_notes); the frontend ``SoulProposal`` type
    expects proposal_id / department_slug / current_body / notes. This
    model is the API-boundary translation so the store's immutable audit
    format never has to change. Without it the UI POSTs to
    ``/souls/proposals/undefined/approve`` (proposal_id was never sent).
    """

    proposal_id: str
    department_slug: str
    mind_name: str | None = None
    status: str
    verdict: str | None = None
    confidence: float | None = None
    created_at: str | None = None
    decided_at: str | None = None
    decided_by: str | None = None
    notes: str | None = None
    current_body: str | None = None
    proposed_body: str | None = None
    improvement_notes: list[str] = Field(default_factory=list)
    gap_report: dict[str, Any] = Field(default_factory=dict)
    evidence_sources: list[Any] = Field(default_factory=list)


def _serialize_proposal(rec: dict[str, Any]) -> SoulProposalOut:
    """Map a stored proposal record to the frontend contract shape."""
    return SoulProposalOut(
        proposal_id=rec.get("id", ""),
        department_slug=rec.get("slug", ""),
        mind_name=rec.get("mind_name"),
        status=rec.get("status", "pending"),
        verdict=rec.get("verdict"),
        confidence=rec.get("confidence"),
        created_at=rec.get("created_at"),
        decided_at=rec.get("decided_at"),
        decided_by=rec.get("decided_by"),
        notes=rec.get("decision_notes"),
        current_body=rec.get("original_body"),
        proposed_body=rec.get("proposed_body"),
        improvement_notes=rec.get("improvement_notes") or [],
        gap_report=rec.get("gap_report") or {},
        evidence_sources=rec.get("evidence_sources") or [],
    )


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


@router.get("/souls/proposals", response_model=list[SoulProposalOut])
async def list_soul_proposals(
    user: CurrentUser = Depends(get_current_user),
    slug: str | None = Query(None, description="Filter by department slug"),
    status: str | None = Query("pending", description="pending | approved | rejected | all"),
    limit: int = Query(100, ge=1, le=500),
) -> list[SoulProposalOut]:
    """List soul refinement proposals awaiting founder review."""
    _ = user
    effective_status = None if (status in (None, "", "all")) else status
    return [
        _serialize_proposal(r)
        for r in list_proposals(slug=slug, status=effective_status, limit=limit)
    ]


@router.get("/souls/vp", response_model=VpMind)
async def get_vp_soul(user: CurrentUser = Depends(get_current_user)) -> VpMind:
    """Fetch Daena's VP-tier Mind -- the pinned Vice President card.

    Distinct from GET /souls (the 10 department peers, which deliberately
    excludes her) and GET /souls/{department}. Declared before the
    ``{department}`` route so the static path is not shadowed. Lets the
    frontend render Daena as the gold VP rather than an eleventh department.
    """
    _ = user
    vp = SoulEngine.get_vp_mind()
    if not vp:
        raise HTTPException(status_code=404, detail="VP Mind not found")
    return VpMind(
        slug=vp.get("slug", ""),
        name=vp.get("name"),
        department=vp.get("department"),
        runtime_preference=vp.get("runtime_preference"),
        voice=vp.get("voice"),
        accent_color=vp.get("accent_color"),
        temperature=_coerce_float(vp.get("temperature")),
        tier=vp.get("tier"),
        pinned=_coerce_bool(vp.get("pinned")),
        role=vp.get("role"),
        fallback_runtimes=_coerce_list(vp.get("fallback_runtimes")),
        tools_enabled=_coerce_list(vp.get("tools_enabled")),
    )


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
    return _serialize_proposal(rec).model_dump()


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
    return _serialize_proposal(rec).model_dump()


@router.get("/souls/proposals/{proposal_id}", response_model=SoulProposalOut)
async def get_soul_proposal(
    proposal_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> SoulProposalOut:
    """Fetch a single proposal (with full diff bodies)."""
    _ = user
    rec = get_proposal(proposal_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _serialize_proposal(rec)


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


def _coerce_bool(value: Any) -> bool:
    """Honestly coerce a frontmatter value to bool.

    The dependency-free frontmatter parser yields raw strings, so a
    ``pinned: true`` overlay field arrives as the string ``"true"``. Treat
    only the explicit truthy tokens as True; ``"false"``/``""``/None are
    False (a naive ``bool("false")`` would be True -- a trap).
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)
