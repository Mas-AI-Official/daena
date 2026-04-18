"""BorderAgent -- per-department liaison that keeps the company self-aware.

The founder's vision, verbatim: departments mostly do their own work, but
they "already connect to each other and know what is going on in real time
not by having meetings." No hard-coded sync cadence, no shared spreadsheet
the humans update. Each department emits its own lifecycle events; every
other department's BorderAgent filters the incoming stream through a
relevance lens and surfaces only signals its owning department cares about.

This maps the "border agent" concept onto primitives Daena already has:

* ``app.core.events.event_bus`` -- process-wide async pub/sub (existing).
* ``DepartmentStateService`` -- WORKING / IDLE / OVERLOADED / OFFLINE state
  (Session A, existing).
* ``DepartmentMessageService`` -- point-to-point ASK / ANSWER (Session C,
  existing).
* ``KnowledgeBus`` inside SubAgentSpawner -- per-session shared knowledge
  (existing, scoped to spawner lifecycle).

BorderAgent is the missing piece: a long-lived per-(tenant, department)
listener on the event_bus that publishes lifecycle events and caches
inbound peer signals. Each department room polls
``GET /api/v1/department-states/{dept}/peer-signals`` to render the feed.

The relevance lens is a static map keyed by listening department. Finance
listens for any ``*.expense_*`` / ``Sales.closed_deal`` event; Legal listens
for ``*.contract_*`` / ``*.compliance_*`` / ``Sales.proposal_sent``; Security
Operations listens for ``*.threat_*`` / ``*.incident_*`` / ``*.governance_tier_high``.

The lens is deliberately a dict, not an LLM classifier. LLM-based relevance
adds latency to every cross-department event. Keep the lens simple; let
Skill Governance evolve it from usage telemetry.
"""

from __future__ import annotations

import asyncio
import fnmatch
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.events import event_bus
from app.core.logging import get_logger

logger = get_logger(__name__)


# Standard event types each department can emit. NOT exhaustive -- agents
# can emit ad-hoc ``{department}.{custom_type}`` events; subscribers
# match via wildcard patterns below.
class DepartmentEvent:
    TASK_STARTED = "department.task_started"
    TASK_COMPLETED = "department.task_completed"
    TASK_REJECTED = "department.task_rejected"
    TASK_FAILED = "department.task_failed"
    FLAGGED_RISK = "department.flagged_risk"
    NEEDS_INPUT = "department.needs_input"
    PROPOSAL_SENT = "Sales.proposal_sent"
    CLOSED_DEAL = "Sales.closed_deal"
    LOST_DEAL = "Sales.lost_deal"
    CONTRACT_SIGNED = "Legal.contract_signed"
    COMPLIANCE_FLAG = "Legal.compliance_flag"
    EXPENSE_PROPOSAL = "Finance.expense_proposal"
    EXPENSE_APPROVED = "Finance.expense_approved"
    THREAT_DETECTED = "SecurityOps.threat_detected"
    INCIDENT = "SecurityOps.incident"
    GOV_TIER_HIGH = "Governance.tier_high"


