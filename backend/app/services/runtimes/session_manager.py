"""Session Manager: persistent session state per runtime.

Tracks active sessions (running tasks) across runtimes, enabling
cancellation, timeout management, and resource cleanup. Each session
maps to a subprocess handle that can be monitored or killed.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RuntimeSession:
    """Tracks one active runtime execution."""
    session_id: str
    runtime_id: str
    task: str
    process: asyncio.subprocess.Process | None = None
    start_time: float = field(default_factory=time.monotonic)
    timeout_seconds: float = 300.0  # 5 minute default
    cancelled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.start_time) * 1000)

    @property
    def is_timed_out(self) -> bool:
        return (time.monotonic() - self.start_time) > self.timeout_seconds


class SessionManager:
    """Manages active runtime sessions across all adapters.

    Usage::

        manager = SessionManager()
        session = manager.create("sess_123", "claude_code", "fix the bug")
        session.process = subprocess_handle

        # Later:
        await manager.cancel("sess_123")
        manager.remove("sess_123")
    """

    def __init__(self, default_timeout: float = 300.0) -> None:
        self._sessions: dict[str, RuntimeSession] = {}
        self._default_timeout = default_timeout

    def create(
        self,
        session_id: str,
        runtime_id: str,
        task: str,
        timeout: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeSession:
        """Create and register a new session."""
        session = RuntimeSession(
            session_id=session_id,
            runtime_id=runtime_id,
            task=task,
            timeout_seconds=timeout or self._default_timeout,
            metadata=metadata or {},
        )
        self._sessions[session_id] = session
        logger.info(
            "runtime_session.created",
            session_id=session_id,
            runtime_id=runtime_id,
        )
        return session

    def get(self, session_id: str) -> RuntimeSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        """Remove a completed session."""
        self._sessions.pop(session_id, None)

    async def cancel(self, session_id: str) -> bool:
        """Cancel a running session by killing its subprocess."""
        session = self._sessions.get(session_id)
        if session is None:
            return False

        session.cancelled = True
        if session.process is not None and session.process.returncode is None:
            try:
                session.process.terminate()
                # Give it 3 seconds to terminate gracefully
                try:
                    await asyncio.wait_for(session.process.wait(), timeout=3.0)
                except TimeoutError:
                    session.process.kill()
                    await session.process.wait()
            except ProcessLookupError:
                pass  # already dead
            logger.info(
                "runtime_session.cancelled",
                session_id=session_id,
                runtime_id=session.runtime_id,
                elapsed_ms=session.elapsed_ms,
            )
        return True

    async def cancel_all_for_runtime(self, runtime_id: str) -> int:
        """Cancel all sessions for a specific runtime."""
        count = 0
        for sid, session in list(self._sessions.items()):
            if session.runtime_id == runtime_id:
                await self.cancel(sid)
                count += 1
        return count

    async def cleanup_timed_out(self) -> list[str]:
        """Find and cancel timed-out sessions. Returns cancelled IDs."""
        timed_out = [
            sid for sid, s in self._sessions.items()
            if s.is_timed_out and not s.cancelled
        ]
        for sid in timed_out:
            await self.cancel(sid)
            logger.warning(
                "runtime_session.timed_out",
                session_id=sid,
                runtime_id=self._sessions[sid].runtime_id,
                elapsed_ms=self._sessions[sid].elapsed_ms,
            )
        return timed_out

    @property
    def active_count(self) -> int:
        """Number of currently active sessions."""
        return len(self._sessions)

    def active_for_runtime(self, runtime_id: str) -> int:
        """Count active sessions for a specific runtime."""
        return sum(
            1 for s in self._sessions.values()
            if s.runtime_id == runtime_id and not s.cancelled
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/monitoring."""
        return {
            "active_sessions": self.active_count,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "runtime_id": s.runtime_id,
                    "task": s.task[:100],
                    "elapsed_ms": s.elapsed_ms,
                    "timed_out": s.is_timed_out,
                    "cancelled": s.cancelled,
                }
                for s in self._sessions.values()
            ],
        }
