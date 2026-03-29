"""Approval Queue: manages rejected actions awaiting user decisions.

When any action is rejected by governance (internal or external), it
enters this queue. Users can approve (override), reject (confirm), or
escalate. Every decision is logged to the audit trail.

This is the in-memory complement to the database GoaRequest model.
For rapid access during active sessions, items live here. Completed
items are persisted to GoaRequest for long-term audit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ApprovalItem:
    """An action awaiting user approval.

    Attributes:
        id: Unique identifier.
        timestamp: When the rejection occurred.
        session_id: Chat session context.
        action_description: What was attempted.
        action_type: Classified action type.
        rejection_source: Pipeline stage that rejected (SecurityGate,
            GovernanceCheck, Council, CostPreflight, CriticalityClassifier).
        rejection_reason: Why it was rejected.
        rejection_confidence: How confident the rejection was (0.0-1.0).
        governance_tier: Which governance tier triggered the rejection.
        subtask_data: Optional subtask data if from SwarmExecutor.
        user_decision: None (pending), "approved", "rejected", "escalated".
        user_decision_time: When the user decided.
        decided_by: User ID who decided.
        override_logged: Whether the override was logged to audit trail.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    session_id: str = ""
    action_description: str = ""
    action_type: str = ""
    rejection_source: str = ""
    rejection_reason: str = ""
    rejection_confidence: float = 0.0
    governance_tier: int = 0
    subtask_data: dict[str, Any] | None = None
    user_decision: str | None = None
    user_decision_time: str | None = None
    decided_by: str | None = None
    override_logged: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/WebSocket transmission."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "action_description": self.action_description,
            "action_type": self.action_type,
            "rejection_source": self.rejection_source,
            "rejection_reason": self.rejection_reason,
            "rejection_confidence": self.rejection_confidence,
            "governance_tier": self.governance_tier,
            "user_decision": self.user_decision,
            "user_decision_time": self.user_decision_time,
            "decided_by": self.decided_by,
            "is_pending": self.user_decision is None,
        }


class ApprovalQueue:
    """In-memory queue for actions awaiting user approval.

    Provides fast access for active session approvals. Items are
    indexed by ID and session_id for efficient retrieval. WebSocket
    notifications are pushed on add, approve, and reject.

    Usage::

        queue = ApprovalQueue()
        item = await queue.add(ApprovalItem(
            session_id="sess-1",
            action_description="Delete production database",
            rejection_source="GovernanceCheck",
            rejection_reason="High-risk action (tier 4)",
        ))

        await queue.approve(item.id, user_id="founder-1")
    """

    def __init__(self, ws_manager: Any = None) -> None:
        """Initialize with optional WebSocket manager for notifications.

        Args:
            ws_manager: ConnectionManager for push notifications.
        """
        self._items: dict[str, ApprovalItem] = {}
        self._ws = ws_manager

    async def add(self, item: ApprovalItem) -> ApprovalItem:
        """Add a rejected action to the queue.

        Args:
            item: ApprovalItem describing the rejected action.

        Returns:
            The item with ID populated.
        """
        self._items[item.id] = item

        logger.info(
            "approval_queue.item_added",
            item_id=item.id,
            session_id=item.session_id,
            source=item.rejection_source,
        )

        # Notify via WebSocket
        if self._ws and item.session_id:
            await self._ws.broadcast(item.session_id, {
                "type": "approval_needed",
                "data": item.to_dict(),
            })

        return item

    async def approve(
        self,
        item_id: str,
        user_id: str,
    ) -> ApprovalItem | None:
        """User approves (overrides) a rejection.

        Logs the override to the audit trail.

        Args:
            item_id: ID of the item to approve.
            user_id: ID of the user approving.

        Returns:
            The updated item, or None if not found.
        """
        item = self._items.get(item_id)
        if not item or item.user_decision is not None:
            return None

        item.user_decision = "approved"
        item.user_decision_time = datetime.now(UTC).isoformat()
        item.decided_by = user_id
        item.override_logged = True

        logger.info(
            "approval_queue.approved",
            item_id=item_id,
            user_id=user_id,
            action=item.action_description[:100],
        )

        # Notify
        if self._ws and item.session_id:
            await self._ws.broadcast(item.session_id, {
                "type": "approval_decided",
                "data": item.to_dict(),
            })

        return item

    async def reject(
        self,
        item_id: str,
        user_id: str,
    ) -> ApprovalItem | None:
        """User confirms the rejection.

        Args:
            item_id: ID of the item.
            user_id: ID of the user confirming.

        Returns:
            The updated item, or None if not found.
        """
        item = self._items.get(item_id)
        if not item or item.user_decision is not None:
            return None

        item.user_decision = "rejected"
        item.user_decision_time = datetime.now(UTC).isoformat()
        item.decided_by = user_id

        logger.info(
            "approval_queue.rejected",
            item_id=item_id,
            user_id=user_id,
        )

        if self._ws and item.session_id:
            await self._ws.broadcast(item.session_id, {
                "type": "approval_decided",
                "data": item.to_dict(),
            })

        return item

    async def escalate(
        self,
        item_id: str,
        user_id: str,
    ) -> ApprovalItem | None:
        """User escalates the item for higher authority review.

        Args:
            item_id: ID of the item.
            user_id: ID of the user escalating.

        Returns:
            The updated item, or None if not found.
        """
        item = self._items.get(item_id)
        if not item or item.user_decision is not None:
            return None

        item.user_decision = "escalated"
        item.user_decision_time = datetime.now(UTC).isoformat()
        item.decided_by = user_id

        logger.info(
            "approval_queue.escalated",
            item_id=item_id,
            user_id=user_id,
        )

        return item

    def get_pending(
        self,
        session_id: str | None = None,
    ) -> list[ApprovalItem]:
        """Get all pending items, optionally filtered by session.

        Args:
            session_id: Filter to a specific session.

        Returns:
            List of pending ApprovalItems.
        """
        items = [
            item for item in self._items.values()
            if item.user_decision is None
        ]
        if session_id:
            items = [i for i in items if i.session_id == session_id]
        return sorted(items, key=lambda x: x.timestamp, reverse=True)

    def get_decided(
        self,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[ApprovalItem]:
        """Get decided items (approved, rejected, escalated).

        Args:
            session_id: Filter to a specific session.
            limit: Max items to return.

        Returns:
            List of decided ApprovalItems, most recent first.
        """
        items = [
            item for item in self._items.values()
            if item.user_decision is not None
        ]
        if session_id:
            items = [i for i in items if i.session_id == session_id]
        items.sort(key=lambda x: x.user_decision_time or "", reverse=True)
        return items[:limit]

    def get_by_id(self, item_id: str) -> ApprovalItem | None:
        """Get a specific item by ID."""
        return self._items.get(item_id)

    @property
    def pending_count(self) -> int:
        """Number of items awaiting decision."""
        return sum(
            1 for item in self._items.values()
            if item.user_decision is None
        )

    def get_summary(self) -> dict[str, int]:
        """Summary counts by decision state."""
        pending = 0
        approved = 0
        rejected = 0
        escalated = 0
        for item in self._items.values():
            if item.user_decision is None:
                pending += 1
            elif item.user_decision == "approved":
                approved += 1
            elif item.user_decision == "rejected":
                rejected += 1
            elif item.user_decision == "escalated":
                escalated += 1
        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "escalated": escalated,
            "total": len(self._items),
        }
