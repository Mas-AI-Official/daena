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


async def _probe_rag(now_iso: str) -> dict:
    """Retrieval probe for the vector RAG layer.

    No vector engine is registered in this build, so this is a hardcoded
    not-configured probe. The shape mirrors the obsidian and recall
    probes so the frontend renders all three surfaces uniformly.

    A future build that wires a vector retrieval engine should:
        1. Replace this body with a real probe (issue a tiny similarity
           query against the configured store, count documents, capture
           latency).
        2. Update the assertion in
           ``test_memory_status_retrieval_test_rag_not_configured`` to
           reflect the new truth.
    """
    return {
        "configured": False,
        "reachable": False,
        "document_count": None,
        "last_test_at": now_iso,
        "error": (
            "No vector retrieval engine registered in this build. "
            "NBMF keyword recall remains available via /memory/memories."
        ),
    }


async def _probe_obsidian(now_iso: str) -> dict:
    """Retrieval probe for the Daena-Mind Obsidian vault.

    Honest: ``configured=True`` requires (a) the vault path resolves AND
    (b) we can list its contents. A bare ``Path.exists()`` check (the
    previous implementation) returned ``True`` for an empty or
    permission-denied path, which let the UI claim "available" even
    when no retrieval was actually possible.

    document_count is the live count of ``*.md`` files under the vault
    root. Zero is honest -- the operator can see the vault is wired but
    contains nothing yet.
    """
    try:
        from app.services.nbmf_archive import VAULT_ROOT

        vault_path = VAULT_ROOT
        if not vault_path.exists():
            return {
                "configured": False,
                "reachable": False,
                "document_count": None,
                "last_test_at": now_iso,
                "error": (
                    f"Daena-Mind vault path does not exist: {vault_path}"
                ),
                "vault_path": str(vault_path),
            }
        # Real retrieval test: glob the vault for markdown files.
        # If the path is unreadable, this raises and we fall through
        # to the except branch with an honest error.
        md_files = list(vault_path.glob("**/*.md"))
        return {
            "configured": True,
            "reachable": True,
            "document_count": len(md_files),
            "last_test_at": now_iso,
            "error": None,
            "vault_path": str(vault_path),
        }
    except Exception as exc:
        return {
            "configured": False,
            "reachable": False,
            "document_count": None,
            "last_test_at": now_iso,
            "error": f"Vault probe failed: {type(exc).__name__}: {exc}",
            "vault_path": None,
        }


async def _probe_recall(
    db: AsyncSession,
    service: MemoryService,
    tenant_id: UUID,
    user_id: UUID,
) -> dict:
    """Retrieval probe for the keyword-Jaccard chat recall path.

    Counts non-archived MemoryEntry rows for the tenant (the corpus
    available to recall) and runs a tiny ``recall_for_chat`` call
    against a sentinel session id. The call should return without
    raising regardless of corpus size; if it does raise, recall is
    NOT honestly reachable and we report the error verbatim.
    """
    from datetime import datetime as _dt
    from uuid import uuid4
    from sqlalchemy import func, select

    from app.models.memory import MemoryEntry

    now_iso = _dt.utcnow().isoformat()
    try:
        # Corpus size: non-archived memory rows for this tenant.
        count_stmt = select(func.count()).where(
            MemoryEntry.tenant_id == tenant_id,
            MemoryEntry.archived_at.is_(None),
        )
        count_result = await db.execute(count_stmt)
        doc_count = int(count_result.scalar() or 0)

        # Real probe: tiny recall call. Sentinel session id never
        # matches anything; ``query`` is a probe token unlikely to
        # collide with real content. Ask for at most 1 result so this
        # stays cheap.
        await service.recall_for_chat(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=uuid4(),
            query="retrieval-test-probe",
            page_size=1,
        )
        return {
            "configured": True,
            "reachable": True,
            "document_count": doc_count,
            "last_test_at": now_iso,
            "error": None,
        }
    except Exception as exc:
        return {
            "configured": False,
            "reachable": False,
            "document_count": None,
            "last_test_at": now_iso,
            "error": f"Recall probe failed: {type(exc).__name__}: {exc}",
        }


@router.get("/retrieval-test")
async def retrieval_test(
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
    db: AsyncSession = Depends(get_db),
):
    """Run live retrieval probes against the three retrieval surfaces.

    Each probe returns ``{configured, reachable, document_count,
    last_test_at, error}``. Distinct from ``/memory/status`` because
    that endpoint blends probe results with NBMF tier counts and the
    recall-algorithm descriptor; this endpoint is the focused
    operator-facing health check for retrieval.

    Honest gating rule: ``configured=true`` requires the probe to
    actually succeed (vault listed, recall returned without raising).
    A bare path-exists or env-var-set check is NOT enough -- those
    were the source of the "RAG sync working" hallucination this PR
    closes.
    """
    from datetime import datetime as _dt

    now_iso = _dt.utcnow().isoformat()
    return {
        "success": True,
        "data": {
            "rag": await _probe_rag(now_iso),
            "obsidian": await _probe_obsidian(now_iso),
            "recall": await _probe_recall(db, service, user.tenant_id, user.id),
            "tested_at": now_iso,
        },
    }


