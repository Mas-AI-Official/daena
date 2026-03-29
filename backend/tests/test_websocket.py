"""Tests for WebSocket ConnectionManager.

Validates:
- Connection lifecycle (connect, disconnect, cleanup)
- Send to individual connections and broadcast
- Multi-session isolation
- Graceful handling of failed sends
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.websocket import ConnectionManager


def _make_ws(*, fail_on_send: bool = False) -> AsyncMock:
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    if fail_on_send:
        ws.send_json = AsyncMock(side_effect=RuntimeError("connection closed"))
    else:
        ws.send_json = AsyncMock()
    return ws


class TestConnectionLifecycle:
    """Connect, disconnect, and cleanup."""

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self) -> None:
        """connect() calls accept() and registers the connection."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect("session-1", ws)

        ws.accept.assert_awaited_once()
        assert mgr.get_connection_count("session-1") == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self) -> None:
        """disconnect() removes the connection from the registry."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect("session-1", ws)
        mgr.disconnect("session-1", ws)

        assert mgr.get_connection_count("session-1") == 0

    @pytest.mark.asyncio
    async def test_disconnect_unknown_session_is_safe(self) -> None:
        """Disconnecting from a non-existent session doesn't raise."""
        mgr = ConnectionManager()
        ws = _make_ws()
        mgr.disconnect("nonexistent", ws)  # Should not raise

    @pytest.mark.asyncio
    async def test_multiple_connections_per_session(self) -> None:
        """Multiple browser tabs connect to the same session."""
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-1", ws2)

        assert mgr.get_connection_count("session-1") == 2

    @pytest.mark.asyncio
    async def test_disconnect_one_leaves_others(self) -> None:
        """Disconnecting one connection doesn't affect siblings."""
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-1", ws2)
        mgr.disconnect("session-1", ws1)

        assert mgr.get_connection_count("session-1") == 1

    @pytest.mark.asyncio
    async def test_session_removed_when_last_connection_leaves(self) -> None:
        """Session key is cleaned up when all connections disconnect."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect("session-1", ws)
        mgr.disconnect("session-1", ws)

        assert "session-1" not in mgr._connections


class TestSendAndBroadcast:
    """send_json and broadcast operations."""

    @pytest.mark.asyncio
    async def test_send_json_to_specific_connection(self) -> None:
        """send_json sends data to one specific connection."""
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect("session-1", ws)

        data = {"type": "chunk", "content": "hello"}
        await mgr.send_json("session-1", ws, data)

        ws.send_json.assert_awaited_once_with(data)

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self) -> None:
        """broadcast sends data to all connections in a session."""
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-1", ws2)

        data = {"type": "done", "message_id": "abc"}
        await mgr.broadcast("session-1", data)

        ws1.send_json.assert_awaited_once_with(data)
        ws2.send_json.assert_awaited_once_with(data)

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_session_is_safe(self) -> None:
        """Broadcasting to a session with no connections doesn't raise."""
        mgr = ConnectionManager()
        await mgr.broadcast("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_failed_send_disconnects_connection(self) -> None:
        """If send_json fails, the connection is cleaned up."""
        mgr = ConnectionManager()
        ws = _make_ws(fail_on_send=True)
        await mgr.connect("session-1", ws)

        await mgr.send_json("session-1", ws, {"type": "test"})

        # Connection should be removed after failure
        assert mgr.get_connection_count("session-1") == 0

    @pytest.mark.asyncio
    async def test_broadcast_cleans_up_failed_connections(self) -> None:
        """Broadcast removes dead connections but delivers to live ones."""
        mgr = ConnectionManager()
        live_ws = _make_ws()
        dead_ws = _make_ws(fail_on_send=True)
        await mgr.connect("session-1", live_ws)
        await mgr.connect("session-1", dead_ws)

        data = {"type": "chunk", "content": "test"}
        await mgr.broadcast("session-1", data)

        live_ws.send_json.assert_awaited_once_with(data)
        assert mgr.get_connection_count("session-1") == 1


class TestSessionTracking:
    """Active session listing and connection counting."""

    @pytest.mark.asyncio
    async def test_get_active_sessions(self) -> None:
        """get_active_sessions returns all sessions with connections."""
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect("session-a", ws1)
        await mgr.connect("session-b", ws2)

        sessions = mgr.get_active_sessions()
        assert set(sessions) == {"session-a", "session-b"}

    @pytest.mark.asyncio
    async def test_get_active_sessions_empty(self) -> None:
        """No active sessions when nothing is connected."""
        mgr = ConnectionManager()
        assert mgr.get_active_sessions() == []

    @pytest.mark.asyncio
    async def test_connection_count_for_unknown_session(self) -> None:
        """Connection count for unknown session is 0."""
        mgr = ConnectionManager()
        assert mgr.get_connection_count("unknown") == 0


class TestMultiSessionIsolation:
    """Messages don't leak between sessions."""

    @pytest.mark.asyncio
    async def test_broadcast_only_targets_correct_session(self) -> None:
        """Broadcasting to session-1 doesn't affect session-2."""
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-2", ws2)

        await mgr.broadcast("session-1", {"type": "test"})

        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_from_one_session_doesnt_affect_other(self) -> None:
        """Disconnecting from session-1 doesn't remove session-2 connections."""
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect("session-1", ws1)
        await mgr.connect("session-2", ws2)
        mgr.disconnect("session-1", ws1)

        assert mgr.get_connection_count("session-1") == 0
        assert mgr.get_connection_count("session-2") == 1
