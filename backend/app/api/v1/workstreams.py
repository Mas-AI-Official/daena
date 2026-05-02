"""Workstream HTTP endpoints — the `/workstreams` Live Console backend.

Per the Council R3 lock, the workstream is Daena's visible unit of
autonomy. This router exposes the operations the console needs:

    GET    /workstreams                  list (filtered by status)
    POST   /workstreams                  start a new workstream
    GET    /workstreams/{id}             detail + recent events
    POST   /workstreams/{id}/redirect    parse + apply a redirect instruction
    POST   /workstreams/{id}/pause       pause autopilot continuation
    POST   /workstreams/{id}/resume      resume autopilot
    POST   /workstreams/{id}/escalate    bump escalation level
    POST   /workstreams/{id}/cancel      mark FAILED (terminal)
    GET    /workstreams/{id}/events      full timeline

All endpoints are tenant-scoped via ``CurrentUser``.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.sse_channels import get_workstream_channel
from app.models.workstream import (
    WorkstreamEscalationLevel,
    WorkstreamSourceType,
    WorkstreamStatus,
)
from app.services.workstream_redirect_parser import (
    RedirectActionKind,
    parse_redirect,
    render_clarification_hint,
)
from app.services.workstream_service import (
    StartParams,
    WorkstreamNotFoundError,
    WorkstreamService,
    WorkstreamTransitionError,
)

logger = get_logger(__name__)

router = APIRouter()


# ── Request/response schemas ────────────────────────────────────────────


class StartWorkstreamRequest(BaseModel):
    department_id: uuid.UUID
    goal: str = Field(..., min_length=4, max_length=500)
    initial_context: dict | None = None
    next_step_text: str | None = Field(default=None, max_length=500)
    # PR-5: optional source attribution. Defaults to MANUAL on the server
    # if omitted so existing callers do not break.
    source_type: WorkstreamSourceType | None = None
    source_ref_id: uuid.UUID | None = None


class RedirectRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)


class EscalateRequest(BaseModel):
    to_level: WorkstreamEscalationLevel
    reason: str = Field(..., min_length=1, max_length=500)


class CancelRequest(BaseModel):
    reason: str = Field(default="cancelled by user", max_length=500)


class DevSafeDemoRequest(BaseModel):
    """Optional inputs for the dev-safe demo endpoint.

    The endpoint defaults the department to the caller's first active
    department when ``department_id`` is not supplied, so the operator
    can hit the button without picking a dept.
    """

    department_id: uuid.UUID | None = None


def _serialize_workstream(ws) -> dict:
    """Stable JSON shape consumed by the frontend WorkstreamCard."""
    return {
        "id": str(ws.id),
        "tenant_id": str(ws.tenant_id),
        "department_id": str(ws.department_id),
        "user_id": str(ws.user_id),
        "goal": ws.goal,
        "status": ws.status.value,
        "blocker_text": ws.blocker_text,
        "next_step_text": ws.next_step_text,
        "escalation_level": ws.escalation_level.value,
        "context": ws.context,
        "total_tokens": ws.total_tokens,
        "total_cost_cents": ws.total_cost_cents,
        "autopilot_paused": ws.autopilot_paused,
        "last_activity_at": (
            ws.last_activity_at.isoformat() if ws.last_activity_at else None
        ),
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
        # PR-5 spine skeleton fields.
        "source_type": ws.source_type.value,
        "source_ref_id": str(ws.source_ref_id) if ws.source_ref_id else None,
        "progress_percent": ws.progress_percent,
        "artifact_refs": ws.artifact_refs or {},
        "audit_event_refs": ws.audit_event_refs or [],
        "notification_refs": ws.notification_refs or [],
        "archived_at": (
            ws.archived_at.isoformat() if ws.archived_at else None
        ),
    }


def _serialize_event(ev) -> dict:
    """Timeline-event JSON shape for the Live Console timeline."""
    return {
        "id": str(ev.id),
        "kind": ev.kind.value,
        "summary": ev.summary,
        "payload": ev.payload,
        "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────


@router.get("")
async def list_workstreams(
    status: WorkstreamStatus | None = None,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List active workstreams for the current tenant.

    Optional ?status filter. Sorted by last_activity_at desc.
    """
    svc = WorkstreamService(db)
    statuses = [status] if status else None
    items = await svc.list_for_tenant(
        user.tenant_id, statuses=statuses, limit=min(limit, 200),
    )
    return {
        "success": True,
        "data": {
            "workstreams": [_serialize_workstream(w) for w in items],
            "count": len(items),
        },
    }


