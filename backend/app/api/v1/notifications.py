"""Notifications API — list recent + emit test (Phase 11 PR-S2).

Two endpoints, both authenticated, both tenant + user scoped:

* ``GET  /api/v1/notifications`` — recent in-app notifications for the
  current user, newest first.
* ``POST /api/v1/notifications/test`` — emit one ``system_info`` row
  (the ``Send Test`` button in Settings → Notifications).

This router DOES NOT expose a generic emit endpoint. Notifications are
emitted by backend services (heartbeat, cost guard, etc.) using
``NotificationService.emit`` directly — never by clients. Letting the
client emit arbitrary types would let any user spam the bell with
forged "governance_rejection" rows.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
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


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
) -> NotificationListResponse:
    """Return this user's recent in-app notifications, newest first."""
    rows = await NotificationService(db).list_recent(
        tenant_id=user.tenant_id,
        user_id=user.id,
        limit=limit,
        unread_only=unread_only,
    )
    return NotificationListResponse(
        data=[NotificationDTO(**r) for r in rows],
    )


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
