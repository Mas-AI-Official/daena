"""Business growth loop orchestrator -- Sprint-19 PR-1.

Single entry point: ``run_discovery_loop(db, *, tenant_id, top_n,
initiator) -> DiscoveryRunResult``.

Flow:
  1. Iterate registered sources, collect DiscoveredOpportunity.
  2. Dedupe by deterministic key (source_name + title hash).
  3. Score each via deterministic scorer.
  4. Sort desc by score, cap at ``top_n``.
  5. Upsert into ``opportunities`` table (insert if not exists by
     dedupe_key, update score / fields if exists).
  6. Return summary.

NEVER calls a tool handler. NEVER sends external traffic. NEVER
auto-approves anything. Pure local-write orchestration.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import Opportunity
from app.services.business_pipeline.discoverer import (
    DiscoveredOpportunity,
    SOURCE_REGISTRY,
)
from app.services.business_pipeline.scorer import score_opportunity

logger = get_logger(__name__)


DEFAULT_TOP_N: int = 10


@dataclass
class DiscoveryRunResult:
    discovered_count: int = 0
    deduped_count: int = 0
    persisted_count: int = 0
    updated_count: int = 0
    capped_count: int = 0
    sources_queried: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None


def _dedupe_key(d: DiscoveredOpportunity) -> str:
    payload = f"{d.source_name}::{d.title.strip().lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


async def run_discovery_loop(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    top_n: int = DEFAULT_TOP_N,
    initiator: str = "operator",
) -> DiscoveryRunResult:
    """Run one full discovery cycle. NEVER raises (all source
    exceptions captured into sources_failed).

    Args:
      db: tenant-scoped DB session.
      tenant_id: tenant to attach Opportunity rows to.
      top_n: maximum number of opportunities to persist this cycle
        (cap is by score-desc; the rest are dropped). Hard wall
        against approval-fatigue.
      initiator: 'operator' / 'scheduler' / 'self_healing' /
        'delegated'. Audit only -- the orchestrator does NOT mutate
        behavior on initiator. Auto-approval gating happens at the
        DOWNSTREAM dispatch path, not here.
    """
    result = DiscoveryRunResult(
        started_at=datetime.now(UTC).isoformat(),
    )

    # Step 1: collect from sources
    collected: list[DiscoveredOpportunity] = []
    for name, fn in SOURCE_REGISTRY.items():
        result.sources_queried.append(name)
        try:
            for op in fn():
                if isinstance(op, DiscoveredOpportunity):
                    collected.append(op)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "business.source.failed", source=name, error=str(exc),
            )
            result.sources_failed.append(name)
    result.discovered_count = len(collected)

    # Step 2: dedupe by source+title
    seen: set[str] = set()
    deduped: list[tuple[str, DiscoveredOpportunity]] = []
    for op in collected:
        key = _dedupe_key(op)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((key, op))
    result.deduped_count = len(deduped)

    # Step 3: score everything
    scored = [(key, op, score_opportunity(op)) for key, op in deduped]

    # Step 4: sort desc, cap at top_n
    scored.sort(key=lambda t: t[2], reverse=True)
    capped = scored[:top_n]
    result.capped_count = len(scored) - len(capped)

    # Step 5: upsert into DB
    for key, op, score in capped:
        existing_stmt = select(Opportunity).where(
            Opportunity.tenant_id == tenant_id,
            Opportunity.dedupe_key == key,
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()

        if existing is None:
            row = Opportunity(
                tenant_id=tenant_id,
                type=op.type,
                title=op.title,
                description=op.description,
                source_name=op.source_name,
                source_url=op.source_url,
                score=score,
                deadline_at=op.deadline_at,
                estimated_value_usd=op.estimated_value_usd,
                effort_hours=op.effort_hours,
                risk_label=op.risk_label,
                next_action=op.next_action,
                status="discovered",
                raw_metadata=op.raw_metadata or None,
                dedupe_key=key,
            )
            db.add(row)
            result.persisted_count += 1
        else:
            # Update score + drift fields, leave status alone (operator
            # may have advanced it through the pipeline).
            existing.score = score
            existing.title = op.title
            existing.description = op.description
            existing.source_url = op.source_url
            existing.deadline_at = op.deadline_at
            existing.estimated_value_usd = op.estimated_value_usd
            existing.effort_hours = op.effort_hours
            existing.risk_label = op.risk_label
            existing.next_action = op.next_action
            existing.raw_metadata = op.raw_metadata or None
            result.updated_count += 1

    try:
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("business.discovery.flush_failed", error=str(exc))

    result.finished_at = datetime.now(UTC).isoformat()
    logger.info(
        "business.discovery.complete",
        discovered=result.discovered_count,
        deduped=result.deduped_count,
        persisted=result.persisted_count,
        updated=result.updated_count,
        capped=result.capped_count,
        initiator=initiator,
    )
    return result
