"""Typed ontology entities for Mission Control (PR-3).

Six first-class organizational entity kinds that have no existing backing
table -- Workflow, Sop, Document, Decision, Risk, Kpi -- plus one
EntityLink edge table for relationships that have no natural foreign key.

Each entity mirrors the project.py convention exactly (Base + TenantMixin +
TimestampMixin, a GUID primary key with a python-side uuid4 default so the
SQLite test path that does not supply an id still works, JSONBCompat meta)
and shares a single column-bundle mixin so the six tables stay identical in
shape. They anchor to the virtual daena:root node in the graph projection
(like project and skill) -- no department FK, because these entities are
org-wide.

A generic entity/edge store was deliberately REJECTED (plan section 5): it
would fork the data model away from the service-layer + governance
conventions every other model follows. These are real typed tables.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class _OntologyEntityMixin:
    """Shared columns for the six typed ontology entities.

    Pure column bundle -- NOT a declarative base. Each concrete entity
    inherits (Base, TenantMixin, TimestampMixin, _OntologyEntityMixin) and
    sets __tablename__ + KIND. tenant_id / created_at / updated_at come from
    the two mixins; id / name / description / status / meta live here.
    SQLAlchemy copies these mapped_column definitions into every subclass,
    the same way TenantMixin.tenant_id is reused across the model layer.
    """

    # ClassVar so the declarative scanner ignores it (not a column); each
    # concrete entity overrides it and to_dict() / the projection read it.
    KIND: ClassVar[str] = "entity"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONBCompat(), default=dict, server_default="{}")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "kind": self.KIND,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "meta": self.meta or {},
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Workflow(Base, TenantMixin, TimestampMixin, _OntologyEntityMixin):
    """A defined multi-step process the organization runs."""

    __tablename__ = "workflows"
    KIND: ClassVar[str] = "workflow"


class Sop(Base, TenantMixin, TimestampMixin, _OntologyEntityMixin):
    """A standard operating procedure."""

    __tablename__ = "sops"
    KIND: ClassVar[str] = "sop"


class Document(Base, TenantMixin, TimestampMixin, _OntologyEntityMixin):
    """A stored organizational document / knowledge artifact."""

    __tablename__ = "documents"
    KIND: ClassVar[str] = "document"


class Decision(Base, TenantMixin, TimestampMixin, _OntologyEntityMixin):
    """A recorded decision (ADR-style); rationale lives in meta."""

    __tablename__ = "decisions"
    KIND: ClassVar[str] = "decision"


class Risk(Base, TenantMixin, TimestampMixin, _OntologyEntityMixin):
    """A tracked organizational risk."""

    __tablename__ = "risks"
    KIND: ClassVar[str] = "risk"


class Kpi(Base, TenantMixin, TimestampMixin, _OntologyEntityMixin):
    """A key performance indicator the organization measures."""

    __tablename__ = "kpis"
    KIND: ClassVar[str] = "kpi"


class EntityLink(Base, TenantMixin, TimestampMixin):
    """A typed edge between two graph entities with no natural foreign key.

    src/dst are stored as (kind, raw_id) pairs; the graph projection
    reconstructs the node id via _nid(kind, raw_id) and emits the edge only
    when BOTH endpoints are present in the projection (dangling-safe). No
    DB-level uniqueness constraint -- the projection dedupes by synthesized
    edge id, so a duplicate (src, dst, rel) row is harmless and an operator
    can attach weighted parallel relationships if needed.
    """

    __tablename__ = "entity_links"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    src_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    src_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dst_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    dst_id: Mapped[str] = mapped_column(String(255), nullable=False)
    rel: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, server_default="1")
    meta: Mapped[dict] = mapped_column(JSONBCompat(), default=dict, server_default="{}")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "src_kind": self.src_kind,
            "src_id": self.src_id,
            "dst_kind": self.dst_kind,
            "dst_id": self.dst_id,
            "rel": self.rel,
            "weight": self.weight,
            "meta": self.meta or {},
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
