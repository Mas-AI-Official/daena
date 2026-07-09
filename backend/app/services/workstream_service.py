"""Workstream Service — the orchestration glue for Daena's locked unit.

Per the Council R3 lock, the workstream is the visible unit of autonomy.
This service owns:

- **Lifecycle**: start, pause/resume, redirect, escalate, cancel, complete.
- **State machine**: which transitions are legal, with reasons.
- **Event log**: append timeline entries for every state change.
- **Heartbeat hooks**: detect stalled workstreams and flip RUNNING -> BLOCKED.

All the underlying primitives (Council/QE, OODA-R, sub-agent spawner,
Plain-English Policy Compiler, NBMF tiers, Shield) are *workstream
services* — invoked through this service when a workstream needs them.

See ``Doc/COUNCIL_DESIGN_LOCK_2026-04-25.md`` for the full design.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.sse_channels import get_workstream_channel, publish_graph_changed
from app.models.workstream import (
    Workstream,
    WorkstreamEscalationLevel,
    WorkstreamEvent,
    WorkstreamEventKind,
    WorkstreamSourceType,
    WorkstreamStatus,
)

logger = get_logger(__name__)


# ── PR-SPINE-06: slim serializers for SSE envelopes ──────────────────
#
# These are intentionally smaller than ``api/v1/workstreams._serialize_workstream``
# so per-event SSE payloads stay tight. The frontend already has the
# full snapshot from its initial GET; only fields that change during a
# workstream's lifetime need to ride on every event.


def _slim_event(event: "WorkstreamEvent") -> dict[str, Any]:
    """Compact SSE shape for a WorkstreamEvent.

    Mirrors ``api/v1/workstreams._serialize_event`` so the consumer can
    hand the dict straight into the timeline render.
    """
    return {
        "id": str(event.id),
        "kind": event.kind.value,
        "summary": event.summary,
        "payload": event.payload,
        "occurred_at": (
            event.occurred_at.isoformat() if event.occurred_at else None
        ),
    }


def _slim_snapshot(ws: "Workstream") -> dict[str, Any]:
    """Compact SSE snapshot of a Workstream's mutable fields.

    Includes everything that changes during a workstream's lifetime
    plus the ids the frontend needs for routing. Static fields
    (department_id, user_id, goal, source_type, source_ref_id,
    created_at) are intentionally omitted -- the frontend has them from
    the initial GET and they never change after start.
    """
    return {
        "id": str(ws.id),
        "status": ws.status.value,
        "escalation_level": ws.escalation_level.value,
        "progress_percent": ws.progress_percent,
        "blocker_text": ws.blocker_text,
        "next_step_text": ws.next_step_text,
        "autopilot_paused": ws.autopilot_paused,
        "last_activity_at": (
            ws.last_activity_at.isoformat() if ws.last_activity_at else None
        ),
        "archived_at": (
            ws.archived_at.isoformat() if ws.archived_at else None
        ),
        "artifact_refs": ws.artifact_refs or {},
        "audit_event_refs": ws.audit_event_refs or [],
        "notification_refs": ws.notification_refs or [],
        "total_tokens": ws.total_tokens,
        "total_cost_cents": ws.total_cost_cents,
        "goal": ws.goal,
    }


async def _publish_workstream_event(
    ws: "Workstream", event: "WorkstreamEvent",
) -> None:
    """Best-effort: emit a workstream.event SSE envelope.

    Failures are logged but never raise -- the spine artifact is the
    source of truth, the SSE channel is the observability layer.
    """
    try:
        ch = await get_workstream_channel(str(ws.id))
        await ch.publish(
            "workstream.event",
            {
                "workstream_id": str(ws.id),
                "event": _slim_event(event),
                "snapshot": _slim_snapshot(ws),
            },
        )
    except Exception as exc:
        logger.warning(
            "workstream.sse_publish_event_failed",
            workstream_id=str(ws.id),
            kind=event.kind.value if event else None,
            error=str(exc),
        )


async def _publish_workstream_snapshot(ws: "Workstream") -> None:
    """Best-effort: emit a workstream.snapshot envelope (no timeline event).

    Used by methods that mutate informational state (progress, refs,
    archive) without appending to the WorkstreamEvent table.
    """
    try:
        ch = await get_workstream_channel(str(ws.id))
        await ch.publish(
            "workstream.snapshot",
            {
                "workstream_id": str(ws.id),
                "snapshot": _slim_snapshot(ws),
            },
        )
    except Exception as exc:
        logger.warning(
            "workstream.sse_publish_snapshot_failed",
            workstream_id=str(ws.id),
            error=str(exc),
        )


# State machine -- which transitions are legal.
# Sourced from the R3 lock: RUNNING is the active state; BLOCKED + WAITING_APPROVAL
# are pause-points; COMPLETE + FAILED are terminal. Redirect is a mutation in
# place (not a transition), but it can resurrect a BLOCKED workstream by
# pairing with an UNBLOCKED event.
LEGAL_TRANSITIONS: dict[WorkstreamStatus, set[WorkstreamStatus]] = {
    WorkstreamStatus.RUNNING: {
        WorkstreamStatus.BLOCKED,
        WorkstreamStatus.WAITING_APPROVAL,
        WorkstreamStatus.COMPLETE,
        WorkstreamStatus.FAILED,
    },
    WorkstreamStatus.BLOCKED: {
        WorkstreamStatus.RUNNING,         # unblocked
        WorkstreamStatus.FAILED,          # gave up
        WorkstreamStatus.COMPLETE,        # accepted partial
        WorkstreamStatus.WAITING_APPROVAL,
    },
    WorkstreamStatus.WAITING_APPROVAL: {
        WorkstreamStatus.RUNNING,         # granted
        WorkstreamStatus.BLOCKED,         # denied, alt path possible
        WorkstreamStatus.FAILED,          # denied, no fallback
    },
    # Terminal states have NO outgoing transitions.
    WorkstreamStatus.COMPLETE: set(),
    WorkstreamStatus.FAILED: set(),
}


# Escalation ladder. Each step buys more reasoning power but costs more.
# Surfaced in the UI as a "currently engaged" badge.
ESCALATION_LADDER: list[WorkstreamEscalationLevel] = [
    WorkstreamEscalationLevel.STANDARD,
    WorkstreamEscalationLevel.HIGH_EFFORT,
    WorkstreamEscalationLevel.COUNCIL,
    WorkstreamEscalationLevel.QUINTESSENCE,
    WorkstreamEscalationLevel.HUMAN_REVIEW,
]


class WorkstreamTransitionError(Exception):
    """Raised when a state transition violates the legal-transitions table."""


class WorkstreamNotFoundError(Exception):
    """Raised when a workstream id doesn't resolve under the given tenant."""


