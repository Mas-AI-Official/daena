"""Skill Refinery API endpoints (Department 9).

CRUD for refined skills, extraction from raw content,
and maturity tier promotion/demotion.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.skill_refinery.extraction_service import (
    build_embedding_text,
    build_extraction_prompt,
    generate_skill_id,
    parse_extraction_response,
)
from app.services.skill_refinery.news_monitor import scan_for_updates
from app.services.skill_refinery.skill_store import SkillStore

logger = get_logger(__name__)

router = APIRouter()


# ── Refinery decision ledger ──
#
# Every refinement verdict (applied or not) is appended to the shared
# MAS-AI learning ledger so rejected refinements become memory instead
# of vanishing. Fail-open by design: a ledger failure is logged loudly
# (Rule 17) but never blocks the API response.

_LEDGER_DIR_DEFAULT = r"D:\agents\AI_COMPANY_OS\state\ledgers"


def _ledger_refinement_decision(row: dict[str, Any]) -> None:
    """Append one refinement decision to refinery_decisions.ndjson.

    Ledger directory override: MASAI_LEDGER_DIR env var (matches the
    other MAS-AI ledgers: skill_edits, optimizer_runs, aqa_verdicts).
    """
    try:
        ledger_dir = Path(os.environ.get("MASAI_LEDGER_DIR", _LEDGER_DIR_DEFAULT))
        ledger_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "source": "daena.skill_refinery",
            **row,
        }
        path = ledger_dir / "refinery_decisions.ndjson"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        logger.warning("skill_refinery.ledger_write_failed", error=str(exc))


# ── Request schemas ──


class ExtractSkillRequest(BaseModel):
    """Submit raw content for skill extraction."""

    content: str = Field(..., min_length=10, max_length=200_000)
    source_metadata: dict | None = Field(
        None,
        description="Source info: platform, creator, url, etc.",
    )


# ── Batch ingest (ContentOps scraper feed) ──────────────────────
#
# External ContentOps pipeline (YouTube -> Grabit -> NotebookLM ->
# transcript) POSTs batches here. Each item becomes one T1 draft
# skill via the same extraction path as /extract, but wrapped so 20+
# transcripts from one scrape session land in a single request.
#
# See docs/pitch/CONTENTOPS-INGEST-CONTRACT.md for the wire contract
# the external scraper writes against.

_ALLOWED_SOURCE_TYPES = {
    "youtube",      # YouTube video transcript (Grabit output)
    "podcast",      # Podcast transcript (Whisper output)
    "rss",          # Blog / substack / newsletter article
    "book",         # Book chapter or section
    "search",       # Google search result set
    "notebooklm",   # NotebookLM structured summary
    "manual",       # Human-pasted text
    "other",
}


class ContentOpsItem(BaseModel):
    """One transcript / article / chapter staged for skill extraction."""

    source_type: str = Field(
        ...,
        description=(
            "Origin category. One of: " + ", ".join(sorted(_ALLOWED_SOURCE_TYPES))
        ),
    )
    source_url: str | None = Field(None, max_length=2048)
    creator: str | None = Field(
        None,
        max_length=200,
        description="Author / channel / speaker identifier (e.g. 'Alex Hormozi').",
    )
    title: str | None = Field(None, max_length=500)
    published_at: str | None = Field(
        None,
        description="ISO-8601 publish date if known. Used for staleness scoring.",
    )
    content: str = Field(..., min_length=10, max_length=200_000)
    extras: dict | None = Field(
        None,
        description="Free-form payload the external pipeline preserves (chapter marks, tags, etc.).",
    )


class ContentOpsBatchRequest(BaseModel):
    """Body for POST /skills/refinery/ingest-batch."""

    batch_label: str | None = Field(
        None,
        max_length=120,
        description="Label for the scrape run (e.g. 'hormozi-2026-Q1').",
    )
    items: list[ContentOpsItem] = Field(..., min_length=1, max_length=50)


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


@router.post("/ingest-batch", status_code=201)
async def ingest_batch(
    body: ContentOpsBatchRequest,
    user: CurrentUser = Depends(get_current_user),
    store: SkillStore = Depends(get_skill_store),
) -> dict[str, Any]:
    """Accept a batch of ContentOps items for skill extraction.

    Contract
    --------
    External scraper (YouTube -> Grabit -> NotebookLM) POSTs a list of
    items. Each item becomes one T1 draft skill via the existing
    extraction pipeline, tagged with source metadata so staleness
    monitoring and source-provenance checks can reference it later.

    Returns per-item status -- ``ok`` with the created skill_id, or
    ``error`` with the failure reason. A partial success is still a
    201 (atomic failure per batch is too brittle for a scraper). The
    scraper reads the response and retries only the error items.

    Governance
    ----------
    All items persist scoped to the caller's tenant. The extraction
    LLM prompt already treats ingested content as untrusted, so
    prompt-injection attempts in a scraped transcript cannot alter
    the skill schema.
    """
    # Validate source_type values up front so a typo in the scraper
    # is caught with a clean 422 rather than a partial write.
    for idx, item in enumerate(body.items):
        if item.source_type.lower() not in _ALLOWED_SOURCE_TYPES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"items[{idx}].source_type={item.source_type!r} not allowed. "
                    f"Valid: {sorted(_ALLOWED_SOURCE_TYPES)}"
                ),
            )

    import httpx
    from app.core.config import get_settings

    settings = get_settings()
    ollama_url = settings.ollama_base_url
    model = settings.ollama_default_model

    batch_label = body.batch_label or f"batch-{datetime.now(UTC).isoformat()}"
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for idx, item in enumerate(body.items):
            # Compose source_metadata. The external scraper may have
            # preserved a much richer payload in ``extras``; keep it
            # intact so staleness + provenance can consult it later.
            source_metadata = {
                "source_type": item.source_type.lower(),
                "source_url": item.source_url,
                "creator": item.creator,
                "title": item.title,
                "published_at": item.published_at,
                "batch_label": batch_label,
                "batch_index": idx,
                "ingested_via": "contentops.ingest_batch",
                **(item.extras or {}),
            }

            prompt = build_extraction_prompt(item.content, source_metadata)
            try:
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
                results.append({
                    "index": idx,
                    "status": "error",
                    "reason": f"LLM extraction failed: {exc}",
                    "source_url": item.source_url,
                })
                continue

            extracted = parse_extraction_response(llm_response)
            if not extracted.get("title"):
                results.append({
                    "index": idx,
                    "status": "error",
                    "reason": "No extractable skill found in content.",
                    "source_url": item.source_url,
                })
                continue

            sid = generate_skill_id(extracted["domain"], extracted["title"])
            emb = build_embedding_text(extracted)
            try:
                skill = await store.create_skill(
                    tenant_id=user.tenant_id,
                    skill_id=sid,
                    title=extracted["title"],
                    domain=extracted["domain"],
                    subdomains=extracted.get("subdomains", []),
                    maturity=1,  # T1_DRAFT
                    source_metadata=source_metadata,
                    steps=extracted.get("steps", []),
                    patterns=extracted.get("patterns", []),
                    anti_patterns=extracted.get("anti_patterns", []),
                    failure_modes=extracted.get("failure_modes", []),
                    confidence=extracted.get("confidence", 0.0),
                    embedding_text=emb,
                )
            except Exception as exc:
                results.append({
                    "index": idx,
                    "status": "error",
                    "reason": f"Persist failed: {exc}",
                    "source_url": item.source_url,
                })
                continue

            results.append({
                "index": idx,
                "status": "ok",
                "skill_id": skill.get("skill_id") or sid,
                "source_url": item.source_url,
                "creator": item.creator,
            })

    ok_count = sum(1 for r in results if r["status"] == "ok")
    error_count = len(results) - ok_count
    logger.info(
        "skill_refinery.contentops_ingest",
        batch_label=batch_label,
        tenant_id=str(user.tenant_id),
        ok=ok_count,
        err=error_count,
    )
    return {
        "success": True,
        "data": {
            "batch_label": batch_label,
            "ok": ok_count,
            "errors": error_count,
            "results": results,
        },
    }


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

    On APPROVE, updates the skill with refined content and promotes
    to T2_REFINED maturity. NEEDS_WORK and REJECT write nothing: the
    proposed changes are returned for human review only. Every verdict
    is appended to the refinery decision ledger with an applied flag.
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

    applied = False

    # Apply and promote on APPROVE only. NEEDS_WORK means the critic
    # found problems -- the proposal goes back for human review and the
    # stored skill is never auto-written on a failing verdict.
    if verdict == "APPROVE" and refined:
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

        applied = True

    _ledger_refinement_decision({
        "skill_id": skill_id,
        "tenant_id": str(user.tenant_id),
        "verdict": verdict,
        "applied": applied,
        "confidence": result.get("confidence", 0.0),
    })

    # Return full result with before/after
    return {
        "success": True,
        "data": {
            "verdict": verdict,
            "applied": applied,
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