# Each key is a listening department; value is a list of glob patterns.
# A peer event matches if its ``event_type`` fits any pattern OR if the
# event payload's ``_tags`` (optional) overlap with the listener's tags.
#
# Tuning rule: keep each dept to 5 to 8 patterns. Broader lists dilute the
# signal. Narrower lists miss real signals. Five to eight is what real
# executive dashboards show.
DEPARTMENT_RELEVANCE: dict[str, list[str]] = {
    "Engineering": [
        "department.task_failed",
        "SecurityOps.threat_detected",
        "Legal.compliance_flag",
    ],
    "Product": [
        "department.needs_input",
        "department.flagged_risk",
        "Sales.closed_deal",
        "SecurityOps.incident",
    ],
    "Marketing": [
        "Sales.closed_deal",
        "Sales.proposal_sent",
        "Sales.lost_deal",
    ],
    "Sales": [
        "Legal.contract_signed",
        "Finance.expense_approved",
        "department.flagged_risk",
    ],
    "Finance": [
        "Sales.closed_deal",
        "Sales.lost_deal",
        "Finance.expense_proposal",
        "department.flagged_risk",
        "*.budget_*",
    ],
    "Operations": [
        "department.task_started",
        "department.task_completed",
        "department.task_failed",
        "Sales.closed_deal",
    ],
    "Research": [
        "department.flagged_risk",
        "SecurityOps.threat_detected",
        "Marketing.*",
    ],
    "Legal & Compliance": [
        "Sales.proposal_sent",
        "Sales.closed_deal",
        "Finance.expense_proposal",
        "*.compliance_*",
        "SecurityOps.incident",
    ],
    "Skill Governance": [
        "department.task_completed",
        "department.task_failed",
        "*",  # Skill Gov learns from everything; opts in globally.
    ],
    "Security Operations": [
        "*.threat_*",
        "*.incident*",
        "Governance.tier_high",
        "Legal.compliance_flag",
        "department.needs_input",
    ],
    # Daena herself is the 11th BorderAgent -- the supervisor / VP
    # Masoud talks to directly. She listens to EVERYTHING across all
    # 10 departments so when the founder asks "what's going on", her
    # chat_orchestrator already has the full company-wide signal feed
    # in hand. Distinct from Skill Governance's '*' (which learns for
    # skill refinement) -- Daena's '*' is for founder situational
    # awareness and cross-department orchestration.
    "Daena": ["*"],
}


@dataclass
class Signal:
    """One peer event received into a department's BorderAgent inbox."""

    id: str
    source_department: str
    event_type: str
    payload: dict[str, Any]
    created_at: float
    # When the signal was seen as relevant to the listening department.
    relevant_because: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_department": self.source_department,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
            "relevant_because": self.relevant_because,
        }


# Ring-buffer capacity per department per tenant. Old signals drop.
_DEFAULT_CAPACITY = 200


