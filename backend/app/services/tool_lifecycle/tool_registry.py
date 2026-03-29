"""Tool Registry -- catalog of every tool/plugin/MCP-server the platform knows about.

Provides lightweight catalog (id + description only) for LLM context injection,
and full schemas loaded only when a tool is activated. Enforces governance rules
at the registration level (allowed departments, approval requirements, concurrency).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GovernanceRules:
    """Per-tool governance constraints."""

    allowed_departments: list[str] = field(default_factory=list)
    requires_approval: bool = False
    max_concurrent_sessions: int = 5


@dataclass(slots=True)
class ToolDefinition:
    """Complete tool definition with schema and governance."""

    id: str
    name: str
    category: str
    light_description: str
    full_schema: dict[str, Any]
    auth_type: str = "none"  # "oauth" | "api_key" | "none"
    connection_cost: str = "low"  # "low" | "medium" | "high"
    governance_rules: GovernanceRules = field(default_factory=GovernanceRules)
    estimated_schema_tokens: int = 0


@dataclass(frozen=True, slots=True)
class LightweightCatalogEntry:
    """Minimal entry for LLM context injection (saves tokens)."""

    id: str
    name: str
    category: str
    light_description: str


class ToolRegistry:
    """Thread-safe in-memory registry for all known tools.

    Design:
        - Tools registered once at startup (from agents, MCP servers, connectors)
        - Lightweight catalog sent to LLM every turn (id + description only)
        - Full schema loaded only when tool is activated by SessionManager
        - Governance checks at registration time (department/approval rules)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._lock = threading.Lock()

    # ── Registration ──────────────────────────────────────────

    def register_tool(self, definition: ToolDefinition) -> None:
        """Register a tool. Raises ValueError on duplicate ID."""
        with self._lock:
            if definition.id in self._tools:
                raise ValueError(
                    f"Tool '{definition.id}' already registered. "
                    "Use update_tool() to modify."
                )
            self._tools[definition.id] = definition

    def register_or_update(self, definition: ToolDefinition) -> None:
        """Register a tool, or update if already exists (idempotent)."""
        with self._lock:
            self._tools[definition.id] = definition

    def unregister_tool(self, tool_id: str) -> bool:
        """Remove a tool from the registry. Returns True if it existed."""
        with self._lock:
            return self._tools.pop(tool_id, None) is not None

    # ── Catalog queries ───────────────────────────────────────

    def get_tool_catalog(self) -> list[LightweightCatalogEntry]:
        """Return lightweight catalog for LLM context. No full schemas leaked."""
        with self._lock:
            return [
                LightweightCatalogEntry(
                    id=t.id,
                    name=t.name,
                    category=t.category,
                    light_description=t.light_description,
                )
                for t in self._tools.values()
            ]

    def get_full_schema(self, tool_id: str) -> dict[str, Any] | None:
        """Return full tool schema. Only call when tool is being activated."""
        with self._lock:
            tool = self._tools.get(tool_id)
            return dict(tool.full_schema) if tool else None

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """Return full tool definition by ID."""
        with self._lock:
            return self._tools.get(tool_id)

    def get_tools_by_category(self, category: str) -> list[ToolDefinition]:
        """Filter tools by category (case-insensitive)."""
        cat_lower = category.lower()
        with self._lock:
            return [
                t for t in self._tools.values()
                if t.category.lower() == cat_lower
            ]

    # ── Governance checks ─────────────────────────────────────

    def is_tool_allowed(
        self,
        tool_id: str,
        department: str,
        agent_id: str | None = None,
    ) -> tuple[bool, str]:
        """Check if a tool is allowed for a given department.

        Returns:
            (allowed, reason) -- reason is empty string if allowed,
            or explanation if blocked.
        """
        with self._lock:
            tool = self._tools.get(tool_id)
            if tool is None:
                return False, f"Tool '{tool_id}' not registered"

            rules = tool.governance_rules

            # Empty allowed_departments means "all departments"
            if rules.allowed_departments and department not in rules.allowed_departments:
                return False, (
                    f"Tool '{tool_id}' not allowed for department '{department}'. "
                    f"Allowed: {rules.allowed_departments}"
                )

            return True, ""

    def requires_approval(self, tool_id: str) -> bool:
        """Check if tool requires human approval before execution."""
        with self._lock:
            tool = self._tools.get(tool_id)
            if tool is None:
                return True  # unknown tools always require approval
            return tool.governance_rules.requires_approval

    # ── Bulk operations ───────────────────────────────────────

    def register_many(self, definitions: list[ToolDefinition]) -> int:
        """Register multiple tools. Returns count of newly registered."""
        count = 0
        with self._lock:
            for defn in definitions:
                if defn.id not in self._tools:
                    self._tools[defn.id] = defn
                    count += 1
        return count

    def clear(self) -> None:
        """Remove all tools (used in testing)."""
        with self._lock:
            self._tools.clear()

    @property
    def count(self) -> int:
        """Number of registered tools."""
        with self._lock:
            return len(self._tools)

    def all_tool_ids(self) -> list[str]:
        """List all registered tool IDs."""
        with self._lock:
            return list(self._tools.keys())

    def get_total_schema_tokens(self, tool_ids: list[str] | None = None) -> int:
        """Calculate total estimated tokens for given tool schemas.

        If tool_ids is None, calculates for ALL tools (the baseline cost).
        """
        with self._lock:
            if tool_ids is None:
                return sum(t.estimated_schema_tokens for t in self._tools.values())
            return sum(
                self._tools[tid].estimated_schema_tokens
                for tid in tool_ids
                if tid in self._tools
            )
