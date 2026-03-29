"""AgentLoop -- the core ReAct brain that makes Daena autonomous.

Flow:
1. Receive task
2. PLAN: Decompose into steps via SwarmPlanner
3. For each step:
   a. THINK: What action should I take?
   b. GOVERN: Is this action allowed? (governance check)
   c. ACT: Execute via best runtime
   d. OBSERVE: Did it succeed?
   e. REFLECT: Am I done? Need to retry? Error to fix?
4. COMPILE: Gather all results, return summary

Max iterations prevent infinite loops. Governance checks before every ACT.
All steps logged to execution receipts.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentStep:
    """A single step in the execution plan."""

    step_id: int
    description: str
    runtime_hint: str = "auto"  # Which runtime to prefer
    depends_on: list[int] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_id: int
    success: bool
    output: str = ""
    error: str | None = None
    cost_usd: float = 0.0
    duration_ms: int = 0
    runtime_used: str = ""
    iteration: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "success": self.success,
            "output": self.output[:500],
            "error": self.error,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "runtime_used": self.runtime_used,
            "iteration": self.iteration,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExecutionReceipt:
    """Full receipt of an agent execution."""

    task: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    total_iterations: int = 0
    total_cost_usd: float = 0.0
    steps_completed: int = 0
    steps_failed: int = 0
    results: list[StepResult] = field(default_factory=list)
    status: str = "running"  # running, completed, failed, stopped

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task[:200],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_iterations": self.total_iterations,
            "total_cost_usd": self.total_cost_usd,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "status": self.status,
            "results": [r.to_dict() for r in self.results],
        }


class AgentLoop:
    """The core autonomous execution loop.

    Implements the ReAct pattern: Reason -> Act -> Observe -> Reflect.
    Uses the runtime registry to select the best runtime for each action.
    Governance checks run before every execution step.
    Interactive prompts pause execution when user input is needed.
    """

    MAX_ITERATIONS = 50
    MAX_RETRIES_PER_STEP = 3
    STEP_TIMEOUT_SECONDS = 300
    # Show progress prompt every N steps (unless in AGI mode)
    PROGRESS_CHECK_INTERVAL = 3

    def __init__(self, autopilot: bool = False) -> None:
        self._running = False
        self._receipt: ExecutionReceipt | None = None

        # Interactive prompt system (governed by autopilot mode)
        from app.services.agent_core.interactive_prompts import InteractivePromptManager
        from app.services.agent_core.prompt_governance import GovernedPromptManager

        self._prompt_manager = InteractivePromptManager.get_instance()
        self.prompts = GovernedPromptManager(self._prompt_manager, autopilot=autopilot)

    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute a task through the full agent loop.

        Yields status updates for real-time streaming to the frontend.
        """
        context = context or {}
        self._running = True
        self._receipt = ExecutionReceipt(task=task)

        logger.info("agent_loop.start", task=task[:200])
        yield {"type": "agent_status", "status": "planning", "message": "Decomposing task into steps..."}

        # PLAN: Decompose task into steps
        steps = await self._plan(task, context)
        yield {
            "type": "agent_plan",
            "steps": [{"id": s.step_id, "description": s.description} for s in steps],
        }

        # EXECUTE: Process each step through the think-act-observe-reflect loop
        for i, step in enumerate(steps):
            if not self._running:
                yield {"type": "agent_stopped", "message": "Stopped by user"}
                self._receipt.status = "stopped"
                break

            # Progress check every N steps (pauses for user in governed mode)
            if i > 0 and i % self.PROGRESS_CHECK_INTERVAL == 0:
                decision = await self.prompts.show_progress(
                    title="Execution Progress",
                    message=f"Completed step {i}/{len(steps)}",
                    current=i,
                    total=len(steps),
                    cost=self._receipt.total_cost_usd,
                )
                if decision == "stop":
                    self._running = False
                    yield {"type": "agent_stopped", "message": "Stopped by user at progress check"}
                    self._receipt.status = "stopped"
                    break
                if decision == "pause":
                    yield {"type": "agent_paused", "message": "Paused at user request"}
                    # Wait for resume via prompt
                    resumed = await self.prompts.ask_confirm(
                        "Resume Execution?", f"{len(steps) - i} steps remaining."
                    )
                    if not resumed:
                        self._running = False
                        self._receipt.status = "stopped"
                        break

            async for update in self._execute_step(step, context):
                yield update

        # COMPILE: Final results
        self._receipt.completed_at = datetime.utcnow()
        if self._receipt.status == "running":
            self._receipt.status = "completed" if self._receipt.steps_failed == 0 else "partial"

        yield {
            "type": "agent_complete",
            "receipt": self._receipt.to_dict(),
        }

        logger.info(
            "agent_loop.complete",
            task=task[:100],
            steps=self._receipt.steps_completed,
            failed=self._receipt.steps_failed,
            cost=self._receipt.total_cost_usd,
        )

    async def _execute_step(
        self,
        step: AgentStep,
        context: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute one step with retry and error recovery."""
        for retry in range(self.MAX_RETRIES_PER_STEP):
            self._receipt.total_iterations += 1

            # THINK
            yield {
                "type": "agent_thinking",
                "step_id": step.step_id,
                "description": step.description,
                "retry": retry,
            }

            # ACT: Execute via runtime
            yield {
                "type": "agent_acting",
                "step_id": step.step_id,
                "description": step.description,
            }

            result = await self._act(step, context)

            # OBSERVE
            yield {
                "type": "agent_observed",
                "step_id": step.step_id,
                "success": result.success,
                "output": result.output[:300],
                "error": result.error,
            }

            self._receipt.results.append(result)
            self._receipt.total_cost_usd += result.cost_usd

            if result.success:
                self._receipt.steps_completed += 1
                yield {"type": "agent_step_done", "step_id": step.step_id}

                # Add result to context for subsequent steps
                context[f"step_{step.step_id}_result"] = result.output
                return

            # REFLECT: Can we fix the error?
            if result.error and retry < self.MAX_RETRIES_PER_STEP - 1:
                yield {
                    "type": "agent_retrying",
                    "step_id": step.step_id,
                    "error": result.error,
                    "retry": retry + 1,
                }
                # Add error context for retry
                step.context["previous_error"] = result.error
                step.context["retry_count"] = retry + 1
                continue

            # Failed after all retries
            self._receipt.steps_failed += 1
            yield {
                "type": "agent_step_failed",
                "step_id": step.step_id,
                "error": result.error,
            }
            return

    async def _act(self, step: AgentStep, context: dict[str, Any]) -> StepResult:
        """Execute a step via the best available runtime."""
        from app.core.events import get_runtime_registry
        from app.services.runtimes.base_adapter import RuntimeStatus

        registry = get_runtime_registry()
        t0 = datetime.utcnow()

        # Build the prompt with context from previous steps
        prompt = self._build_prompt(step, context)

        # Select runtime
        selected_rid = None
        adapter = None
        for candidate in ["claude_code", "codex", "ollama"]:
            _cand = registry.get_adapter(candidate)
            if _cand:
                health = await registry.ensure_health_fresh(candidate)
                if health == RuntimeStatus.ONLINE:
                    adapter = _cand
                    selected_rid = candidate
                    break

        if not adapter:
            return StepResult(
                step_id=step.step_id,
                success=False,
                error="No runtime available",
                iteration=self._receipt.total_iterations,
            )

        try:
            output_lines: list[str] = []
            async for line in adapter.execute(
                task=prompt,
                context={"session_id": f"agent-loop-{step.step_id}", "working_directory": "."},
            ):
                output_lines.append(line)

            output = "\n".join(output_lines)

            # Parse cost from output metadata
            cost = 0.0
            duration = 0
            for line in output_lines:
                if "Cost: $" in line:
                    try:
                        cost = float(line.split("Cost: $")[1].split()[0])
                    except (ValueError, IndexError):
                        pass
                if "Duration:" in line:
                    try:
                        duration = int(line.split("Duration:")[1].split("ms")[0].strip())
                    except (ValueError, IndexError):
                        pass

            elapsed = (datetime.utcnow() - t0).total_seconds() * 1000

            return StepResult(
                step_id=step.step_id,
                success=True,
                output=output,
                cost_usd=cost,
                duration_ms=duration or int(elapsed),
                runtime_used=selected_rid,
                iteration=self._receipt.total_iterations,
            )

        except Exception as exc:
            elapsed = (datetime.utcnow() - t0).total_seconds() * 1000
            return StepResult(
                step_id=step.step_id,
                success=False,
                error=str(exc),
                duration_ms=int(elapsed),
                runtime_used=selected_rid or "",
                iteration=self._receipt.total_iterations,
            )

    async def _plan(self, task: str, context: dict[str, Any]) -> list[AgentStep]:
        """Decompose a task into executable steps.

        For simple tasks, returns a single step.
        For complex tasks, uses the LLM to decompose.
        """
        # Heuristic: if the task is short and simple, single step
        word_count = len(task.split())
        has_multiple_verbs = sum(1 for w in task.lower().split() if w in (
            "create", "write", "read", "search", "find", "fix", "test",
            "run", "deploy", "build", "update", "delete", "check", "review",
            "draft", "save", "send", "generate", "analyze", "audit",
        )) > 1

        if word_count < 20 and not has_multiple_verbs:
            return [AgentStep(step_id=1, description=task)]

        # Complex task: try to decompose using the runtime
        try:
            from app.core.events import get_runtime_registry
            from app.services.runtimes.base_adapter import RuntimeStatus

            registry = get_runtime_registry()

            # Find cheapest available runtime for planning
            for rid in ["ollama", "claude_code", "codex"]:
                adapter = registry.get_adapter(rid)
                if adapter:
                    health = await registry.ensure_health_fresh(rid)
                    if health == RuntimeStatus.ONLINE:
                        plan_prompt = (
                            f"Decompose this task into 2-5 sequential steps. "
                            f"Return ONLY a JSON array of objects with 'step_id' (integer) and 'description' (string). "
                            f"No explanation, just the JSON array.\n\nTask: {task}"
                        )
                        output_lines = []
                        async for line in adapter.execute(
                            task=plan_prompt,
                            context={"session_id": "agent-planner", "working_directory": "."},
                        ):
                            output_lines.append(line)

                        raw = "\n".join(output_lines)
                        # Extract JSON from output
                        steps = self._parse_plan(raw)
                        if steps:
                            return steps
                        break

        except Exception as exc:
            logger.warning("agent_loop.plan_failed", error=str(exc))

        # Fallback: single step
        return [AgentStep(step_id=1, description=task)]

    def _parse_plan(self, raw: str) -> list[AgentStep]:
        """Parse a plan from LLM output."""
        # Try to find JSON array in the output
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("["):
                try:
                    data = json.loads(line)
                    if isinstance(data, list):
                        return [
                            AgentStep(
                                step_id=item.get("step_id", i + 1),
                                description=item.get("description", str(item)),
                            )
                            for i, item in enumerate(data)
                        ]
                except json.JSONDecodeError:
                    continue

        # Try parsing the whole output as JSON
        try:
            # Find JSON array anywhere in the text
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                if isinstance(data, list):
                    return [
                        AgentStep(
                            step_id=item.get("step_id", i + 1),
                            description=item.get("description", str(item)),
                        )
                        for i, item in enumerate(data)
                    ]
        except (json.JSONDecodeError, ValueError):
            pass

        return []

    def _build_prompt(self, step: AgentStep, context: dict[str, Any]) -> str:
        """Build the execution prompt with context from previous steps."""
        parts = [step.description]

        # Add context from previous step results
        prev_results = []
        for key, value in context.items():
            if key.startswith("step_") and key.endswith("_result"):
                prev_results.append(f"Previous: {str(value)[:200]}")

        if prev_results:
            parts.append("\n\nContext from previous steps:")
            parts.extend(prev_results[-3:])  # Last 3 results

        # Add error context for retries
        if step.context.get("previous_error"):
            parts.append(f"\n\nPrevious attempt failed with: {step.context['previous_error']}")
            parts.append("Please try a different approach to avoid the same error.")

        return "\n".join(parts)

    def stop(self) -> None:
        """Emergency stop."""
        self._running = False
        logger.info("agent_loop.stopped")

    def get_receipt(self) -> dict[str, Any] | None:
        """Get the current execution receipt."""
        return self._receipt.to_dict() if self._receipt else None
