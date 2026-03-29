"""Organization models: Department, Agent, BrainModel.

Defines the Sunflower-Honeycomb agent hierarchy.
10 departments x 6 sub-capabilities = 60 agents.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.identity import Tenant


class Department(Base, TenantMixin, TimestampMixin):
    """One of 10 departments in Daena's organizational structure.

    Positioned via Sunflower-Honeycomb architecture (golden angle spiral).
    """

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_departments_tenant_id_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    sunflower_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cell_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    config: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="departments")
    agents: Mapped[list[Agent]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )


class Agent(Base, TenantMixin, TimestampMixin):
    """Individual agent with one sub-capability within a department.

    10 departments x 6 sub-capabilities = 60 possible agents.
    Unique constraint ensures one sub-cap per department.
    """

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint(
            "department_id", "sub_capability",
            name="uq_agents_department_id_sub_capability",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_capability: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    model_preference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    department: Mapped[Department] = relationship(back_populates="agents")


class BrainModel(Base, TenantMixin, TimestampMixin):
    """Registry of available AI/LLM models. Health-checked periodically."""

    __tablename__ = "brain_models"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", "model_name",
            name="uq_brain_models_tenant_id_provider_model_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,

    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    capabilities: Mapped[list] = mapped_column(JSONBCompat, nullable=False, server_default="[]")
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    health_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="UNAVAILABLE"
    )
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    config: Mapped[dict] = mapped_column(JSONBCompat, nullable=False, server_default="{}")
