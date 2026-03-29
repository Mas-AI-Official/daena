"""SwarmPlanner: decomposes complex tasks and routes subtasks to runtimes.

Uses the Main Mind (highest complex_reasoning runtime) to break a user
task into ordered subtasks with typed dependencies, then routes each
subtask to the best runtime via RuntimeRegistry and estimates costs
via CostEstimator.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import ExecutionReceipt
from app.services.runtimes.cost_estimator import CostEstimator
from app.services.runtimes.registry import RuntimeRegistry

logger = get_logger(__name__)


@dataclass
class SubTask:
    """A single decomposed task unit routed to a runtime.

    Attributes:
        id: Unique identifier for dependency tracking.
        description: Human-readable task description.
        task_type: Capability field name (code_generation, web_research, etc.).
        assigned_runtime: Runtime ID selected by Mind Selection Engine.
        fallback_runtime: Backup runtime if primary fails.
        depends_on: IDs of subtasks that must complete before this one.
        estimated_tokens: Estimated token usage for cost estimation.
        estimated_cost_usd: Pre-execution cost estimate.
        status: Current execution state.
        receipt: Filled after execution completes.
        result_data: Output from the runtime execution.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    task_type: str = "simple_chat"
    assigned_runtime: str = ""
    fallback_runtime: str | None = None
    depends_on: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0
    status: str = "pending"  # pending, running, complete, failed, rejected, cancelled
    receipt: ExecutionReceipt | None = None
    result_data: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/WebSocket transmission."""
        return {
            "id": self.id,
            "description": self.description,
            "task_type": self.task_type,
            "assigned_runtime": self.assigned_runtime,
            "fallback_runtime": self.fallback_runtime,
            "depends_on": self.depends_on,
            "estimated_tokens": self.estimated_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "status": self.status,
            "receipt": self.receipt.to_dict() if self.receipt else None,
        }


_DECOMPOSITION_PROMPT = """\
You are Daena's task decomposition engine. Break the following task into \
subtasks that can be executed by different AI runtimes.

For each subtask, return a JSON object with:
- "description": human-readable description
- "task_type": one of: complex_reasoning, code_generation, code_editing, \
file_operations, web_research, data_analysis, browser_automation, \
simple_chat, bulk_operations
- "depends_on": array of subtask indices (0-based) this depends on
- "estimated_tokens": rough token estimate (500 for simple, 2000 for medium, \
5000 for complex)

Available runtimes and their strengths:
{capabilities_summary}

Task: {task}

Return ONLY a JSON array. No explanation, no markdown.
"""


class SwarmPlanner:
    """Decomposes tasks and routes subtasks to optimal runtimes.

    The planner uses the Main Mind (highest complex_reasoning score)
    to decompose a task, then routes each subtask through the
    Mind Selection Engine for optimal runtime assignment.

    Usage::

        planner = SwarmPlanner(registry, cost_estimator)
        subtasks = await planner.decompose_and_route(
            "Build a REST API with tests",
            context={"cost_ceiling": 0.05}
        )
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        cost_estimator: CostEstimator | None = None,
    ) -> None:
        self._registry = registry
        self._cost = cost_estimator or CostEstimator()

    async def decompose_and_route(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> list[SubTask]:
        """Break a task into subtasks and route each to a runtime.

        Steps:
            1. Use Main Mind to decompose the task into subtasks
            2. Classify each subtask by capability type
            3. Route each to the best runtime via RuntimeRegistry
            4. Identify fallback runtimes
            5. Estimate costs

        Args:
            task: Natural language task description.
            context: Optional context (cost_ceiling, user_preferred_runtime,
                     auto_mode, working_directory, etc.)

        Returns:
            List of SubTask objects ready for SwarmExecutor.
        """
        ctx = context or {}

        # Step 1: Get decomposition from Main Mind (or fallback to single subtask)
        try:
            raw_subtasks = await self._decompose_with_llm(task)
        except Exception as exc:
            logger.warning("swarm.decomposition_failed", error=str(exc))
            raw_subtasks = self._fallback_single_task(task)

        # Step 2-5: Route, estimate, assign fallbacks
        subtasks: list[SubTask] = []
        for _i, raw in enumerate(raw_subtasks):
            st = SubTask(
                id=raw.get("id", str(uuid.uuid4())[:8]),
                description=raw.get("description", task),
                task_type=raw.get("task_type", "simple_chat"),
                estimated_tokens=raw.get("estimated_tokens", 1000),
            )

            # Map depends_on indices to subtask IDs
            dep_indices = raw.get("depends_on", [])
            st.depends_on = [
                subtasks[idx].id
                for idx in dep_indices
                if isinstance(idx, int) and 0 <= idx < len(subtasks)
            ]

            # Route to best runtime
            try:
                st.assigned_runtime = await self._registry.select_runtime(
                    st.task_type,
                    user_preference=ctx.get("user_preferred_runtime"),
                    auto_mode=ctx.get("auto_mode", True),
                    cost_ceiling=ctx.get("cost_ceiling"),
                )
            except Exception:
                st.assigned_runtime = "ollama"

            # Get fallback runtime (second best, excluding primary)
            try:
                st.fallback_runtime = await self._registry.select_runtime(
                    st.task_type,
                    auto_mode=True,
                    cost_ceiling=ctx.get("cost_ceiling"),
                    exclude=[st.assigned_runtime],
                )
            except Exception:
                st.fallback_runtime = None

            # Cost estimate
            estimate = self._cost.estimate(st.assigned_runtime, st.estimated_tokens)
            st.estimated_cost_usd = estimate.estimated_cost_usd

            subtasks.append(st)

        logger.info(
            "swarm.plan_created",
            task_count=len(subtasks),
            runtimes=list({st.assigned_runtime for st in subtasks}),
            total_estimated_cost=sum(st.estimated_cost_usd for st in subtasks),
        )

        return subtasks

    async def _decompose_with_llm(self, task: str) -> list[dict]:
        """Use LLM to decompose task into structured subtasks."""
        import httpx

        from app.core.config import get_settings

        settings = get_settings()
        caps_summary = await self._registry.get_capabilities_summary()

        prompt = _DECOMPOSITION_PROMPT.format(
            capabilities_summary=caps_summary,
            task=task,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("message", {}).get("content", "")

        return self._parse_decomposition(raw)

    def _parse_decomposition(self, raw: str) -> list[dict]:
        """Parse LLM JSON response into subtask dicts."""
        text = raw.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "subtasks" in parsed:
                return parsed["subtasks"]
        except json.JSONDecodeError:
            pass

        # Attempt to extract JSON array from mixed output
        import re
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("swarm.parse_failed", raw_length=len(raw))
        return []

    def _fallback_single_task(self, task: str) -> list[dict]:
        """When decomposition fails, wrap entire task as single subtask."""
        return [
            {
                "description": task,
                "task_type": "complex_reasoning",
                "depends_on": [],
                "estimated_tokens": 2000,
            }
        ]