@router.get("/status")
async def memory_status(
    user: CurrentUser = Depends(get_current_user),
    service: MemoryService = Depends(get_memory_service),
    db: AsyncSession = Depends(get_db),
):
    """Get honest Memory/RAG/Obsidian availability for the frontend.

    Memory is backed by NBMF and SQL persistence. RAG/vector retrieval
    is not exposed as a dedicated service in this build, so it is
    reported as not_configured instead of pretending to be online.
    Obsidian status comes from a real glob of the Daena-Mind vault --
    NOT a bare path-exists check (the previous implementation reported
    "available" for any path that happened to exist on disk, which let
    the UI claim retrieval was working when no document had ever been
    listed).

    Each retrieval surface (rag/obsidian/recall) carries the same five
    diagnostic fields the operator needs to triage: configured,
    reachable, document_count, last_test_at, error.
    """
    from datetime import datetime as _dt

    stats = await memory_stats(user=user, service=service)
    memory_data = stats.get("data", {})

    now_iso = _dt.utcnow().isoformat()
    rag_probe = await _probe_rag(now_iso)
    obsidian_probe = await _probe_obsidian(now_iso)
    recall_probe = await _probe_recall(db, service, user.tenant_id, user.id)

    # Backward-compat: the prior shape had ``status`` ("online" /
    # "not_configured" / "available" / "error") + ``enabled`` (bool) +
    # ``reason`` (str). Frontend SettingsMemory.tsx still reads those
    # for the badge. Map the new probe fields into those legacy fields
    # so the existing UI keeps working without churn.
    #
    # Distinguishes intentional "not configured" (no engine wired,
    # vault path doesn't exist yet) from runtime "error" (probe raised
    # an exception). Probes flag exceptions with the literal "probe
    # failed:" prefix in their error string.
    def _legacy_status(probe: dict) -> str:
        if probe.get("configured") and probe.get("reachable"):
            return "available"
        err = (probe.get("error") or "").lower()
        if "probe failed:" in err:
            return "error"
        return "not_configured"

    def _legacy_reason(probe: dict, ok_reason: str) -> str:
        return probe.get("error") or ok_reason

    rag_block = {
        # Legacy fields (preserved for existing frontend consumers)
        "status": _legacy_status(rag_probe),
        "enabled": bool(rag_probe.get("configured") and rag_probe.get("reachable")),
        "reason": _legacy_reason(
            rag_probe,
            "Vector RAG retrieval engine is reachable.",
        ),
        # New retrieval-test fields (PR-AUDIT-VERIFY+RAG-HONEST PR #2)
        **rag_probe,
    }
    obsidian_block = {
        "status": _legacy_status(obsidian_probe),
        "enabled": bool(
            obsidian_probe.get("configured") and obsidian_probe.get("reachable"),
        ),
        "reason": _legacy_reason(
            obsidian_probe,
            f"Vault listed: {obsidian_probe.get('document_count', 0)} markdown file(s).",
        ),
        # vault_path is preserved at the top level for the existing UI
        "vault_path": obsidian_probe.get("vault_path"),
        **{k: v for k, v in obsidian_probe.items() if k != "vault_path"},
    }
    recall_block_status = {
        "status": _legacy_status(recall_probe),
        "enabled": bool(
            recall_probe.get("configured") and recall_probe.get("reachable"),
        ),
        "reason": _legacy_reason(
            recall_probe,
            f"Recall corpus available: {recall_probe.get('document_count', 0)} memory entries.",
        ),
        **recall_probe,
    }

    # PR-RAG-HONEST (PR #1) recall-algorithm descriptor: surfaces what
    # the chat-recall algorithm actually does, separate from the live
    # probe result above. The descriptor describes the formula
    # ('keyword Jaccard blend' with 0.50/0.20/0.20/0.10 weights); the
    # probe describes whether it currently works for THIS tenant.
    recall_descriptor = {
        "mode": "keyword_jaccard_blend",
        "embeddings_enabled": False,
        "function_path": "app.services.memory.MemoryService.recall_for_chat",
        "scoring": {
            "keyword_relevance": 0.50,
            "tier_normalized": 0.20,
            "confidence": 0.20,
            "recency_decay": 0.10,
        },
        "scope_priority": ["SESSION", "USER", "TENANT"],
        "filters": [
            "non_quarantined",
            "non_expired",
            "tier_>=_LONG_TERM",
        ],
        "tokenizer": (
            "ASCII alphanumeric with dash/underscore separators, "
            "min length 2, English stopwords stripped"
        ),
        "default_top_k": 5,
        "reason": (
            "Chat recall is a deterministic blend of keyword Jaccard "
            "overlap, NBMF tier, entry confidence, and recency decay. "
            "No vector/embedding retrieval is configured in this build."
        ),
    }

    return {
        "success": True,
        "data": {
            "memory": {
                "status": "online",
                "enabled": True,
                **memory_data,
            },
            "rag": rag_block,
            "obsidian": obsidian_block,
            "recall_status": recall_block_status,
            "recall": recall_descriptor,
            "tested_at": now_iso,
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
