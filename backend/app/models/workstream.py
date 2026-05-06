"""Workstream model — Daena's visible unit of autonomy.

The Council R3 lock-in (2026-04-25): the user-facing primitive that
spans Daena is the **workstream**: a governed, interruptible thread of
work owned by a department, with a goal, decisions, artifacts,
blockers, and an audit trail.

Hierarchy (locked):
    Tenant -> Department -> Workstream -> Task

Every existing backend mechanism (10 depts × 6 capabilities, KnowledgeBus,
Council/Quintessence, OODA-R, Plain-English Policy Compiler, NBMF
5-tier memory, Shield/Asset Shield/PII Guard, approval queue, audit log,
sub-agent spawner, three-tier escalation router, completeness probe)
serves the workstream — they are workstream services, not parallel UI
concepts.

See ``Doc/COUNCIL_DESIGN_LOCK_2026-04-25.md`` for the full primitive
mapping and design rationale.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    GUID,
    Base,
    JSONBCompat,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.identity import Tenant, User
    from app.models.organization import Department


class WorkstreamStatus(str, Enum):
    """The single visible state for a workstream (R3 lock).

    Five states. Each must answer "what is this workstream doing right
    now, and if it isn't moving, what's it blocked on?" in one sentence.
    """

    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class WorkstreamEscalationLevel(str, Enum):
    """How much reasoning power this workstream draws on right now.

    Maps to the three-tier escalation router. Surfaces in the UI as a
    badge so the user knows what their tokens are paying for.
    """

    STANDARD = "STANDARD"
    HIGH_EFFORT = "HIGH_EFFORT"
    COUNCIL = "COUNCIL"
    QUINTESSENCE = "QUINTESSENCE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class WorkstreamSourceType(str, Enum):
    """Where the workstream originated.

    Drives the source badge in the UI so the operator can distinguish a
    chat-spawned workstream from a scan-driven one or a manual task. The
    set is closed -- new sources require a model change so the UI
    badge map and the spine inventory stay in sync.
    """

    CHAT = "chat"
    SCAN = "scan"
    TASK = "task"
    DEPARTMENT = "department"
    COMPANY_MODE = "company_mode"
    MANUAL = "manual"
    DEV_DEMO = "dev_demo"
    # Sprint-12 PR-4 (2026-05-05): operator promoted a draft to a
    # workstream. source_ref_id holds the ResearchDraft.id /
    # FormDraft.id; context.draft_kind holds "career" / "content" /
    # "form".
    DRAFT = "draft"
    # Sprint-20 PR-3 (2026-05-06): operator (or routine) promoted a
    # discovered Opportunity to a tracked workstream. source_ref_id
    # holds Opportunity.id; context.opportunity_type / .source_url /
    # .deadline_at copy the inbox row at time of promotion so the
    # workstream remains stable if the opportunity row later changes.
    OPPORTUNITY = "opportunity"


class Workstream(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """A governed, interruptible thread of work owned by a department.

    Every ChatSession in EXE/Council mode optionally attaches to a
    workstream. Heartbeat-triggered work, autopilot continuations, and
    multi-step tasks all roll up under a single workstream. The
    workstream is the thing the user manages; everything else is the
    workstream's plumbing.
    """

    __tablename__ = "workstreams"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Owner department + initiating user
    department_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The product-visible fields. ``goal`` is the one-sentence "what is
    # being achieved" the user typed when starting the workstream.
    # ``blocker_text`` is the plain-English "blocked on what / doing what
    # next" line — required reading for the Workstreams console.
    goal: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[WorkstreamStatus] = mapped_column(
        SAEnum(WorkstreamStatus, name="workstream_status"),
        nullable=False,
        default=WorkstreamStatus.RUNNING,
        server_default=WorkstreamStatus.RUNNING.value,
        index=True,
    )
    blocker_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_step_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Escalation level — how much reasoning power is currently engaged.
    # Surfaced as a badge in the UI so the user can see Council/QE cost.
    escalation_level: Mapped[WorkstreamEscalationLevel] = mapped_column(
        SAEnum(WorkstreamEscalationLevel, name="workstream_escalation_level"),
        nullable=False,
        default=WorkstreamEscalationLevel.STANDARD,
        server_default=WorkstreamEscalationLevel.STANDARD.value,
    )

    # Free-form context: scope / constraints / redirect history / metadata.
    # Append-only; rendered as the workstream's decision log.
    context: Mapped[dict] = mapped_column(
        JSONBCompat,
        nullable=False,
        server_default="{}",
    )

    # Cost + token attribution rolled up across the workstream's tasks.
    # Updated by Stage 10 of the orchestrator when a task completes.
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # When the workstream last advanced. Heartbeat reads this to detect
    # stalled workstreams (no progress + status=RUNNING => promote to
    # BLOCKED with stale_progress reason).
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Whether the workstream is paused for autopilot continuation.
    # When True, heartbeat skips it but user actions still apply.
    # Both default=False (Python side) AND server_default="false" (DB side)
    # because the SQLite "false" literal can be returned as truthy on
    # round-trip if Python doesn't set the value at INSERT time.
    autopilot_paused: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )

    # Long-form notes the founder can append; not used for routing.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Where this workstream came from. Closed enum -- adding a source means
    # adding a UI badge map at the same time. Defaults to MANUAL so the
    # legacy `start_workstream` POST that does not declare a source still
    # works unchanged.
    source_type: Mapped[WorkstreamSourceType] = mapped_column(
        SAEnum(WorkstreamSourceType, name="workstream_source_type"),
        nullable=False,
        default=WorkstreamSourceType.MANUAL,
        server_default=WorkstreamSourceType.MANUAL.value,
        index=True,
    )
    # Opaque ref to the upstream artifact (e.g. task.id, scan_job.id,
    # chat_message.id). Not a FK because the target table varies by
    # source_type; the frontend renders it via a /workstreams/{id} link
    # against the appropriate page.
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True,
    )
    # 0..100 progress hint maintained by the runtime. Visible in the
    # WorkstreamsPage card as a thin bar; informational, not a state
    # transition signal (the state machine still owns lifecycle).
    progress_percent: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0",
    )
    # Dict of side-effect artifact references the workstream produced,
    # grouped by kind. Schema (free-form, append-only):
    #   {"scan_report_ids": [...], "draft_ids": [...], "file_ids": [...],
    #    "task_ids": [...], "approval_ids": [...]}
    # The frontend renders these as "Artifacts produced" with one-click
    # navigation per the Execution Spine PRD section 7.3.
    artifact_refs: Mapped[dict] = mapped_column(
        JSONBCompat, nullable=False, server_default="{}",
    )
    # Append-only list of audit_event_ids emitted by this workstream's
    # spine traversal. Drives the "View N audit events" link on the
    # detail drawer (PRD section 11.2 row 5).
    audit_event_refs: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )
    # Append-only list of notification_ids emitted by this workstream's
    # spine traversal. Drives the bell-cross-link on completion / block.
    notification_refs: Mapped[list] = mapped_column(
        JSONBCompat, nullable=False, server_default="[]",
    )

    # Relationships
    department: Mapped["Department"] = relationship(
        foreign_keys=[department_id],
    )
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    events: Mapped[list["WorkstreamEvent"]] = relationship(
        back_populates="workstream",
        cascade="all, delete-orphan",
        order_by="WorkstreamEvent.occurred_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Workstream id={self.id} status={self.status.value} "
            f"goal={self.goal[:40]!r}>"
        )


class WorkstreamEventKind(str, Enum):
    """Categorization of events on the workstream timeline.

    Drives the badges + icons rendered in the Live Console timeline.
    Keep tight: every kind is a real, distinct concept the user cares
    about. Adding a new kind without UI design = drift.
    """

    STARTED = "STARTED"
    REDIRECTED = "REDIRECTED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    ESCALATED = "ESCALATED"
    BLOCKED = "BLOCKED"
    UNBLOCKED = "UNBLOCKED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    DECISION = "DECISION"          # a synthesis or chairman call
    ARTIFACT = "ARTIFACT"          # a file / report / output produced
    TOOL_CALL = "TOOL_CALL"        # an EXE tool invocation
    SUB_AGENT_SPAWNED = "SUB_AGENT_SPAWNED"
    COMPLETENESS_FOOTER = "COMPLETENESS_FOOTER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkstreamEvent(Base, TenantMixin, TimestampMixin):
    """Append-only timeline entries for a workstream.

    The Workstreams console renders these as the **Governed Execution
    Timeline** — the per-workstream stream of pipeline stage, runtime,
    policy checks, tool calls, artifacts, approvals, and audit events.

    Designed append-only: you never mutate an event; you append a new
    one (e.g. UNBLOCKED after BLOCKED, REDIRECTED with a new goal).
    This is what makes the workstream auditable.
    """

    __tablename__ = "workstream_events"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    workstream_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workstreams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[WorkstreamEventKind] = mapped_column(
        SAEnum(WorkstreamEventKind, name="workstream_event_kind"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict] = mapped_column(
        JSONBCompat,
        nullable=False,
        server_default="{}",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    workstream: Mapped[Workstream] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<WorkstreamEvent kind={self.kind.value} ws={self.workstream_id}>"
