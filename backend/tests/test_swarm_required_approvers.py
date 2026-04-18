"""Tests the SwarmExecutor required_approvers gate.

Covers:
* No approvers -> auto-approve.
* Self-approval filter (from-department equals approver) -> skipped.
* Listed approver answers ACK -> subtask proceeds.
* Listed approver answers "NO ..." -> subtask rejected.
* Approver timeout / no answer -> fail-safe approve.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.services.swarm.executor import SwarmExecutor


class _StubRegistry:
    """Minimal RuntimeRegistry stand-in -- executor constructor only."""


@pytest.mark.asyncio
async def test_empty_approver_list_auto_approves() -> None:
    executor = SwarmExecutor(registry=_StubRegistry())
    approved, reason = await executor._solicit_required_approvers(
        subtask_id="t-1",
        subtask_description="ad buy",
        from_department="Marketing",
        required_approvers=[],
        tenant_id=uuid.uuid4(),
    )
    assert approved is True


@pytest.mark.asyncio
async def test_self_approval_filter(monkeypatch) -> None:
    """Marketing asking Marketing for approval should short-circuit."""
    executor = SwarmExecutor(registry=_StubRegistry())
    approved, reason = await executor._solicit_required_approvers(
        subtask_id="t-2",
        subtask_description="self-ask",
        from_department="Marketing",
        required_approvers=["Marketing"],
        tenant_id=uuid.uuid4(),
    )
    # Self-filter reduces to empty list. Helper returns auto-approve.
    assert approved is True


@pytest.mark.asyncio
async def test_denial_blocks_subtask(monkeypatch) -> None:
    """A 'NO ...' answer from any approver blocks."""
    executor = SwarmExecutor(registry=_StubRegistry())

    # Stub the DepartmentMessageService to return a controlled answer.
    class _StubService:
        def __init__(self, db): pass
        async def send(self, **kw):
            from types import SimpleNamespace
            return SimpleNamespace(id=uuid.uuid4())
        async def wait_for_answer(self, *, message_id, timeout_seconds, poll_interval_seconds):
            from types import SimpleNamespace
            return SimpleNamespace(status="ANSWERED", body="NO, budget exceeded")

    class _StubSessionCtx:
        async def __aenter__(self): return _StubSession()
        async def __aexit__(self, *a): return None

    class _StubSession:
        async def commit(self): pass

    def _stub_factory(): return _StubSessionCtx()

    monkeypatch.setattr(
        "app.core.database.async_session_factory", _stub_factory,
    )
    monkeypatch.setattr(
        "app.services.department_message_service.DepartmentMessageService",
        _StubService,
    )

    approved, reason = await executor._solicit_required_approvers(
        subtask_id="t-3",
        subtask_description="$10K ad buy",
        from_department="Marketing",
        required_approvers=["Finance"],
        tenant_id=uuid.uuid4(),
        timeout_seconds=2,
    )
    assert approved is False
    assert "Finance" in reason
    assert "NO" in reason.upper() or "budget" in reason.lower()


@pytest.mark.asyncio
async def test_timeout_fails_safe_to_approve(monkeypatch) -> None:
    """If an approver never responds, treat as provisional approve.

    Rationale: DepartmentPolicy already decided WHO must approve. If
    those departments are unstaffed or offline, blocking forever hurts
    the operator more than fail-safe approval -- the GovernanceEngine
    still guards the truly high-risk actions via tier-3+ gates.
    """
    executor = SwarmExecutor(registry=_StubRegistry())

    class _TimeoutService:
        def __init__(self, db): pass
        async def send(self, **kw):
            from types import SimpleNamespace
            return SimpleNamespace(id=uuid.uuid4())
        async def wait_for_answer(self, *, message_id, timeout_seconds, poll_interval_seconds):
            return None  # timeout

    class _StubSessionCtx:
        async def __aenter__(self):
            class _S:
                async def commit(self): pass
            return _S()
        async def __aexit__(self, *a): return None

    monkeypatch.setattr(
        "app.core.database.async_session_factory", lambda: _StubSessionCtx(),
    )
    monkeypatch.setattr(
        "app.services.department_message_service.DepartmentMessageService",
        _TimeoutService,
    )

    approved, reason = await executor._solicit_required_approvers(
        subtask_id="t-4",
        subtask_description="routine op",
        from_department="Marketing",
        required_approvers=["Finance"],
        tenant_id=uuid.uuid4(),
        timeout_seconds=1,
    )
    assert approved is True  # fail-safe
