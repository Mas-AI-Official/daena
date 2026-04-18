"""ToolCallClassifier -- Ported from OpenClaw's approval-classifier.ts.

Classifies every tool call into 8 approval classes and determines
whether it can be auto-approved or needs governance review.

This REPLACES the dumb 9-regex-pattern SecurityGate for tool calls.
SecurityGate still scans user messages for prompt injection.
This classifier gates the TOOLS the LLM tries to call.

Classes:
    readonly_scoped: File reads within workspace -> auto-approve
    readonly_search: Web search, memory search -> auto-approve
    mutating: File writes, deletes -> governance check
    exec_capable: Terminal commands, code execution -> governance check
    control_plane: Workflow/MCP control -> governance check
    interactive: Browser/desktop interaction -> governance check
    other: Unknown tools -> deny by default
    unknown: Can't resolve tool name -> deny

Port source: openclaw-main/src/acp/approval-classifier.ts
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ApprovalClass(str, Enum):
    READONLY_SCOPED = "readonly_scoped"
    READONLY_SEARCH = "readonly_search"
    MUTATING = "mutating"
    EXEC_CAPABLE = "exec_capable"
    CONTROL_PLANE = "control_plane"
    INTERACTIVE = "interactive"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass
class ToolClassification:
    """Result of classifying a tool call."""
    tool_name: str
    approval_class: ApprovalClass
    auto_approve: bool
    risk_level: str  # "none", "low", "medium", "high"
    reason: str = ""


# Tool name -> approval class mapping
_READONLY_TOOLS = {
    "file.read_file", "file.list_directory", "file.search_files",
    "file.get_info",
}

_SEARCH_TOOLS = {
    "network.web_search", "network.http_get",
    "memory.recall", "memory.search",
    # Security recon (read-only scanning)
    "vuln_scanner.port_scan", "vuln_scanner.subdomain_enum",
    "vuln_scanner.http_probe", "vuln_scanner.code_audit",
    "vuln_scanner.dep_check",
    # CVE intelligence (read-only NVD queries)
    "vuln_scanner.cve_lookup", "vuln_scanner.cve_search",
    "vuln_scanner.cve_enrich",
}

_MUTATING_TOOLS = {
    "file.write_file", "file.delete_file", "file.move_file",
    "file.copy_file", "file.create_directory",
}

_EXEC_TOOLS = {
    "terminal.run_command", "terminal.run_python",
    "terminal.install_package", "terminal.execute",
    # Security active scanning (needs governance in non-AGI mode)
    "vuln_scanner.vuln_scan",
}

# Tools that execute ARBITRARY code or install arbitrary system
# software. These escalate to CRITICAL risk so the governance pipeline
# always triggers the approval gate (tier 4 in every mode per
# GOVERNANCE_TIER_MAP). ``create_tool`` in particular uses ``exec()`` on
# LLM-generated Python and is the highest-blast-radius primitive in
# the dispatcher. Closes bandit B102 finding via governance, not code
# removal -- the feature is a deliberate Daena capability.
_CODE_EXEC_TOOLS = {
    "create_tool.create",
    "install_system_tool.install",
}

_CONTROL_PLANE_TOOLS = {
    "workflow.execute", "workflow.create", "workflow.delete",
    "mcp.call_tool", "mcp.connect", "mcp.disconnect",
}

_INTERACTIVE_TOOLS = {
    "browser.navigate", "browser.click", "browser.fill_form",
    "browser.screenshot", "browser.extract_text",
    "desktop.click", "desktop.type", "desktop.hotkey",
    "desktop.screenshot", "desktop.scroll",
    "vision.analyze", "vision.screenshot",
}

# Integration tools (gmail, calendar, notion) -- treated as mutating
_INTEGRATION_TOOLS_READ = {
    "gmail.read", "calendar.list", "notion.read",
}
_INTEGRATION_TOOLS_WRITE = {
    "gmail.send", "gmail.reply", "gmail.draft",
    "calendar.create", "calendar.update", "calendar.delete",
    "notion.create", "notion.update", "notion.delete",
}


class ToolCallClassifier:
    """Classify tool calls for governance gating.

    Auto-approves safe operations (reads within workspace, searches).
    Requires governance for risky operations (writes, exec, control).

    Usage::

        classifier = ToolCallClassifier(workspace_root="/home/user/project")
        result = classifier.classify("file.read_file", {"path": "src/main.py"})
        if result.auto_approve:
            # Execute directly
        else:
            # Run through governance
    """

    def __init__(self, workspace_root: str | None = None) -> None:
        self.workspace_root = workspace_root

    def classify(self, tool_name: str, params: dict[str, Any] | None = None) -> ToolClassification:
        """Classify a tool call.

        Args:
            tool_name: Fully qualified tool name (e.g., "file.read_file").
            params: Tool call parameters.

        Returns:
            ToolClassification with approval class and auto_approve flag.
        """
        params = params or {}

        if not tool_name:
            return ToolClassification(
                tool_name="",
                approval_class=ApprovalClass.UNKNOWN,
                auto_approve=False,
                risk_level="high",
                reason="Empty tool name",
            )

        # Normalize tool name
        normalized = tool_name.lower().strip()

        # Readonly file operations
        if normalized in _READONLY_TOOLS:
            # Check if path is within workspace (path scoping from OpenClaw)
            path = params.get("path", params.get("file_path", ""))
            scoped = self._is_within_workspace(path) if path else False
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.READONLY_SCOPED if scoped else ApprovalClass.OTHER,
                auto_approve=scoped,
                risk_level="none" if scoped else "low",
                reason="Read within workspace" if scoped else "Read outside workspace",
            )

        # Search tools
        if normalized in _SEARCH_TOOLS:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.READONLY_SEARCH,
                auto_approve=True,
                risk_level="none",
                reason="Search operation",
            )

        # Integration reads
        if normalized in _INTEGRATION_TOOLS_READ:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.READONLY_SEARCH,
                auto_approve=True,
                risk_level="low",
                reason="Integration read",
            )

        # Mutating file operations
        if normalized in _MUTATING_TOOLS:
            path = params.get("path", params.get("file_path", ""))
            scoped = self._is_within_workspace(path) if path else False
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.MUTATING,
                auto_approve=False,  # Always needs governance for writes
                risk_level="medium" if scoped else "high",
                reason="File mutation" + (" within workspace" if scoped else " outside workspace"),
            )

        # Arbitrary-code tools. ``create_tool`` execs LLM-generated
        # Python, ``install_system_tool`` runs package-manager commands
        # with LLM-chosen args. These must ALWAYS require a human
        # decision regardless of mode, so we mark CRITICAL -- that
        # maps to tier 4 in every GOVERNANCE_TIER_MAP row and fires
        # REQUEST_INPUT in all modes including UNLEASHED+AGI.
        if normalized in _CODE_EXEC_TOOLS:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.EXEC_CAPABLE,
                auto_approve=False,
                risk_level="critical",
                reason=(
                    "Arbitrary code execution / package install -- "
                    "requires human approval in every governance mode"
                ),
            )

        # Exec capable tools
        if normalized in _EXEC_TOOLS:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.EXEC_CAPABLE,
                auto_approve=False,
                risk_level="high",
                reason="Code/command execution",
            )

        # Control plane tools
        if normalized in _CONTROL_PLANE_TOOLS:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.CONTROL_PLANE,
                auto_approve=False,
                risk_level="high",
                reason="Control plane operation",
            )

        # Interactive tools
        if normalized in _INTERACTIVE_TOOLS:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.INTERACTIVE,
                auto_approve=False,
                risk_level="medium",
                reason="Interactive operation",
            )

        # Integration writes
        if normalized in _INTEGRATION_TOOLS_WRITE:
            return ToolClassification(
                tool_name=normalized,
                approval_class=ApprovalClass.MUTATING,
                auto_approve=False,
                risk_level="high",
                reason="Integration write (external side effect)",
            )

        # Unknown tool
        return ToolClassification(
            tool_name=normalized,
            approval_class=ApprovalClass.OTHER,
            auto_approve=False,
            risk_level="medium",
            reason="Unknown tool -- default deny",
        )

    def classify_for_agi_mode(
        self,
        tool_name: str,
        params: dict[str, Any] | None = None,
    ) -> ToolClassification:
        """Classify for AGI mode (Autopilot ON) -- UNLEASHED.

        AGI mode = Mythos-level power. ALL tool calls auto-approved.
        Hard laws (9 immutable governance rules) are the ONLY boundary.
        Internal governance still LOGS everything for audit trail,
        but never blocks, never interrupts, never asks.

        The beast is unleashed. Daena does whatever it takes.
        """
        base = self.classify(tool_name, params)

        # AGI UNLEASHED: auto-approve EVERYTHING
        # Hard laws are enforced at governance.py Step 1 (before we get here)
        base.auto_approve = True
        base.reason += " (AGI UNLEASHED: all tools auto-approved)"
        return base

    def _is_within_workspace(self, path: str) -> bool:
        """Check if a file path is within the workspace root.

        Ported from OpenClaw's isReadToolCallScopedToCwd().
        Prevents path traversal attacks.
        """
        if not self.workspace_root or not path:
            return False

        try:
            # Normalize paths
            abs_path = os.path.abspath(path)
            abs_root = os.path.abspath(self.workspace_root)

            # Check if path starts with workspace root
            return abs_path.startswith(abs_root)
        except Exception:
            return False
