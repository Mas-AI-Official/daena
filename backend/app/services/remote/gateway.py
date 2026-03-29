"""Remote Gateway -- enables command execution from mobile/remote devices.

Architecture:
    Phone (Claude App / Browser)
        |
        | HTTPS to public endpoint (Cloudflare Tunnel)
        v
    Remote Gateway (on home desktop)
        | auth + rate limit + queue
        v
    Daena Core (Orchestra -> TLM -> Agent)
        | results
        v
    Stream back via SSE
"""

from __future__ import annotations

import asyncio
import time
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable


class CommandStatus(str, Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class RemoteCommand:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "browser"  # "claude_app" | "browser" | "api" | "cli"
    command: str = ""
    priority: str = "P1"
    max_execution_seconds: int = 300
    stream_results: bool = True
    user_id: str = ""
    device_id: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class CommandResult:
    command_id: str
    status: CommandStatus = CommandStatus.QUEUED
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    execution_seconds: float = 0.0


class RemoteGateway:
    """Manages remote command execution via secure tunnel.

    Usage:
        gw = RemoteGateway()
        cmd_id = gw.enqueue(RemoteCommand(command="check system status"))
        result = gw.get_result(cmd_id)
    """

    def __init__(
        self,
        max_queue_size: int = 100,
        rate_limit_per_minute: int = 60,
    ) -> None:
        self._queue: deque[RemoteCommand] = deque(maxlen=max_queue_size)
        self._results: dict[str, CommandResult] = {}
        self._lock = threading.Lock()
        self._rate_limit = rate_limit_per_minute
        self._request_log: dict[str, list[float]] = {}  # device_id -> timestamps
        self._tunnel_url: str | None = None
        self._executor: Callable[[str], Awaitable[dict]] | None = None
        self._on_awake: Callable[[], None] | None = None
        self._on_idle: Callable[[], None] | None = None

    # ── Command Queue ─────────────────────────────────────────

    def enqueue(self, command: RemoteCommand) -> str:
        """Add a command to the execution queue. Returns command ID."""
        with self._lock:
            # Rate limiting
            if not self._check_rate_limit(command.device_id):
                raise ValueError("Rate limit exceeded (60/min)")

            self._queue.append(command)
            self._results[command.id] = CommandResult(
                command_id=command.id,
                status=CommandStatus.QUEUED,
            )

            # Trigger stay-awake
            if self._on_awake:
                self._on_awake()

            return command.id

    def get_result(self, command_id: str) -> CommandResult | None:
        """Get the result of a queued/executed command."""
        with self._lock:
            return self._results.get(command_id)

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue state."""
        with self._lock:
            return {
                "queue_size": len(self._queue),
                "pending": sum(
                    1 for r in self._results.values()
                    if r.status == CommandStatus.QUEUED
                ),
                "executing": sum(
                    1 for r in self._results.values()
                    if r.status == CommandStatus.EXECUTING
                ),
                "completed": sum(
                    1 for r in self._results.values()
                    if r.status == CommandStatus.COMPLETED
                ),
                "tunnel_url": self._tunnel_url,
            }

    def get_next_command(self) -> RemoteCommand | None:
        """Pop the next command from the queue (priority-ordered)."""
        with self._lock:
            if not self._queue:
                return None
            # Sort by priority: P0 first
            priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
            items = list(self._queue)
            items.sort(key=lambda c: priority_order.get(c.priority, 9))
            cmd = items[0]
            self._queue.remove(cmd)
            self._results[cmd.id].status = CommandStatus.EXECUTING
            self._results[cmd.id].started_at = time.time()
            return cmd

    def complete_command(
        self,
        command_id: str,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        """Mark a command as completed or failed."""
        with self._lock:
            cr = self._results.get(command_id)
            if not cr:
                return
            cr.completed_at = time.time()
            if cr.started_at:
                cr.execution_seconds = cr.completed_at - cr.started_at
            if error:
                cr.status = CommandStatus.FAILED
                cr.error = error
            else:
                cr.status = CommandStatus.COMPLETED
                cr.result = result

            # Check if queue is empty -> allow idle
            if not self._queue and self._on_idle:
                all_done = all(
                    r.status in (CommandStatus.COMPLETED, CommandStatus.FAILED, CommandStatus.TIMEOUT)
                    for r in self._results.values()
                )
                if all_done:
                    self._on_idle()

    def timeout_command(self, command_id: str) -> None:
        """Mark a command as timed out."""
        with self._lock:
            cr = self._results.get(command_id)
            if cr:
                cr.status = CommandStatus.TIMEOUT
                cr.completed_at = time.time()
                cr.error = "Execution timeout exceeded"

    # ── Tunnel Management ─────────────────────────────────────

    def set_tunnel_url(self, url: str) -> None:
        """Set the public tunnel URL (from cloudflared/ngrok)."""
        self._tunnel_url = url

    def get_tunnel_url(self) -> str | None:
        return self._tunnel_url

    # ── Integration Hooks ─────────────────────────────────────

    def set_executor(self, executor: Callable[[str], Awaitable[dict]]) -> None:
        """Set the function that executes commands on local Daena."""
        self._executor = executor

    def set_awake_hooks(
        self,
        on_awake: Callable[[], None],
        on_idle: Callable[[], None],
    ) -> None:
        """Connect to StayAwakeService."""
        self._on_awake = on_awake
        self._on_idle = on_idle

    # ── Rate Limiting ─────────────────────────────────────────

    def _check_rate_limit(self, device_id: str) -> bool:
        """Check if device is within rate limit. Must hold lock."""
        now = time.time()
        window = 60.0  # 1 minute window

        if device_id not in self._request_log:
            self._request_log[device_id] = []

        # Clean old entries
        self._request_log[device_id] = [
            t for t in self._request_log[device_id]
            if now - t < window
        ]

        if len(self._request_log[device_id]) >= self._rate_limit:
            return False

        self._request_log[device_id].append(now)
        return True

    def validate_auth(self, token: str, device_fingerprint: str) -> bool:
        """Validate remote authentication. Placeholder for JWT + device check."""
        # In production: validate JWT + check device fingerprint
        return bool(token and device_fingerprint)

    # ── Cleanup ───────────────────────────────────────────────

    def clear_results(self, max_age_seconds: float = 3600) -> int:
        """Remove old results. Returns count removed."""
        cutoff = time.time() - max_age_seconds
        removed = 0
        with self._lock:
            to_remove = [
                cid for cid, cr in self._results.items()
                if cr.completed_at and cr.completed_at < cutoff
            ]
            for cid in to_remove:
                del self._results[cid]
                removed += 1
        return removed

    def clear_all(self) -> None:
        with self._lock:
            self._queue.clear()
            self._results.clear()
            self._request_log.clear()
