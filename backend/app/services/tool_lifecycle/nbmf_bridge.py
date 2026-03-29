"""NBMF Bridge -- connects TLM to Daena's memory system for predictive
tool activation.

Memory tiers used for tool lifecycle:
    L1 (Ephemeral): Recent tool-use patterns for THIS conversation
    L2 (Working): Agent-level learned patterns (agent usually needs X after Y)
    L2Q (Department): Department norms (Finance agents always need spreadsheet tools)
    L3 (Institutional): Org-wide defaults

The bridge reads from NBMF to predict which tools an agent will need,
and writes session outcomes back to NBMF for future learning.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PredictedTool:
    """A tool predicted to be needed based on memory patterns."""

    tool_id: str
    confidence: float  # 0.0 to 1.0
    source: str  # "L1_conversation" | "L2_agent" | "L2Q_department" | "L3_org"
    reason: str  # human-readable explanation


@dataclass(slots=True)
class MemoryEntry:
    """Simplified memory entry for the bridge's internal store.

    In production, this would read/write from the actual NBMF tables.
    For now, we use an in-memory store that mimics the NBMF tier behavior.
    """

    tier: str  # "L1" | "L2" | "L2Q" | "L3"
    key: str  # scoping key: conversation_id, agent_id, department, or "global"
    tool_ids: list[str] = field(default_factory=list)
    call_counts: dict[str, int] = field(default_factory=dict)
    sequence_pairs: list[tuple[str, str]] = field(default_factory=list)


class NBMFBridge:
    """Bridge between TLM and NBMF memory for predictive tool activation.

    In production, this reads from the actual Memory model (backend/app/models/memory.py)
    via the memory service. For testability, the bridge maintains its own lightweight
    store that mirrors the NBMF tier structure.
    """

    def __init__(self) -> None:
        # tier -> key -> MemoryEntry
        self._store: dict[str, dict[str, MemoryEntry]] = defaultdict(dict)

    # ── Prediction ────────────────────────────────────────────

    def predict_next_tools(
        self,
        conversation_id: str,
        agent_id: str,
        department: str,
        current_tools: list[str],
        max_predictions: int = 3,
    ) -> list[PredictedTool]:
        """Predict which tools the agent will need next.

        Checks tiers in order: L1 (conversation) > L2 (agent) > L2Q (department) > L3 (org).
        Higher tiers have higher confidence. Predictions are de-duplicated
        and exclude tools already in current_tools.
        """
        predictions: list[PredictedTool] = []
        seen: set[str] = set(current_tools)

        # L1: Conversation-specific patterns
        l1 = self._store.get("L1", {}).get(conversation_id)
        if l1:
            for tool_a, tool_b in l1.sequence_pairs:
                if tool_a in current_tools and tool_b not in seen:
                    predictions.append(PredictedTool(
                        tool_id=tool_b,
                        confidence=0.9,
                        source="L1_conversation",
                        reason=f"Used {tool_b} after {tool_a} in this conversation",
                    ))
                    seen.add(tool_b)

        # L2: Agent-level patterns
        l2 = self._store.get("L2", {}).get(agent_id)
        if l2:
            for tool_id, count in sorted(l2.call_counts.items(), key=lambda x: -x[1]):
                if tool_id not in seen:
                    confidence = min(0.8, 0.3 + (count * 0.1))
                    predictions.append(PredictedTool(
                        tool_id=tool_id,
                        confidence=confidence,
                        source="L2_agent",
                        reason=f"Agent used {tool_id} in {count} previous sessions",
                    ))
                    seen.add(tool_id)

        # L2Q: Department norms
        l2q = self._store.get("L2Q", {}).get(department)
        if l2q:
            for tool_id in l2q.tool_ids:
                if tool_id not in seen:
                    predictions.append(PredictedTool(
                        tool_id=tool_id,
                        confidence=0.6,
                        source="L2Q_department",
                        reason=f"Standard tool for {department} department",
                    ))
                    seen.add(tool_id)

        # L3: Org-wide defaults
        l3 = self._store.get("L3", {}).get("global")
        if l3:
            for tool_id in l3.tool_ids:
                if tool_id not in seen:
                    predictions.append(PredictedTool(
                        tool_id=tool_id,
                        confidence=0.4,
                        source="L3_org",
                        reason=f"Org-wide default tool",
                    ))
                    seen.add(tool_id)

        # Sort by confidence (highest first), limit
        predictions.sort(key=lambda p: -p.confidence)
        return predictions[:max_predictions]

    def get_prewarm_suggestions(
        self,
        agent_id: str,
        max_suggestions: int = 3,
    ) -> list[str]:
        """Suggest tools to pre-warm based on agent's history.

        Returns tool IDs that the agent uses most frequently.
        """
        l2 = self._store.get("L2", {}).get(agent_id)
        if not l2:
            return []

        # Return top tools by call count
        sorted_tools = sorted(l2.call_counts.items(), key=lambda x: -x[1])
        return [tid for tid, _ in sorted_tools[:max_suggestions]]

    # ── Learning ──────────────────────────────────────────────

    def learn_from_session(
        self,
        conversation_id: str,
        agent_id: str,
        department: str,
        tool_sequence: list[str],
        tool_call_counts: dict[str, int],
    ) -> None:
        """Learn from a completed session. Updates all relevant NBMF tiers.

        Args:
            conversation_id: the session that just ended
            agent_id: which agent was active
            department: department context
            tool_sequence: ordered list of tools used (in order of first use)
            tool_call_counts: {tool_id: call_count}
        """
        # L1: Store sequence patterns for this conversation
        pairs: list[tuple[str, str]] = []
        for i in range(len(tool_sequence) - 1):
            pairs.append((tool_sequence[i], tool_sequence[i + 1]))

        self._store["L1"][conversation_id] = MemoryEntry(
            tier="L1",
            key=conversation_id,
            tool_ids=tool_sequence,
            call_counts=dict(tool_call_counts),
            sequence_pairs=pairs,
        )

        # L2: Update agent-level cumulative counts
        l2 = self._store["L2"].get(agent_id)
        if not l2:
            l2 = MemoryEntry(tier="L2", key=agent_id)
            self._store["L2"][agent_id] = l2

        for tid, count in tool_call_counts.items():
            l2.call_counts[tid] = l2.call_counts.get(tid, 0) + count
            if tid not in l2.tool_ids:
                l2.tool_ids.append(tid)

        # Merge sequence pairs
        existing_pairs = set(l2.sequence_pairs)
        for pair in pairs:
            if pair not in existing_pairs:
                l2.sequence_pairs.append(pair)
                existing_pairs.add(pair)

        # L2Q: Update department norms (tools used by ANY agent in this dept)
        l2q = self._store["L2Q"].get(department)
        if not l2q:
            l2q = MemoryEntry(tier="L2Q", key=department)
            self._store["L2Q"][department] = l2q

        for tid in tool_sequence:
            if tid not in l2q.tool_ids:
                l2q.tool_ids.append(tid)

    def set_org_defaults(self, tool_ids: list[str]) -> None:
        """Set organization-wide default tools (L3 tier)."""
        self._store["L3"]["global"] = MemoryEntry(
            tier="L3",
            key="global",
            tool_ids=list(tool_ids),
        )

    # ── Query ─────────────────────────────────────────────────

    def get_agent_history(self, agent_id: str) -> MemoryEntry | None:
        """Get L2 agent memory entry."""
        return self._store.get("L2", {}).get(agent_id)

    def get_department_norms(self, department: str) -> list[str]:
        """Get L2Q department standard tools."""
        l2q = self._store.get("L2Q", {}).get(department)
        return list(l2q.tool_ids) if l2q else []

    # ── Cleanup ───────────────────────────────────────────────

    def clear_conversation(self, conversation_id: str) -> None:
        """Remove L1 memory for a conversation."""
        l1 = self._store.get("L1", {})
        l1.pop(conversation_id, None)

    def clear_all(self) -> None:
        """Remove all memory (testing)."""
        self._store.clear()
