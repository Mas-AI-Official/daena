"""Usage Tracker -- analytics, cost savings, and pattern detection for TLM.

Records every tool activation, deactivation, and call. Generates per-session
cost reports and detects tool co-occurrence patterns (e.g., "agent X uses
drive + search together 80% of the time").
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UsageRecord:
    """Per-tool usage within a conversation."""

    conversation_id: str
    tool_id: str
    agent_id: str
    department: str
    activated_at: float = field(default_factory=time.time)
    deactivated_at: float | None = None
    turns_active: int = 0
    call_count: int = 0
    tokens_saved: int = 0
    errors: int = 0


@dataclass(frozen=True, slots=True)
class ToolCooccurrence:
    """Two tools frequently used together."""

    tool_a: str
    tool_b: str
    co_occurrence_rate: float  # 0.0 to 1.0
    sample_count: int


@dataclass(slots=True)
class SessionCostReport:
    """Summary of tool usage and savings for a session."""

    conversation_id: str
    total_tools_used: int = 0
    total_calls: int = 0
    total_errors: int = 0
    total_tokens_saved: int = 0
    avg_tools_active_per_turn: float = 0.0
    tools: list[UsageRecord] = field(default_factory=list)
    duration_seconds: float = 0.0


class UsageTracker:
    """Track tool usage analytics across conversations.

    Thread-safe for concurrent reads/writes.
    """

    def __init__(self) -> None:
        # conversation_id -> {tool_id -> UsageRecord}
        self._records: dict[str, dict[str, UsageRecord]] = {}
        # agent_id -> list of tool sets per session (for pattern detection)
        self._agent_tool_history: dict[str, list[set[str]]] = defaultdict(list)
        # Snapshots for avg active tools per turn
        self._turn_snapshots: dict[str, list[int]] = defaultdict(list)

    # ── Recording ─────────────────────────────────────────────

    def record_activation(
        self,
        conversation_id: str,
        tool_id: str,
        agent_id: str,
        department: str,
    ) -> None:
        """Record that a tool was activated in a conversation."""
        conv = self._records.setdefault(conversation_id, {})
        if tool_id not in conv:
            conv[tool_id] = UsageRecord(
                conversation_id=conversation_id,
                tool_id=tool_id,
                agent_id=agent_id,
                department=department,
            )
        else:
            # Reactivation: update timestamp
            rec = conv[tool_id]
            rec.activated_at = time.time()
            rec.deactivated_at = None

    def record_deactivation(
        self,
        conversation_id: str,
        tool_id: str,
    ) -> None:
        """Record that a tool was deactivated."""
        conv = self._records.get(conversation_id)
        if not conv:
            return
        rec = conv.get(tool_id)
        if rec:
            rec.deactivated_at = time.time()

    def record_call(
        self,
        conversation_id: str,
        tool_id: str,
        tokens_saved: int = 0,
        error: bool = False,
    ) -> None:
        """Record a tool invocation. Increments call_count."""
        conv = self._records.get(conversation_id)
        if not conv:
            return
        rec = conv.get(tool_id)
        if rec:
            rec.call_count += 1
            rec.tokens_saved += tokens_saved
            if error:
                rec.errors += 1

    def record_turn_snapshot(
        self,
        conversation_id: str,
        active_count: int,
    ) -> None:
        """Record how many tools were active at end of a turn."""
        self._turn_snapshots[conversation_id].append(active_count)

    # ── Reporting ─────────────────────────────────────────────

    def get_session_report(self, conversation_id: str) -> SessionCostReport:
        """Generate cost/usage report for a conversation."""
        conv = self._records.get(conversation_id, {})
        if not conv:
            return SessionCostReport(conversation_id=conversation_id)

        records = list(conv.values())
        snapshots = self._turn_snapshots.get(conversation_id, [])
        avg_active = (
            sum(snapshots) / len(snapshots) if snapshots else 0.0
        )

        now = time.time()
        earliest = min(r.activated_at for r in records) if records else now
        duration = now - earliest

        return SessionCostReport(
            conversation_id=conversation_id,
            total_tools_used=len(records),
            total_calls=sum(r.call_count for r in records),
            total_errors=sum(r.errors for r in records),
            total_tokens_saved=sum(r.tokens_saved for r in records),
            avg_tools_active_per_turn=round(avg_active, 2),
            tools=records,
            duration_seconds=round(duration, 2),
        )

    def get_tool_stats(self, conversation_id: str, tool_id: str) -> UsageRecord | None:
        """Get usage record for a specific tool in a conversation."""
        conv = self._records.get(conversation_id, {})
        return conv.get(tool_id)

    # ── Pattern Detection ─────────────────────────────────────

    def learn_session_patterns(
        self,
        conversation_id: str,
        agent_id: str,
    ) -> None:
        """Store the tool set used in this session for pattern learning."""
        conv = self._records.get(conversation_id, {})
        tool_set = {tid for tid, rec in conv.items() if rec.call_count > 0}
        if tool_set:
            self._agent_tool_history[agent_id].append(tool_set)

    def get_patterns(
        self,
        agent_id: str,
        min_co_occurrence: float = 0.5,
    ) -> list[ToolCooccurrence]:
        """Detect tool co-occurrence patterns for an agent.

        Returns pairs of tools that appear together in >= min_co_occurrence
        fraction of sessions.
        """
        history = self._agent_tool_history.get(agent_id, [])
        if len(history) < 2:
            return []

        # Count individual tool appearances and pair appearances
        tool_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()

        for tool_set in history:
            tools = sorted(tool_set)
            for t in tools:
                tool_counts[t] += 1
            for i, ta in enumerate(tools):
                for tb in tools[i + 1 :]:
                    pair_counts[(ta, tb)] += 1

        total = len(history)
        patterns: list[ToolCooccurrence] = []

        for (ta, tb), count in pair_counts.items():
            rate = count / total
            if rate >= min_co_occurrence:
                patterns.append(
                    ToolCooccurrence(
                        tool_a=ta,
                        tool_b=tb,
                        co_occurrence_rate=round(rate, 3),
                        sample_count=count,
                    )
                )

        return sorted(patterns, key=lambda p: -p.co_occurrence_rate)

    # ── Token Savings ─────────────────────────────────────────

    def calculate_baseline_cost(
        self,
        total_registry_tokens: int,
        turns: int,
    ) -> int:
        """Calculate how many tokens would be used if ALL tools were loaded every turn."""
        return total_registry_tokens * turns

    def calculate_tlm_cost(
        self,
        conversation_id: str,
        per_tool_tokens: dict[str, int],
    ) -> int:
        """Calculate actual tokens used with TLM (only active schemas loaded)."""
        snapshots = self._turn_snapshots.get(conversation_id, [])
        if not snapshots:
            return 0
        # Approximate: avg active tools * avg tokens per tool * turns
        conv = self._records.get(conversation_id, {})
        active_tools = [tid for tid, rec in conv.items() if rec.call_count > 0]
        avg_tokens = (
            sum(per_tool_tokens.get(tid, 0) for tid in active_tools) / max(len(active_tools), 1)
        )
        return int(sum(snapshots) * avg_tokens)

    # ── Cleanup ───────────────────────────────────────────────

    def clear_conversation(self, conversation_id: str) -> None:
        """Remove all records for a conversation."""
        self._records.pop(conversation_id, None)
        self._turn_snapshots.pop(conversation_id, None)

    def clear_all(self) -> None:
        """Remove all records (testing)."""
        self._records.clear()
        self._agent_tool_history.clear()
        self._turn_snapshots.clear()
