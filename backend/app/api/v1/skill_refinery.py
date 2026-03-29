"""Skill Refinery API endpoints (Department 9).

CRUD for refined skills, extraction from raw content,
and maturity tier promotion/demotion.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.services.skill_refinery.extraction_service import (
    build_embedding_text,
    build_extraction_prompt,
    generate_skill_id,
    parse_extraction_response,
)
from app.services.skill_refinery.news_monitor import scan_for_updates
from app.services.skill_refinery.skill_store import SkillStore

router = APIRouter()


# ── Request schemas ──


class ExtractSkillRequest(BaseModel):
    """Submit raw content for skill extraction."""

    content: str = Field(..., min_length=10, max_length=200_000)
    source_metadata: dict | None = Field(
        None,
        description="Source info: platform, creator, url, etc.",
    )


class PromoteRequest(BaseModel):
    """Empty body -- promotion uses path param only."""


# ── Dependencies ──


async def get_skill_store(
    db: AsyncSession = Depends(get_db),
) -> SkillStore:
    """Factory for SkillStore."""
    return SkillStore(db)


# ── Endpoints ──


@router.get("/search")
async def search_skills_endpoint(
    q: str = Query(..., min_length=2, max_length=500),
    domain: str | None = Query(None),
    top_k: int = Query(5, ge=1, le=20),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Search skills by relevance to a query string.

    Only returns T2_REFINED and above (production-safe skills).
    """
    from app.services.skill_refinery.retrieval_service import search_skills

    results = await search_skills(
        db,
        tenant_id=user.tenant_id,
        query=q,
        domain=domain,
        top_k=top_k,
    )
    return {"success": True, "data": results, "count": len(results)}


