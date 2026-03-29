"""Tests for Remote Gateway -- command queue, auth, rate limiting."""

from __future__ import annotations

import time
import pytest

from app.services.remote.gateway import (
    CommandResult,
    CommandStatus,
    RemoteCommand,
    RemoteGateway,
)


@pytest.fixture
def gw() -> RemoteGateway:
    return RemoteGateway(max_queue_size=10, rate_limit_per_minute=5)


class TestEnqueue:
    def test_enqueue_returns_id(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="check status", device_id="d1")
        cmd_id = gw.enqueue(cmd)
        assert cmd_id == cmd.id

    def test_enqueue_creates_result(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="test", device_id="d1")
        cmd_id = gw.enqueue(cmd)
        result = gw.get_result(cmd_id)
        assert result is not None
        assert result.status == CommandStatus.QUEUED


class TestExecution:
    def test_get_next_command(self, gw: RemoteGateway):
        gw.enqueue(RemoteCommand(command="task 1", device_id="d1"))
        cmd = gw.get_next_command()
        assert cmd is not None
        assert cmd.command == "task 1"

    def test_get_next_marks_executing(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="task", device_id="d1")
        gw.enqueue(cmd)
        gw.get_next_command()
        result = gw.get_result(cmd.id)
        assert result.status == CommandStatus.EXECUTING

    def test_complete_command(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="task", device_id="d1")
        gw.enqueue(cmd)
        gw.get_next_command()
        gw.complete_command(cmd.id, result={"output": "done"})
        result = gw.get_result(cmd.id)
        assert result.status == CommandStatus.COMPLETED
        assert result.result == {"output": "done"}

    def test_failed_command(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="bad task", device_id="d1")
        gw.enqueue(cmd)
        gw.get_next_command()
        gw.complete_command(cmd.id, error="Something went wrong")
        result = gw.get_result(cmd.id)
        assert result.status == CommandStatus.FAILED
        assert "wrong" in result.error

    def test_timeout_command(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="slow task", device_id="d1")
        gw.enqueue(cmd)
        gw.timeout_command(cmd.id)
        result = gw.get_result(cmd.id)
        assert result.status == CommandStatus.TIMEOUT


class TestPriorityQueue:
    def test_p0_dequeued_first(self, gw: RemoteGateway):
        gw.enqueue(RemoteCommand(command="p2 task", priority="P2", device_id="d1"))
        gw.enqueue(RemoteCommand(command="p0 task", priority="P0", device_id="d1"))
        gw.enqueue(RemoteCommand(command="p1 task", priority="P1", device_id="d1"))
        cmd = gw.get_next_command()
        assert cmd.priority == "P0"


class TestRateLimit:
    def test_rate_limit_enforced(self, gw: RemoteGateway):
        # Limit is 5 per minute
        for i in range(5):
            gw.enqueue(RemoteCommand(command=f"cmd {i}", device_id="d1"))
        with pytest.raises(ValueError, match="Rate limit"):
            gw.enqueue(RemoteCommand(command="one too many", device_id="d1"))

    def test_different_devices_independent(self, gw: RemoteGateway):
        for i in range(5):
            gw.enqueue(RemoteCommand(command=f"cmd {i}", device_id="d1"))
        # d2 should still work
        gw.enqueue(RemoteCommand(command="d2 cmd", device_id="d2"))


class TestAuth:
    def test_valid_auth(self, gw: RemoteGateway):
        assert gw.validate_auth("valid-token", "device-fp") is True

    def test_empty_token_rejected(self, gw: RemoteGateway):
        assert gw.validate_auth("", "device-fp") is False

    def test_empty_fingerprint_rejected(self, gw: RemoteGateway):
        assert gw.validate_auth("token", "") is False


class TestTunnel:
    def test_set_and_get_tunnel_url(self, gw: RemoteGateway):
        gw.set_tunnel_url("https://daena-remote.trycloudflare.com")
        assert gw.get_tunnel_url() == "https://daena-remote.trycloudflare.com"


class TestStayAwakeIntegration:
    def test_awake_hook_called_on_enqueue(self, gw: RemoteGateway):
        called = []
        gw.set_awake_hooks(
            on_awake=lambda: called.append("awake"),
            on_idle=lambda: called.append("idle"),
        )
        gw.enqueue(RemoteCommand(command="test", device_id="d1"))
        assert "awake" in called

    def test_idle_hook_called_when_done(self, gw: RemoteGateway):
        called = []
        gw.set_awake_hooks(
            on_awake=lambda: called.append("awake"),
            on_idle=lambda: called.append("idle"),
        )
        cmd = RemoteCommand(command="test", device_id="d1")
        gw.enqueue(cmd)
        gw.get_next_command()
        gw.complete_command(cmd.id, result="ok")
        assert "idle" in called


class TestQueueStatus:
    def test_status_counts(self, gw: RemoteGateway):
        gw.enqueue(RemoteCommand(command="a", device_id="d1"))
        gw.enqueue(RemoteCommand(command="b", device_id="d1"))
        status = gw.get_queue_status()
        assert status["queue_size"] == 2
        assert status["pending"] == 2


class TestCleanup:
    def test_clear_old_results(self, gw: RemoteGateway):
        cmd = RemoteCommand(command="old", device_id="d1")
        gw.enqueue(cmd)
        gw.get_next_command()
        gw.complete_command(cmd.id, result="done")
        # Force old timestamp
        gw._results[cmd.id].completed_at = time.time() - 7200
        removed = gw.clear_results(max_age_seconds=3600)
        assert removed == 1