@dataclass(slots=True)
class StartParams:
    """Inputs needed to spin up a new workstream."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    department_id: uuid.UUID
    goal: str
    initial_context: dict[str, Any] | None = None
    next_step_text: str | None = None
    # PR-5 (2026-05-02): source attribution. Defaults to MANUAL so legacy
    # callers that never declared a source still resolve.
    source_type: WorkstreamSourceType = WorkstreamSourceType.MANUAL
    source_ref_id: uuid.UUID | None = None


class WorkstreamService:
    """Public API for workstream lifecycle + state transitions.

    Usage::

        svc = WorkstreamService(db)
        ws = await svc.start(StartParams(...))
        await svc.transition(ws.id, WorkstreamStatus.WAITING_APPROVAL,
                             reason="tier 3 tool call queued")
        await svc.redirect(ws.id, new_goal="...", scope_constraints=[...])
        await svc.complete(ws.id, summary="...")
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -- read paths ---------------------------------------------------------

    async def get(
        self, workstream_id: uuid.UUID, *, tenant_id: uuid.UUID,
    ) -> Workstream:
        """Load a workstream scoped to the tenant. Raises NotFoundError."""
        stmt = select(Workstream).where(
            Workstream.id == workstream_id,
            Workstream.tenant_id == tenant_id,
            Workstream.archived_at.is_(None),
        )
        result = await self._db.execute(stmt)
        ws = result.scalar_one_or_none()
        if ws is None:
            raise WorkstreamNotFoundError(
                f"Workstream {workstream_id} not found for tenant {tenant_id}",
            )
        return ws

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        statuses: list[WorkstreamStatus] | None = None,
        limit: int = 50,
    ) -> list[Workstream]:
        """List active workstreams for a tenant, newest activity first."""
        stmt = (
            select(Workstream)
            .where(
                Workstream.tenant_id == tenant_id,
                Workstream.archived_at.is_(None),
            )
            .order_by(Workstream.last_activity_at.desc().nullslast())
            .limit(limit)
        )
        if statuses:
            stmt = stmt.where(Workstream.status.in_(statuses))
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # -- lifecycle ----------------------------------------------------------

    async def start(self, params: StartParams) -> Workstream:
        """Create a new workstream in RUNNING."""
        ws = Workstream(
            tenant_id=params.tenant_id,
            user_id=params.user_id,
            department_id=params.department_id,
            goal=params.goal,
            status=WorkstreamStatus.RUNNING,
            escalation_level=WorkstreamEscalationLevel.STANDARD,
            context=params.initial_context or {},
            next_step_text=params.next_step_text,
            last_activity_at=datetime.utcnow(),
            source_type=params.source_type,
            source_ref_id=params.source_ref_id,
            progress_percent=0,
            artifact_refs={},
            audit_event_refs=[],
            notification_refs=[],
        )
        self._db.add(ws)
        await self._db.flush()
        event = await self._append_event(
            ws,
            kind=WorkstreamEventKind.STARTED,
            summary=f"Workstream started: {params.goal[:140]}",
            payload={
                "initial_context": params.initial_context or {},
                "source_type": params.source_type.value,
                "source_ref_id": (
                    str(params.source_ref_id) if params.source_ref_id else None
                ),
            },
        )
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        # Live Brain doorbell (best-effort): a new workstream node just entered
        # RUNNING, which adds a pulsing node to the org projection, so nudge the
        # canvas to re-pull GET /graph. transition() covers later status flips;
        # start() is the only place a workstream is born, so without this the
        # brand-new RUNNING node would not light until the 15s poll backstop.
        await publish_graph_changed(
            "workstream_started",
            workstream_id=str(ws.id),
            # node_id lets the live Brain pulse the exact node that moved.
            # Mirrors graph_service._nid("workstream", ws.id) -- keep the prefix
            # in sync (a workstream renders as node workstream:<id>).
            node_id=f"workstream:{ws.id}",
        )
        logger.info(
            "workstream.started",
            workstream_id=str(ws.id),
            tenant_id=str(params.tenant_id),
            department_id=str(params.department_id),
            source_type=params.source_type.value,
            goal=params.goal[:80],
        )
        return ws

    async def transition(
        self,
        workstream_id: uuid.UUID,
        new_status: WorkstreamStatus,
        *,
        tenant_id: uuid.UUID,
        reason: str,
        blocker_text: str | None = None,
        next_step_text: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Workstream:
        """Move a workstream to a new status. Validates against the table."""
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        legal = LEGAL_TRANSITIONS.get(ws.status, set())
        if new_status not in legal:
            raise WorkstreamTransitionError(
                f"Illegal transition {ws.status.value} -> {new_status.value} "
                f"(legal: {sorted(s.value for s in legal)})",
            )

        # Decide which event kind to emit based on the destination state.
        # This is the visible audit signal; internal state changes that
        # don't have a user-facing meaning should NOT call transition().
        kind_map = {
            WorkstreamStatus.BLOCKED: WorkstreamEventKind.BLOCKED,
            WorkstreamStatus.RUNNING: WorkstreamEventKind.UNBLOCKED,
            WorkstreamStatus.WAITING_APPROVAL: WorkstreamEventKind.APPROVAL_REQUESTED,
            WorkstreamStatus.COMPLETE: WorkstreamEventKind.COMPLETED,
            WorkstreamStatus.FAILED: WorkstreamEventKind.FAILED,
        }
        old_status = ws.status
        ws.status = new_status
        ws.last_activity_at = datetime.utcnow()
        if blocker_text is not None:
            ws.blocker_text = blocker_text
        if next_step_text is not None:
            ws.next_step_text = next_step_text
        # Clear blocker copy when leaving BLOCKED so stale text doesn't render.
        if new_status == WorkstreamStatus.RUNNING and old_status == WorkstreamStatus.BLOCKED:
            ws.blocker_text = None

        event = await self._append_event(
            ws,
            kind=kind_map[new_status],
            summary=reason,
            payload={
                "from_status": old_status.value,
                "to_status": new_status.value,
                **(payload or {}),
            },
        )
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        # Live Brain doorbell (best-effort): a workstream node just changed
        # status, which moves the org projection, so nudge the canvas to
        # re-pull GET /graph. Only fired from transition() -- the lone funnel
        # that flips ws.status, the field the graph signature keys on -- so a
        # progress/text-only event never triggers a wasted refetch.
        await publish_graph_changed(
            "workstream_transitioned",
            workstream_id=str(workstream_id),
            # Mirrors graph_service._nid("workstream", workstream_id); see the
            # start() doorbell for the contract.
            node_id=f"workstream:{workstream_id}",
            status=new_status.value,
        )
        logger.info(
            "workstream.transitioned",
            workstream_id=str(workstream_id),
            from_status=old_status.value,
            to_status=new_status.value,
            reason=reason[:200],
        )
        return ws

    async def pause_autopilot(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        reason: str = "user paused",
    ) -> Workstream:
        """Stop autopilot continuation without changing status."""
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        ws.autopilot_paused = True
        event = await self._append_event(
            ws,
            kind=WorkstreamEventKind.PAUSED,
            summary=reason,
            payload={"autopilot_paused": True},
        )
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        logger.info("workstream.paused", workstream_id=str(workstream_id))
        return ws

    async def resume_autopilot(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        reason: str = "user resumed",
    ) -> Workstream:
        """Re-enable autopilot continuation."""
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        ws.autopilot_paused = False
        event = await self._append_event(
            ws,
            kind=WorkstreamEventKind.RESUMED,
            summary=reason,
            payload={"autopilot_paused": False},
        )
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        logger.info("workstream.resumed", workstream_id=str(workstream_id))
        return ws

    async def redirect(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        new_goal: str | None = None,
        scope_constraints: list[str] | None = None,
        new_department_id: uuid.UUID | None = None,
        raw_instruction: str | None = None,
    ) -> Workstream:
        """Apply a redirect to a workstream.

        Per the Council R3 lock, redirect is the workstream's *single
        most important* user action. The user types something like
        "pause file edits, ask Council, only produce a migration plan"
        and we compose the parsed actions in ONE atomic call here.

        The natural-language parsing lives in
        ``services/workstream_redirect_parser.py``; this method takes
        the parsed structured fields and applies them.
        """
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        prior_goal = ws.goal
        if new_goal:
            ws.goal = new_goal
        if new_department_id:
            ws.department_id = new_department_id

        # Append the redirect to the workstream's context — append-only
        # so the decision log shows what redirected and why.
        history = list(ws.context.get("redirect_history", []))
        history.append(
            {
                "at": datetime.utcnow().isoformat(),
                "from_goal": prior_goal,
                "to_goal": new_goal,
                "scope_constraints": scope_constraints or [],
                "raw_instruction": raw_instruction,
                "new_department_id": str(new_department_id) if new_department_id else None,
            },
        )
        new_context = dict(ws.context)
        new_context["redirect_history"] = history
        if scope_constraints:
            new_context["scope_constraints"] = scope_constraints
        ws.context = new_context
        ws.last_activity_at = datetime.utcnow()

        event = await self._append_event(
            ws,
            kind=WorkstreamEventKind.REDIRECTED,
            summary=f"Redirected: {(new_goal or raw_instruction or 'scope updated')[:140]}",
            payload={
                "from_goal": prior_goal,
                "to_goal": new_goal,
                "scope_constraints": scope_constraints or [],
                "raw_instruction": raw_instruction,
            },
        )
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        logger.info(
            "workstream.redirected",
            workstream_id=str(workstream_id),
            from_goal=prior_goal[:80],
            to_goal=(new_goal or "")[:80],
            constraint_count=len(scope_constraints or []),
        )
        return ws

    async def escalate(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        new_level: WorkstreamEscalationLevel,
        reason: str,
    ) -> Workstream:
        """Bump the workstream to a higher reasoning tier.

        Allows lateral moves (e.g. STANDARD -> COUNCIL skipping HIGH_EFFORT)
        because the user may explicitly request a level. We only block
        de-escalation through this method — that should be a separate
        ``downgrade()`` call when implemented (deferred for v1).
        """
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        old_level = ws.escalation_level
        try:
            old_idx = ESCALATION_LADDER.index(old_level)
            new_idx = ESCALATION_LADDER.index(new_level)
        except ValueError as exc:
            raise WorkstreamTransitionError(
                f"Unknown escalation level: {exc}",
            ) from exc
        if new_idx < old_idx:
            raise WorkstreamTransitionError(
                f"escalate() only moves UP the ladder; "
                f"got {old_level.value} -> {new_level.value}",
            )
        ws.escalation_level = new_level
        ws.last_activity_at = datetime.utcnow()
        event = await self._append_event(
            ws,
            kind=WorkstreamEventKind.ESCALATED,
            summary=f"Escalated to {new_level.value}: {reason[:160]}",
            payload={
                "from_level": old_level.value,
                "to_level": new_level.value,
            },
        )
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        logger.info(
            "workstream.escalated",
            workstream_id=str(workstream_id),
            from_level=old_level.value,
            to_level=new_level.value,
        )
        return ws

    async def complete(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        summary: str,
        artifact_refs: list[str] | None = None,
    ) -> Workstream:
        """Mark a workstream as COMPLETE with a summary + artifact list."""
        return await self.transition(
            workstream_id,
            WorkstreamStatus.COMPLETE,
            tenant_id=tenant_id,
            reason=summary,
            payload={"artifact_refs": artifact_refs or []},
        )

    async def fail(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        reason: str,
        recoverable: bool = False,
    ) -> Workstream:
        """Mark a workstream as FAILED. Reason is shown verbatim to the user."""
        return await self.transition(
            workstream_id,
            WorkstreamStatus.FAILED,
            tenant_id=tenant_id,
            reason=reason,
            payload={"recoverable": recoverable},
        )

    # -- archive (PR-5 soft-delete) ---------------------------------------

    async def _get_including_archived(
        self, workstream_id: uuid.UUID, *, tenant_id: uuid.UUID,
    ) -> Workstream:
        """Fetch a workstream regardless of archived state.

        Used by archive() so re-archiving is idempotent (the standard
        get() filters archived rows; that is correct for read paths but
        wrong for the archive operation itself).
        """
        stmt = select(Workstream).where(
            Workstream.id == workstream_id,
            Workstream.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        ws = result.scalar_one_or_none()
        if ws is None:
            raise WorkstreamNotFoundError(
                f"Workstream {workstream_id} not found for tenant {tenant_id}",
            )
        return ws

    async def archive(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        archived_by_user_id: uuid.UUID | None = None,
    ) -> Workstream:
        """Soft-delete a workstream by setting ``archived_at`` (Hard Law #2).

        Idempotent: archiving an already-archived workstream is a no-op
        and returns the row unchanged. Status is preserved (we do NOT
        force COMPLETE/FAILED on archive) so the timeline reflects what
        actually happened. The list endpoints exclude archived rows via
        ``archived_at IS NULL`` so the row simply leaves the visible
        surface.
        """
        ws = await self._get_including_archived(
            workstream_id, tenant_id=tenant_id,
        )
        if ws.archived_at is not None:
            return ws
        ws.archived_at = datetime.utcnow()
        ws.archived_by = archived_by_user_id
        await self._db.commit()
        # Snapshot only -- archive is a UI declutter, not a lifecycle
        # transition. Subscribers see ``archived_at`` flip to a value
        # and should close their drawers / detach.
        await _publish_workstream_snapshot(ws)
        logger.info(
            "workstream.archived",
            workstream_id=str(workstream_id),
            archived_by=str(archived_by_user_id) if archived_by_user_id else None,
        )
        return ws

    # -- progress + ref attachment helpers (PR-5) -------------------------

    async def update_progress(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        percent: int,
    ) -> Workstream:
        """Set ``progress_percent`` (clamped to 0..100). Informational only.

        Does not change ``status`` -- the state machine still owns
        lifecycle. Bumps ``last_activity_at`` so the heartbeat doesn't
        flag the workstream as stale.
        """
        clamped = max(0, min(100, int(percent)))
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        ws.progress_percent = clamped
        ws.last_activity_at = datetime.utcnow()
        await self._db.commit()
        # Snapshot only -- progress is informational, no timeline entry.
        await _publish_workstream_snapshot(ws)
        return ws

    async def attach_artifact_ref(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        kind: str,
        ref_id: str,
        emit_event: bool = True,
    ) -> Workstream:
        """Append an artifact id under ``artifact_refs[kind]``.

        Schema convention: kind is plural (``scan_report_ids``,
        ``draft_ids``, ``file_ids``, ``task_ids``, ``approval_ids``).
        Append-only -- duplicates are skipped to keep the list small,
        but order is preserved. Optionally emits an ARTIFACT timeline
        event so the user sees the link land in real time.
        """
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        refs = dict(ws.artifact_refs or {})
        bucket: list = list(refs.get(kind, []))
        if ref_id not in bucket:
            bucket.append(ref_id)
        refs[kind] = bucket
        ws.artifact_refs = refs
        ws.last_activity_at = datetime.utcnow()
        emitted_event: WorkstreamEvent | None = None
        if emit_event:
            emitted_event = await self._append_event(
                ws,
                kind=WorkstreamEventKind.ARTIFACT,
                summary=f"Artifact emitted: {kind}={ref_id[:40]}",
                payload={"artifact_kind": kind, "ref_id": ref_id},
            )
        await self._db.commit()
        # Publish: workstream.event when a timeline entry was emitted
        # (carries the new snapshot too); workstream.snapshot otherwise
        # so subscribers still see the ref-count bump.
        if emitted_event is not None:
            await _publish_workstream_event(ws, emitted_event)
        else:
            await _publish_workstream_snapshot(ws)
        return ws

    async def attach_audit_event_ref(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        audit_event_id: str,
    ) -> Workstream:
        """Append an audit_event id to ``audit_event_refs`` (deduplicated).

        Drives the "View N audit events" link on the detail drawer (PRD
        section 11.2 row 5). Does NOT emit a timeline event -- audit
        events are routine and would flood the timeline.
        """
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        refs = list(ws.audit_event_refs or [])
        if audit_event_id not in refs:
            refs.append(audit_event_id)
        ws.audit_event_refs = refs
        await self._db.commit()
        # Snapshot only -- audit refs are routine; no timeline entry.
        await _publish_workstream_snapshot(ws)
        return ws

    async def attach_notification_ref(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        notification_id: str,
    ) -> Workstream:
        """Append a notification id to ``notification_refs`` (deduplicated).

        Cross-links the bell. Does NOT emit a timeline event for the same
        anti-flood reason as audit refs.
        """
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        refs = list(ws.notification_refs or [])
        if notification_id not in refs:
            refs.append(notification_id)
        ws.notification_refs = refs
        await self._db.commit()
        # Snapshot only -- same anti-flood reason as audit refs.
        await _publish_workstream_snapshot(ws)
        return ws

    # -- dev-safe demo (PR-5) ---------------------------------------------

    async def create_dev_safe_demo(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> Workstream:
        """Create a populated demo workstream for spine validation.

        Operator-facing affordance so the founder can see every PR-5
        field rendered without first wiring chat / scan / task flows.
        Safe by construction:

          - source_type=DEV_DEMO so it is visually distinct in the list
          - no external send (the brief's hard rule 7)
          - no governance bypass (still uses the same start path)
          - synthetic artifact ids ("demo-artifact-1") so any link
            navigation lands on a graceful 404 rather than touching
            production rows

        Emits a small but representative event sequence so the timeline
        shows what an operator will see during real spine traversal.
        """
        ws = await self.start(
            StartParams(
                tenant_id=tenant_id,
                user_id=user_id,
                department_id=department_id,
                goal="dev-safe demo: walk the workstream spine end-to-end",
                next_step_text="run plan stage",
                initial_context={"dev_safe_demo": True},
                source_type=WorkstreamSourceType.DEV_DEMO,
                source_ref_id=None,
            ),
        )

        # Bump progress + attach synthetic refs so the detail drawer has
        # something to render. Each helper commits independently so the
        # final state is durable even if one step fails mid-demo.
        await self.update_progress(
            ws.id, tenant_id=tenant_id, percent=25,
        )
        await self.append_timeline_event(
            ws.id,
            tenant_id=tenant_id,
            kind=WorkstreamEventKind.DECISION,
            summary="Picked single-mind STANDARD (dev demo)",
            payload={"primary_runtime": "demo", "reasoning_mode": "STANDARD"},
        )
        await self.attach_artifact_ref(
            ws.id, tenant_id=tenant_id,
            kind="file_ids", ref_id="demo-artifact-file-1",
        )
        await self.update_progress(
            ws.id, tenant_id=tenant_id, percent=75,
        )
        await self.append_timeline_event(
            ws.id,
            tenant_id=tenant_id,
            kind=WorkstreamEventKind.TOOL_CALL,
            summary="Demo tool call: file.read(demo.md)",
            payload={"tool": "file.read", "args": {"path": "demo.md"}},
        )
        ws = await self.complete(
            ws.id,
            tenant_id=tenant_id,
            summary="Dev-safe demo finished walking the spine",
            artifact_refs=["demo-artifact-file-1"],
        )
        # update_progress to 100 happens after complete() so the visible
        # state matches the terminal status.
        ws = await self.update_progress(
            ws.id, tenant_id=tenant_id, percent=100,
        )
        return ws

    # -- timeline + audit helpers ------------------------------------------

    async def append_timeline_event(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        kind: WorkstreamEventKind,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> WorkstreamEvent:
        """Append a free-form timeline event (TOOL_CALL, ARTIFACT, DECISION, ...).

        Called from the orchestrator when something happens that the user
        should see on the workstream timeline but that isn't a status
        transition. Does NOT touch ``status`` / ``escalation_level``.
        """
        ws = await self.get(workstream_id, tenant_id=tenant_id)
        event = await self._append_event(ws, kind=kind, summary=summary, payload=payload)
        await self._db.commit()
        await _publish_workstream_event(ws, event)
        return event

    async def _append_event(
        self,
        ws: Workstream,
        *,
        kind: WorkstreamEventKind,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> WorkstreamEvent:
        """Internal: append an event WITHOUT committing (caller commits)."""
        event = WorkstreamEvent(
            tenant_id=ws.tenant_id,
            workstream_id=ws.id,
            kind=kind,
            summary=summary[:500],
            payload=payload or {},
            occurred_at=datetime.utcnow(),
        )
        self._db.add(event)
        return event

    async def list_events(
        self,
        workstream_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        limit: int = 200,
    ) -> list[WorkstreamEvent]:
        """Read the timeline (oldest first) for the Live Console."""
        await self.get(workstream_id, tenant_id=tenant_id)  # tenant check
        stmt = (
            select(WorkstreamEvent)
            .where(
                WorkstreamEvent.workstream_id == workstream_id,
                WorkstreamEvent.tenant_id == tenant_id,
            )
            .order_by(WorkstreamEvent.occurred_at.asc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())


# ── Module-level helpers (PR-SPINE-04) ────────────────────────────────


async def find_workstream_linked_to_task(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
) -> Workstream | None:
    """Find the Workstream that references this task as its work output.

    Returns the first match in priority order:

    1. **Direct link** (PR-5): ``source_type=TASK`` AND
       ``source_ref_id=task_id``. This is what
       ``ExecutionService.create_task(also_create_workstream=True)`` writes.
    2. **Indirect link via artifact_refs** (PR-SCAN-WS-01):
       ``source_type=SCAN`` AND ``artifact_refs.task_ids`` contains
       ``str(task_id)``. This is what the scan-finding remediation flow
       writes.

    Archived workstreams are skipped on purpose: a soft-deleted workstream
    should not silently re-flip back to RUNNING because a long-running
    task associated with it finally completed.

    The SCAN-sourced lookup is a per-tenant linear scan in Python (the
    JSON-contains query is dialect-specific). Acceptable cost: SCAN-
    sourced workstreams stay small per tenant.

    Returns ``None`` when no link is found. Callers MUST treat None as
    "this task is not part of a tracked workstream; skip the sync."
    """
    # 1. Direct TASK -> Workstream link.
    stmt = (
        select(Workstream)
        .where(
            Workstream.tenant_id == tenant_id,
            Workstream.source_type == WorkstreamSourceType.TASK,
            Workstream.source_ref_id == task_id,
            Workstream.archived_at.is_(None),
        )
        .limit(1)
    )
    direct = (await db.execute(stmt)).scalar_one_or_none()
    if direct is not None:
        return direct

    # 2. Indirect via SCAN artifact_refs.task_ids. Linear scan in Python
    # so the lookup behaves identically across SQLite and Postgres.
    stmt = select(Workstream).where(
        Workstream.tenant_id == tenant_id,
        Workstream.source_type == WorkstreamSourceType.SCAN,
        Workstream.archived_at.is_(None),
    )
    scans = (await db.execute(stmt)).scalars().all()
    task_id_str = str(task_id)
    for ws in scans:
        refs = ws.artifact_refs or {}
        task_ids = refs.get("task_ids") or []
        if task_id_str in task_ids:
            return ws
    return None


# Mapping from normalized task status -> intent. The intent is what the
# Workstream's lifecycle sync should attempt; the actual transition may
# be a no-op when the workstream is already in a compatible state.
TASK_STATUS_TO_WS_INTENT: dict[str, str] = {
    "PENDING": "noop",
    "RUNNING": "running",
    "COMPLETED": "complete",
    "COMPLETE": "complete",
    "SUCCESS": "complete",
    "FAILED": "fail",
    "CANCELLED": "fail",
    "PAUSED": "noop",
}
