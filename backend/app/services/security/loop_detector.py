"""LoopDetector -- Ported from OpenClaw's tool-loop-detection.ts.

Prevents infinite tool call loops with 4 detection strategies:
    1. generic_repeat: Same tool+params called N times
    2. known_poll_no_progress: Polling returns identical results N times
    3. global_circuit_breaker: Any tool repeated 30x with no progress
    4. ping_pong: Two tools alternating A->B->A->B with no progress

DAENA ADDITION (not in OpenClaw):
    When a loop is detected, instead of just stopping, we trigger
    the 5 Whys analysis to find root cause and suggest a different approach.
    This is the anti-fragility principle: failures make us smarter.

Port source: openclaw-main/src/agents/tool-loop-detection.ts
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HISTORY_SIZE = 30
WARNING_THRESHOLD = 10
CRITICAL_THRESHOLD = 20
GLOBAL_CIRCUIT_BREAKER_THRESHOLD = 30

# Tools that are expected to be called repeatedly (polling)
KNOWN_POLL_TOOLS = {"process_poll", "command_status", "task_status", "job_status"}


class DetectorKind(str, Enum):
    GENERIC_REPEAT = "generic_repeat"
    KNOWN_POLL_NO_PROGRESS = "known_poll_no_progress"
    GLOBAL_CIRCUIT_BREAKER = "global_circuit_breaker"
    PING_PONG = "ping_pong"


class DetectionLevel(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolCallRecord:
    """A record of a tool call for pattern matching."""
    tool_name: str
    args_hash: str
    result_hash: str | None = None
    success: bool = True
    error: str = ""


@dataclass
class LoopDetectionResult:
    """Result of loop detection analysis."""
    stuck: bool = False
    level: DetectionLevel = DetectionLevel.OK
    detector: DetectorKind | None = None
    count: int = 0
    message: str = ""
    paired_tool: str = ""  # For ping-pong detection


# ---------------------------------------------------------------------------
# Hashing (ported from OpenClaw)
# ---------------------------------------------------------------------------

def _stable_stringify(value: Any) -> str:
    """Deterministic JSON serialization for hashing."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ",".join(_stable_stringify(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return "{" + ",".join(
            f"{json.dumps(k)}:{_stable_stringify(value[k])}" for k in keys
        ) + "}"
    return str(value)


def _digest(value: Any) -> str:
    """SHA-256 digest of stable-serialized value."""
    serialized = _stable_stringify(value)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def hash_tool_call(tool_name: str, params: Any) -> str:
    """Hash a tool call for pattern matching."""
    return f"{tool_name}:{_digest(params)}"


def hash_tool_outcome(result: Any, error: str = "") -> str | None:
    """Hash a tool call outcome for progress detection."""
    if error:
        return f"error:{_digest(error)}"
    if result is None:
        return None
    return _digest(result)


# ---------------------------------------------------------------------------
# Detection functions (ported from OpenClaw)
# ---------------------------------------------------------------------------

def _get_no_progress_streak(
    history: list[ToolCallRecord],
    tool_name: str,
    args_hash: str,
) -> tuple[int, str | None]:
    """Count consecutive identical-outcome calls for the same tool+params.

    Returns (streak_count, latest_result_hash).
    """
    streak = 0
    latest_hash: str | None = None

    for record in reversed(history):
        if record.tool_name != tool_name or record.args_hash != args_hash:
            continue
        if not record.result_hash:
            continue
        if latest_hash is None:
            latest_hash = record.result_hash
            streak = 1
            continue
        if record.result_hash != latest_hash:
            break
        streak += 1

    return streak, latest_hash


def _get_ping_pong_streak(
    history: list[ToolCallRecord],
    current_hash: str,
) -> tuple[int, str]:
    """Detect A->B->A->B alternating pattern.

    Returns (alternating_count, paired_tool_name).
    """
    if not history:
        return 0, ""

    last = history[-1]
    other_hash: str | None = None
    other_tool: str = ""

    # Find the "other" tool in the alternation
    for record in reversed(history[:-1]):
        if record.args_hash != last.args_hash:
            other_hash = record.args_hash
            other_tool = record.tool_name
            break

    if not other_hash:
        return 0, ""

    # Count alternating tail
    count = 0
    expected_hashes = [last.args_hash, other_hash]
    for i, record in enumerate(reversed(history)):
        expected = expected_hashes[i % 2]
        if record.args_hash != expected:
            break
        count += 1

    return count, other_tool


# ---------------------------------------------------------------------------
# LoopDetector
# ---------------------------------------------------------------------------

