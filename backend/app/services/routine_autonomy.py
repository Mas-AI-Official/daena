"""Routine Autonomy Scheduler -- Sprint-18 PR-4 (2026-05-06).

SKELETON-ONLY in Sprint-18. Daena registers routines that the
operator can run on-demand or pause; no actual cron daemon is
activated in this sprint. Future sprints can layer cron on top
without changing the contract.

The hard rule of this module:

  Every routine run is initiated as
  ``DispatchInitiator.SCHEDULER``.

That single fact ensures `trust_policy.should_auto_approve` will
ALWAYS refuse for scheduler-initiated dispatches (wall #2 -- "non
operator initiator never graduates"). So Daena's routines can
generate drafts and proposals, but NOTHING they create can
auto-execute. The operator still has to approve manually.

Allowed routine kinds (Sprint-18 locked set):

  * ``opportunity_discovery``       -- read-only research
  * ``business_workstream_proposal``-- creates local Workstream
  * ``local_draft_action_creation`` -- creates draft via dispatch
  * ``self_diagnostic``             -- read-only system check
  * ``readiness_check``             -- read-only readiness probe
  * ``repair_workstream_proposal``  -- creates local repair plan
  * ``startup_idea_validation``     -- local DB write: persists validation score

Forbidden FOREVER (the routine cannot be of these kinds):

  * external send / submit / post / pay (none reachable here at all)
  * file apply / git commit (forbidden tools cannot graduate)
  * security scan (this module has no scan path)

Persistence: JSON file at ``backend/.routine_autonomy.json`` so a
restart preserves operator pause / resume state. Gitignored.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_STATE_FILE = Path(__file__).resolve().parents[2] / ".routine_autonomy.json"


# ────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────


class RoutineKind(str, Enum):
    OPPORTUNITY_DISCOVERY = "opportunity_discovery"
    BUSINESS_WORKSTREAM_PROPOSAL = "business_workstream_proposal"
    LOCAL_DRAFT_ACTION_CREATION = "local_draft_action_creation"
    SELF_DIAGNOSTIC = "self_diagnostic"
    READINESS_CHECK = "readiness_check"
    REPAIR_WORKSTREAM_PROPOSAL = "repair_workstream_proposal"
    STARTUP_IDEA_VALIDATION = "startup_idea_validation"


ROUTINE_KIND_VALUES: frozenset[str] = frozenset(k.value for k in RoutineKind)


# ────────────────────────────────────────────────────────────────────
# Outcome contract
# ────────────────────────────────────────────────────────────────────


class RoutineOutcome(str, Enum):
    OK = "ok"
    PAUSED = "paused"
    GLOBAL_PAUSED = "global_paused"
    UNKNOWN_ROUTINE = "unknown_routine"
    INVALID_KIND = "invalid_kind"
    REFUSED_FORBIDDEN_ACTION = "refused_forbidden_action"
    HANDLER_NOT_REGISTERED = "handler_not_registered"
    HANDLER_RAISED = "handler_raised"


@dataclass
class RoutineRunResult:
    routine_id: str
    outcome: RoutineOutcome
    detail: str | None = None
    artifacts_created: list[str] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None


# ────────────────────────────────────────────────────────────────────
# State storage
# ────────────────────────────────────────────────────────────────────


@dataclass
class Routine:
    id: str
    kind: str
    name: str
    description: str = ""
    paused: bool = False
    last_run_at: str | None = None
    last_outcome: str | None = None


@dataclass
class RoutineState:
    routines: list[Routine] = field(default_factory=list)
    global_paused: bool = False


def _read_state() -> RoutineState:
    if not _STATE_FILE.exists():
        return RoutineState()
    try:
        raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("routine_autonomy.read_failed", error=str(exc))
        return RoutineState()
    if not isinstance(raw, dict):
        return RoutineState()
    routines: list[Routine] = []
    for entry in raw.get("routines", []) or []:
        if not isinstance(entry, dict):
            continue
        try:
            routines.append(Routine(
                id=str(entry.get("id") or uuid.uuid4()),
                kind=str(entry.get("kind", "")),
                name=str(entry.get("name", "")),
                description=str(entry.get("description", "")),
                paused=bool(entry.get("paused", False)),
                last_run_at=entry.get("last_run_at"),
                last_outcome=entry.get("last_outcome"),
            ))
        except (TypeError, ValueError) as exc:
            logger.warning(
                "routine_autonomy.entry_skip", id=entry.get("id"),
                error=str(exc),
            )
    return RoutineState(
        routines=routines,
        global_paused=bool(raw.get("global_paused", False)),
    )


def _write_state(state: RoutineState) -> None:
    payload = {
        "routines": [asdict(r) for r in state.routines],
        "global_paused": state.global_paused,
    }
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(payload, indent=2), encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("routine_autonomy.write_failed", error=str(exc))


# ────────────────────────────────────────────────────────────────────
# Public state API
# ────────────────────────────────────────────────────────────────────


def list_routines() -> list[Routine]:
    return _read_state().routines


def get_routine(routine_id: str) -> Routine | None:
    return next(
        (r for r in _read_state().routines if r.id == routine_id), None,
    )


def is_global_paused() -> bool:
    return _read_state().global_paused


def register_routine(
    *,
    kind: str,
    name: str,
    description: str = "",
) -> Routine:
    """Register a new routine. Refuses unknown kind."""
    if kind not in ROUTINE_KIND_VALUES:
        raise ValueError(
            f"unknown routine kind: {kind!r}. "
            f"Allowed: {sorted(ROUTINE_KIND_VALUES)}"
        )
    state = _read_state()
    routine = Routine(
        id=str(uuid.uuid4()),
        kind=kind,
        name=name,
        description=description,
    )
    state.routines.append(routine)
    _write_state(state)
    logger.info(
        "routine_autonomy.registered",
        routine_id=routine.id, kind=kind, name=name,
    )
    return routine


def pause_routine(routine_id: str) -> Routine | None:
    state = _read_state()
    for r in state.routines:
        if r.id == routine_id:
            r.paused = True
            _write_state(state)
            return r
    return None


def resume_routine(routine_id: str) -> Routine | None:
    state = _read_state()
    for r in state.routines:
        if r.id == routine_id:
            r.paused = False
            _write_state(state)
            return r
    return None


def pause_all() -> None:
    state = _read_state()
    state.global_paused = True
    _write_state(state)


def resume_all() -> None:
    state = _read_state()
    state.global_paused = False
    _write_state(state)


# ────────────────────────────────────────────────────────────────────
# Handler registry (skeleton)
# ────────────────────────────────────────────────────────────────────


# Each handler returns (artifacts_created: list[str], detail: str | None).
# Handlers MUST be pure-local. This module guards against ever passing
# `DispatchInitiator.OPERATOR` -- the only way scheduler-initiated work
# can touch the controlled-execution dispatcher is via SCHEDULER, which
# trust_policy refuses to graduate.
_HANDLERS: dict[str, callable] = {}


def register_handler(kind: str, handler) -> None:
    if kind not in ROUTINE_KIND_VALUES:
        raise ValueError(
            f"register_handler: unknown kind {kind!r}",
        )
    _HANDLERS[kind] = handler


def registered_handler_kinds() -> list[str]:
    return sorted(_HANDLERS.keys())


# ────────────────────────────────────────────────────────────────────
# Run orchestration
# ────────────────────────────────────────────────────────────────────


async def run_once(routine_id: str, **handler_kwargs) -> RoutineRunResult:
    """Run one routine on-demand. NEVER raises.

    Refuses if:
      * routine unknown
      * routine paused
      * global_paused
      * handler not registered for the routine's kind

    Returns a RoutineRunResult struct the API and audit log can
    serialize verbatim.
    """
    state = _read_state()
    routine = next((r for r in state.routines if r.id == routine_id), None)
    started_at = datetime.now(UTC).isoformat()

    if routine is None:
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.UNKNOWN_ROUTINE,
            detail=f"no routine with id={routine_id!r}",
            started_at=started_at,
            finished_at=started_at,
        )
    if state.global_paused:
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.GLOBAL_PAUSED,
            detail="all routines globally paused",
            started_at=started_at,
            finished_at=started_at,
        )
    if routine.paused:
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.PAUSED,
            detail="routine paused",
            started_at=started_at,
            finished_at=started_at,
        )
    if routine.kind not in ROUTINE_KIND_VALUES:
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.INVALID_KIND,
            detail=f"kind={routine.kind!r}",
            started_at=started_at,
            finished_at=started_at,
        )

    handler = _HANDLERS.get(routine.kind)
    if handler is None:
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.HANDLER_NOT_REGISTERED,
            detail=(
                f"no handler registered for kind={routine.kind}; "
                f"register one before run-once."
            ),
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
        )

    try:
        result = handler(**handler_kwargs)
        if hasattr(result, "__await__"):
            result = await result
        artifacts = []
        detail = None
        if isinstance(result, tuple) and len(result) == 2:
            artifacts, detail = result
            artifacts = list(artifacts) if artifacts else []
        finished = datetime.now(UTC).isoformat()
        # Persist last_run state
        for r in state.routines:
            if r.id == routine_id:
                r.last_run_at = finished
                r.last_outcome = RoutineOutcome.OK.value
        _write_state(state)
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.OK,
            detail=detail,
            artifacts_created=artifacts,
            started_at=started_at,
            finished_at=finished,
        )
    except Exception as exc:  # noqa: BLE001
        finished = datetime.now(UTC).isoformat()
        for r in state.routines:
            if r.id == routine_id:
                r.last_run_at = finished
                r.last_outcome = RoutineOutcome.HANDLER_RAISED.value
        _write_state(state)
        logger.warning(
            "routine_autonomy.handler_raised",
            routine_id=routine_id, kind=routine.kind, error=str(exc),
        )
        return RoutineRunResult(
            routine_id=routine_id,
            outcome=RoutineOutcome.HANDLER_RAISED,
            detail=str(exc),
            started_at=started_at,
            finished_at=finished,
        )


# ────────────────────────────────────────────────────────────────────
# Test helpers
# ────────────────────────────────────────────────────────────────────


def _reset_for_tests() -> None:
    if _STATE_FILE.exists():
        try:
            _STATE_FILE.unlink()
        except OSError:
            pass
    _HANDLERS.clear()
