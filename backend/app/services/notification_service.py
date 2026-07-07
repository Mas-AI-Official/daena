"""NotificationService — in-app notification emitter (Phase 11 PR-S2).

Closes the DEAD-status notification toggles documented in
``docs/Ultraview/PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md`` §2.9.
Six of the nine ``notif_*`` toggles now have a real backend consumer:

================  =============================  =====================
notif_* flag      Event type                     Default behavior
================  =============================  =====================
notif_task_complete  task_complete               on  (write row)
notif_budget_alert   budget_alert                on  (write row)
notif_heartbeat      heartbeat                   on  (write row)
notif_gov_reject     governance_rejection        on  (write row)
notif_runtime_disconnect  runtime_disconnect     on  (write row)
(no flag)            privacy_blocked             always emit
(no flag)            system_info                 always emit
================  =============================  =====================

The other three (``notif_desktop``, ``notif_sound``, ``notif_email``,
``notif_daily_digest``) are NOT consumed here:

* ``notif_desktop`` is a client-side master gate — it controls whether
  the browser asks for OS notification permission and whether the test
  button is allowed to fire one. Server-side row creation is orthogonal.
* ``notif_sound`` / ``notif_email`` / ``notif_daily_digest`` need a
  delivery channel that does not exist yet (no SMTP, no audio
  pipeline, no scheduler-driven digest). They stay Coming Soon.

The in-app DB row is the source of truth. The bell at
``frontend/src/components/layout/Header.tsx`` and the test button at
``frontend/src/pages/settings/SettingsNotifications.tsx`` consume it.

G6 addendum (2026-07-02): push-worthy types (see ``_PUSH_TYPES``) are
additionally MIRRORED to Web Push via the channel seam in
``app.services.notification_channels`` -- one-way, best-effort,
default OFF (``push_alerts_enabled=false``), gated per-user by the
fail-open ``notif_push`` flag. Push failures never block the row.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from sqlalchemy import desc, func, select, update

from app.models.identity import User
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.services._base import BaseService
from app.services.notification_channels import get_push_channel

_log = logging.getLogger(__name__)


# Known event types. Keep small + intentional — every type that lands
# here is one the founder can document a "where does this surface?"
# answer for (per CLAUDE.md Rule 17).
_NOTIF_TYPES: Final[frozenset[str]] = frozenset({
    "task_complete",
    "budget_alert",
    "heartbeat",
    "governance_rejection",
    "runtime_disconnect",
    "privacy_blocked",
    "system_info",
})

# Mapping from event type -> users.settings flag that gates it.
# ``None`` means "always emit" — privacy-block + system-info both
# represent decisions the user MUST see; they bypass user opt-out
# because hiding them would be a worse trust hazard than an extra row
# in the bell.
_TYPE_TO_FLAG: Final[dict[str, str | None]] = {
    "task_complete": "notif_task_complete",
    "budget_alert": "notif_budget_alert",
    "heartbeat": "notif_heartbeat",
    "governance_rejection": "notif_gov_reject",
    "runtime_disconnect": "notif_runtime_disconnect",
    "privacy_blocked": None,
    "system_info": None,
}

_VALID_SEVERITIES: Final[frozenset[str]] = frozenset(
    {"info", "success", "warning", "error"},
)

# Types worth waking the founder's phone for (G6, 2026-07-02).
# heartbeat + system_info are deliberately excluded: heartbeat fires on
# a timer and system_info is the ungated test/misc bucket -- mirroring
# either would train the founder to ignore push. Unknown types never
# push (allow-list, not deny-list).
_PUSH_TYPES: Final[frozenset[str]] = frozenset({
    "task_complete",
    "budget_alert",
    "governance_rejection",
    "runtime_disconnect",
    "privacy_blocked",
})

# Truncation guards so a misbehaving caller can never oversize the row.
_MAX_TITLE_LEN: Final[int] = 200
_MAX_MESSAGE_LEN: Final[int] = 2000


class NotificationService(BaseService):
    """Create and read in-app notifications, gated by user settings.

    Usage::

        svc = NotificationService(db)
        result = await svc.emit(
            tenant_id=tenant_id,
            user_id=user_id,
            type="task_complete",
            title="Outreach mission finished",
            message="Sent 12 drafts; 4 awaiting approval.",
            severity="success",
            source="missions.engine",
        )
        if result.get("blocked_by_setting"):
            # caller gets the sentinel; row was NOT written.
            ...
    """

    async def _user_allows(
        self, *, user_id: UUID, flag: str | None,
    ) -> bool:
        """Return True unless ``users.settings[flag]`` is explicitly False.

        Mirrors the fail-open semantic of MemoryService's privacy gate
        (Phase 11 PR-S1): if the user row read fails or the setting is
        unset, default to ALLOW. The brief explicitly says "Default
        should remain current behavior unless explicit user setting
        says false."
        """
        if flag is None:
            return True  # uninhibited type (privacy_blocked, system_info)
        try:
            row = (
                await self.db.execute(
                    select(User.settings).where(User.id == user_id)
                )
            ).scalar_one_or_none()
            if row is None:
                return True
            settings = row if isinstance(row, dict) else {}
            return settings.get(flag) is not False
        except Exception:  # noqa: BLE001
            _log.debug(
                "notification.gate_check_failed user=%s flag=%s",
                user_id, flag, exc_info=True,
            )
            return True  # fail-open

    async def emit(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        type: str,  # noqa: A002 — matches the column name + UI vocab
        title: str,
        message: str,
        severity: str = "info",
        source: str | None = None,
    ) -> dict:
        """Create one in-app notification row, gated by user settings.

        Args:
            tenant_id: Tenant scope (FK).
            user_id: Recipient (FK).
            type: One of :data:`_NOTIF_TYPES`. Unknown types are accepted
                but logged at warning so a typo doesn't silently DROP a
                row — the row still lands; the gate just skips
                (treats unknown as ungated, like privacy_blocked).
            title: Short headline (<=200 chars, truncated if longer).
            message: Body copy (<=2000 chars, truncated).
            severity: info / success / warning / error. Anything else is
                coerced to "info" with a warning log.
            source: Free-form attribution e.g. "heartbeat" or
                "cost_guard". Optional; helpful for grep.

        Returns:
            Dict — either the persisted row (with ``id`` set) or a
            sentinel ``{"blocked_by_setting": True, "reason": ...,
            "id": None}`` when the user opted out via the matching
            ``notif_*`` flag.
        """
        if type not in _NOTIF_TYPES:
            _log.warning(
                "notification.unknown_type type=%s (passing through ungated)",
                type,
            )

        if severity not in _VALID_SEVERITIES:
            _log.warning(
                "notification.bad_severity severity=%s -> coercing to 'info'",
                severity,
            )
            severity = "info"

        flag = _TYPE_TO_FLAG.get(type)  # None => ungated
        if not await self._user_allows(user_id=user_id, flag=flag):
            # Fast path: user has opted out of this event type.
            # No row, no audit (this is a routine preference, not a
            # governance event — gating it would spam the ledger).
            _log.debug(
                "notification.suppressed_by_setting "
                "user=%s type=%s flag=%s",
                user_id, type, flag,
            )
            return {
                "blocked_by_setting": True,
                "reason": f"{flag}=false",
                "id": None,
                "type": type,
            }

        # Truncate guards (the column constraints would also reject,
        # but graceful truncation is friendlier for callers passing a
        # long upstream string).
        if len(title) > _MAX_TITLE_LEN:
            title = title[: _MAX_TITLE_LEN - 1] + "…"
        if len(message) > _MAX_MESSAGE_LEN:
            message = message[: _MAX_MESSAGE_LEN - 1] + "…"

        row = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            severity=severity,
            source=source,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        result = self._to_dict(row)

        # Mirror to push AFTER the in-app row exists (row = source of
        # truth; push is best-effort). Awaited inline on purpose: a
        # detached create_task escapes the request's session lifetime
        # and races cleanup (proven by the G5 test-infra failure);
        # fan-out is 1-3 founder devices, so inline latency is fine.
        # If device counts ever grow, move to a queue -- do NOT switch
        # to fire-and-forget on the same session.
        await self._mirror_to_push(result)
        return result

    async def _mirror_to_push(self, notif: dict) -> None:
        """Best-effort Web Push mirror of one just-written notification.

        NEVER raises -- push is an amenity layered on the in-app row.
        Skips silently when: the type is not push-worthy, the channel
        is unavailable (feature off / no keys / pywebpush missing), or
        the user opted out via the ``notif_push`` master flag
        (fail-open like every other notif_* gate).
        """
        try:
            if notif.get("type") not in _PUSH_TYPES:
                return
            channel = get_push_channel()
            if not channel.available():
                return
            user_id = UUID(notif["user_id"])
            tenant_id = UUID(notif["tenant_id"])
            if not await self._user_allows(user_id=user_id, flag="notif_push"):
                return

            subs = (
                await self.db.execute(
                    select(PushSubscription).where(
                        PushSubscription.tenant_id == tenant_id,
                        PushSubscription.user_id == user_id,
                        PushSubscription.revoked_at.is_(None),
                    )
                )
            ).scalars().all()
            if not subs:
                return

            payload = {
                "type": notif["type"],
                "title": notif["title"],
                "message": notif["message"],
                "severity": notif["severity"],
                "notification_id": notif["id"],
            }
            revoked_any = False
            for sub in subs:
                result = await channel.deliver(
                    subscription={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    payload=payload,
                )
                if result.gone:
                    # Push service says the device is gone -- revoke so
                    # we stop sending. Soft-revoke, never delete (R2).
                    sub.revoked_at = datetime.now(timezone.utc)
                    revoked_any = True
                    _log.info(
                        "notification.push_endpoint_revoked user=%s detail=%s",
                        user_id, result.detail,
                    )
                elif not result.ok:
                    _log.warning(
                        "notification.push_delivery_failed user=%s detail=%s",
                        user_id, result.detail,
                    )
            if revoked_any:
                # Emit already flushes the notification row; flush the
                # revoke too so it is durable within the same contract.
                await self.db.flush()
        except Exception:  # noqa: BLE001 -- push must never break emit
            _log.warning("notification.push_mirror_failed", exc_info=True)

    async def list_recent(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        limit: int = 20,
        unread_only: bool = False,
    ) -> list[dict]:
        """Return the user's most recent notifications (newest first).

        Tenant + user scoped — defense-in-depth over the API layer's
        own auth check.
        """
        limit = max(1, min(limit, 100))
        stmt = (
            select(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
            )
            .order_by(desc(Notification.created_at))
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        rows = (await self.db.execute(stmt)).scalars().all()
        return [self._to_dict(r) for r in rows]

    async def unread_count(self, *, tenant_id: UUID, user_id: UUID) -> int:
        """Count this user's unread notifications (read_at IS NULL)."""
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        return int((await self.db.execute(stmt)).scalar_one() or 0)

    async def mark_read(
        self, *, notification_id: UUID, tenant_id: UUID, user_id: UUID
    ) -> bool:
        """Mark ONE notification read. Returns True if a row was updated.

        Scoped to (tenant_id, user_id, id): a notification belonging to a
        different user matches zero rows (no cross-user mark-read / IDOR),
        so the caller gets False rather than touching another user's data.
        Idempotent: re-marking an already-read row still returns True.
        """
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
            )
            .values(read_at=func.now())
        )
        await self.db.commit()
        return (result.rowcount or 0) > 0

    async def mark_all_read(self, *, tenant_id: UUID, user_id: UUID) -> int:
        """Mark all of this user's UNREAD notifications read. Returns count."""
        result = await self.db.execute(
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=func.now())
        )
        await self.db.commit()
        return int(result.rowcount or 0)

    @staticmethod
    def _to_dict(row: Notification) -> dict:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "user_id": str(row.user_id),
            "type": row.type,
            "title": row.title,
            "message": row.message,
            "severity": row.severity,
            "source": row.source,
            "read_at": row.read_at.isoformat() if row.read_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
