"""Notifications API — list recent + emit test (Phase 11 PR-S2).

All endpoints authenticated, all tenant + user scoped:

* ``GET  /api/v1/notifications`` — recent in-app notifications for the
  current user, newest first.
* ``POST /api/v1/notifications/{id}/read`` / ``/read-all`` — mark read.
* ``POST /api/v1/notifications/test`` — emit one ``system_info`` row
  (the ``Send Test`` button in Settings → Notifications).
* ``GET  /api/v1/notifications/push/status`` — push readiness (G6).
* ``POST /api/v1/notifications/push/subscribe`` — FOUNDER-only device
  registration for Web Push mirroring (G6, 2026-07-02).
* ``POST /api/v1/notifications/push/unsubscribe`` — FOUNDER-only
  soft-revoke of one device.

This router DOES NOT expose a generic emit endpoint. Notifications are
emitted by backend services (heartbeat, cost guard, etc.) using
``NotificationService.emit`` directly — never by clients. Letting the
client emit arbitrary types would let any user spam the bell with
forged "governance_rejection" rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.models.push_subscription import PushSubscription
from app.services.notification_channels import get_push_channel
from app.services.notification_service import NotificationService

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────


class NotificationDTO(BaseModel):
    """Wire-shape of one notification row, mirrored to the bell UI."""

    id: str
    tenant_id: str
    user_id: str
    type: str
    title: str
    message: str
    severity: str
    source: str | None = None
    read_at: str | None = None
    created_at: str | None = None


class NotificationListResponse(BaseModel):
    success: bool = True
    data: list[NotificationDTO]
    unread_count: int = 0


class MarkReadResponse(BaseModel):
    success: bool = True
    # For one row: read=True if it was marked (or already read). For
    # read-all: marked = how many unread rows were flipped.
    marked: int = 0


class TestNotificationBody(BaseModel):
    """Body of POST /notifications/test (all fields optional)."""

    title: str | None = Field(
        default=None, max_length=200,
        description="Optional override; default is 'Test notification'.",
    )
    message: str | None = Field(
        default=None, max_length=2000,
        description="Optional override; default is a fixed system string.",
    )
    severity: Literal["info", "success", "warning", "error"] = "info"


class TestNotificationResponse(BaseModel):
    success: bool = True
    data: NotificationDTO


class PushKeys(BaseModel):
    """The two client-side crypto values a PushSubscription carries."""

    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class PushSubscribeBody(BaseModel):
    """Body of POST /notifications/push/subscribe (G6, 2026-07-02).

    Mirrors the browser's ``PushSubscription.toJSON()`` shape so the
    frontend can pass it through unmodified.
    """

    endpoint: str = Field(min_length=1, max_length=1024)
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=200)

    @field_validator("endpoint")
    @classmethod
    def _endpoint_must_be_https(cls, v: str) -> str:
        # Push services are always https; anything else is a client bug
        # or an attempt to make the backend POST to an arbitrary URL.
        if not v.startswith("https://"):
            raise ValueError("endpoint must be an https:// URL")
        return v


class PushStatusResponse(BaseModel):
    success: bool = True
    # True only when the channel is fully provisioned server-side
    # (flag + VAPID keys + pywebpush importable).
    enabled: bool = False
    # VAPID public key the browser needs for subscribe(); None until
    # the founder provisions keys.
    public_key: str | None = None
    # Active (non-revoked) subscriptions for the calling user.
    subscriptions: int = 0


class PushSubscribeResponse(BaseModel):
    success: bool = True
    # True = new row, False = existing endpoint re-registered/updated.
    created: bool = False


class PushUnsubscribeResponse(BaseModel):
    success: bool = True
    revoked: int = 0


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
) -> NotificationListResponse:
    """Return this user's recent in-app notifications, newest first."""
    svc = NotificationService(db)
    rows = await svc.list_recent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        limit=limit,
        unread_only=unread_only,
    )
    unread = await svc.unread_count(tenant_id=user.tenant_id, user_id=user.id)
    return NotificationListResponse(
        data=[NotificationDTO(**r) for r in rows],
        unread_count=unread,
    )