@router.get("/catalog")
async def list_skills(
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
    domain: str | None = Query(None),
    maturity: int | None = Query(None, ge=0, le=4),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """List all skills, filterable by domain and maturity tier."""
    if domain is not None:
        result = await store.search_skills_by_domain(
            tenant_id=user.tenant_id,
            domain=domain,
            min_maturity=maturity or 0,
            page=page,
            page_size=page_size,
        )
    elif maturity is not None:
        result = await store.list_skills_by_maturity(
            tenant_id=user.tenant_id,
            maturity=maturity,
            page=page,
            page_size=page_size,
        )
    else:
        # List all (no filter) -- use domain search with empty domain trick
        # or just list by maturity 0+ which is effectively all
        result = await store.search_skills_by_domain(
            tenant_id=user.tenant_id,
            domain=domain or "",
            min_maturity=0,
            page=page,
            page_size=page_size,
        )
        if domain is None:
            # Re-query without domain filter
            from sqlalchemy import select

            from app.models.skill import RefinedSkill

            stmt = (
                select(RefinedSkill)
                .where(
                    RefinedSkill.tenant_id == user.tenant_id,
                    RefinedSkill.archived_at.is_(None),
                )
                .order_by(RefinedSkill.created_at.desc())
            )
            result = await store._paginate(
                stmt, user.tenant_id, page, page_size,
            )

    return {"success": True, **result}


@router.get("/health")
async def refinery_health(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Skill Refinery health check: library stats and freshness scan.

    Returns total skills by tier, average confidence, and a list
    of skills needing refresh (stale, high-usage, or low-success).
    """
    from sqlalchemy import select as sa_select

    from app.models.skill import MATURITY_LABELS, RefinedSkill

    all_stmt = sa_select(RefinedSkill).where(
        RefinedSkill.tenant_id == user.tenant_id,
        RefinedSkill.archived_at.is_(None),
    )
    result = await db.execute(all_stmt)
    all_skills = result.scalars().all()

    tier_counts: dict[str, int] = {}
    confidences: list[float] = []
    for skill in all_skills:
        label = MATURITY_LABELS.get(skill.maturity, f"T{skill.maturity}")
        tier_counts[label] = tier_counts.get(label, 0) + 1
        confidences.append(float(skill.confidence))

    avg_confidence = (
        round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    )

    needing_refresh = await scan_for_updates(
        db=db,
        tenant_id=user.tenant_id,
    )

    return {
        "success": True,
        "data": {
            "total_skills": len(all_skills),
            "skills_by_tier": tier_counts,
            "average_confidence": avg_confidence,
            "skills_needing_refresh": len(needing_refresh),
            "refresh_details": needing_refresh[:20],
        },
    }


@router.post("/emergency-stop", dependencies=[Depends(require_role("FOUNDER"))])
async def emergency_stop(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict:
    """Emergency stop: abort all running skill refinements. Founder-only."""
    from app.services.skill_refinery.refinement_service import (
        trigger_emergency_stop,
    )

    trigger_emergency_stop()
    return {
        "success": True,
        "data": {"status": "emergency_stop_active", "stopped": True},
    }


@router.post("/emergency-resume", dependencies=[Depends(require_role("FOUNDER"))])
async def emergency_resume(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict:
    """Resume refinements after emergency stop. Founder-only."""
    from app.services.skill_refinery.refinement_service import (
        clear_emergency_stop,
    )

    clear_emergency_stop()
    return {
        "success": True,
        "data": {"status": "refinements_resumed", "stopped": False},
    }


@router.get("/daily-cost")
async def get_refinement_daily_cost(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get today's refinement token usage and budget status."""
    from app.services.skill_refinery.refinement_service import get_daily_cost

    return {"success": True, "data": get_daily_cost()}


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Get a single skill by its skill_id."""
    data = await store.get_skill(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": data}


@router.post("/extract", status_code=201)
async def extract_skill(
    body: ExtractSkillRequest,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Extract a skill from raw content using LLM.

    The raw content is treated as untrusted. The extraction prompt
    explicitly instructs the LLM to ignore any embedded instructions.

    Returns the draft skill (T1_DRAFT maturity).
    """
    # Build the extraction prompt
    prompt = build_extraction_prompt(
        body.content,
        body.source_metadata,
    )

    # Call LLM via simple Ollama fallback (keeps extraction independent
    # of chat_orchestrator per Phase 1 constraints)
    import httpx

    from app.core.config import get_settings

    settings = get_settings()
    ollama_url = settings.ollama_base_url
    model = settings.ollama_default_model

    llm_response = ""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
            )
            resp.raise_for_status()
            llm_response = resp.json().get("message", {}).get("content", "")
    except Exception as exc:
        return {
            "success": False,
            "error": f"LLM extraction failed: {exc}",
            "data": None,
        }

    # Parse LLM response into structured skill
    extracted = parse_extraction_response(llm_response)

    if not extracted.get("title"):
        return {
            "success": False,
            "error": "No extractable skill found in content.",
            "data": extracted,
        }

    # Generate skill_id and embedding text
    sid = generate_skill_id(extracted["domain"], extracted["title"])
    emb = build_embedding_text(extracted)

    # Store as T1_DRAFT (untrusted, needs refinement)
    skill = await store.create_skill(
        tenant_id=user.tenant_id,
        skill_id=sid,
        title=extracted["title"],
        domain=extracted["domain"],
        subdomains=extracted.get("subdomains", []),
        maturity=1,  # T1_DRAFT
        source_metadata=body.source_metadata or {},
        steps=extracted.get("steps", []),
        patterns=extracted.get("patterns", []),
        anti_patterns=extracted.get("anti_patterns", []),
        failure_modes=extracted.get("failure_modes", []),
        confidence=extracted.get("confidence", 0.0),
        embedding_text=emb,
    )

    return {"success": True, "data": skill}


@router.post("/{skill_id}/refine")
async def refine_skill_endpoint(
    skill_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Run the 3-pass refinement pipeline on a skill.

    Pass 1 (Gap Finder): identifies missing steps, outdated info.
    Pass 2 (Improver): proposes fixes, modern alternatives.
    Pass 3 (Critic): validates improvements, scores confidence.

    On success, updates the skill with refined content and promotes
    to T2_REFINED maturity.
    """
    from app.services.skill_refinery.refinement_service import (
        refine_skill as run_refinement,
    )

    # Get the current skill
    skill_data = await store.get_skill(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
    )

    # Run 3-pass pipeline
    result = await run_refinement(skill_data)

    verdict = result.get("critic_verdict", {}).get("verdict", "REJECT")
    refined = result.get("refined", {})

    # If approved, update the skill and promote to T2
    if verdict in ("APPROVE", "NEEDS_WORK") and refined:
        # Bump version
        old_version = skill_data.get("version", "1.0")
        parts = old_version.split(".")
        try:
            major, minor = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            new_version = f"{major}.{minor + 1}"
        except ValueError:
            new_version = "2.0"

        await store.update_skill_version(
            skill_id=skill_id,
            tenant_id=user.tenant_id,
            version=new_version,
            steps=refined.get("steps"),
            patterns=refined.get("patterns"),
            anti_patterns=refined.get("anti_patterns"),
            failure_modes=refined.get("failure_modes"),
            improvements_by_daena=refined.get("improvements_by_daena"),
            confidence=result.get("confidence"),
        )

        # Promote to T2_REFINED if currently below
        if skill_data.get("maturity", 0) < 2:
            current = skill_data.get("maturity", 0)
            while current < 2:
                await store.promote_skill(
                    skill_id=skill_id,
                    tenant_id=user.tenant_id,
                )
                current += 1

    # Return full result with before/after
    return {
        "success": True,
        "data": {
            "verdict": verdict,
            "confidence": result.get("confidence", 0.0),
            "gap_report": result.get("gap_report", {}),
            "improvements": result.get("improvements", {}),
            "critic_verdict": result.get("critic_verdict", {}),
            "before": skill_data,
            "after": refined,
        },
    }


@router.put("/{skill_id}/promote")
async def promote_skill(
    skill_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Promote a skill to the next maturity tier."""
    data = await store.promote_skill(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": data}


@router.put("/{skill_id}/demote")
async def demote_skill(
    skill_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Demote a skill to the previous maturity tier."""
    data = await store.demote_skill(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": data}


@router.delete("/{skill_id}")
async def archive_skill(
    skill_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Archive a skill (soft delete per Rule 2: never hard delete)."""
    data = await store.archive_skill(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": data}


# ── Phase 3: Usage tracking + monitoring ──


class TrackUsageRequest(BaseModel):
    """Report a skill usage event."""

    success: bool = Field(..., description="Whether the skill usage was successful")
    feedback: str | None = Field(
        None, max_length=1000, description="Optional feedback about the usage"
    )


@router.post("/{skill_id}/usage")
async def track_skill_usage(
    skill_id: str,
    body: TrackUsageRequest,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Track a skill usage event and update quality metrics.

    Increments usage count and updates success rate.
    After 10 uses, the skill is flagged for re-refinement review.
    """
    data = await store.track_usage(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
        success=body.success,
        feedback=body.feedback,
    )
    return {"success": True, "data": data}


@router.get("/{skill_id}/usage")
async def get_skill_usage_stats(
    skill_id: str,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Get usage statistics for a skill."""
    data = await store.get_usage_stats(
        skill_id=skill_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": data}


