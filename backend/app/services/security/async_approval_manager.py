"""AsyncApprovalManager -- Non-blocking governance approval.

Ported from OpenClaw's exec-approval-manager.ts.

Instead of blocking execution while waiting for user approval,
this uses asyncio.Future to allow the execution loop to yield
an "approval_required" event and then WAIT for the user's decision.

Flow:
    1. Tool call classified as needing approval (by ToolCallClassifier)
    2. AsyncApprovalManager.create() creates a pending approval record
    3. Execution loop yields approval_required SSE event
    4. Frontend shows approve/deny buttons in chat
    5. User clicks approve -> API resolves the future
    6. Execution continues (or stops if denied)

Features:
    - Configurable timeout (default 60s)
    - Grace period for late decisions (15s)
    - allow-once vs allow-always semantics
    - Timeout default behavior: configurable (deny or allow)

Port source: openclaw-main/src/gateway/exec-approval-manager.ts
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


class ApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    APPROVED_ALWAYS = "approved_always"  # Don't ask again for this tool


@dataclass
class ApprovalRequest:
    """A pending approval request."""
    id: str = field(default_factory=lambda: str(uuid4()))
    tool_name: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "medium"
    reason: str = ""
    decision: ApprovalDecision = ApprovalDecision.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: str = ""  # "user", "timeout", "auto"


class AsyncApprovalManager:
    """Non-blocking approval manager.

    Usage::

        manager = AsyncApprovalManager()

        # When a tool call needs approval:
        request = await manager.create(tool_name, params, risk_level)
        future = manager.register(request.id)

        # Yield SSE event for frontend
        yield {"type": "approval_required", "request_id": request.id, ...}

        # Wait for user decision (with timeout)
        decision = await asyncio.wait_for(future, timeout=60)

        if decision == ApprovalDecision.APPROVED:
            # Execute the tool
        else:
            # Skip this tool call
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 60.0,
        grace_period_seconds: float = 15.0,
        timeout_default: ApprovalDecision = ApprovalDecision.DENIED,
    ) -> None:
        self._timeout = timeout_seconds
        self._grace_period = grace_period_seconds
        self._timeout_default = timeout_default
        self._pending: dict[str, ApprovalRequest] = {}
        self._futures: dict[str, asyncio.Future[ApprovalDecision]] = {}
        self._always_approved: set[str] = set()  # tool names with "always approve"

    async def create(
        self,
        tool_name: str,
        params: dict[str, Any],
        risk_level: str = "medium",
        reason: str = "",
    ) -> ApprovalRequest:
        """Create a new approval request.

        Returns the request object. The frontend should show
        approve/deny buttons for this request.
        """
        # Check if tool has "always approve"
        if tool_name in self._always_approved:
            request = ApprovalRequest(
                tool_name=tool_name,
                params=params,
                risk_level=risk_level,
                reason=reason,
                decision=ApprovalDecision.APPROVED_ALWAYS,
                decided_by="auto",
            )
            logger.info(
                "approval.auto_approved",
                tool=tool_name,
                reason="always_approved",
            )
            return request

        request = ApprovalRequest(
            tool_name=tool_name,
            params=params,
            risk_level=risk_level,
            reason=reason,
        )
        self._pending[request.id] = request

        logger.info(
            "approval.created",
            request_id=request.id,
            tool=tool_name,
            risk=risk_level,
        )
        return request

    def register(self, request_id: str) -> asyncio.Future[ApprovalDecision]:
        """Register a future for an approval request.

        Returns an asyncio.Future that resolves when the user decides.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[ApprovalDecision] = loop.create_future()
        self._futures[request_id] = future
        return future

    async def resolve(
        self,
        request_id: str,
        decision: ApprovalDecision,
        decided_by: str = "user",
    ) -> bool:
        """Resolve an approval request (user clicked approve/deny).

        Called from the API endpoint when user makes a decision.
        Returns True if the request was pending and resolved.
        """
        request = self._pending.get(request_id)
        if not request:
            logger.warning("approval.resolve_not_found", request_id=request_id)
            return False

        request.decision = decision
        request.decided_at = datetime.now(timezone.utc)
        request.decided_by = decided_by

        # Handle "always approve"
        if decision == ApprovalDecision.APPROVED_ALWAYS:
            self._always_approved.add(request.tool_name)

        # Resolve the future
        future = self._futures.get(request_id)
        if future and not future.done():
            future.set_result(decision)

        # Cleanup
        self._pending.pop(request_id, None)
        self._futures.pop(request_id, None)

        logger.info(
            "approval.resolved",
            request_id=request_id,
            decision=decision.value,
            decided_by=decided_by,
        )
        return True

    async def wait_for_decision(
        self,
        request_id: str,
    ) -> ApprovalDecision:
        """Wait for a decision with timeout.

        Returns the decision or the timeout default.
        Includes grace period for late decisions.
        """
        future = self._futures.get(request_id)
        if not future:
            return self._timeout_default

        try:
            decision = await asyncio.wait_for(future, timeout=self._timeout)
            return decision
        except asyncio.TimeoutError:
            # Grace period
            try:
                decision = await asyncio.wait_for(future, timeout=self._grace_period)
                logger.info("approval.grace_period_decision", request_id=request_id)
                return decision
            except asyncio.TimeoutError:
                # Truly timed out
                logger.info(
                    "approval.timed_out",
                    request_id=request_id,
                    default=self._timeout_default.value,
                )
                # Cleanup
                self._pending.pop(request_id, None)
                self._futures.pop(request_id, None)
                return self._timeout_default

    def is_always_approved(self, tool_name: str) -> bool:
        """Check if a tool has been permanently approved."""
        return tool_name in self._always_approved

    def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self._pending.values())

    def clear(self) -> None:
        """Clear all pending requests and futures."""
        for future in self._futures.values():
            if not future.done():
                future.set_result(self._timeout_default)
        self._pending.clear()
        self._futures.clear()
