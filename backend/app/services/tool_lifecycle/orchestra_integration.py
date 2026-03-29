"""Orchestra Integration -- wires TLM into the chat_orchestrator pipeline.

This module provides the TLM singleton and helper functions that the
chat_orchestrator calls at Stage 7.5. The integration is non-invasive:
Orchestra can work with or without TLM (graceful degradation).

Integration points:
    - Before LLM call: inject lightweight tool catalog + active schemas
    - After tool execution: record usage, update sessions
    - After each turn: tick idle counters, deactivate stale tools
    - On session end: generate report, learn patterns to NBMF
"""

from __future__ import annotations

import contextlib
from typing import Any

from app.core.logging import get_logger
from app.services.tool_lifecycle.tool_registry import (
    GovernanceRules,
    ToolDefinition,
    ToolRegistry,
)
from app.services.tool_lifecycle.session_manager import SessionManager
from app.services.tool_lifecycle.activation_proxy import ActivationProxy
from app.services.tool_lifecycle.usage_tracker import UsageTracker
from app.services.tool_lifecycle.nbmf_bridge import NBMFBridge
from app.services.tool_lifecycle.phase_detector import (
    AdaptiveToolSelector,
    ConversationPhaseDetector,
)

logger = get_logger(__name__)

# ── Singleton TLM Instance ────────────────────────────────────

_registry: ToolRegistry | None = None
_session_manager: SessionManager | None = None
_proxy: ActivationProxy | None = None
_tracker: UsageTracker | None = None
_bridge: NBMFBridge | None = None
_selector: AdaptiveToolSelector | None = None
_initialized = False


def get_tlm_registry() -> ToolRegistry:
    """Get or create the TLM ToolRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def get_tlm_session_manager() -> SessionManager:
    """Get or create the TLM SessionManager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(
            idle_turns_before_cooldown=3,
            idle_turns_before_deactivate=5,
            max_active_tools=8,
        )
    return _session_manager


def get_tlm_proxy() -> ActivationProxy:
    """Get or create the TLM ActivationProxy singleton."""
    global _proxy
    if _proxy is None:
        _proxy = ActivationProxy(get_tlm_registry(), get_tlm_session_manager())
    return _proxy


def get_tlm_tracker() -> UsageTracker:
    """Get or create the TLM UsageTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker


def get_tlm_bridge() -> NBMFBridge:
    """Get or create the TLM NBMFBridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = NBMFBridge()
    return _bridge


def initialize_tlm() -> None:
    """Initialize TLM with default tools from DaenaBot agents.

    Called during app startup to register built-in tools
    (FileAgent, TerminalAgent, BrowserAgent operations).
    """
    global _initialized
    if _initialized:
        return

    registry = get_tlm_registry()

    # Register built-in DaenaBot tools
    builtin_tools = [
        # FileAgent operations
        ToolDefinition(
            id="file.read_file",
            name="Read File",
            category="file",
            light_description="Read contents of a file",
            full_schema={"type": "function", "name": "file.read_file", "params": {"path": "string"}},
            estimated_schema_tokens=80,
        ),
        ToolDefinition(
            id="file.write_file",
            name="Write File",
            category="file",
            light_description="Write content to a file",
            full_schema={"type": "function", "name": "file.write_file", "params": {"path": "string", "content": "string"}},
            governance_rules=GovernanceRules(requires_approval=False),
            estimated_schema_tokens=120,
        ),
        ToolDefinition(
            id="file.list_directory",
            name="List Directory",
            category="file",
            light_description="List files in a directory",
            full_schema={"type": "function", "name": "file.list_directory", "params": {"path": "string"}},
            estimated_schema_tokens=80,
        ),
        ToolDefinition(
            id="file.search_files",
            name="Search Files",
            category="file",
            light_description="Search for files by pattern",
            full_schema={"type": "function", "name": "file.search_files", "params": {"query": "string", "path": "string"}},
            estimated_schema_tokens=100,
        ),
        ToolDefinition(
            id="file.delete_file",
            name="Delete File",
            category="file",
            light_description="Delete a file (moved to archive)",
            full_schema={"type": "function", "name": "file.delete_file", "params": {"path": "string"}},
            governance_rules=GovernanceRules(requires_approval=True),
            estimated_schema_tokens=80,
        ),
        ToolDefinition(
            id="file.move_file",
            name="Move File",
            category="file",
            light_description="Move or rename a file",
            full_schema={"type": "function", "name": "file.move_file", "params": {"source": "string", "dest": "string"}},
            estimated_schema_tokens=90,
        ),

        # TerminalAgent operations
        ToolDefinition(
            id="terminal.execute_command",
            name="Execute Command",
            category="terminal",
            light_description="Run a shell command",
            full_schema={"type": "function", "name": "terminal.execute_command", "params": {"command": "string", "cwd": "string"}},
            governance_rules=GovernanceRules(
                allowed_departments=["engineering", "security", "operations"],
            ),
            estimated_schema_tokens=100,
        ),

        # BrowserAgent operations
        ToolDefinition(
            id="browser.navigate",
            name="Navigate",
            category="browser",
            light_description="Open a URL in browser",
            full_schema={"type": "function", "name": "browser.navigate", "params": {"url": "string"}},
            estimated_schema_tokens=80,
        ),
        ToolDefinition(
            id="browser.screenshot",
            name="Screenshot",
            category="browser",
            light_description="Take a screenshot of current page",
            full_schema={"type": "function", "name": "browser.screenshot", "params": {}},
            estimated_schema_tokens=60,
        ),
        ToolDefinition(
            id="browser.extract_text",
            name="Extract Text",
            category="browser",
            light_description="Extract text from current page",
            full_schema={"type": "function", "name": "browser.extract_text", "params": {"selector": "string"}},
            estimated_schema_tokens=80,
        ),
    ]

    count = registry.register_many(builtin_tools)
    _initialized = True
    logger.info("tlm.initialized", tools_registered=count, total=registry.count)


