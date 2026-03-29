"""Session Manager -- per-conversation tool activation lifecycle.

Tracks which tools are active, cooling, or deactivated per conversation.
Handles idle-turn counting, automatic deactivation, max-active-tools cap,
and LRU eviction when the cap is reached.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolStatus(str, Enum):
    ACTIVATING = "activating"
    ACTIVE = "active"
    COOLING = "cooling"
    DEACTIVATED = "deactivated"


@dataclass
class ToolSession:
    """Per-tool activation state within a conversation."""

    tool_id: str
    session_id: str  # the conversation ID
    activated_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    turns_since_last_use: int = 0
    status: ToolStatus = ToolStatus.ACTIVE
    connection_handle: Any = None
    call_count: int = 0


@dataclass(frozen=True, slots=True)
class DeactivationReport:
    """Result of a tick_turn operation."""

    cooled: list[str]  # tools that entered cooling
    deactivated: list[str]  # tools that were fully deactivated
    evicted: list[str]  # tools evicted due to max cap


class SessionManager:
    """Manages tool activation state per conversation.

    Configuration:
        idle_turns_before_cooldown: turns unused before entering 'cooling' (default 3)
        idle_turns_before_deactivate: turns unused before full deactivation (default 5)
        max_active_tools: hard cap per conversation (default 8)
    """

    def __init__(
        self,
        idle_turns_before_cooldown: int = 3,
        idle_turns_before_deactivate: int = 5,
        max_active_tools: int = 8,
    ) -> None:
        self.idle_turns_before_cooldown = idle_turns_before_cooldown
        self.idle_turns_before_deactivate = idle_turns_before_deactivate
        self.max_active_tools = max_active_tools

        # conversation_id -> {tool_id -> ToolSession}
        self._sessions: dict[str, dict[str, ToolSession]] = {}
        self._lock = threading.Lock()

    # ── Activation / Deactivation ─────────────────────────────

    def activate_tool(
        self,
        tool_id: str,
        conversation_id: str,
        connection_handle: Any = None,
    ) -> ToolSession:
        """Activate a tool for a conversation. Returns the session.

        If already active, returns existing session (reactivates if deactivated).
        If max cap is reached, evicts the oldest idle tool.
        """
        with self._lock:
            conv = self._sessions.setdefault(conversation_id, {})
            existing = conv.get(tool_id)

            if existing and existing.status in (ToolStatus.ACTIVE, ToolStatus.ACTIVATING):
                return existing

            # Reactivation of cooled/deactivated tool
            if existing and existing.status in (ToolStatus.COOLING, ToolStatus.DEACTIVATED):
                existing.status = ToolStatus.ACTIVE
                existing.turns_since_last_use = 0
                existing.last_used_at = time.time()
                existing.connection_handle = connection_handle or existing.connection_handle
                return existing

            # New activation -- check cap
            active_count = sum(
                1 for s in conv.values()
                if s.status in (ToolStatus.ACTIVE, ToolStatus.ACTIVATING, ToolStatus.COOLING)
            )
            if active_count >= self.max_active_tools:
                self._evict_oldest_idle(conv)

            session = ToolSession(
                tool_id=tool_id,
                session_id=conversation_id,
                connection_handle=connection_handle,
            )
            conv[tool_id] = session
            return session

    def deactivate_tool(self, tool_id: str, conversation_id: str) -> bool:
        """Manually deactivate a tool. Returns True if it was active."""
        with self._lock:
            conv = self._sessions.get(conversation_id)
            if not conv:
                return False
            session = conv.get(tool_id)
            if not session or session.status == ToolStatus.DEACTIVATED:
                return False
            session.status = ToolStatus.DEACTIVATED
            session.connection_handle = None
            return True

    # ── Turn Management ───────────────────────────────────────

    def tick_turn(self, conversation_id: str) -> DeactivationReport:
        """Advance one turn. Increment idle counters, deactivate stale tools.

        Called after each LLM turn. Tools that were used this turn should have
        their counters reset via record_use() BEFORE calling tick_turn().
        """
        cooled: list[str] = []
        deactivated: list[str] = []
        evicted: list[str] = []

        with self._lock:
            conv = self._sessions.get(conversation_id)
            if not conv:
                return DeactivationReport(cooled=[], deactivated=[], evicted=[])

            for tool_id, session in conv.items():
                if session.status == ToolStatus.DEACTIVATED:
                    continue

                session.turns_since_last_use += 1

                if session.turns_since_last_use >= self.idle_turns_before_deactivate:
                    session.status = ToolStatus.DEACTIVATED
                    session.connection_handle = None
                    deactivated.append(tool_id)
                elif session.turns_since_last_use >= self.idle_turns_before_cooldown:
                    if session.status != ToolStatus.COOLING:
                        session.status = ToolStatus.COOLING
                        cooled.append(tool_id)

        return DeactivationReport(cooled=cooled, deactivated=deactivated, evicted=evicted)

    def record_use(self, tool_id: str, conversation_id: str) -> None:
        """Record that a tool was used this turn. Resets idle counter."""
        with self._lock:
            conv = self._sessions.get(conversation_id)
            if not conv:
                return
            session = conv.get(tool_id)
            if not session:
                return
            session.last_used_at = time.time()
            session.turns_since_last_use = 0
            session.call_count += 1
            if session.status == ToolStatus.COOLING:
                session.status = ToolStatus.ACTIVE

    # ── Query ─────────────────────────────────────────────────

    def get_active_tools(self, conversation_id: str) -> list[ToolSession]:
        """Return all non-deactivated tools for a conversation."""
        with self._lock:
            conv = self._sessions.get(conversation_id, {})
            return [
                s for s in conv.values()
                if s.status in (ToolStatus.ACTIVE, ToolStatus.ACTIVATING, ToolStatus.COOLING)
            ]

    def is_tool_active(self, tool_id: str, conversation_id: str) -> bool:
        """Check if a tool is currently active (not deactivated)."""
        with self._lock:
            conv = self._sessions.get(conversation_id, {})
            session = conv.get(tool_id)
            if not session:
                return False
            return session.status in (ToolStatus.ACTIVE, ToolStatus.ACTIVATING, ToolStatus.COOLING)

    def get_tool_session(self, tool_id: str, conversation_id: str) -> ToolSession | None:
        """Get the session for a specific tool, if any."""
        with self._lock:
            conv = self._sessions.get(conversation_id, {})
            return conv.get(tool_id)

    def get_active_cost(self, conversation_id: str) -> dict[str, int]:
        """Return active tool count and estimated connection count."""
        with self._lock:
            conv = self._sessions.get(conversation_id, {})
            active = [
                s for s in conv.values()
                if s.status in (ToolStatus.ACTIVE, ToolStatus.ACTIVATING)
            ]
            return {
                "active_count": len(active),
                "cooling_count": sum(
                    1 for s in conv.values() if s.status == ToolStatus.COOLING
                ),
                "total_calls": sum(s.call_count for s in conv.values()),
            }

    # ── Cleanup ───────────────────────────────────────────────

    def clear_conversation(self, conversation_id: str) -> None:
        """Remove all tool state for a conversation (session ended)."""
        with self._lock:
            self._sessions.pop(conversation_id, None)

    def clear_all(self) -> None:
        """Remove all state (used in testing)."""
        with self._lock:
            self._sessions.clear()

    # ── Internal ──────────────────────────────────────────────

    def _evict_oldest_idle(self, conv: dict[str, ToolSession]) -> str | None:
        """Evict the tool with highest turns_since_last_use. Must hold lock."""
        candidates = [
            s for s in conv.values()
            if s.status in (ToolStatus.ACTIVE, ToolStatus.COOLING)
        ]
        if not candidates:
            return None

        # Prefer cooling tools, then oldest idle active
        candidates.sort(
            key=lambda s: (
                0 if s.status == ToolStatus.COOLING else 1,
                -s.turns_since_last_use,
            )
        )
        victim = candidates[0]
        victim.status = ToolStatus.DEACTIVATED
        victim.connection_handle = None
        return victim.tool_id
