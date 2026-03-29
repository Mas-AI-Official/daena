"""Tool Lifecycle Manager (TLM) -- manages tool discovery, activation,
session tracking, usage analytics, and NBMF memory integration.

Sits AFTER Orchestra routes to an agent, BEFORE tool execution.
Zero accuracy loss: the LLM tells us what tools it wants, we intercept,
activate/deactivate as needed.

Components:
    - ToolRegistry: catalog of all known tools with governance rules
    - SessionManager: per-conversation tool activation state
    - ActivationProxy: intercepts tool_calls, activates/deactivates
    - UsageTracker: analytics and cost savings tracking
    - NBMFBridge: predictive tool activation from memory patterns
"""


def __getattr__(name: str):
    """Lazy imports to allow building components incrementally."""
    if name == "ToolRegistry":
        from app.services.tool_lifecycle.tool_registry import ToolRegistry
        return ToolRegistry
    if name == "SessionManager":
        from app.services.tool_lifecycle.session_manager import SessionManager
        return SessionManager
    if name == "ActivationProxy":
        from app.services.tool_lifecycle.activation_proxy import ActivationProxy
        return ActivationProxy
    if name == "UsageTracker":
        from app.services.tool_lifecycle.usage_tracker import UsageTracker
        return UsageTracker
    if name == "NBMFBridge":
        from app.services.tool_lifecycle.nbmf_bridge import NBMFBridge
        return NBMFBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
