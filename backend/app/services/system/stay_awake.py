"""Stay-Awake System -- prevents Windows from sleeping during active operations.

Three modes:
    TASK: Keep awake while any agent task is running
    SESSION: Keep awake while any user session is active
    SCHEDULED: Keep awake during configured hours

Uses SetThreadExecutionState on Windows. On non-Windows, uses a no-op fallback.
Safety cap: never keeps system awake more than max_awake_minutes.
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class AwakeMode(str, Enum):
    TASK = "task"
    SESSION = "session"
    SCHEDULED = "scheduled"


@dataclass
class StayAwakeConfig:
    mode: AwakeMode = AwakeMode.TASK
    scheduled_start_hour: int = 9   # 9am
    scheduled_end_hour: int = 23    # 11pm
    max_awake_minutes: int = 480    # 8 hours safety cap
    cooldown_seconds: int = 300     # 5 min cooldown after last task
    notify_on_sleep: bool = True


@dataclass
class AwakeStatus:
    awake: bool = False
    mode: AwakeMode = AwakeMode.TASK
    minutes_remaining: float = 0.0
    active_tasks: int = 0
    awake_since: float | None = None
    total_awake_minutes: float = 0.0


class StayAwakeService:
    """Manages system sleep prevention for active Daena operations.

    Usage:
        svc = StayAwakeService(config)
        svc.on_task_start("task-123")  # prevents sleep
        svc.on_task_end("task-123")    # starts cooldown
        # After cooldown with no new tasks -> releases
    """

    def __init__(self, config: StayAwakeConfig | None = None) -> None:
        self.config = config or StayAwakeConfig()
        self._awake = False
        self._awake_since: float | None = None
        self._active_tasks: set[str] = set()
        self._cooldown_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._is_windows = platform.system() == "Windows"
        self._notify_callback: Callable[[str], None] | None = None
        self._max_timer: threading.Timer | None = None

    # ── Core Control ──────────────────────────────────────────

    def start_keep_awake(self, reason: str = "manual") -> bool:
        """Activate keep-awake. Returns True if state changed."""
        with self._lock:
            if self._awake:
                return False
            self._awake = True
            self._awake_since = time.time()
            self._cancel_cooldown()
            self._set_safety_timer()
            self._execute_awake_command(True)
            return True

    def stop_keep_awake(self, reason: str = "manual") -> bool:
        """Deactivate keep-awake. Returns True if state changed."""
        with self._lock:
            if not self._awake:
                return False
            self._awake = False
            self._cancel_cooldown()
            self._cancel_safety_timer()
            self._execute_awake_command(False)
            if self.config.notify_on_sleep and self._notify_callback:
                self._notify_callback("System entering sleep-allowed state")
            return True

    def get_status(self) -> AwakeStatus:
        """Get current stay-awake status."""
        with self._lock:
            minutes_remaining = 0.0
            total_minutes = 0.0
            if self._awake and self._awake_since:
                elapsed = (time.time() - self._awake_since) / 60
                total_minutes = elapsed
                minutes_remaining = max(0, self.config.max_awake_minutes - elapsed)

            return AwakeStatus(
                awake=self._awake,
                mode=self.config.mode,
                minutes_remaining=round(minutes_remaining, 1),
                active_tasks=len(self._active_tasks),
                awake_since=self._awake_since,
                total_awake_minutes=round(total_minutes, 1),
            )

    # ── Task Lifecycle Hooks ──────────────────────────────────

    def on_task_start(self, task_id: str) -> None:
        """Called when an agent task starts. Prevents sleep if mode=TASK."""
        with self._lock:
            self._active_tasks.add(task_id)
            self._cancel_cooldown()
            if self.config.mode == AwakeMode.TASK and not self._awake:
                self._awake = True
                self._awake_since = time.time()
                self._set_safety_timer()
                self._execute_awake_command(True)

    def on_task_end(self, task_id: str) -> None:
        """Called when an agent task ends. Starts cooldown if no more tasks."""
        with self._lock:
            self._active_tasks.discard(task_id)
            if self.config.mode == AwakeMode.TASK and not self._active_tasks:
                self._start_cooldown()

    def on_all_tasks_complete(self) -> None:
        """Called when all tasks are done. Immediate release (no cooldown)."""
        with self._lock:
            self._active_tasks.clear()
            if self._awake:
                self._awake = False
                self._cancel_cooldown()
                self._cancel_safety_timer()
                self._execute_awake_command(False)

    # ── Session Lifecycle Hooks ───────────────────────────────

    def on_session_start(self, session_id: str) -> None:
        """Keep awake while sessions exist (mode=SESSION)."""
        if self.config.mode == AwakeMode.SESSION:
            self.on_task_start(f"session:{session_id}")

    def on_session_end(self, session_id: str) -> None:
        if self.config.mode == AwakeMode.SESSION:
            self.on_task_end(f"session:{session_id}")

    # ── Scheduled Mode ────────────────────────────────────────

    def check_scheduled(self) -> bool:
        """Check if current time is within scheduled awake hours.

        Returns True if system should be awake based on schedule.
        """
        if self.config.mode != AwakeMode.SCHEDULED:
            return False

        import datetime
        now = datetime.datetime.now()
        current_hour = now.hour

        start = self.config.scheduled_start_hour
        end = self.config.scheduled_end_hour

        if start <= end:
            return start <= current_hour < end
        else:
            # Overnight schedule (e.g., 22 to 6)
            return current_hour >= start or current_hour < end

    # ── Notification ──────────────────────────────────────────

    def set_notify_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for sleep notifications."""
        self._notify_callback = callback

    # ── Internal ──────────────────────────────────────────────

    def _execute_awake_command(self, awake: bool) -> None:
        """Execute the platform-specific keep-awake command."""
        if not self._is_windows:
            return  # No-op on non-Windows

        try:
            if awake:
                # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                cmd = (
                    'powershell -NoProfile -Command "'
                    '[System.Runtime.InteropServices.Marshal]::'
                    'SetThreadExecutionState(0x80000003)"'
                )
            else:
                # ES_CONTINUOUS only (clear flags)
                cmd = (
                    'powershell -NoProfile -Command "'
                    '[System.Runtime.InteropServices.Marshal]::'
                    'SetThreadExecutionState(0x80000000)"'
                )
            subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass  # Non-critical: log but don't crash

    def _start_cooldown(self) -> None:
        """Start cooldown timer. Must hold lock."""
        self._cancel_cooldown()
        self._cooldown_timer = threading.Timer(
            self.config.cooldown_seconds,
            self._cooldown_expired,
        )
        self._cooldown_timer.daemon = True
        self._cooldown_timer.start()

    def _cooldown_expired(self) -> None:
        """Cooldown finished: release sleep if no new tasks appeared."""
        with self._lock:
            if not self._active_tasks and self._awake:
                self._awake = False
                self._cancel_safety_timer()
                self._execute_awake_command(False)
                if self.config.notify_on_sleep and self._notify_callback:
                    self._notify_callback("Cooldown expired, allowing sleep")

    def _cancel_cooldown(self) -> None:
        """Cancel pending cooldown timer. Must hold lock."""
        if self._cooldown_timer:
            self._cooldown_timer.cancel()
            self._cooldown_timer = None

    def _set_safety_timer(self) -> None:
        """Set maximum awake timer. Must hold lock."""
        self._cancel_safety_timer()
        self._max_timer = threading.Timer(
            self.config.max_awake_minutes * 60,
            self._safety_cap_reached,
        )
        self._max_timer.daemon = True
        self._max_timer.start()

    def _safety_cap_reached(self) -> None:
        """Safety cap: force release after max_awake_minutes."""
        with self._lock:
            self._awake = False
            self._execute_awake_command(False)
            if self._notify_callback:
                self._notify_callback(
                    f"Safety cap reached ({self.config.max_awake_minutes} min). Allowing sleep."
                )

    def _cancel_safety_timer(self) -> None:
        if self._max_timer:
            self._max_timer.cancel()
            self._max_timer = None
