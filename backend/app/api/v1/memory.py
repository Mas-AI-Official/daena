"""Memory (NBMF) endpoints: store, recall, promote, demote, experiences.

Thin router layer; all business logic lives in MemoryService.

NBMF extensions:
    - POST /experiences: store agent experience (auto-quarantined)
    - GET /experiences: recall validated agent experiences
    - POST /experiences/validate: background promotion of quarantined items
    - GET /status: full memory stats including quarantine and trust
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.memory import (
    DemoteRequest,
    PromoteRequest,
    StoreExperienceRequest,
    StoreMemoryRequest,
)
from app.services.memory import MemoryService

router = APIRouter()


# ── Dependency factory ──


async def get_memory_service(
    db: AsyncSession = Depends(get_db),
) -> MemoryService:
    """Create MemoryService per request."""
    return MemoryService(db)


# ── Store ──


@router.post("/memories", status_code=201)
async def store_memory(
    body: StoreMemoryRequest,
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Store a new memory entry in the NBMF system.

    Tier 0-2 allowed for direct storage. Higher tiers
    require promotion. CAS dedup prevents duplicates.
    """
    result = await service.store(
        tenant_id=user.tenant_id,
        user_id=user.id,
        content=body.content,
        content_type=body.content_type,
        summary=body.summary,
        tags=body.tags,
        source=body.source,
        confidence=body.confidence,
        tier=body.tier,
        scope=body.scope,
        session_id=body.session_id,
        agent_id=body.agent_id,
        skill_id=body.skill_id,
        success_flag=body.success_flag,
        metadata=body.metadata,
    )
    return {"success": True, "data": result}


# ── Recall ──


@router.get("/memories")
async def list_memories(
    content_type: str | None = Query(None),
    tier: int | None = Query(None, ge=0, le=4),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """List memory entries for the tenant with optional filters."""
    result = await service.recall(
        tenant_id=user.tenant_id,
        content_type=content_type,
        tier=tier,
        page=page,
        page_size=page_size,
    )
    return {"success": True, **result}


@router.get("/memories/{memory_id}")
async def get_memory(
    memory_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Retrieve a specific memory entry. Increments access count."""
    result = await service.recall(
        tenant_id=user.tenant_id,
        memory_id=memory_id,
    )
    return {"success": True, "data": result["data"][0]}


# ── Promote / Demote ──


@router.post("/memories/{memory_id}/promote")
async def promote_memory(
    memory_id: UUID,
    body: PromoteRequest,
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Promote a memory to the next tier."""
    result = await service.promote(
        memory_id=memory_id,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        reason=body.reason,
    )
    return {"success": True, "data": result}


@router.post("/memories/{memory_id}/demote")
async def demote_memory(
    memory_id: UUID,
    body: DemoteRequest,
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Demote a memory to the previous tier."""
    result = await service.demote(
        memory_id=memory_id,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        reason=body.reason,
    )
    return {"success": True, "data": result}


# ── History ──


@router.get("/memories/{memory_id}/history")
async def get_memory_history(
    memory_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Get the tier change history (learning log) for a memory."""
    result = await service.get_history(
        memory_id=memory_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": result}


# ── Ephemeral cleanup ──


@router.post("/memories/clear-ephemeral")
async def clear_ephemeral_memories(
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Archive current user's T0/T1 memories and return count."""
    result = await service.clear_ephemeral(
        tenant_id=user.tenant_id,
        user_id=user.id,
    )
    return {"success": True, "data": result}


# ── Agent Experience Endpoints ──


@router.post("/experiences", status_code=201)
async def store_experience(
    body: StoreExperienceRequest,
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Store an agent experience (auto-quarantined in L2Q).

    Experiences are agent decisions, skill outcomes, learned patterns,
    or failed approaches. They enter quarantine and must pass trust
    validation before being recalled in future agent prompts.
    """
    result = await service.store_experience(
        tenant_id=user.tenant_id,
        user_id=user.id,
        agent_id=body.agent_id,
        content=body.content,
        content_type=body.content_type,
        summary=body.summary,
        skill_id=body.skill_id,
        success_flag=body.success_flag,
        confidence=body.confidence,
        tags=body.tags,
        metadata=body.metadata,
    )
    return {"success": True, "data": result}


@router.get("/experiences")
async def list_experiences(
    agent_id: UUID | None = Query(None),
    skill_id: str | None = Query(None),
    query: str | None = Query(None),
    top_k: int = Query(5, ge=1, le=20),
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Recall validated (non-quarantined) agent experiences.

    Only returns experiences that passed trust validation.
    Results scored by relevance, trust, confidence, and recency.
    """
    results = await service.recall_experiences(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        skill_id=skill_id,
        query=query,
        top_k=top_k,
    )
    return {"success": True, "data": results}


@router.post("/experiences/validate")
async def validate_experiences(
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Run trust validation on quarantined experiences.

    Promotes repeated successes, archives repeated failures.
    Intended to be called periodically by the heartbeat daemon.
    """
    result = await service.validate_quarantined(
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": result}


# ── Stats ──


@router.get("/stats")
async def memory_stats(
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
):
    """Get memory statistics: total, per-tier, quarantine, experience counts."""
    tier_counts: dict[str, int] = {}
    total = 0
    for tier in range(5):
        result = await service.recall(
            tenant_id=user.tenant_id,
            tier=tier,
            page=1,
            page_size=1,
        )
        count = result.get("pagination", {}).get("total", 0)
        tier_counts[f"T{tier}"] = count
        total += count

    # Experience-specific stats
    exp_stats = await service.get_experience_stats(
        tenant_id=user.tenant_id,
    )

    return {
        "success": True,
        "data": {
            "total_memories": total,
            "per_tier_counts": tier_counts,
            **exp_stats,
        },
    }


# ── Dream Engine Endpoints ──


@router.post("/dream/run")
async def run_dream_cycle(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger one Dream Engine consolidation cycle.

    Returns a DreamReport summary showing what was merged, promoted,
    synthesized, decayed, and flagged as sensitive.
    """
    from app.services.dream_engine import get_dream_engine

    engine = get_dream_engine()
    report = await engine.run_cycle(
        db_session=db,
        tenant_id=str(user.tenant_id),
    )
    return {"success": True, "data": report.summary()}


@router.get("/dream/status")
async def dream_status(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    """Get Dream Engine status: last run, total cycles, running state."""
    from app.services.dream_engine import get_dream_engine

    engine = get_dream_engine()
    return {
        "success": True,
        "data": {
            "last_run": engine.last_run.isoformat() if engine.last_run else None,
            "total_cycles": engine.total_cycles,
            "is_running": engine.is_running,
        },
    }
