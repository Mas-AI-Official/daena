"""ConnectionV2 state machine: derive 14 labels from 6 truth dims + active ops.

Per ADR-002 D-001 (per-dim failure storage), D-002 (op-lock for
in-progress state), D-005 (stale != failed -- explicit healthy_stale
and degraded_stale labels), and V2 spec §3.

Pure function. No I/O. Tests pin every transition.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.models.connection_v2 import ConnectionV2

# 15 labels per V2 §3 amendment + PR-CONN-V2-SEED-IMPORT (skill_pack).
LABELS = (
    "unknown",
    "installable",
    "installing",
    "needs_config",
    "needs_auth",
    "auth_pending",
    "probing",
    "healthy",
    "healthy_stale",
    "degraded",
    "degraded_stale",
    "failed",
    "disabled",
    "archived",
    "skill_pack",
)

# Default TTL for "callable" freshness. Beyond this, derive_label returns
# *_stale unless a more recent failure overrides.
CALLABLE_TTL = timedelta(minutes=5)
DEGRADED_THRESHOLD = 0.7  # ratio above which we render healthy vs degraded


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _failure_is_fresh(at_value: datetime | None, failure_at: datetime | None) -> bool:
    """A failure is "fresh" (more recent than success) if failure_at >= at_value."""
    if failure_at is None:
        return False
    if at_value is None:
        return True
    return failure_at >= at_value


def derive_label(row: ConnectionV2, active_ops: Iterable[str] = ()) -> str:
    """Pure function: (row state + active ops) -> one of LABELS.

    Caller passes the set of active op strings from
    ``connection_v2_op_lock`` (filtered to expires_at > now()) so this
    function stays pure.
    """
    ops = set(active_ops)

    if row.archived:
        return "archived"
    if row.disabled:
        return "disabled"

    # In-progress beats steady state.
    if "install" in ops:
        return "installing"
    if "authenticate" in ops:
        return "auth_pending"
    if "probe" in ops:
        return "probing"

    if not row.detected:
        return "unknown"
    if not row.configured:
        return "needs_config"
    if not row.imported:
        return "installable"

    # PR-CONN-V2-SEED-IMPORT: skill packs are never callable. Once
    # detected/configured/imported, render as the terminal "skill_pack"
    # label so the UI can show "not callable, instructional bundle"
    # without lying about reachable / authenticated / callable dims.
    if row.kind == "skill_pack":
        return "skill_pack"

    # Most-recent-failure tests use per-dim failure_at, not a single triple.
    if _failure_is_fresh(row.reachable_at, row.reachable_failure_at):
        return "failed"
    if not row.reachable:
        return "failed"

    requires_auth = (row.auth_method or "none") != "none"
    if requires_auth and not row.authenticated:
        return "needs_auth"
    if requires_auth and _failure_is_fresh(row.authenticated_at, row.authenticated_failure_at):
        return "failed"

    if _failure_is_fresh(row.callable_at, row.callable_failure_at):
        return "failed"

    if not row.callable:
        return "failed"

    # Callable=True path -- check freshness for stale split.
    # Defensive tz-coercion: SQLite drops timezone info on retrieval even
    # when the column is DateTime(timezone=True), so we re-attach UTC here
    # before comparing against tz-aware _now().
    callable_at = row.callable_at or _now()
    if callable_at.tzinfo is None:
        callable_at = callable_at.replace(tzinfo=timezone.utc)
    age = _now() - callable_at
    ratio = row.healthy_call_ratio if row.healthy_call_ratio is not None else 1.0
    if age < CALLABLE_TTL:
        return "healthy" if ratio > DEGRADED_THRESHOLD else "degraded"
    # Stale != failed. Per ADR-002 D-005.
    return "healthy_stale" if ratio > DEGRADED_THRESHOLD else "degraded_stale"
