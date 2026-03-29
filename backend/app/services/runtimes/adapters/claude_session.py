"""Persistent Claude Code session manager.

Maintains stateful sessions across multiple task invocations using
the Claude CLI's --resume flag. Each Daena chat session maps to a
Claude Code CLI session, preserving context between commands.

Architecture:
    DaenaChatSession -> ClaudeSession -> claude -p "task" --resume <id>

    First task: claude -p "task" --output-format json -> captures session_id
    Follow-ups: claude -p "task" --resume <session_id> --output-format json
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _run_claude(
    cmd: list[str],
    *,
    cwd: str | None = None,
    timeout: float = 300.0,
) -> subprocess.CompletedProcess[str]:
    """Run claude command synchronously (called from thread pool)."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


@dataclass
class ClaudeSessionResult:
    """Result of a single command in a Claude session."""

    result_text: str
    session_id: str
    is_error: bool = False
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    raw_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaudeSession:
    """A persistent Claude Code CLI session.

    Tracks the CLI session_id so follow-up commands can use --resume
    to maintain full conversation context.
    """

    daena_session_id: str  # Maps to Daena's chat session
    cli_session_id: str | None = None  # Claude CLI session ID (set after first command)
    claude_bin: str = "claude"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime | None = None
    command_count: int = 0
    total_cost_usd: float = 0.0
    is_alive: bool = True
    history: list[ClaudeSessionResult] = field(default_factory=list)

    async def send_command(
        self,
        task: str,
        *,
        cwd: str = ".",
        timeout: float = 300.0,
    ) -> ClaudeSessionResult:
        """Send a command to this session.

        First command creates the session. Subsequent commands resume it.
        """
        cmd = [
            self.claude_bin, "-p", task,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        # Resume existing session if we have a CLI session ID
        if self.cli_session_id:
            cmd.extend(["--resume", self.cli_session_id])

        logger.info(
            "claude_session.send",
            daena_session=self.daena_session_id,
            cli_session=self.cli_session_id or "new",
            task=task[:200],
            command_num=self.command_count + 1,
        )

        try:
            proc_result = await asyncio.to_thread(
                _run_claude, cmd, cwd=cwd, timeout=timeout,
            )

            # Parse the JSON result (may be multiple lines, take last result type)
            result = self._parse_output(proc_result.stdout)

            # Capture CLI session ID from first response
            if result.session_id and not self.cli_session_id:
                self.cli_session_id = result.session_id
                logger.info(
                    "claude_session.established",
                    daena_session=self.daena_session_id,
                    cli_session=self.cli_session_id,
                )

            self.command_count += 1
            self.last_used = datetime.utcnow()
            self.total_cost_usd += result.cost_usd
            self.history.append(result)

            return result

        except subprocess.TimeoutExpired:
            self.is_alive = False
            return ClaudeSessionResult(
                result_text="[Session timed out]",
                session_id=self.cli_session_id or "",
                is_error=True,
                duration_ms=int(timeout * 1000),
            )
        except Exception as exc:
            logger.error(
                "claude_session.error",
                daena_session=self.daena_session_id,
                error=str(exc),
            )
            return ClaudeSessionResult(
                result_text=f"[Session error: {exc}]",
                session_id=self.cli_session_id or "",
                is_error=True,
            )

    def _parse_output(self, stdout: str) -> ClaudeSessionResult:
        """Parse Claude CLI JSON output, extracting the result line."""
        lines = stdout.strip().splitlines()

        # Find the result JSON (type=result) -- scan from end
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if data.get("type") == "result":
                    return ClaudeSessionResult(
                        result_text=data.get("result", ""),
                        session_id=data.get("session_id", ""),
                        is_error=data.get("is_error", False),
                        cost_usd=data.get("total_cost_usd", 0),
                        duration_ms=data.get("duration_ms", 0),
                        num_turns=data.get("num_turns", 0),
                        raw_json=data,
                    )
            except json.JSONDecodeError:
                continue

        # Fallback: return raw output
        return ClaudeSessionResult(
            result_text=stdout.strip()[:4000] if stdout.strip() else "[No output]",
            session_id="",
            is_error=True,
        )

    def get_status(self) -> dict[str, Any]:
        """Get session status for API/frontend."""
        return {
            "daena_session_id": self.daena_session_id,
            "cli_session_id": self.cli_session_id,
            "is_alive": self.is_alive,
            "command_count": self.command_count,
            "total_cost_usd": self.total_cost_usd,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


class ClaudeSessionManager:
    """Manages multiple persistent Claude sessions.

    Maps Daena chat sessions to Claude CLI sessions. Handles
    session lifecycle, error recovery, and cleanup.
    """

    def __init__(self, claude_bin: str = "claude") -> None:
        self._sessions: dict[str, ClaudeSession] = {}
        self._claude_bin = claude_bin

    def get_or_create(self, daena_session_id: str) -> ClaudeSession:
        """Get existing session or create a new one."""
        if daena_session_id not in self._sessions:
            self._sessions[daena_session_id] = ClaudeSession(
                daena_session_id=daena_session_id,
                claude_bin=self._claude_bin,
            )
            logger.info(
                "session_manager.created",
                daena_session=daena_session_id,
            )
        return self._sessions[daena_session_id]

    def get(self, daena_session_id: str) -> ClaudeSession | None:
        """Get session if it exists."""
        return self._sessions.get(daena_session_id)

    async def send(
        self,
        daena_session_id: str,
        task: str,
        *,
        cwd: str = ".",
        timeout: float = 300.0,
    ) -> ClaudeSessionResult:
        """Send a command to a session (creating if needed).

        If the session died, automatically restarts it.
        """
        session = self.get_or_create(daena_session_id)

        # Error recovery: if session died, restart it
        if not session.is_alive:
            logger.warning(
                "session_manager.recovering",
                daena_session=daena_session_id,
                old_cli_session=session.cli_session_id,
            )
            # Create fresh session but keep history
            old_history = session.history
            session = ClaudeSession(
                daena_session_id=daena_session_id,
                claude_bin=self._claude_bin,
            )
            session.history = old_history
            self._sessions[daena_session_id] = session

        return await session.send_command(task, cwd=cwd, timeout=timeout)

    def end_session(self, daena_session_id: str) -> bool:
        """End and remove a session."""
        if daena_session_id in self._sessions:
            session = self._sessions.pop(daena_session_id)
            session.is_alive = False
            logger.info(
                "session_manager.ended",
                daena_session=daena_session_id,
                commands=session.command_count,
                cost=session.total_cost_usd,
            )
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [s.get_status() for s in self._sessions.values()]

    def cleanup_stale(self, max_age_hours: int = 24) -> int:
        """Remove sessions that haven't been used recently."""
        now = datetime.utcnow()
        stale = []
        for sid, session in self._sessions.items():
            age = now - session.created_at
            if age.total_seconds() > max_age_hours * 3600:
                stale.append(sid)

        for sid in stale:
            self.end_session(sid)

        return len(stale)