class LoopDetector:
    """Detects and prevents infinite tool call loops.

    Maintains a sliding window of recent tool calls and checks for
    repetitive patterns that indicate the agent is stuck.

    Usage::

        detector = LoopDetector()

        # Before each tool call:
        result = detector.detect(tool_name, params)
        if result.stuck and result.level == "critical":
            break  # Stop the loop

        # After each tool call:
        detector.record_outcome(tool_name, params, result, error)
    """

    def __init__(
        self,
        *,
        history_size: int = HISTORY_SIZE,
        warning_threshold: int = WARNING_THRESHOLD,
        critical_threshold: int = CRITICAL_THRESHOLD,
        circuit_breaker_threshold: int = GLOBAL_CIRCUIT_BREAKER_THRESHOLD,
    ) -> None:
        self._history: list[ToolCallRecord] = []
        self._history_size = history_size
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._circuit_breaker = circuit_breaker_threshold

    def detect(self, tool_name: str, params: Any) -> LoopDetectionResult:
        """Check if the next tool call would be part of a loop.

        Run this BEFORE executing the tool call.
        """
        args_hash = hash_tool_call(tool_name, params)

        # 1. Global circuit breaker (any tool repeated too many times)
        total_same = sum(
            1 for r in self._history
            if r.tool_name == tool_name and r.args_hash == args_hash
        )
        if total_same >= self._circuit_breaker:
            return LoopDetectionResult(
                stuck=True,
                level=DetectionLevel.CRITICAL,
                detector=DetectorKind.GLOBAL_CIRCUIT_BREAKER,
                count=total_same,
                message=f"Circuit breaker: {tool_name} called {total_same} times with same params",
            )

        # 2. Generic repeat (same tool+params)
        streak, _ = _get_no_progress_streak(self._history, tool_name, args_hash)
        if streak >= self._critical_threshold:
            return LoopDetectionResult(
                stuck=True,
                level=DetectionLevel.CRITICAL,
                detector=DetectorKind.GENERIC_REPEAT,
                count=streak,
                message=f"Loop detected: {tool_name} repeated {streak} times with identical results",
            )
        if streak >= self._warning_threshold:
            return LoopDetectionResult(
                stuck=True,
                level=DetectionLevel.WARNING,
                detector=DetectorKind.GENERIC_REPEAT,
                count=streak,
                message=f"Warning: {tool_name} repeated {streak} times -- consider different approach",
            )

        # 3. Known poll with no progress
        is_poll = tool_name in KNOWN_POLL_TOOLS
        if is_poll:
            poll_streak, _ = _get_no_progress_streak(self._history, tool_name, args_hash)
            if poll_streak >= self._critical_threshold:
                return LoopDetectionResult(
                    stuck=True,
                    level=DetectionLevel.CRITICAL,
                    detector=DetectorKind.KNOWN_POLL_NO_PROGRESS,
                    count=poll_streak,
                    message=f"Poll stuck: {tool_name} returned identical results {poll_streak} times",
                )
            if poll_streak >= self._warning_threshold:
                return LoopDetectionResult(
                    stuck=True,
                    level=DetectionLevel.WARNING,
                    detector=DetectorKind.KNOWN_POLL_NO_PROGRESS,
                    count=poll_streak,
                    message=f"Poll warning: {tool_name} showing no progress after {poll_streak} calls",
                )

        # 4. Ping-pong detection (A->B->A->B)
        pp_count, paired = _get_ping_pong_streak(self._history, args_hash)
        if pp_count >= self._warning_threshold:
            level = DetectionLevel.CRITICAL if pp_count >= self._critical_threshold else DetectionLevel.WARNING
            return LoopDetectionResult(
                stuck=True,
                level=level,
                detector=DetectorKind.PING_PONG,
                count=pp_count,
                message=f"Ping-pong: {tool_name} and {paired} alternating {pp_count} times",
                paired_tool=paired,
            )

        return LoopDetectionResult(stuck=False)

    def record_outcome(
        self,
        tool_name: str,
        params: Any,
        result: Any = None,
        error: str = "",
    ) -> None:
        """Record a tool call outcome for future detection.

        Run this AFTER executing the tool call.
        """
        record = ToolCallRecord(
            tool_name=tool_name,
            args_hash=hash_tool_call(tool_name, params),
            result_hash=hash_tool_outcome(result, error),
            success=not bool(error),
            error=error[:200] if error else "",
        )
        self._history.append(record)

        # Maintain sliding window
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

    def reset(self) -> None:
        """Reset detection state."""
        self._history.clear()

    @property
    def call_count(self) -> int:
        """Total tool calls tracked."""
        return len(self._history)
