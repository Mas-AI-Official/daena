"""Skill store: CRUD + tier promotion/demotion for refined skills.

Manages the lifecycle of RefinedSkill entries:
    create -> search -> promote -> version -> archive

Follows the same patterns as MemoryService (tier-based,
tenant-scoped, soft-delete via archived_at).
"""

from __future__ import annotations

import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.skill import MATURITY_LABELS, MATURITY_TIERS, RefinedSkill

# After this many uses, flag the skill for re-refinement review
_USAGE_REFINEMENT_THRESHOLD = 10

logger = get_logger(__name__)

_MAX_MATURITY = MATURITY_TIERS["T4_COMPOUND"]
_MIN_MATURITY = MATURITY_TIERS["T0_RAW"]


class SkillStore:
    """CRUD + promotion/demotion for refined skills.

    Usage::

        store = SkillStore(db)
        skill = await store.create_skill(
            tenant_id=tid,
            skill_id="skill_web_001",
            title="SaaS hero section",
            domain="web_design",
            steps=["Write headline", "Add CTA"],
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_skill(
        self,
        *,
        tenant_id: UUID,
        skill_id: str,
        title: str,
        domain: str,
        subdomains: list[str] | None = None,
        maturity: int = 0,
        source_metadata: dict | None = None,
        steps: list[str] | None = None,
        patterns: list[str] | None = None,
        anti_patterns: list[str] | None = None,
        improvements_by_daena: list[str] | None = None,
        failure_modes: list[str] | None = None,
        confidence: float = 0.0,
        embedding_text: str | None = None,
    ) -> dict:
        """Create a new refined skill entry."""
        if maturity > MATURITY_TIERS["T1_DRAFT"]:
            msg = (
                f"Cannot directly create at maturity {maturity}. "
                "New skills enter at T0_RAW or T1_DRAFT. Use promote_skill() for higher tiers."
            )
            raise ValidationError(msg)

        entry = RefinedSkill(
            tenant_id=tenant_id,
            skill_id=skill_id,
            title=title,
            domain=domain,
            subdomains=subdomains or [],
            maturity=maturity,
            source_metadata=source_metadata or {},
            steps=steps or [],
            patterns=patterns or [],
            anti_patterns=anti_patterns or [],
            improvements_by_daena=improvements_by_daena or [],
            failure_modes=failure_modes or [],
            confidence=confidence,
            embedding_text=embedding_text,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        logger.info(
            "skill_store.created",
            skill_id=skill_id,
            domain=domain,
            maturity=MATURITY_LABELS.get(maturity, str(maturity)),
        )
        return self._to_dict(entry)

    async def get_skill(
        self,
        *,
        skill_id: str,
        tenant_id: UUID,
    ) -> dict:
        """Get a single skill by its skill_id."""
        entry = await self._get_by_skill_id(skill_id, tenant_id)
        return self._to_dict(entry)

    async def search_skills_by_domain(
        self,
        *,
        tenant_id: UUID,
        domain: str,
        min_maturity: int = 0,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Search skills by domain with optional maturity filter."""
        stmt = (
            select(RefinedSkill)
            .where(
                RefinedSkill.tenant_id == tenant_id,
                RefinedSkill.domain == domain,
                RefinedSkill.maturity >= min_maturity,
                RefinedSkill.archived_at.is_(None),
            )
            .order_by(RefinedSkill.confidence.desc())
        )

        return await self._paginate(stmt, tenant_id, page, page_size)

    async def list_skills_by_maturity(
        self,
        *,
        tenant_id: UUID,
        maturity: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """List all skills at a specific maturity tier."""
        stmt = (
            select(RefinedSkill)
            .where(
                RefinedSkill.tenant_id == tenant_id,
                RefinedSkill.maturity == maturity,
                RefinedSkill.archived_at.is_(None),
            )
            .order_by(RefinedSkill.created_at.desc())
        )

        return await self._paginate(stmt, tenant_id, page, page_size)

    async def update_skill_version(
        self,
        *,
        skill_id: str,
        tenant_id: UUID,
        version: str,
        steps: list[str] | None = None,
        patterns: list[str] | None = None,
        anti_patterns: list[str] | None = None,
        improvements_by_daena: list[str] | None = None,
        failure_modes: list[str] | None = None,
        confidence: float | None = None,
        embedding_text: str | None = None,
    ) -> dict:
        """Update a skill's version and content fields."""
        entry = await self._get_by_skill_id(skill_id, tenant_id)
        entry.version = version
        if steps is not None:
            entry.steps = steps
        if patterns is not None:
            entry.patterns = patterns
        if anti_patterns is not None:
            entry.anti_patterns = anti_patterns
        if improvements_by_daena is not None:
            entry.improvements_by_daena = improvements_by_daena
        if failure_modes is not None:
            entry.failure_modes = failure_modes
        if confidence is not None:
            entry.confidence = confidence
        if embedding_text is not None:
            entry.embedding_text = embedding_text

        await self.db.flush()
        await self.db.refresh(entry)

        logger.info(
            "skill_store.version_updated",
            skill_id=skill_id,
            version=version,
        )
        return self._to_dict(entry)

    async def promote_skill(
        self,
        *,
        skill_id: str,
        tenant_id: UUID,
    ) -> dict:
        """Promote a skill to the next maturity tier."""
        entry = await self._get_by_skill_id(skill_id, tenant_id)

        if entry.maturity >= _MAX_MATURITY:
            msg = f"Cannot promote beyond {MATURITY_LABELS[_MAX_MATURITY]}"
            raise ValidationError(msg)

        old_tier = entry.maturity
        entry.maturity = old_tier + 1
        entry.last_validated = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(entry)

        logger.info(
            "skill_store.promoted",
            skill_id=skill_id,
            from_tier=MATURITY_LABELS[old_tier],
            to_tier=MATURITY_LABELS[entry.maturity],
        )
        return self._to_dict(entry)

    async def demote_skill(
        self,
        *,
        skill_id: str,
        tenant_id: UUID,
    ) -> dict:
        """Demote a skill to the previous maturity tier."""
        entry = await self._get_by_skill_id(skill_id, tenant_id)

        if entry.maturity <= _MIN_MATURITY:
            msg = f"Cannot demote below {MATURITY_LABELS[_MIN_MATURITY]}"
            raise ValidationError(msg)

        old_tier = entry.maturity
        entry.maturity = old_tier - 1

        await self.db.flush()
        await self.db.refresh(entry)

        logger.info(
            "skill_store.demoted",
            skill_id=skill_id,
            from_tier=MATURITY_LABELS[old_tier],
            to_tier=MATURITY_LABELS[entry.maturity],
        )
        return self._to_dict(entry)

    async def archive_skill(
        self,
        *,
        skill_id: str,
        tenant_id: UUID,
    ) -> dict:
        """Archive a skill (soft delete per Rule 2)."""
        entry = await self._get_by_skill_id(skill_id, tenant_id)
        entry.archived_at = datetime.utcnow()

        await self.db.flush()
        await self.db.refresh(entry)

        logger.info("skill_store.archived", skill_id=skill_id)
        return self._to_dict(entry)

    # ── Usage tracking ──

    async def track_usage(
        self,
        skill_id: str,
        tenant_id: UUID,
        *,
        success: bool,
        feedback: str | None = None,
    ) -> dict:
        """Record a skill usage event and update quality metrics.

        Increments usage_count, recomputes success_rate as a running
        average, and flags the skill for re-refinement after reaching
        the usage threshold (10 uses).

        Args:
            skill_id: Unique skill identifier.
            tenant_id: Tenant UUID for scoping.
            success: Whether the skill usage was successful.
            feedback: Optional user feedback text.

        Returns:
            Dict with updated stats and needs_refinement flag.
        """
        entry = await self._get_by_skill_id(skill_id, tenant_id)

        old_count = entry.usage_count or 0
        old_rate = entry.success_rate if entry.success_rate is not None else 1.0
        new_count = old_count + 1

        # Running average for success rate
        new_rate = ((old_rate * old_count) + (1.0 if success else 0.0)) / new_count

        entry.usage_count = new_count
        entry.success_rate = round(new_rate, 4)
        entry.last_validated = datetime.utcnow()

        # Store feedback in improvements_by_daena if provided
        if feedback:
            existing = list(entry.improvements_by_daena or [])
            existing.append(
                f"[usage-feedback] {feedback} (success={success})"
            )
            entry.improvements_by_daena = existing

        await self.db.flush()

        needs_refinement = new_count >= _USAGE_REFINEMENT_THRESHOLD
        if needs_refinement:
            logger.info(
                "skill_refinement_flagged",
                skill_id=skill_id,
                usage_count=new_count,
                success_rate=new_rate,
                reason="usage_threshold_reached",
            )

        return {
            "skill_id": skill_id,
            "usage_count": new_count,
            "success_rate": new_rate,
            "needs_refinement": needs_refinement,
            "last_used": (
                entry.last_validated.isoformat() if entry.last_validated else None
            ),
        }

    async def get_usage_stats(
        self,
        skill_id: str,
        tenant_id: UUID,
    ) -> dict:
        """Get usage statistics for a specific skill.

        Args:
            skill_id: Unique skill identifier.
            tenant_id: Tenant UUID for scoping.

        Returns:
            Dict with usage_count, success_rate, last_used,
            needs_refinement flag, and feedback summary.
        """
        entry = await self._get_by_skill_id(skill_id, tenant_id)

        usage_count = entry.usage_count or 0
        success_rate = (
            float(entry.success_rate) if entry.success_rate is not None else None
        )
        last_used = (
            entry.last_validated.isoformat() if entry.last_validated else None
        )

        # Extract feedback entries from improvements_by_daena
        feedback_entries = [
            item
            for item in (entry.improvements_by_daena or [])
            if isinstance(item, str) and item.startswith("[usage-feedback]")
        ]

        return {
            "skill_id": skill_id,
            "usage_count": usage_count,
            "success_rate": success_rate,
            "last_used": last_used,
            "needs_refinement": usage_count >= _USAGE_REFINEMENT_THRESHOLD,
            "feedback_count": len(feedback_entries),
            "feedback_summary": feedback_entries[-5:] if feedback_entries else [],
        }

    # ── Internal helpers ──

    async def _get_by_skill_id(
        self,
        skill_id: str,
        tenant_id: UUID,
    ) -> RefinedSkill:
        """Fetch a skill by skill_id scoped to tenant."""
        stmt = select(RefinedSkill).where(
            RefinedSkill.skill_id == skill_id,
            RefinedSkill.tenant_id == tenant_id,
            RefinedSkill.archived_at.is_(None),
        )
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError(f"Skill not found: {skill_id}")
        return entry

    async def _paginate(
        self,
        stmt,
        tenant_id: UUID,
        page: int,
        page_size: int,
    ) -> dict:
        """Execute a paginated query."""
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        paginated = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(paginated)
        items = list(result.scalars().all())

        return {
            "data": [self._to_dict(e) for e in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": max(1, math.ceil(total / page_size)),
            },
        }

    @staticmethod
    def _to_dict(entry: RefinedSkill) -> dict:
        """Convert RefinedSkill to response dict."""
        return {
            "id": str(entry.id),
            "skill_id": entry.skill_id,
            "version": entry.version,
            "title": entry.title,
            "domain": entry.domain,
            "subdomains": entry.subdomains or [],
            "maturity": entry.maturity,
            "maturity_label": MATURITY_LABELS.get(entry.maturity, f"T{entry.maturity}"),
            "source_metadata": entry.source_metadata or {},
            "steps": entry.steps or [],
            "patterns": entry.patterns or [],
            "anti_patterns": entry.anti_patterns or [],
            "improvements_by_daena": entry.improvements_by_daena or [],
            "failure_modes": entry.failure_modes or [],
            "confidence": float(entry.confidence),
            "usage_count": entry.usage_count,
            "success_rate": float(entry.success_rate) if entry.success_rate is not None else None,
            "last_validated": (
                entry.last_validated.isoformat() if entry.last_validated else None
            ),
            "embedding_text": entry.embedding_text,
            "archived_at": (
                entry.archived_at.isoformat() if entry.archived_at else None
            ),
            "tenant_id": str(entry.tenant_id),
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }
