"""Business Autonomy Mission Control endpoint.

Sprint-13 PR-1 (2026-05-06). The operator-facing meta-control over
what classes of action Daena is allowed to take autonomously.

Five modes (locked enum):

    off                       no autonomous action at all
    observe                   read-only surveillance only
    research_draft (default)  research + create local drafts
    propose_actions           draft + queue approvals
    approved_execution        execute already-approved items only

The mode is persisted as a single JSON file at
``backend/.autonomy_mode.json`` so it survives restart and can be
inspected by other services without a DB hop. The file is
gitignored.

This PR ships the *control surface only*. Downstream services
consuming the mode (opportunity discovery, draft factory, security
scout, self-healing) land in PR-2..PR-6.

Honesty rules
-------------

* No secret read or print.
* Counts come from existing ApprovalQueue and Workstream tables --
  never from synthetic stubs.
* The allowed/blocked action class lists are deterministic per mode
  so the UI renders the same content the backend would enforce.
* PUT only changes the persisted mode; it never executes any action.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.logging import get_logger
from app.models.governance import GoaRequest
from app.models.workstream import Workstream, WorkstreamStatus

logger = get_logger(__name__)
router = APIRouter()


# Persistence ---------------------------------------------------------------

_AUTONOMY_FILE = Path(__file__).resolve().parents[3] / ".autonomy_mode.json"


class AutonomyMode(str, Enum):
    OFF = "off"
    OBSERVE = "observe"
    RESEARCH_DRAFT = "research_draft"
    PROPOSE_ACTIONS = "propose_actions"
    APPROVED_EXECUTION = "approved_execution"


_DEFAULT_MODE = AutonomyMode.RESEARCH_DRAFT


# Action classes per mode (deterministic) -----------------------------------

# Always-blocked classes regardless of mode. These map to the Sprint-13
# brief's hard stops and the v3.7 Asset Shield rules. Phase 3 unlocks
# none of these without per-tool consent + payload_hash.
_HARD_BLOCKED: tuple[str, ...] = (
    "external_send_unapproved",
    "external_submit_unapproved",
    "external_post_unapproved",
    "external_apply_unapproved",
    "external_pay",
    "scan_unauthorized_target",
    "install_packages_globally",
    "deploy_production",
    "force_push",
    "secret_read",
)


_ALLOWED_BY_MODE: dict[AutonomyMode, tuple[str, ...]] = {
    AutonomyMode.OFF: (),
    AutonomyMode.OBSERVE: (
        "research_read_only",
    ),
    AutonomyMode.RESEARCH_DRAFT: (
        "research_read_only",
        "draft_local",
        "qe_review",
        "workstream_create",
    ),
    AutonomyMode.PROPOSE_ACTIONS: (
        "research_read_only",
        "draft_local",
        "qe_review",
        "workstream_create",
        "approval_queue_enqueue",
    ),
    AutonomyMode.APPROVED_EXECUTION: (
        "research_read_only",
        "draft_local",
        "qe_review",
        "workstream_create",
        "approval_queue_enqueue",
        "execute_approved_item",
    ),
}


# API models ----------------------------------------------------------------


class AutonomyState(BaseModel):
    mode: AutonomyMode
    allowed_action_classes: list[str]
    blocked_action_classes: list[str]
    active_workstreams: int
    queued_approvals: int
    last_changed_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC of the last mode change, if known.",
    )


class AutonomyModeUpdate(BaseModel):
    mode: AutonomyMode


# Persistence helpers -------------------------------------------------------


def _read_persisted() -> dict[str, Any]:
    try:
        if not _AUTONOMY_FILE.exists():
            return {}
        raw = _AUTONOMY_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("autonomy.persistence.read_failed", error=str(exc))
        return {}


def _write_persisted(mode: AutonomyMode) -> None:
    payload = {
        "mode": mode.value,
        "last_changed_at": datetime.now(UTC).isoformat(),
    }
    try:
        _AUTONOMY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _AUTONOMY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("autonomy.persistence.write_failed", error=str(exc))


def _current_mode() -> tuple[AutonomyMode, str | None]:
    data = _read_persisted()
    raw = data.get("mode")
    last_changed = data.get("last_changed_at")
    if isinstance(raw, str):
        try:
            return AutonomyMode(raw), last_changed if isinstance(last_changed, str) else None
        except ValueError:
            pass
    return _DEFAULT_MODE, None


# Counts ---------------------------------------------------------------------


async def _live_counts(db: AsyncSession, tenant_id: Any) -> tuple[int, int]:
    """Return (active_workstreams, queued_approvals) for the tenant.

    Active = workstreams whose status is NOT in a terminal set.
    Queued = approvals whose status is ``pending``.
    Both queries are best-effort; on error the count falls back to 0.
    """

    active = 0
    queued = 0
    try:
        terminal = (WorkstreamStatus.COMPLETE, WorkstreamStatus.FAILED)
        stmt = (
            select(func.count(Workstream.id))
            .where(Workstream.tenant_id == tenant_id)
            .where(~Workstream.status.in_(terminal))
        )
        active = int((await db.execute(stmt)).scalar() or 0)
    except Exception as exc:  # noqa: BLE001 -- best-effort counts
        logger.debug("autonomy.counts.workstreams_failed", error=str(exc))

    try:
        stmt2 = (
            select(func.count(GoaRequest.id))
            .where(GoaRequest.tenant_id == tenant_id)
            .where(GoaRequest.status == "pending")
        )
        queued = int((await db.execute(stmt2)).scalar() or 0)
    except Exception as exc:  # noqa: BLE001 -- best-effort counts
        logger.debug("autonomy.counts.approvals_failed", error=str(exc))

    return active, queued


# Routes ---------------------------------------------------------------------


@router.get("/autonomy-mode", response_model=AutonomyState)
async def get_autonomy_mode(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutonomyState:
    """Return the current autonomy mode + live counts."""

    mode, last_changed = _current_mode()
    active, queued = await _live_counts(db, user.tenant_id)
    return AutonomyState(
        mode=mode,
        allowed_action_classes=list(_ALLOWED_BY_MODE[mode]),
        blocked_action_classes=list(_HARD_BLOCKED),
        active_workstreams=active,
        queued_approvals=queued,
        last_changed_at=last_changed,
    )


@router.put("/autonomy-mode", response_model=AutonomyState)
async def set_autonomy_mode(
    body: AutonomyModeUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AutonomyState:
    """Persist a new autonomy mode. Never executes any action."""

    if body.mode not in AutonomyMode:
        raise HTTPException(status_code=422, detail="invalid autonomy mode")

    _write_persisted(body.mode)
    logger.info(
        "autonomy.mode_changed",
        mode=body.mode.value,
        actor_user_id=str(getattr(user, "id", "unknown")),
    )

    active, queued = await _live_counts(db, user.tenant_id)
    return AutonomyState(
        mode=body.mode,
        allowed_action_classes=list(_ALLOWED_BY_MODE[body.mode]),
        blocked_action_classes=list(_HARD_BLOCKED),
        active_workstreams=active,
        queued_approvals=queued,
        last_changed_at=datetime.now(UTC).isoformat(),
    )
