"""Mission Control graph endpoint -- read-only org projection.

Mirrors the auth + ``{"success": True, "data": ...}`` envelope used by
``agents.py``. No writes, no migrations. Cache-Control keeps the canvas
snappy without staleness risk on a low-write graph.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.sse_channels import graph_channel
from app.schemas.graph import GraphSearchRequest
from app.services.graph_service import GraphService

router = APIRouter()

# Standard SSE response headers; matches the autopilot/queue/scan stream
# convention so every Daena SSE endpoint frames identically (no-cache so a
# proxy never replays a stale event, no buffering so pushes arrive promptly).
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("")
async def get_graph(
    response: Response,
    kinds: str | None = Query(default=None, description="comma-separated kinds"),
    center: str | None = Query(default=None, description="node id to center on"),
    depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=1000, ge=1, le=5000),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the tenant's org graph as nodes + edges + stats."""
    kinds_tuple = (
        tuple(k.strip() for k in kinds.split(",") if k.strip()) if kinds else None
    )
    svc = GraphService(db, tenant_id=user.tenant_id)
    data = await svc.build_graph(
        kinds=kinds_tuple, center=center, depth=depth, limit=limit
    )
    response.headers["Cache-Control"] = "private, max-age=30"
    return {"success": True, "data": data.model_dump(mode="json")}


@router.get("/stream")
async def stream_graph(
    request: Request,
    _user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Live "something moved" doorbell for the Mission Control Brain.

    Subscribes to ``graph_channel`` and forwards each envelope as an SSE
    frame. The events are THIN notifications -- the canvas reacts by
    re-fetching GET /graph and diffing it client-side, so this stream never
    carries the projection (and therefore never goes stale or races the
    read endpoint). ``ping`` heartbeats (every 25s idle) keep proxies from
    reaping the connection; the client ignores them.

    Auth mirrors GET /graph (``get_current_user``) so the stream is no more
    exposed than the projection it announces. Read-only: opening or closing
    the stream mutates nothing. Stays open until the client disconnects.
    """

    async def _event_stream():
        async for envelope in graph_channel.subscribe():
            if await request.is_disconnected():
                break
            data = json.dumps(envelope)
            yield f"event: {envelope['type']}\ndata: {data}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/search")
async def search_graph(
    body: GraphSearchRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ragx-highlight semantic search across the tenant's org graph (PR-4).

    No Cache-Control: ragx state can flip between calls and an offline
    result must surface in real time per Rule 17.
    """
    svc = GraphService(db, tenant_id=user.tenant_id)
    result = await svc.semantic_search(q=body.q, k=body.k)
    return {"success": True, "data": result.model_dump(mode="json")}


@router.get("/node/{kind}/{node_id}")
async def get_node(
    kind: str,
    node_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detail payload for one node plus its depth-1 neighbors (PR-5).

    No Cache-Control: the Activity and AI Context tabs reflect live audit
    and ragx state. A 404 covers cross-tenant ids and unknown kinds (the
    projection is tenant-filtered, so a missing id is never confirmed as
    belonging to another tenant -- Rule 17 honesty without leakage).
    """
    svc = GraphService(db, tenant_id=user.tenant_id)
    detail = await svc.get_node_detail(kind=kind, node_id=node_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="node not found")
    return {"success": True, "data": detail.model_dump(mode="json")}