@router.post("", status_code=201)
async def start_workstream(
    body: StartWorkstreamRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new workstream in RUNNING."""
    svc = WorkstreamService(db)
    ws = await svc.start(
        StartParams(
            tenant_id=user.tenant_id,
            user_id=user.id,
            department_id=body.department_id,
            goal=body.goal,
            initial_context=body.initial_context,
            next_step_text=body.next_step_text,
            source_type=body.source_type or WorkstreamSourceType.MANUAL,
            source_ref_id=body.source_ref_id,
        ),
    )
    return {"success": True, "data": _serialize_workstream(ws)}


@router.get("/{workstream_id}")
async def get_workstream(
    workstream_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Detail view: workstream metadata + last 50 timeline events."""
    svc = WorkstreamService(db)
    try:
        ws = await svc.get(workstream_id, tenant_id=user.tenant_id)
        events = await svc.list_events(
            workstream_id, tenant_id=user.tenant_id, limit=50,
        )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "success": True,
        "data": {
            "workstream": _serialize_workstream(ws),
            "events": [_serialize_event(e) for e in events],
        },
    }


@router.post("/{workstream_id}/redirect")
async def redirect_workstream(
    workstream_id: uuid.UUID,
    body: RedirectRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Parse + apply a redirect instruction.

    Pipeline:
      1. ``parse_redirect`` turns the instruction into a list of
         ``RedirectAction``.
      2. If the parser couldn't fully understand, return 422 with a
         clarification hint instead of partially applying.
      3. Apply each action in order via ``WorkstreamService``.
      4. Return the updated workstream + the applied action list.
    """
    parse_result = await parse_redirect(body.instruction)
    if parse_result.needs_user_clarification:
        hint = render_clarification_hint(parse_result)
        return {
            "success": False,
            "error": {
                "code": "REDIRECT_NOT_UNDERSTOOD",
                "message": hint,
                "unmatched_segments": parse_result.unmatched_segments,
                "raw_instruction": parse_result.raw_instruction,
            },
        }

    svc = WorkstreamService(db)
    try:
        # Group actions: scope/goal/dept changes are batched into one
        # `redirect()` call so they share a single REDIRECTED event.
        # Lifecycle actions (pause/resume/escalate/cancel) are applied
        # separately because each emits its own event.
        scope_constraints: list[str] = []
        new_goal: str | None = None
        new_department_id: uuid.UUID | None = None

        for action in parse_result.actions:
            if action.kind == RedirectActionKind.NARROW_SCOPE:
                if "constraint" in action.payload:
                    scope_constraints.append(action.payload["constraint"])
            elif action.kind == RedirectActionKind.BROADEN_SCOPE:
                if "constraint" in action.payload:
                    scope_constraints.append(f"broaden:{action.payload['constraint']}")
            elif action.kind == RedirectActionKind.REPLACE_GOAL:
                new_goal = action.payload.get("new_goal")
            elif action.kind == RedirectActionKind.REASSIGN_DEPARTMENT:
                # Resolve dept slug to id via the founder's dept list.
                slug = action.payload.get("department_slug", "")
                from sqlalchemy import select
                from app.models.organization import Department
                stmt = select(Department).where(
                    Department.tenant_id == user.tenant_id,
                    Department.is_active.is_(True),
                )
                rows = (await db.execute(stmt)).scalars().all()
                # Find by name match (case-insensitive).
                match = next(
                    (d for d in rows if d.name.lower().replace(" ", "_") == slug),
                    None,
                )
                if match:
                    new_department_id = match.id

        # Apply the goal/scope/dept changes as a single mutation.
        ws = await svc.redirect(
            workstream_id,
            tenant_id=user.tenant_id,
            new_goal=new_goal,
            scope_constraints=scope_constraints or None,
            new_department_id=new_department_id,
            raw_instruction=parse_result.raw_instruction,
        )

        # Apply lifecycle actions in order.
        for action in parse_result.actions:
            if action.kind == RedirectActionKind.PAUSE_AUTOPILOT:
                ws = await svc.pause_autopilot(
                    workstream_id, tenant_id=user.tenant_id,
                    reason=f"redirect: {action.matched_phrase}",
                )
            elif action.kind == RedirectActionKind.RESUME_AUTOPILOT:
                ws = await svc.resume_autopilot(
                    workstream_id, tenant_id=user.tenant_id,
                    reason=f"redirect: {action.matched_phrase}",
                )
            elif action.kind == RedirectActionKind.ESCALATE_COUNCIL:
                ws = await svc.escalate(
                    workstream_id, tenant_id=user.tenant_id,
                    new_level=WorkstreamEscalationLevel.COUNCIL,
                    reason=f"redirect: {action.matched_phrase}",
                )
            elif action.kind == RedirectActionKind.ESCALATE_QUINTESSENCE:
                ws = await svc.escalate(
                    workstream_id, tenant_id=user.tenant_id,
                    new_level=WorkstreamEscalationLevel.QUINTESSENCE,
                    reason=f"redirect: {action.matched_phrase}",
                )
            elif action.kind == RedirectActionKind.ESCALATE_HUMAN:
                ws = await svc.escalate(
                    workstream_id, tenant_id=user.tenant_id,
                    new_level=WorkstreamEscalationLevel.HUMAN_REVIEW,
                    reason=f"redirect: {action.matched_phrase}",
                )
            elif action.kind == RedirectActionKind.CANCEL:
                ws = await svc.fail(
                    workstream_id, tenant_id=user.tenant_id,
                    reason=f"cancelled by redirect: {action.matched_phrase}",
                )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkstreamTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "success": True,
        "data": {
            "workstream": _serialize_workstream(ws),
            "applied_actions": [
                {
                    "kind": a.kind.value,
                    "payload": a.payload,
                    "matched_phrase": a.matched_phrase,
                }
                for a in parse_result.actions
            ],
            "unmatched_segments": parse_result.unmatched_segments,
        },
    }


@router.post("/{workstream_id}/pause")
async def pause_workstream(
    workstream_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkstreamService(db)
    try:
        ws = await svc.pause_autopilot(workstream_id, tenant_id=user.tenant_id)
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": _serialize_workstream(ws)}


@router.post("/{workstream_id}/resume")
async def resume_workstream(
    workstream_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkstreamService(db)
    try:
        ws = await svc.resume_autopilot(workstream_id, tenant_id=user.tenant_id)
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": _serialize_workstream(ws)}


@router.post("/{workstream_id}/escalate")
async def escalate_workstream(
    workstream_id: uuid.UUID,
    body: EscalateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkstreamService(db)
    try:
        ws = await svc.escalate(
            workstream_id, tenant_id=user.tenant_id,
            new_level=body.to_level, reason=body.reason,
        )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkstreamTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "data": _serialize_workstream(ws)}


@router.post("/{workstream_id}/cancel")
async def cancel_workstream(
    workstream_id: uuid.UUID,
    body: CancelRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = WorkstreamService(db)
    try:
        ws = await svc.fail(
            workstream_id, tenant_id=user.tenant_id, reason=body.reason,
        )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkstreamTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "data": _serialize_workstream(ws)}


@router.get("/{workstream_id}/events")
async def list_workstream_events(
    workstream_id: uuid.UUID,
    limit: int = 200,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Full timeline (oldest first) for the Live Console."""
    svc = WorkstreamService(db)
    try:
        events = await svc.list_events(
            workstream_id, tenant_id=user.tenant_id, limit=min(limit, 1000),
        )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "success": True,
        "data": {
            "workstream_id": str(workstream_id),
            "events": [_serialize_event(e) for e in events],
            "count": len(events),
        },
    }


