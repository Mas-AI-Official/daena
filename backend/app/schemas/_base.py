"""Shared schema base classes and response envelopes.

Provides:
- StandardResponse[T]: Typed success envelope  {"success": true, "data": T}
- ErrorDetail: Error sub-object                {"code": "...", "message": "..."}
- ErrorResponse: Typed error envelope          {"success": false, "error": {...}}
- PaginatedResponse[T]: Paginated envelope     {"success": true, "data": [...], ...}
- PaginationParams: Query param extractor
- DaenaSchema: Base model with common config
"""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class DaenaSchema(BaseModel):
    """Base schema with shared Pydantic configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorDetail(BaseModel):
    """Error detail within an error response."""

    code: str
    message: str
    details: dict | None = None


class StandardResponse(BaseModel, Generic[T]):
    """Standard success response envelope.

    Usage in routes::

        @router.get("/items/{id}")
        async def get_item(...) -> StandardResponse[ItemResponse]:
            return StandardResponse(data=item)
    """

    success: bool = True
    data: T


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    Matches the format produced by the DaenaError exception handler.
    """

    success: bool = False
    error: ErrorDetail


class PaginationParams(BaseModel):
    """Common pagination query parameters."""

    page: int = 1
    page_size: int = 50

    @property
    def offset(self) -> int:
        """Calculate SQL offset from page number."""
        return (self.page - 1) * self.page_size


class PaginatedMeta(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated success response envelope."""

    success: bool = True
    data: list[T]
    pagination: PaginatedMeta


# --- Common field types reused across schemas ---


class TenantScoped(DaenaSchema):
    """Schema with tenant_id for multi-tenant responses."""

    tenant_id: UUID


class TimestampedResponse(DaenaSchema):
    """Schema with created_at/updated_at for responses."""

    created_at: str | None = None
    updated_at: str | None = None
