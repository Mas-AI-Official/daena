"""Activation Proxy -- intercepts tool_calls between LLM response and execution.

The CORE component of TLM. Sits AFTER Orchestra, BEFORE tool execution:

    1. LLM generates response with tool_calls
    2. ActivationProxy intercepts each tool_call
    3. For each call:
       a. Active tool -> pass through to executor
       b. Registered but inactive -> activate (load schema, open connection) -> execute
       c. Not registered -> error
       d. Blocked by governance -> reject with reason
    4. After execution, update lastUsedAt via SessionManager
    5. Run tickTurn() to handle idle deactivations
    6. Return ProxyResult with execution results + cost savings
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from app.services.tool_lifecycle.tool_registry import ToolRegistry
from app.services.tool_lifecycle.session_manager import SessionManager, ToolStatus


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool invocation request from the LLM."""

    tool_id: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True, slots=True)
class ToolCallResult:
    """Result of executing a single tool call."""

    tool_id: str
    success: bool
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class BlockedCall:
    """A tool call that was blocked by governance."""

    tool_id: str
    reason: str


@dataclass(slots=True)
class CostSavings:
    """Tokens saved by not loading inactive tool schemas."""

    tokens_not_loaded: int = 0
    connections_avoided: int = 0


@dataclass(slots=True)
class ProxyResult:
    """Complete result of a proxy interception round."""

    executed: list[ToolCallResult] = field(default_factory=list)
    activated: list[str] = field(default_factory=list)
    deactivated: list[str] = field(default_factory=list)
    blocked: list[BlockedCall] = field(default_factory=list)
    cost_savings: CostSavings = field(default_factory=CostSavings)
    errors: list[str] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.executed) and not self.errors


# Type alias for the actual tool executor function
# Given (tool_id, params) -> result dict
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class ActivationProxy:
    """Intercepts and manages tool calls with lifecycle awareness.

    Usage:
        proxy = ActivationProxy(registry, session_manager)
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("google_drive", {"query": "budget"})],
            conversation_id="conv-123",
            department="finance",
            executor=my_tool_executor,
        )
    """

    def __init__(
        self,
        registry: ToolRegistry,
        session_manager: SessionManager,
    ) -> None:
        self.registry = registry
        self.session_manager = session_manager

    async def intercept_and_execute(
        self,
        tool_calls: list[ToolCall],
        conversation_id: str,
        department: str,
        executor: ToolExecutor,
        agent_id: str | None = None,
    ) -> ProxyResult:
        """Intercept tool calls, activate/block as needed, execute, track.

        Args:
            tool_calls: tool invocations from LLM response
            conversation_id: current conversation/session ID
            department: agent's department for governance checks
            executor: async function that actually executes a tool call
            agent_id: optional agent identifier for finer governance

        Returns:
            ProxyResult with executed results, activated/deactivated lists,
            blocked calls, and cost savings.
        """
        result = ProxyResult()

        # Calculate baseline token cost (all schemas loaded)
        total_tokens = self.registry.get_total_schema_tokens()
        active_before = self.session_manager.get_active_tools(conversation_id)
        active_ids_before = {s.tool_id for s in active_before}

        for call in tool_calls:
            call_result = await self._process_single_call(
                call=call,
                conversation_id=conversation_id,
                department=department,
                executor=executor,
                agent_id=agent_id,
                result=result,
            )
            if call_result is not None:
                result.executed.append(call_result)

        # After all executions, tick the turn to handle deactivations
        deactivation_report = self.session_manager.tick_turn(conversation_id)
        result.deactivated.extend(deactivation_report.deactivated)
        result.deactivated.extend(deactivation_report.evicted)

        # Calculate cost savings
        active_after = self.session_manager.get_active_tools(conversation_id)
        active_ids_after = {s.tool_id for s in active_after}
        inactive_tokens = self.registry.get_total_schema_tokens(
            [tid for tid in self.registry.all_tool_ids() if tid not in active_ids_after]
        )
        result.cost_savings.tokens_not_loaded = inactive_tokens
        result.cost_savings.connections_avoided = len(
            [tid for tid in self.registry.all_tool_ids() if tid not in active_ids_after]
        )

        return result

    async def _process_single_call(
        self,
        call: ToolCall,
        conversation_id: str,
        department: str,
        executor: ToolExecutor,
        agent_id: str | None,
        result: ProxyResult,
    ) -> ToolCallResult | None:
        """Process a single tool call through the activation pipeline."""

        # Step 1: Check if tool is registered
        tool_def = self.registry.get_tool(call.tool_id)
        if tool_def is None:
            error_msg = f"Tool '{call.tool_id}' not registered in TLM"
            result.errors.append(error_msg)
            return ToolCallResult(
                tool_id=call.tool_id,
                success=False,
                error=error_msg,
            )

        # Step 2: Governance check
        allowed, reason = self.registry.is_tool_allowed(
            call.tool_id, department, agent_id
        )
        if not allowed:
            result.blocked.append(BlockedCall(tool_id=call.tool_id, reason=reason))
            return None

        # Step 3: Activate if not already active
        was_inactive = not self.session_manager.is_tool_active(
            call.tool_id, conversation_id
        )
        if was_inactive:
            self.session_manager.activate_tool(call.tool_id, conversation_id)
            result.activated.append(call.tool_id)

        # Step 4: Execute
        start = time.perf_counter()
        try:
            exec_result = await executor(call.tool_id, call.params)
            latency_ms = (time.perf_counter() - start) * 1000
            call_result = ToolCallResult(
                tool_id=call.tool_id,
                success=True,
                result=exec_result,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            call_result = ToolCallResult(
                tool_id=call.tool_id,
                success=False,
                error=str(exc),
                latency_ms=latency_ms,
            )

        # Step 5: Record usage (resets idle counter)
        self.session_manager.record_use(call.tool_id, conversation_id)

        return call_result

    def get_context_for_llm(self, conversation_id: str) -> dict[str, Any]:
        """Build the tool context to inject into LLM messages.

        Returns:
            {
                "catalog": [...],  # lightweight catalog for ALL tools
                "active_schemas": {...},  # full schemas ONLY for active tools
                "active_tool_ids": [...],
            }
        """
        catalog = self.registry.get_tool_catalog()
        active_sessions = self.session_manager.get_active_tools(conversation_id)
        active_ids = [s.tool_id for s in active_sessions]

        active_schemas = {}
        for tool_id in active_ids:
            schema = self.registry.get_full_schema(tool_id)
            if schema:
                active_schemas[tool_id] = schema

        return {
            "catalog": [
                {"id": e.id, "name": e.name, "description": e.light_description}
                for e in catalog
            ],
            "active_schemas": active_schemas,
            "active_tool_ids": active_ids,
        }
