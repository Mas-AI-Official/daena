"""Skill freshness monitor: detect stale skills needing re-refinement.

Scans each skill's tools_referenced (from source_metadata) against
current date to flag skills that may be outdated. This is a utility
function, not a cron job. Call it on-demand or from a future scheduler.

Part of Skill Refinery Phase 3: governance + monitoring.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.skill import MATURITY_LABELS, RefinedSkill

logger = get_logger(__name__)

# Skills not validated within this window are considered stale
_STALENESS_THRESHOLD_DAYS = 90

# Usage threshold that triggers refinement review
_USAGE_REFINEMENT_THRESHOLD = 10


async def scan_for_updates(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    domains: list[str] | None = None,
    staleness_days: int = _STALENESS_THRESHOLD_DAYS,
) -> list[dict]:
    """Scan skills for freshness and flag those needing re-refinement.

    A skill is flagged if any of these conditions are met:
    1. It hasn't been validated within the staleness window
    2. Its usage_count has crossed the refinement threshold
    3. Its success_rate has dropped below 0.6 (60%)
    4. It has a tool reference in source_metadata with a version
       that may have changed (heuristic: age-based check)

    Args:
        db: Async database session.
        tenant_id: Tenant UUID for scoping.
        domains: Optional list of domains to check. If None, checks all.
        staleness_days: Days after which a skill is considered stale.

    Returns:
        List of dicts describing skills needing refresh, each with:
        skill_id, title, domain, maturity_label, reason, last_validated.
    """
    stmt = select(RefinedSkill).where(
        RefinedSkill.tenant_id == tenant_id,
        RefinedSkill.archived_at.is_(None),
    )
    if domains:
        stmt = stmt.where(RefinedSkill.domain.in_(domains))

    result = await db.execute(stmt)
    skills = result.scalars().all()

    cutoff = datetime.utcnow() - timedelta(days=staleness_days)
    flagged: list[dict] = []

    for skill in skills:
        reasons: list[str] = []

        # Check 1: staleness by last_validated date
        if skill.last_validated is None or skill.last_validated < cutoff:
            days_stale = (
                (datetime.utcnow() - skill.last_validated).days
                if skill.last_validated
                else None
            )
            reasons.append(
                f"not_validated_in_{staleness_days}_days"
                + (f" (last: {days_stale}d ago)" if days_stale else " (never)")
            )

        # Check 2: usage threshold crossed
        if (skill.usage_count or 0) >= _USAGE_REFINEMENT_THRESHOLD:
            reasons.append(
                f"usage_threshold_reached ({skill.usage_count} uses)"
            )

        # Check 3: low success rate
        if (
            skill.success_rate is not None
            and skill.usage_count
            and skill.usage_count >= 5
            and skill.success_rate < 0.6
        ):
            reasons.append(
                f"low_success_rate ({skill.success_rate:.0%})"
            )

        # Check 4: tool version staleness (heuristic)
        source_meta = skill.source_metadata or {}
        tools_referenced = source_meta.get("tools_referenced", [])
        if tools_referenced and skill.last_validated:
            # If tools are referenced and skill hasn't been checked in 60+ days,
            # flag for version verification
            tools_cutoff = datetime.utcnow() - timedelta(days=60)
            if skill.last_validated < tools_cutoff:
                tool_names = (
                    ", ".join(tools_referenced[:3])
                    if isinstance(tools_referenced, list)
                    else str(tools_referenced)
                )
                reasons.append(
                    f"tools_may_have_updated ({tool_names})"
                )

        if reasons:
            flagged.append({
                "skill_id": skill.skill_id,
                "title": skill.title,
                "domain": skill.domain,
                "maturity_label": MATURITY_LABELS.get(
                    skill.maturity, f"T{skill.maturity}"
                ),
                "reasons": reasons,
                "last_validated": (
                    skill.last_validated.isoformat()
                    if skill.last_validated
                    else None
                ),
                "usage_count": skill.usage_count or 0,
                "success_rate": (
                    float(skill.success_rate)
                    if skill.success_rate is not None
                    else None
                ),
            })

    logger.info(
        "skill_freshness_scan",
        tenant_id=str(tenant_id),
        total_scanned=len(skills),
        flagged_count=len(flagged),
        domains=domains,
    )

    return flagged