class BorderAgent:
    """One liaison per (tenant, department). Lives for the process lifetime.

    Not an LLM agent. A pure event filter + cache. It does NOT reason
    about payloads; it only routes them. Reasoning happens when the
    owning department's chat_orchestrator pulls signals at turn start.
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        department: str,
        capacity: int = _DEFAULT_CAPACITY,
    ) -> None:
        self.tenant_id = tenant_id
        self.department = department
        self._inbox: deque[Signal] = deque(maxlen=capacity)
        self._patterns = DEPARTMENT_RELEVANCE.get(department, [])
        self._bus = event_bus
        self._started = False
        self._seq = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Subscribe to every known department event type.

        Done once. The listener inside filters by (a) tenant match, (b)
        source is not us, (c) relevance pattern hits.
        """
        if self._started:
            return
        self._started = True
        # Register ONE handler per distinct event_type we care about.
        # Using wildcards here would require the bus to support them;
        # EventBus keys by exact event_type, so we subscribe to the
        # concrete types we know about. Ad-hoc types still reach us if
        # another department publishes with that exact key AND we listed
        # a matching glob in DEPARTMENT_RELEVANCE.
        for event_type in _known_event_types():
            self._bus.subscribe(event_type, self._on_event)
        logger.info(
            "border_agent.started",
            tenant_id=str(self.tenant_id),
            department=self.department,
            patterns=len(self._patterns),
        )

    async def emit(
        self,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Publish a lifecycle event from this department."""
        envelope = {
            "_source_department": self.department,
            "_source_tenant_id": str(self.tenant_id),
            "_event_type": event_type,
            "_timestamp": time.time(),
            **(payload or {}),
        }
        await self._bus.publish(event_type, **envelope)
        logger.debug(
            "border_agent.emitted",
            department=self.department,
            event_type=event_type,
        )

    async def _on_event(self, **kwargs: Any) -> None:
        """Filter inbound event, append to inbox if relevant."""
        # Same-tenant only. Cross-tenant leakage would violate Hard Law 7.
        src_tenant = kwargs.get("_source_tenant_id")
        if src_tenant != str(self.tenant_id):
            return

        source_department = kwargs.get("_source_department")
        if source_department == self.department:
            return  # don't echo our own emits back

        event_type = kwargs.get("_event_type") or ""
        matched = self._match(event_type)
        if not matched:
            return

        # Strip the envelope keys before surfacing the payload.
        payload = {
            k: v for k, v in kwargs.items()
            if not (isinstance(k, str) and k.startswith("_"))
        }

        async with self._lock:
            self._seq += 1
            signal = Signal(
                id=f"{self.department}-{self._seq}",
                source_department=str(source_department),
                event_type=event_type,
                payload=payload,
                created_at=float(kwargs.get("_timestamp") or time.time()),
                relevant_because=matched,
            )
            self._inbox.append(signal)

    def _match(self, event_type: str) -> str:
        """Return the first pattern that matches, or empty string if none."""
        for pattern in self._patterns:
            if pattern == event_type or fnmatch.fnmatch(event_type, pattern):
                return pattern
        return ""

    def recent_signals(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the N most recent relevant peer signals, newest first."""
        items = list(self._inbox)
        items.reverse()
        return [s.to_dict() for s in items[:limit]]

    def clear(self) -> None:
        """Drop the inbox. Used by tests; not a production path."""
        self._inbox.clear()
        self._seq = 0


def format_signals_for_prompt(
    signals: list[dict[str, Any]], *, max_lines: int = 5
) -> str:
    """Render a list of recent_signals() entries as prompt-ready lines.

    Used by chat_orchestrator Stage 6.4 to inject peer-department
    awareness into the system prompt. Format is deliberately compact
    -- each line is a single `[Source] event_type: summary` entry so
    the LLM can skim without eating a large chunk of context window.

    Args:
        signals: Output of BorderAgent.recent_signals() (list of dicts
            with event_type, source_department, payload).
        max_lines: Cap on output lines. Caller typically passes 5-10.

    Returns:
        Newline-joined string, or empty string if no signals.
    """
    if not signals:
        return ""
    lines = []
    for sig in signals[:max_lines]:
        src = sig.get("source_department", "?")
        evt = sig.get("event_type", "?")
        payload = sig.get("payload") or {}
        summary = payload.get("task_summary") or payload.get("reason") or evt
        lines.append(f"- [{src}] {evt}: {summary}")
    return "\n".join(lines)


# ── Registry (process-wide, per (tenant, department)) ──────────


_REGISTRY: dict[tuple[str, str], BorderAgent] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def get_border_agent(
    *, tenant_id: UUID, department: str,
) -> BorderAgent:
    """Get or create the BorderAgent for (tenant, department).

    First call constructs + starts. Subsequent calls return the live
    instance so the inbox stays contiguous across requests.
    """
    key = (str(tenant_id), department)
    async with _REGISTRY_LOCK:
        ba = _REGISTRY.get(key)
        if ba is None:
            ba = BorderAgent(tenant_id=tenant_id, department=department)
            await ba.start()
            _REGISTRY[key] = ba
    return ba


async def reset_registry() -> None:
    """Test helper -- wipe the process registry so a test starts clean."""
    async with _REGISTRY_LOCK:
        _REGISTRY.clear()


def _known_event_types() -> list[str]:
    """Collect all named DepartmentEvent constants.

    Plus any concrete (non-wildcard) entry from DEPARTMENT_RELEVANCE so
    ad-hoc event types listed there get subscribed too. Wildcards
    themselves cannot be subscribed (EventBus keys on exact string);
    events must be published with a concrete type that matches the glob.
    """
    attrs = [
        v for k, v in vars(DepartmentEvent).items()
        if not k.startswith("_") and isinstance(v, str)
    ]
    # Pull concrete patterns from relevance map too.
    for patterns in DEPARTMENT_RELEVANCE.values():
        for p in patterns:
            if "*" not in p and "?" not in p and "[" not in p:
                if p not in attrs:
                    attrs.append(p)
    return attrs
