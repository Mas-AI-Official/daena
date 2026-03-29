"""Tests for Session Sync -- cross-device session persistence."""

from __future__ import annotations

import time
import pytest

from app.services.session.session_sync import (
    DeviceRecord,
    PersistentSession,
    SessionSyncService,
)


def _desktop() -> DeviceRecord:
    return DeviceRecord(
        device_id="desktop-1",
        device_type="desktop",
        platform="windows",
        capabilities=["browser", "file_system", "gpu"],
    )


def _mobile() -> DeviceRecord:
    return DeviceRecord(
        device_id="mobile-1",
        device_type="mobile",
        platform="ios",
        capabilities=["browser"],
    )


@pytest.fixture
def svc() -> SessionSyncService:
    return SessionSyncService()


class TestCreateAndJoin:
    def test_create_session(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        assert session.session_id
        assert session.user_id == "user-1"
        assert len(session.devices) == 1
        assert session.primary_device_id == "desktop-1"

    def test_join_session(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        result = svc.join_session(session.session_id, _mobile())
        assert result is not None
        assert len(result.devices) == 2

    def test_join_nonexistent_returns_none(self, svc: SessionSyncService):
        assert svc.join_session("nonexistent", _mobile()) is None

    def test_join_updates_existing_device(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        updated = DeviceRecord(device_id="desktop-1", capabilities=["browser", "gpu", "file_system", "terminal"])
        svc.join_session(session.session_id, updated)
        state = svc.sync_state(session.session_id)
        assert len(state.devices) == 1  # same device, not duplicated


class TestSync:
    def test_sync_state(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        state = svc.sync_state(session.session_id)
        assert state is not None
        assert state.session_id == session.session_id

    def test_sync_nonexistent(self, svc: SessionSyncService):
        assert svc.sync_state("nonexistent") is None


class TestTransfer:
    def test_transfer_primary(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        svc.join_session(session.session_id, _mobile())
        assert svc.transfer_primary(session.session_id, "mobile-1") is True
        state = svc.sync_state(session.session_id)
        assert state.primary_device_id == "mobile-1"

    def test_transfer_to_unknown_device_fails(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        assert svc.transfer_primary(session.session_id, "nonexistent") is False


class TestToolsAndState:
    def test_update_tools(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        svc.update_tools(session.session_id, ["terminal", "github", "slack"])
        state = svc.sync_state(session.session_id)
        assert state.active_tools == ["terminal", "github", "slack"]

    def test_update_agent_state(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        svc.update_agent_state(session.session_id, {"context": "researching", "step": 3})
        state = svc.sync_state(session.session_id)
        assert state.agent_state["step"] == 3


class TestSerialization:
    def test_serialize_for_mobile(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        svc.update_tools(session.session_id, ["terminal", "file_system"])
        svc.update_agent_state(session.session_id, {"big_data": "x" * 500})

        mobile_view = svc.serialize_for_device(session.session_id, "mobile")
        assert mobile_view is not None
        assert "agent_state" not in mobile_view  # full state not sent to mobile
        assert "agent_state_summary" in mobile_view
        assert mobile_view["requires_desktop"] is True  # file_system needs desktop

    def test_serialize_for_desktop(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        svc.update_agent_state(session.session_id, {"context": "full"})

        desktop_view = svc.serialize_for_device(session.session_id, "desktop")
        assert desktop_view is not None
        assert "agent_state" in desktop_view
        assert "devices" in desktop_view

    def test_serialize_nonexistent(self, svc: SessionSyncService):
        assert svc.serialize_for_device("nope", "mobile") is None


class TestCleanup:
    def test_cleanup_stale(self, svc: SessionSyncService):
        session = svc.create_session("user-1", _desktop())
        # Force session to be old
        session.last_active_at = time.time() - 100000
        removed = svc.cleanup_stale(max_age_seconds=1)
        assert removed == 1

    def test_get_user_sessions(self, svc: SessionSyncService):
        svc.create_session("user-1", _desktop())
        svc.create_session("user-1", _mobile())
        svc.create_session("user-2", _desktop())
        sessions = svc.get_user_sessions("user-1")
        assert len(sessions) == 2
