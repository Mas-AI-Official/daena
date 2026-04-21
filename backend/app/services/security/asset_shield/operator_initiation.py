"""Operator-initiation trace.

Determines whether a given op chain traces back to a chat message
or UI action by the founder within the last 5 minutes. This is the
"auto-consent" signal the Asset Shield consumes to decide whether a
pivot needs an interactive approval prompt.

Rules:
    * Operator-initiated (session_id traces back to a founder action
      within 5 min) -> auto_consent=True, tiers collapse to T0-T1
    * Background / heartbeat / scheduled / team / delegated agent ->
      auto_consent=False, full T0-T4 ladder applies

The store is in-process; the chat orchestrator writes a marker at
the start of every founder turn, and op chains read it to answer
``is_operator_initiated()``.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


OPERATOR_INITIATION_TTL_SECONDS = 300  # 5 minutes


@dataclass
class InitiationMarker:
    session_id: str
    user_id: str
    user_role: str
    marked_at: float


# session_id -> InitiationMarker. Scoped by session so parallel chats
# do not bleed into each other's consent state.
_markers: dict[str, InitiationMarker] = {}


def mark_operator_initiated(
    session_id: str,
    user_id: str,
    user_role: str,
) -> None:
    """Record that this session just received a founder/operator action.

    Called by the chat orchestrator at the start of every user turn
    (when user_role == FOUNDER). Also safe to call for ADMIN / MANAGER
    roles that should get the same auto-consent UX.
    """
    if not session_id:
        return
    _markers[session_id] = InitiationMarker(
        session_id=session_id,
        user_id=user_id,
        user_role=str(user_role or "").upper(),
        marked_at=time.time(),
    )


def is_operator_initiated(session_id: str | None) -> bool:
    """Return True if the session was operator-initiated recently.

    Background ops (heartbeat, scheduled jobs, delegated agents) do
    not carry a session_id, so this returns False for them.
    """
    if not session_id:
        return False
    marker = _markers.get(session_id)
    if marker is None:
        return False
    if time.time() - marker.marked_at > OPERATOR_INITIATION_TTL_SECONDS:
        # Stale; clear on read.
        _markers.pop(session_id, None)
        return False
    return marker.user_role in {"FOUNDER", "ADMIN", "MANAGER"}


def get_marker(session_id: str | None) -> InitiationMarker | None:
    """Inspect the marker without checking freshness."""
    if not session_id:
        return None
    return _markers.get(session_id)


def clear_markers() -> None:
    """Test helper."""
    _markers.clear()


def collapse_tier_for_operator_initiated(
    tier: int,
    is_initiated: bool,
    is_asset_crossing: bool,
) -> int:
    """Initiator-aware tier collapse helper.

    When the op was operator-initiated AND does not touch an Asset
    Shield crossing, collapse the governance tier to T0 (silent) or
    T1 (log-only). Asset Shield crossings always stay at the original
    tier so the approval gate fires.

    The function is a pure helper; callers invoke it where they would
    normally use the raw tier.
    """
    if not is_initiated:
        return tier
    if is_asset_crossing:
        return tier
    # Collapse: tier 2/3/4 -> tier 1 (log-only).
    if tier >= 2:
        return 1
    return tier
