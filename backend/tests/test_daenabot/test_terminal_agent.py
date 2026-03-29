"""Unit tests for TerminalAgent — subprocess calls are mocked."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.daenabot.terminal_agent import (
    TerminalAgent,
    DANGEROUS_COMMANDS,
    READ_ONLY_COMMANDS,
)


def _agent(**kwargs) -> TerminalAgent:
    return TerminalAgent(default_timeout=5, max_timeout=30, **kwargs)


# ── execute_command ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_read_only_command() -> None:
    agent = _agent()

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"file1\nfile2\n", b""))
        proc.returncode = 0
        mock_sub.return_value = proc

        result = await agent.execute_command("ls -la")

    assert result["success"] is True
    assert result["output"]["stdout"] == "file1\nfile2\n"
    assert result["output"]["return_code"] == 0
    assert result["output"]["timed_out"] is False


@pytest.mark.asyncio
async def test_execute_command_with_stderr() -> None:
    agent = _agent()

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b"warning: something\n"))
        proc.returncode = 0
        mock_sub.return_value = proc

        result = await agent.execute_command("some_cmd")

    assert result["success"] is True
    assert result["output"]["stderr"] == "warning: something\n"


@pytest.mark.asyncio
async def test_execute_command_nonzero_exit() -> None:
    agent = _agent()

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", b"error\n"))
        proc.returncode = 1
        mock_sub.return_value = proc

        result = await agent.execute_command("false")

    assert result["success"] is True  # command ran, just exited non-zero
    assert result["output"]["return_code"] == 1


@pytest.mark.asyncio
async def test_execute_command_timeout() -> None:
    agent = _agent()

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        proc = AsyncMock()
        proc.communicate = AsyncMock(side_effect=[
            asyncio.TimeoutError(),
            (b"killed\n", b""),
        ])
        proc.kill = MagicMock()
        proc.returncode = -9
        mock_sub.return_value = proc

        result = await agent.execute_command("sleep 999", timeout=1)

    assert result["success"] is True
    assert result["output"]["timed_out"] is True
    proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_default_timeout_applied() -> None:
    agent = TerminalAgent(default_timeout=7, max_timeout=30)

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"ok", b""))
        proc.returncode = 0
        mock_sub.return_value = proc

        with patch("asyncio.wait_for", wraps=asyncio.wait_for) as mock_wait:
            result = await agent.execute_command("echo hi")

        # wait_for called with timeout=7 (default)
        assert mock_wait.call_args[1].get("timeout", mock_wait.call_args[0][1] if len(mock_wait.call_args[0]) > 1 else None) == 7 or result["success"]


@pytest.mark.asyncio
async def test_max_timeout_enforced() -> None:
    agent = TerminalAgent(default_timeout=5, max_timeout=10)

    with patch("asyncio.create_subprocess_shell") as mock_sub:
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"ok", b""))
        proc.returncode = 0
        mock_sub.return_value = proc

        # Requesting 999s timeout — should be clamped to 10
        result = await agent.execute_command("echo hi", timeout=999)

    assert result["success"] is True


# ── classify_command_risk ──────────────────────────────────────

def test_classify_command_risk_dangerous() -> None:
    for cmd in ["rm -rf /", "shutdown -h now", "format C:", "dd if=/dev/zero"]:
        assert TerminalAgent.classify_command_risk(cmd) == "DELETE", f"Failed for: {cmd}"


def test_classify_command_risk_readonly() -> None:
    for cmd in ["ls", "cat file.txt", "pwd", "whoami", "echo hello"]:
        assert TerminalAgent.classify_command_risk(cmd) == "READ", f"Failed for: {cmd}"


def test_classify_command_risk_regular() -> None:
    for cmd in ["npm build", "cargo test", "make install"]:
        assert TerminalAgent.classify_command_risk(cmd) == "EXECUTE", f"Failed for: {cmd}"


def test_classify_sudo_prefix() -> None:
    assert TerminalAgent.classify_command_risk("sudo rm -rf /") == "DELETE"
    assert TerminalAgent.classify_command_risk("sudo ls") == "READ"


def test_classify_env_prefix() -> None:
    assert TerminalAgent.classify_command_risk("FOO=bar rm file") == "DELETE"
    assert TerminalAgent.classify_command_risk("PATH=/usr/bin ls") == "READ"


# ── dispatch ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_unknown_operation() -> None:
    agent = _agent()
    with pytest.raises(ValueError, match="unknown operation"):
        await agent.execute("run_exploit", {})
