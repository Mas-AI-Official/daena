"""Tests for Approval Queue (Sprint 3, Phase 4).

Covers ApprovalItem, ApprovalQueue operations (add, approve,
reject, escalate), filtering, summary, and WebSocket notifications.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.approval_queue import ApprovalItem, ApprovalQueue

# ── ApprovalItem tests ──


class TestApprovalItem:
    def test_to_dict_serialization(self):
        item = ApprovalItem(
            id="item-1",
            session_id="sess-1",
            action_description="Delete files",
            rejection_source="GovernanceCheck",
            rejection_reason="High risk",
            governance_tier=4,
        )
        d = item.to_dict()
        assert d["id"] == "item-1"
        assert d["is_pending"] is True
        assert d["rejection_source"] == "GovernanceCheck"

    def test_pending_when_no_decision(self):
        item = ApprovalItem()
        assert item.user_decision is None
        assert item.to_dict()["is_pending"] is True

    def test_not_pending_after_decision(self):
        item = ApprovalItem(user_decision="approved")
        assert item.to_dict()["is_pending"] is False

    def test_default_fields(self):
        item = ApprovalItem()
        assert item.id  # auto-generated UUID
        assert item.timestamp  # auto-generated timestamp
        assert item.governance_tier == 0
        assert item.override_logged is False


# ── ApprovalQueue tests ──


class TestApprovalQueue:
    @pytest.fixture
    def queue(self):
        return ApprovalQueue()

    @pytest.mark.asyncio
    async def test_add_item(self, queue):
        item = ApprovalItem(
            session_id="s1",
            action_description="Test action",
        )
        result = await queue.add(item)
        assert result.id == item.id
        assert queue.pending_count == 1

    @pytest.mark.asyncio
    async def test_approve_item(self, queue):
        item = ApprovalItem(
            session_id="s1",
            action_description="Delete config",
        )
        await queue.add(item)
        result = await queue.approve(item.id, "user-1")
        assert result is not None
        assert result.user_decision == "approved"
        assert result.decided_by == "user-1"
        assert result.user_decision_time is not None
        assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_reject_item(self, queue):
        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        result = await queue.reject(item.id, "user-2")
        assert result is not None
        assert result.user_decision == "rejected"

    @pytest.mark.asyncio
    async def test_escalate_item(self, queue):
        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        result = await queue.escalate(item.id, "user-3")
        assert result is not None
        assert result.user_decision == "escalated"

    @pytest.mark.asyncio
    async def test_approve_nonexistent(self, queue):
        result = await queue.approve("no-such-id", "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_approve_already_decided(self, queue):
        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        await queue.approve(item.id, "user-1")
        # Try again: should return None
        result = await queue.approve(item.id, "user-2")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pending(self, queue):
        item1 = ApprovalItem(session_id="s1")
        item2 = ApprovalItem(session_id="s1")
        item3 = ApprovalItem(session_id="s2")
        await queue.add(item1)
        await queue.add(item2)
        await queue.add(item3)

        all_pending = queue.get_pending()
        assert len(all_pending) == 3

        s1_pending = queue.get_pending(session_id="s1")
        assert len(s1_pending) == 2

    @pytest.mark.asyncio
    async def test_get_decided(self, queue):
        item1 = ApprovalItem(session_id="s1")
        item2 = ApprovalItem(session_id="s1")
        await queue.add(item1)
        await queue.add(item2)
        await queue.approve(item1.id, "user-1")

        decided = queue.get_decided()
        assert len(decided) == 1
        assert decided[0].user_decision == "approved"

    @pytest.mark.asyncio
    async def test_get_by_id(self, queue):
        item = ApprovalItem(id="specific-id", session_id="s1")
        await queue.add(item)
        found = queue.get_by_id("specific-id")
        assert found is not None
        assert found.id == "specific-id"

    def test_get_by_id_nonexistent(self, queue):
        assert queue.get_by_id("nope") is None

    @pytest.mark.asyncio
    async def test_summary(self, queue):
        items = [ApprovalItem(session_id="s1") for _ in range(5)]
        for item in items:
            await queue.add(item)
        await queue.approve(items[0].id, "u1")
        await queue.reject(items[1].id, "u1")
        await queue.escalate(items[2].id, "u1")

        summary = queue.get_summary()
        assert summary["pending"] == 2
        assert summary["approved"] == 1
        assert summary["rejected"] == 1
        assert summary["escalated"] == 1
        assert summary["total"] == 5

    @pytest.mark.asyncio
    async def test_ws_notification_on_add(self):
        mock_ws = MagicMock()
        mock_ws.broadcast = AsyncMock()
        queue = ApprovalQueue(ws_manager=mock_ws)

        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        mock_ws.broadcast.assert_called_once()
        call_args = mock_ws.broadcast.call_args
        assert call_args[0][0] == "s1"
        assert call_args[0][1]["type"] == "approval_needed"

    @pytest.mark.asyncio
    async def test_ws_notification_on_approve(self):
        mock_ws = MagicMock()
        mock_ws.broadcast = AsyncMock()
        queue = ApprovalQueue(ws_manager=mock_ws)

        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        await queue.approve(item.id, "u1")

        # Second call should be the decision notification
        assert mock_ws.broadcast.call_count == 2
        second_call = mock_ws.broadcast.call_args_list[1]
        assert second_call[0][1]["type"] == "approval_decided"

    @pytest.mark.asyncio
    async def test_pending_count(self, queue):
        assert queue.pending_count == 0
        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        assert queue.pending_count == 1
        await queue.approve(item.id, "u1")
        assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_override_logged_on_approve(self, queue):
        item = ApprovalItem(session_id="s1")
        await queue.add(item)
        result = await queue.approve(item.id, "u1")
        assert result.override_logged is True