# ── PR-5: archive + dev-safe-demo ─────────────────────────────────────


@router.patch("/{workstream_id}/archive")
async def archive_workstream(
    workstream_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete the workstream (Hard Law #2: never delete).

    Sets ``archived_at`` so list views drop the row. Status is preserved
    so the audit trail still tells the truth about what happened. Idempotent
    (archiving an already-archived workstream is a no-op).
    """
    svc = WorkstreamService(db)
    try:
        ws = await svc.archive(
            workstream_id,
            tenant_id=user.tenant_id,
            archived_by_user_id=user.id,
        )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": _serialize_workstream(ws)}


async def _resolve_demo_department(
    db: AsyncSession, tenant_id: uuid.UUID,
    requested_id: uuid.UUID | None,
) -> uuid.UUID:
    """Pick a department for the dev-safe demo.

    If the caller named one, validate it belongs to the tenant. Otherwise
    fall back to the first active department for the tenant. Raises 422
    when the tenant has no active departments at all (operator should
    seed before demoing).
    """
    from sqlalchemy import select
    from app.models.organization import Department

    if requested_id is not None:
        stmt = select(Department).where(
            Department.id == requested_id,
            Department.tenant_id == tenant_id,
            Department.is_active.is_(True),
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "DEPARTMENT_NOT_FOUND",
                        "message": (
                            "Requested department_id is not active for "
                            "this tenant"
                        ),
                    },
                },
            )
        return row.id

    stmt = (
        select(Department)
        .where(
            Department.tenant_id == tenant_id,
            Department.is_active.is_(True),
        )
        .order_by(Department.sunflower_index.asc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "NO_ACTIVE_DEPARTMENTS",
                    "message": (
                        "No active departments for this tenant. Seed "
                        "departments before running the dev-safe demo."
                    ),
                },
            },
        )
    return row.id


@router.post("/dev-safe-demo", status_code=201)
async def create_dev_safe_demo_workstream(
    body: DevSafeDemoRequest | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Spin up a populated demo workstream so the operator can see the spine.

    Safe by construction: source_type=DEV_DEMO, no external send, no
    governance bypass, synthetic artifact ids ("demo-artifact-*"). The
    workstream traverses RUNNING -> COMPLETE with a small representative
    timeline (DECISION + ARTIFACT + TOOL_CALL events) and ends with
    progress_percent=100.

    Useful for validating the WorkstreamsPage rendering of new fields
    (source badge, progress bar, artifact links) without touching chat
    / scan / task flows.
    """
    requested_dept = body.department_id if body is not None else None
    department_id = await _resolve_demo_department(
        db, user.tenant_id, requested_dept,
    )
    svc = WorkstreamService(db)
    ws = await svc.create_dev_safe_demo(
        tenant_id=user.tenant_id,
        user_id=user.id,
        department_id=department_id,
    )
    return {"success": True, "data": _serialize_workstream(ws)}


# ── PR-SPINE-06: live console SSE stream ──────────────────────────────


@router.get("/{workstream_id}/stream")
async def stream_workstream_events(
    workstream_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Server-sent events for a single workstream.

    The stream emits two event types:

    * ``workstream.event`` -- a new entry was appended to the timeline.
      Payload carries the slim event (id, kind, summary, payload,
      occurred_at) and a slim snapshot (current status, progress,
      escalation, autopilot_paused, refs, archived_at).

    * ``workstream.snapshot`` -- the workstream's mutable state changed
      without a timeline entry (progress bump, ref attached, archive
      flip). Payload carries only the snapshot.

    Before any live event the route emits one ``workstream.bootstrap``
    envelope containing the full snapshot + last 50 timeline events so a
    fresh subscriber can render immediately without an extra GET.

    Tenant scoping happens at connection time via ``svc.get`` -- a
    cross-tenant request gets a 404 before the SSE channel is opened.

    Connection terminates when the client disconnects, when the
    workstream is archived (drawer should close), or when the request
    is cancelled.
    """
    svc = WorkstreamService(db)
    try:
        ws = await svc.get(workstream_id, tenant_id=user.tenant_id)
        events = await svc.list_events(
            workstream_id, tenant_id=user.tenant_id, limit=50,
        )
    except WorkstreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    bootstrap_payload = {
        "workstream_id": str(workstream_id),
        "snapshot": _serialize_workstream(ws),
        "events": [_serialize_event(e) for e in events],
    }
    workstream_id_str = str(workstream_id)

    async def _event_stream():
        # 1. Bootstrap so a fresh subscriber can render immediately.
        yield (
            f"event: workstream.bootstrap\n"
            f"data: {json.dumps(bootstrap_payload)}\n\n"
        )

        # 2. Live forward.
        channel = await get_workstream_channel(workstream_id_str)
        try:
            async for envelope in channel.subscribe():
                if await request.is_disconnected():
                    break
                event_type = envelope.get("type", "message")
                # ``ping`` is the SSEChannel idle heartbeat -- serialize
                # as an SSE comment so it keeps the connection warm
                # without surfacing in the consumer's onEvent handler.
                if event_type == "ping":
                    yield ": heartbeat\n\n"
                    continue
                data_payload = envelope.get("data") or {}
                yield (
                    f"event: {event_type}\n"
                    f"data: {json.dumps(data_payload)}\n\n"
                )
                # When archive lands, flush + close so the drawer can
                # detach instead of waiting for the next idle ping.
                snap = data_payload.get("snapshot") or {}
                if snap.get("archived_at"):
                    yield "event: workstream.closed\ndata: {\"reason\": \"archived\"}\n\n"
                    break
        except asyncio.CancelledError:
            # Client disconnect (most common) or app shutdown. The
            # channel.subscribe finally-block detaches the queue.
            raise
        except Exception as exc:
            logger.warning(
                "workstream.stream_failed",
                workstream_id=workstream_id_str,
                error=str(exc),
            )
            yield (
                "event: workstream.closed\n"
                f"data: {json.dumps({'reason': 'stream_error'})}\n\n"
            )

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
