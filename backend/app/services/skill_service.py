"""Skill catalog service: CRUD + discovery for reusable tool definitions.

Skills are Daena's equivalent of MCP tools — each skill defines:
- A name and description
- A JSON Schema for input parameters
- An implementation reference (Python code or module path)
- A governance tier (default risk classification)

Skills are tenant-scoped. A tenant's skill catalog determines what
tools are available to their agents and DaenaBot.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update

from app.core.exceptions import ConflictError
from app.core.logging import get_logger
from app.models.execution import Skill
from app.services._base import BaseService

logger = get_logger(__name__)


class SkillService(BaseService):
    """Manages the skill catalog: registration, discovery, and lifecycle.

    Usage::

        svc = SkillService(db)

        # Register a skill
        skill = await svc.create_skill(
            name="web_search",
            description="Search the web using Perplexity",
            schema_def={"type": "object", "properties": {...}},
            governance_tier=1,
            tenant_id=tenant_id,
        )

        # Find skills by category
        results = await svc.list_skills(
            tenant_id=tenant_id, category="research"
        )
    """

    @staticmethod
    def _skill_to_dict(skill: Skill) -> dict:
        """Convert a Skill ORM instance to a JSON-serializable dict."""
        return {
            "id": str(skill.id),
            "tenant_id": str(skill.tenant_id),
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "schema_def": skill.schema_def,
            "implementation": skill.implementation,
            "governance_tier": skill.governance_tier,
            "is_active": skill.is_active,
            "version": skill.version,
            "usage_count": skill.usage_count,
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
            "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
        }

    async def create_skill(
        self,
        *,
        name: str,
        tenant_id: UUID,
        description: str | None = None,
        category: str | None = None,
        schema_def: dict | None = None,
        implementation: str | None = None,
        governance_tier: int = 0,
        version: str = "1.0.0",
    ) -> Skill:
        """Register a new skill in the catalog.

        Args:
            name: Unique skill name within the tenant.
            tenant_id: Owning tenant.
            description: Human-readable description.
            category: Grouping category (e.g. "research", "file_ops").
            schema_def: JSON Schema for input parameters.
            implementation: Python code or module reference.
            governance_tier: Default governance tier (0-4).
            version: Semantic version string.

        Returns:
            Created Skill instance.

        Raises:
            ConflictError: If a skill with this name already exists.
        """
        # Check for duplicate name within tenant
        existing = await self.db.execute(
            select(Skill)
            .where(Skill.tenant_id == tenant_id)
            .where(Skill.name == name)
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(f"Skill '{name}' already exists")

        skill = Skill(
            name=name,
            description=description,
            category=category,
            schema_def=schema_def or {},
            implementation=implementation,
            governance_tier=governance_tier,
            version=version,
            tenant_id=tenant_id,
            is_active=True,
            usage_count=0,
        )
        self.db.add(skill)
        await self.db.commit()
        await self.db.refresh(skill)

        logger.info(
            "skill_created",
            skill_id=str(skill.id),
            name=name,
            tier=governance_tier,
        )
        return self._skill_to_dict(skill)

    async def _get_skill_orm(self, skill_id: UUID, tenant_id: UUID) -> Skill:
        """Get a skill ORM object by ID (for internal use)."""
        return await self._get_or_404(
            Skill, skill_id, "Skill", tenant_id=tenant_id,
        )

    async def get_skill(self, skill_id: UUID, tenant_id: UUID) -> dict:
        """Get a skill by ID (serialized dict for API responses)."""
        skill = await self._get_skill_orm(skill_id, tenant_id)
        return self._skill_to_dict(skill)

    async def get_skill_by_name(
        self, name: str, tenant_id: UUID
    ) -> Skill | None:
        """Look up a skill by name within a tenant.

        Returns None if not found (no exception).
        """
        result = await self.db.execute(
            select(Skill)
            .where(Skill.tenant_id == tenant_id)
            .where(Skill.name == name)
        )
        return result.scalar_one_or_none()

    async def list_skills(
        self,
        *,
        tenant_id: UUID,
        category: str | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ):
        """List skills with optional filtering.

        Args:
            tenant_id: Tenant scope.
            category: Filter by category.
            active_only: If True, exclude deactivated skills.
            page: Page number (1-based).
            page_size: Items per page.
        """
        from app.schemas.skills import SkillSummaryResponse

        stmt = select(Skill).where(Skill.tenant_id == tenant_id)
        if category is not None:
            stmt = stmt.where(Skill.category == category)
        if active_only:
            stmt = stmt.where(Skill.is_active.is_(True))
        stmt = stmt.order_by(Skill.name)

        return await self._paginate(
            stmt, Skill, page, page_size,
            response_schema=SkillSummaryResponse,
        )

    async def update_skill(
        self,
        skill_id: UUID,
        tenant_id: UUID,
        *,
        description: str | None = None,
        category: str | None = None,
        schema_def: dict | None = None,
        implementation: str | None = None,
        governance_tier: int | None = None,
        is_active: bool | None = None,
        version: str | None = None,
    ) -> Skill:
        """Update a skill's metadata or implementation.

        Only provided (non-None) fields are updated.
        """
        skill = await self._get_skill_orm(skill_id, tenant_id)

        if description is not None:
            skill.description = description
        if category is not None:
            skill.category = category
        if schema_def is not None:
            skill.schema_def = schema_def
        if implementation is not None:
            skill.implementation = implementation
        if governance_tier is not None:
            skill.governance_tier = governance_tier
        if is_active is not None:
            skill.is_active = is_active
        if version is not None:
            skill.version = version

        await self.db.commit()
        await self.db.refresh(skill)

        logger.info(
            "skill_updated",
            skill_id=str(skill_id),
            name=skill.name,
        )
        return self._skill_to_dict(skill)

    async def increment_usage(
        self, skill_id: UUID, tenant_id: UUID
    ) -> None:
        """Increment the usage counter for a skill.

        Called after successful tool execution to track popularity.
        """
        await self.db.execute(
            update(Skill)
            .where(Skill.id == skill_id)
            .where(Skill.tenant_id == tenant_id)
            .values(usage_count=Skill.usage_count + 1)
        )
        await self.db.commit()

    async def deactivate_skill(
        self, skill_id: UUID, tenant_id: UUID
    ) -> Skill:
        """Soft-deactivate a skill (keeps in catalog but hidden)."""
        return await self.update_skill(
            skill_id, tenant_id, is_active=False,
        )
