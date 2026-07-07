"""Minimal CRUD for the typed ontology entities and EntityLink edges (PR-3).

The six entity kinds (workflow / sop / document / decision / risk / kpi) share
one shape, so a single pair of list/create routes keyed by ``{kind}`` covers all
of them; a second pair covers the operator-defined EntityLink edges. Every query
is tenant-scoped via ``user.tenant_id`` and returns the house
``{"success", "data"}`` envelope (mirroring graph.py). Writes follow the
flush -> refresh -> to_dict -> commit pattern so the server-default created_at is
populated before serialization (get_db also commits on success; the explicit
commit matches the projects.py CRUD convention).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.ontology import (
    Decision,
    Document,
    EntityLink,
    Kpi,
    Risk,
    Sop,
    Workflow,
)
from app.schemas.ontology import EntityLinkCreate, OntologyEntityCreate

router = APIRouter()

# Maps the URL {kind} segment to its backing model. Keeping this here (not on the
# graph projection's _ONTOLOGY_KINDS, which also carries the projection verb)
# avoids importing service-layer concerns into the API surface.
_MODELS = {
    "workflow": Workflow,
    "sop": Sop,
    "document": Document,
    "decision": Decision,
    "risk": Risk,
    "kpi": Kpi,
}


def _model_for(kind: str):
    """Resolve a {kind} URL segment to its model, or 404 on an unknown kind."""
    model = _MODELS.get(kind)
    if model is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown ontology kind '{kind}'. Valid kinds: {', '.join(_MODELS)}.",
        )
    return model


# -- Entities --


@router.get("/entities/{kind}")
async def list_entities(
    kind: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all entities of one kind for the caller's tenant."""
    model = _model_for(kind)
    rows = (
        await db.execute(
            select(model).where(model.tenant_id == user.tenant_id)
        )
    ).scalars().all()
    return {"success": True, "data": [r.to_dict() for r in rows]}


@router.post("/entities/{kind}")
async def create_entity(
    kind: str,
    body: OntologyEntityCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create one entity of the given kind."""
    model = _model_for(kind)
    row = model(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        status=body.status,
        meta=body.meta,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    result = row.to_dict()
    await db.commit()
    return {"success": True, "data": result}


# -- Operator-defined edges --


@router.get("/links")
async def list_links(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all operator-defined edges for the caller's tenant."""
    rows = (
        await db.execute(
            select(EntityLink).where(EntityLink.tenant_id == user.tenant_id)
        )
    ).scalars().all()
    return {"success": True, "data": [r.to_dict() for r in rows]}


@router.post("/links")
async def create_link(
    body: EntityLinkCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create one operator-defined edge.

    No endpoint-existence validation here: the graph projection is dangling-safe
    (it drops an edge whose src/dst node is absent), so a link can be created
    before its endpoints exist and will light up once they do.
    """
    row = EntityLink(
        tenant_id=user.tenant_id,
        src_kind=body.src_kind,
        src_id=body.src_id,
        dst_kind=body.dst_kind,
        dst_id=body.dst_id,
        rel=body.rel,
        weight=body.weight,
        meta=body.meta,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    result = row.to_dict()
    await db.commit()
    return {"success": True, "data": result}