@router.post("/notifications/{notification_id}/read", response_model=MarkReadResponse)
async def mark_notification_read(
    notification_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark ONE of the current user's notifications read (NOTIF-02).

    Scoped to (tenant, user, id): a notification owned by another user
    matches nothing -> 404 (no cross-user mark-read).
    """
    ok = await NotificationService(db).mark_read(
        notification_id=notification_id,
        tenant_id=user.tenant_id,
        user_id=user.id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="notification_not_found")
    return MarkReadResponse(marked=1)


@router.post("/notifications/read-all", response_model=MarkReadResponse)
async def mark_all_notifications_read(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """Mark ALL of the current user's unread notifications read (NOTIF-02)."""
    count = await NotificationService(db).mark_all_read(
        tenant_id=user.tenant_id,
        user_id=user.id,
    )
    return MarkReadResponse(marked=count)


@router.post(
    "/notifications/test", response_model=TestNotificationResponse,
)
async def emit_test_notification(
    body: TestNotificationBody | None = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TestNotificationResponse:
    """Emit a single ``system_info`` notification for the current user.

    This is what the ``Send Test`` button in Settings → Notifications
    calls. ``system_info`` is intentionally ungated so the test always
    lands in the bell — the user is asking for confirmation that the
    plumbing works, so suppressing the row would be confusing.
    """
    body = body or TestNotificationBody()
    result = await NotificationService(db).emit(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="system_info",
        title=body.title or "Test notification",
        message=body.message or (
            "Notification system is working. This row was created by "
            "POST /api/v1/notifications/test."
        ),
        severity=body.severity,
        source="settings.notifications.test_button",
    )
    # system_info bypasses the gate, so the result is always the
    # persisted row — no blocked_by_setting branch.
    return TestNotificationResponse(data=NotificationDTO(**result))


# -- Push subscriptions (G6, 2026-07-02) ----------------------------
#
# Web Push mirror of founder alerts. Subscribe/unsubscribe are
# FOUNDER-only: push is a founder-alert channel, and letting any user
# register endpoints would grow an outward-facing surface no other
# role needs. Status is open to any authenticated user so the
# Settings UI can render honestly (Rule 17) without a 403.


@router.get("/notifications/push/status", response_model=PushStatusResponse)
async def push_status(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PushStatusResponse:
    """Report push-channel readiness + the caller's active devices."""
    settings = get_settings()
    count = (
        await db.execute(
            select(func.count())
            .select_from(PushSubscription)
            .where(
                PushSubscription.tenant_id == user.tenant_id,
                PushSubscription.user_id == user.id,
                PushSubscription.revoked_at.is_(None),
            )
        )
    ).scalar_one()
    return PushStatusResponse(
        enabled=get_push_channel().available(),
        public_key=settings.vapid_public_key or None,
        subscriptions=count,
    )


@router.post("/notifications/push/subscribe", response_model=PushSubscribeResponse)
async def push_subscribe(
    body: PushSubscribeBody,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> PushSubscribeResponse:
    """Register (or re-register) this browser's push subscription.

    Upsert keyed on endpoint ALONE: push endpoints are globally unique
    per browser profile, so an existing row -- even one that belonged
    to a different user (device reassignment) -- is updated in place
    with fresh keys and ownership, and un-revoked. Soft-revoked rows
    resurrect the same way (Rule 2: no deletes).
    """
    existing = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == body.endpoint
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.tenant_id = user.tenant_id
        existing.user_id = user.id
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.user_agent = body.user_agent
        existing.revoked_at = None
        await db.commit()
        return PushSubscribeResponse(created=False)

    db.add(
        PushSubscription(
            tenant_id=user.tenant_id,
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            user_agent=body.user_agent,
        )
    )
    await db.commit()
    return PushSubscribeResponse(created=True)


class PushUnsubscribeBody(BaseModel):
    """Body of POST /notifications/push/unsubscribe."""

    endpoint: str = Field(min_length=1, max_length=1024)


@router.post("/notifications/push/unsubscribe", response_model=PushUnsubscribeResponse)
async def push_unsubscribe(
    body: PushUnsubscribeBody,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> PushUnsubscribeResponse:
    """Soft-revoke ONE of the caller's push subscriptions.

    Scoped to (tenant, user, endpoint): another user's endpoint
    matches nothing -> 404. POST (not DELETE) because DELETE-with-body
    is dropped by some proxies.
    """
    row = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.tenant_id == user.tenant_id,
                PushSubscription.user_id == user.id,
                PushSubscription.endpoint == body.endpoint,
                PushSubscription.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="push_subscription_not_found")
    row.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return PushUnsubscribeResponse(revoked=1)
