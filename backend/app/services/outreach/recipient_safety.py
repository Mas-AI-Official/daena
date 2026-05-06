"""Recipient safety checks -- Sprint-19 PR-3 (2026-05-06).

Concrete checks before any outreach draft is created or before any
controlled send is attempted.

Walls:

  1. parses as RFC-5322-ish single address (no smuggled headers,
     no multiple recipients, no display-name-only)
  2. not in suppression list
     (``backend/.recipient_suppression.json``, gitignored, list of
     lowercased addresses that have unsubscribed / bounced)
  3. not in tenant's own user table (don't email yourself)
  4. v1 enforcement: ONE recipient only

NEVER raises. Returns a structured ``RecipientSafetyResult``.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.identity import User

logger = get_logger(__name__)

_SUPPRESSION_FILE = Path(__file__).resolve().parents[3] / ".recipient_suppression.json"

# Conservative RFC-5322-ish single address. Refuses multiple
# addresses (no commas), display-name-only ("Bob"), and obvious
# header injection (CR / LF / NUL).
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


@dataclass
class RecipientSafetyResult:
    safe: bool
    recipient: str
    reason: str | None = None  # stable code when not safe


def _read_suppression() -> set[str]:
    if not _SUPPRESSION_FILE.exists():
        return set()
    try:
        raw = json.loads(_SUPPRESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("recipient_safety.suppression_read_failed", error=str(exc))
        return set()
    if not isinstance(raw, list):
        return set()
    return {str(x).strip().lower() for x in raw if isinstance(x, str)}


async def check_recipient_safety(
    db: AsyncSession,
    *,
    recipient: str,
    tenant_id: uuid.UUID,
) -> RecipientSafetyResult:
    """Returns structured safety result. NEVER raises.

    The ``reason`` field is a stable code so the UI + audit log can
    match: ``invalid_email`` / ``multiple_recipients`` /
    ``control_chars`` / ``in_suppression_list`` /
    ``recipient_is_internal_user``.
    """
    if not isinstance(recipient, str) or not recipient.strip():
        return RecipientSafetyResult(
            safe=False, recipient=str(recipient or ""),
            reason="empty_recipient",
        )

    candidate = recipient.strip()

    # Wall: control chars
    for ch in candidate:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            return RecipientSafetyResult(
                safe=False, recipient=candidate, reason="control_chars",
            )

    # Wall: single address only (no commas, no semicolons)
    if "," in candidate or ";" in candidate:
        return RecipientSafetyResult(
            safe=False, recipient=candidate, reason="multiple_recipients",
        )

    # Wall: parse
    if not _EMAIL_RE.match(candidate):
        return RecipientSafetyResult(
            safe=False, recipient=candidate, reason="invalid_email",
        )

    lowered = candidate.lower()

    # Wall: suppression list
    if lowered in _read_suppression():
        return RecipientSafetyResult(
            safe=False, recipient=candidate, reason="in_suppression_list",
        )

    # Wall: tenant's own users (don't email yourself).
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        User.email == lowered,
    )
    own_user = (await db.execute(stmt)).scalar_one_or_none()
    if own_user is not None:
        return RecipientSafetyResult(
            safe=False, recipient=candidate,
            reason="recipient_is_internal_user",
        )

    return RecipientSafetyResult(safe=True, recipient=candidate)
