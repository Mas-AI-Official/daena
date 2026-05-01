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

No external send. All emission is in-app only. The bell at
``frontend/src/components/layout/Header.tsx`` and the test button at
``frontend/src/pages/settings/SettingsNotifications.tsx`` are the
only consumers today.
"""

from __future__ import annotations

import logging
from typing import Final
from uuid import UUID

from sqlalchemy import desc, select

from app.models.identity import User
from app.models.notification import Notification
from app.services._base import BaseService

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
        return self._to_dict(row)

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
