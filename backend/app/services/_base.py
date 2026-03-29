"""Base service class with shared utilities.

All Daena services inherit from BaseService for:
- Tenant-scoped query building
- Pagination helpers
- Common get-or-404 pattern
"""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.schemas._base import PaginatedMeta, PaginatedResponse


class BaseService:
    """Base class for all Daena services.

    Provides tenant-scoped query helpers and pagination utilities.
    Instantiated per-request via FastAPI dependency injection.

    Usage::

        class ChatService(BaseService):
            async def get_session(self, session_id: UUID):
                return await self._get_or_404(
                    ChatSession, session_id, "Chat session"
                )
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_or_404(
        self,
        model: type,
        entity_id: UUID,
        label: str = "Resource",
        *,
        tenant_id: UUID | None = None,
    ):
        """Fetch a single entity by ID, raising NotFoundError if missing.

        Args:
            model: SQLAlchemy model class.
            entity_id: Primary key UUID.
            label: Human-readable name for error messages.
            tenant_id: Optional tenant filter for multi-tenant isolation.

        Returns:
            The model instance.

        Raises:
            NotFoundError: If entity does not exist.
        """
        stmt = select(model).where(model.id == entity_id)
        if tenant_id is not None and hasattr(model, "tenant_id"):
            stmt = stmt.where(model.tenant_id == tenant_id)

        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise NotFoundError(f"{label} not found: {entity_id}")
        return entity

    def _tenant_filter(
        self, stmt: Select, model: type, tenant_id: UUID
    ) -> Select:
        """Add tenant_id filter to a query if the model supports it.

        Args:
            stmt: SQLAlchemy select statement.
            model: ORM model class.
            tenant_id: Tenant UUID to filter by.

        Returns:
            Filtered select statement.
        """
        if hasattr(model, "tenant_id"):
            return stmt.where(model.tenant_id == tenant_id)
        return stmt

    async def _paginate(
        self,
        stmt: Select,
        model: type,
        page: int,
        page_size: int,
        *,
        response_schema: type | None = None,
    ) -> PaginatedResponse:
        """Execute a paginated query and return envelope response.

        Args:
            stmt: Base select statement (filters already applied).
            model: ORM model class for count query.
            page: 1-based page number.
            page_size: Items per page.
            response_schema: Optional Pydantic schema to serialize items.

        Returns:
            PaginatedResponse with data, pagination meta.
        """
        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        paginated = stmt.offset(offset).limit(page_size)
        result = await self.db.execute(paginated)
        items = list(result.scalars().all())

        # Serialize if schema provided
        if response_schema is not None:
            data = [response_schema.model_validate(item) for item in items]
        else:
            data = items

        return PaginatedResponse(
            data=data,
            pagination=PaginatedMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=max(1, math.ceil(total / page_size)),
            ),
        )
