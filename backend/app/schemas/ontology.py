"""Request schemas for the typed ontology CRUD endpoints (PR-3).

Only inbound payloads need a schema here: response bodies are produced by each
model's ``to_dict()`` (ontology.py), so there is no response model to duplicate.
``OntologyEntityCreate`` is shared by all six entity kinds because they share one
column bundle; ``EntityLinkCreate`` covers the operator-defined edge.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OntologyEntityCreate(BaseModel):
    """Inbound payload for creating any of the six typed entities."""

    name: str
    description: str = ""
    status: str | None = None
    meta: dict = Field(default_factory=dict)


class EntityLinkCreate(BaseModel):
    """Inbound payload for creating an operator-defined edge."""

    src_kind: str
    src_id: str
    dst_kind: str
    dst_id: str
    rel: str
    weight: float = 1.0
    meta: dict = Field(default_factory=dict)
