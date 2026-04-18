"""REST API for inter-department messaging.

Session C. Four endpoints covering the ASK/ANSWER lifecycle:

* ``POST /messages`` -- send a message (Marketing -> Legal)
* ``GET /messages/inbox?department=Legal`` -- Legal fetches unread
* ``GET /messages/outbox?department=Marketing`` -- Marketing checks
  whether its request got answered
* ``POST /messages/{id}/answer`` -- Legal writes the reply

Auth-gated by the standard session JWT. Tenant is taken from the
current user's tenant_id so the API cannot leak messages across
tenants.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.services.department_message_service import (
    DEFAULT_TTL_SECONDS,
    DepartmentMessageService,
)

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    from_department: str = Field(..., min_length=1, max_length=50)
    to_department: str = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=4000)
    context_ref: str | None = Field(None, max_length=200)
    ttl_seconds: int | None = Field(DEFAULT_TTL_SECONDS, ge=0)


class AnswerMessageRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: str
    from_department: str
    to_department: str
    subject: str
    body: str
    context_ref: str | None = None
    status: str
    answer: str | None = None
    created_at: str | None = None
    acknowledged_at: str | None = None
    answered_at: str | None = None
    expires_at: str | None = None


# ── Endpoints ───────────────────────────────────────────────────


@router.post("", response_model=MessageResponse, status_code=201)
async def send_message(
    body: SendMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a message from one department to another."""
    svc = DepartmentMessageService(db)
    try:
        msg = await svc.send(
            tenant_id=user.tenant_id,
            from_department=body.from_department,
            to_department=body.to_department,
            subject=body.subject,
            body=body.body,
            context_ref=body.context_ref,
            ttl_seconds=body.ttl_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return MessageResponse(**msg.to_dict())


@router.get("/inbox", response_model=list[MessageResponse])
async def inbox(
    department: str = Query(..., min_length=1, max_length=50),
    include_closed: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    """Messages addressed TO this department.

    By default returns only SENT + ACKNOWLEDGED (open messages).
    Pass ``include_closed=true`` to also see ANSWERED / EXPIRED for
    audit / history view.
    """
    svc = DepartmentMessageService(db)
    msgs = await svc.list_inbox(
        tenant_id=user.tenant_id,
        department=department,
        include_closed=include_closed,
    )
    return [MessageResponse(**m.to_dict()) for m in msgs]


@router.get("/outbox", response_model=list[MessageResponse])
async def outbox(
    department: str = Query(..., min_length=1, max_length=50),
    include_closed: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    """Messages THIS department sent -- to poll for answers."""
    svc = DepartmentMessageService(db)
    msgs = await svc.list_outbox(
        tenant_id=user.tenant_id,
        department=department,
        include_closed=include_closed,
    )
    return [MessageResponse(**m.to_dict()) for m in msgs]


@router.post("/{message_id}/answer", response_model=MessageResponse)
async def answer(
    message_id: UUID,
    body: AnswerMessageRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reviewing department writes the answer."""
    svc = DepartmentMessageService(db)
    try:
        msg = await svc.answer(message_id=message_id, body=body.body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Tenant check -- service does not enforce, but the API must:
    # someone with a valid JWT for tenant A cannot answer tenant B's
    # message. Best-effort: we fetched the row to answer it, verify
    # tenant matches.
    if msg.tenant_id != user.tenant_id:
        # Paranoid reset -- we already flushed the answer. Roll back.
        await db.rollback()
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageResponse(**msg.to_dict())