def get_tlm_selector() -> AdaptiveToolSelector:
    """Get or create the TLM AdaptiveToolSelector singleton."""
    global _selector
    if _selector is None:
        _selector = AdaptiveToolSelector()
    return _selector


# ── Pipeline Helpers ──────────────────────────────────────────

def optimize_tools_for_turn(
    conversation_id: str,
    user_message: str,
) -> dict[str, Any]:
    """Phase-aware tool optimization for the current turn.

    Called BEFORE the LLM call (Stage 7). Analyzes the user message
    with zero-cost heuristics, activates/deactivates tools in
    the SessionManager, and returns the optimized tool context.

    This is the KEY function that saves tokens per turn.
    """
    selector = get_tlm_selector()
    sm = get_tlm_session_manager()
    registry = get_tlm_registry()

    # Get currently active tools
    active = sm.get_active_tools(conversation_id)
    active_ids = [s.tool_id for s in active]

    # Detect phase and get recommendations (zero LLM cost)
    detection = selector.select_tools_for_turn(
        user_message, active_ids, registry.count
    )

    # Deactivate tools not needed for this phase
    for tool_id in detection.deactivate_tools:
        sm.deactivate_tool(tool_id, conversation_id)

    # Activate recommended tools
    for tool_id in detection.recommended_tools:
        if not sm.is_tool_active(tool_id, conversation_id):
            sm.activate_tool(tool_id, conversation_id)

    # Build optimized context (only active schemas)
    proxy = get_tlm_proxy()
    context = proxy.get_context_for_llm(conversation_id)

    context["phase"] = detection.phase
    context["phase_confidence"] = detection.confidence
    context["tools_activated"] = len(detection.recommended_tools)
    context["tools_deactivated"] = len(detection.deactivate_tools)

    logger.info(
        "tlm.phase_optimized",
        phase=detection.phase,
        active_tools=len(context["active_tool_ids"]),
        total_tools=registry.count,
    )

    return context


def get_tool_context_for_llm(conversation_id: str) -> dict[str, Any]:
    """Get tool catalog + active schemas for LLM context injection.

    Called at Stage 7 (BuildRequest) to include tool info in the LLM prompt.
    Returns minimal data to keep token usage low.
    """
    proxy = get_tlm_proxy()
    return proxy.get_context_for_llm(conversation_id)


def record_tool_execution(
    conversation_id: str,
    tool_name: str,
    agent_id: str,
    department: str,
    success: bool = True,
    tokens_saved: int = 0,
) -> None:
    """Record a tool execution in the usage tracker.

    Called after each tool execution in Stage 7.5.
    """
    tracker = get_tlm_tracker()
    with contextlib.suppress(Exception):
        tracker.record_activation(conversation_id, tool_name, agent_id, department)
        tracker.record_call(conversation_id, tool_name, tokens_saved=tokens_saved, error=not success)


def tick_conversation_turn(conversation_id: str) -> dict[str, Any]:
    """Advance one turn for a conversation. Called after each LLM response.

    Returns dict with deactivation info for logging/audit.
    """
    sm = get_tlm_session_manager()
    tracker = get_tlm_tracker()
    report = sm.tick_turn(conversation_id)

    active_count = len(sm.get_active_tools(conversation_id))
    tracker.record_turn_snapshot(conversation_id, active_count)

    return {
        "cooled": report.cooled,
        "deactivated": report.deactivated,
        "active_count": active_count,
    }


def finalize_session(
    conversation_id: str,
    agent_id: str,
    department: str,
) -> dict[str, Any]:
    """Finalize a conversation: generate report, learn patterns, cleanup.

    Called when a chat session ends.
    """
    tracker = get_tlm_tracker()
    bridge = get_tlm_bridge()
    sm = get_tlm_session_manager()

    # Generate usage report
    report = tracker.get_session_report(conversation_id)

    # Learn patterns for NBMF
    if report.tools:
        tool_sequence = [r.tool_id for r in report.tools if r.call_count > 0]
        tool_counts = {r.tool_id: r.call_count for r in report.tools if r.call_count > 0}
        if tool_sequence:
            bridge.learn_from_session(
                conversation_id, agent_id, department,
                tool_sequence=tool_sequence,
                tool_call_counts=tool_counts,
            )

    # Cleanup session state
    sm.clear_conversation(conversation_id)

    return {
        "total_tools_used": report.total_tools_used,
        "total_calls": report.total_calls,
        "total_tokens_saved": report.total_tokens_saved,
        "avg_active_per_turn": report.avg_tools_active_per_turn,
        "duration_seconds": report.duration_seconds,
    }


# ── Reset (for testing) ──────────────────────────────────────

def reset_tlm() -> None:
    """Reset all TLM state. Used in testing only."""
    global _registry, _session_manager, _proxy, _tracker, _bridge, _selector, _initialized
    _registry = None
    _session_manager = None
    _proxy = None
    _tracker = None
    _bridge = None
    _selector = None
    _initialized = False
