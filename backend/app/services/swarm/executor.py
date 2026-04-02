"""SwarmExecutor: parallel task execution with dependency resolution.

Executes subtasks from SwarmPlanner in parallel where dependencies
allow, with governance checks before each task, automatic fallback
on failure, and full audit trail via ExecutionReceipts.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import ExecutionReceipt, RuntimeStatus
from app.services.runtimes.cost_estimator import CostEstimator
from app.services.runtimes.registry import RuntimeRegistry
from app.services.swarm.planner import SubTask

logger = get_logger(__name__)

# Global maximum parallel subtasks
MAX_PARALLEL_SUBTASKS = 40

# Per-runtime concurrency limits to prevent overload
RUNTIME_CONCURRENCY_LIMITS: dict[str, int] = {
    "claude_code": 8,   # Each spawns a subprocess
    "codex": 8,          # Each spawns a subprocess
    "gemini_cli": 5,     # Rate-limited by Google
    "grok_cli": 5,
    "ollama": 4,          # GPU memory bound (1 model at a time on most GPUs)
}
DEFAULT_RUNTIME_CONCURRENCY = 5

# Per-subtask execution timeout (seconds)
SUBTASK_TIMEOUT = 300.0


class SwarmExecutor:
    """Runs subtasks in parallel where dependencies allow.

    Processes the SubTask dependency DAG layer by layer:
    1. Find all subtasks whose dependencies are satisfied
    2. Run governance check on each (if governance engine provided)
    3. Execute approved tasks in parallel via runtime adapters
    4. On failure: attempt fallback runtime, then mark failed
    5. Collect ExecutionReceipts for audit trail

    Usage::

        executor = SwarmExecutor(registry, cost_estimator)
        receipts = await executor.execute_plan(subtasks, context)
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        cost_estimator: CostEstimator | None = None,
        governance_engine: Any = None,
    ) -> None:
        self._registry = registry
        self._cost = cost_estimator or CostEstimator()
        self._governance = governance_engine
        self._cancelled = False
        # Per-runtime semaphores for concurrent execution control
        self._runtime_semaphores: dict[str, asyncio.Semaphore] = {
            rid: asyncio.Semaphore(limit)
            for rid, limit in RUNTIME_CONCURRENCY_LIMITS.items()
        }

    def cancel(self) -> None:
        """Signal cancellation to stop processing new subtasks."""
        self._cancelled = True

    async def execute_plan(
        self,
        subtasks: list[SubTask],
        context: dict[str, Any] | None = None,
    ) -> list[ExecutionReceipt]:
        """Execute a plan of subtasks respecting dependencies.

        Args:
            subtasks: List of SubTask objects from SwarmPlanner.
            context: Execution context (governance_slider, user_id, etc.).

        Returns:
            List of ExecutionReceipts for all executed subtasks.
        """
        ctx = context or {}
        receipts: list[ExecutionReceipt] = []
        completed: set[str] = set()
        failed: set[str] = set()
        semaphore = asyncio.Semaphore(MAX_PARALLEL_SUBTASKS)

        while len(completed) + len(failed) < len(subtasks):
            if self._cancelled:
                logger.info("swarm.execution_cancelled")
                break

            # Find ready subtasks (all dependencies met, not yet started)
            ready = [
                st for st in subtasks
                if st.id not in completed
                and st.id not in failed
                and st.status == "pending"
                and all(dep in completed for dep in st.depends_on)
            ]

            # Check for deadlock: no ready tasks but not all done
            if not ready:
                # Check if remaining tasks depend on failed tasks
                remaining = [
                    st for st in subtasks
                    if st.id not in completed and st.id not in failed
                ]
                if remaining:
                    for st in remaining:
                        if any(dep in failed for dep in st.depends_on):
                            st.status = "failed"
                            failed.add(st.id)
                            st.receipt = self._make_receipt(
                                st, "failed",
                                error="Dependency failed",
                                duration_ms=0,
                            )
                            receipts.append(st.receipt)
                    # Re-check after marking dependency failures
                    if not any(
                        st for st in subtasks
                        if st.id not in completed
                        and st.id not in failed
                        and st.status == "pending"
                        and all(dep in completed for dep in st.depends_on)
                    ):
                        break
                    continue
                break

            # Execute ready subtasks in parallel
            tasks = [
                self._execute_with_semaphore(semaphore, st, ctx)
                for st in ready
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for st, result in zip(ready, results, strict=True):
                if isinstance(result, Exception):
                    logger.error(
                        "swarm.subtask_exception",
                        subtask_id=st.id,
                        error=str(result),
                    )
                    st.status = "failed"
                    failed.add(st.id)
                    st.receipt = self._make_receipt(
                        st, "error",
                        error=str(result),
                        duration_ms=0,
                    )
                    receipts.append(st.receipt)
                elif isinstance(result, ExecutionReceipt):
                    receipts.append(result)
                    if result.status == "success":
                        completed.add(st.id)
                    else:
                        failed.add(st.id)

        logger.info(
            "swarm.plan_execution_complete",
            completed=len(completed),
            failed=len(failed),
            total=len(subtasks),
            total_cost=sum(r.estimated_cost_usd for r in receipts),
        )

        return receipts

    async def execute_single(
        self,
        subtask: SubTask,
        context: dict[str, Any] | None = None,
    ) -> ExecutionReceipt:
        """Execute a single subtask. Used by Autopilot continuation loop.

        Args:
            subtask: The subtask to execute.
            context: Execution context.

        Returns:
            ExecutionReceipt for the execution.
        """
        ctx = context or {}
        return await self._execute_subtask(subtask, ctx)

    async def _execute_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        subtask: SubTask,
        context: dict[str, Any],
    ) -> ExecutionReceipt:
        """Wrap execution with global + per-runtime concurrency limiters.

        Two-layer gating:
        1. Global semaphore (40 total) prevents total system overload
        2. Per-runtime semaphore (e.g., 8 for Claude Code) prevents
           overloading any single runtime
        """
        # Get per-runtime semaphore
        rid = subtask.assigned_runtime
        rt_sem = self._runtime_semaphores.get(
            rid,
            asyncio.Semaphore(DEFAULT_RUNTIME_CONCURRENCY),
        )

        async with semaphore:
            async with rt_sem:
                return await self._execute_subtask(subtask, context)

    async def _execute_subtask(
        self,
        subtask: SubTask,
        context: dict[str, Any],
    ) -> ExecutionReceipt:
        """Execute a single subtask with fallback on failure.

        Steps:
            1. Optional governance check
            2. Execute on assigned runtime
            3. On failure, try fallback runtime
            4. Return receipt
        """
        subtask.status = "running"
        start = time.perf_counter()

        # Optional governance check
        if self._governance:
            try:
                gov_result = await self._governance.evaluate(
                    action_type="RUNTIME_EXECUTION",
                    action_params={
                        "task_type": subtask.task_type,
                        "runtime": subtask.assigned_runtime,
                        "description": subtask.description[:200],
                    },
                    governance_slider=context.get("governance_slider", "STANDARD"),
                    actor_type="SYSTEM",
                    actor_role=context.get("user_role", "OPERATOR"),
                    tenant_id=context.get("tenant_id"),
                    user_id=context.get("user_id"),
                    session_id=context.get("session_id"),
                )
                if not gov_result.get("allowed", True):
                    subtask.status = "rejected"
                    duration = int((time.perf_counter() - start) * 1000)
                    receipt = self._make_receipt(
                        subtask, "rejected",
                        error=gov_result.get("message", "Governance rejected"),
                        duration_ms=duration,
                    )
                    subtask.receipt = receipt
                    return receipt
            except Exception as exc:
                logger.warning(
                    "swarm.governance_check_failed",
                    subtask_id=subtask.id,
                    error=str(exc),
                )
                # Fail-safe: proceed without governance if engine errors

        # Execute on primary runtime
        result = await self._try_runtime(subtask, subtask.assigned_runtime, context)
        if result.status == "success":
            subtask.status = "complete"
            subtask.receipt = result
            return result

        # Try fallback runtime
        if subtask.fallback_runtime:
            logger.info(
                "swarm.trying_fallback",
                subtask_id=subtask.id,
                primary=subtask.assigned_runtime,
                fallback=subtask.fallback_runtime,
            )
            result = await self._try_runtime(
                subtask, subtask.fallback_runtime, context,
            )
            if result.status == "success":
                subtask.status = "complete"
                subtask.receipt = result
                return result

        # Both failed
        subtask.status = "failed"
        subtask.receipt = result
        return result

    async def _try_runtime(
        self,
        subtask: SubTask,
        runtime_id: str,
        context: dict[str, Any],
    ) -> ExecutionReceipt:
        """Attempt execution on a specific runtime.

        Streams output, collects result, builds receipt.
        """
        start = time.perf_counter()
        adapter = self._registry.get_adapter(runtime_id)

        if adapter is None:
            duration = int((time.perf_counter() - start) * 1000)
            return self._make_receipt(
                subtask, "error",
                error=f"Runtime '{runtime_id}' not registered",
                duration_ms=duration,
                runtime_override=runtime_id,
            )

        # Check health
        health = self._registry.get_health(runtime_id)
        if health != RuntimeStatus.ONLINE:
            duration = int((time.perf_counter() - start) * 1000)
            return self._make_receipt(
                subtask, "error",
                error=f"Runtime '{runtime_id}' is {health.value}",
                duration_ms=duration,
                runtime_override=runtime_id,
            )

        # Execute with timeout
        output_chunks: list[str] = []
        try:
            await asyncio.wait_for(
                self._collect_output(adapter, subtask, context, output_chunks),
                timeout=SUBTASK_TIMEOUT,
            )
        except TimeoutError:
            duration = int((time.perf_counter() - start) * 1000)
            return self._make_receipt(
                subtask, "timeout",
                error=f"Execution timed out after {SUBTASK_TIMEOUT}s",
                duration_ms=duration,
                runtime_override=runtime_id,
                output="".join(output_chunks),
            )
        except Exception as exc:
            duration = int((time.perf_counter() - start) * 1000)
            return self._make_receipt(
                subtask, "error",
                error=str(exc),
                duration_ms=duration,
                runtime_override=runtime_id,
                output="".join(output_chunks),
            )

        duration = int((time.perf_counter() - start) * 1000)
        output = "".join(output_chunks)
        subtask.result_data = output

        # Record actual cost (approximate: 30% input, 70% output)
        input_tokens = int(subtask.estimated_tokens * 0.3)
        output_tokens = subtask.estimated_tokens - input_tokens
        self._cost.record_actual(
            "default",  # session_id placeholder
            runtime_id,
            input_tokens,
            output_tokens,
        )

        return self._make_receipt(
            subtask, "success",
            duration_ms=duration,
            runtime_override=runtime_id,
            output=output,
        )

    async def _collect_output(
        self,
        adapter: Any,
        subtask: SubTask,
        context: dict[str, Any],
        output_chunks: list[str],
    ) -> None:
        """Collect streaming output from a runtime adapter.

        If the subtask is routed to a department agent, injects the
        agent's specialized prompt into the task description.
        """
        task_desc = subtask.description

        # Inject department agent prompt if routed
        dept = subtask.metadata.get("department")
        sub_cap = subtask.metadata.get("sub_capability")
        if dept and sub_cap:
            try:
                from app.services.department_prompts import get_agent_prompt
                agent_prompt = get_agent_prompt(dept, sub_cap)
                task_desc = f"[{dept}.{sub_cap}] {agent_prompt}\n\nTASK: {task_desc}"
            except Exception:
                pass  # Fall back to plain description

        async for chunk in adapter.execute(task_desc, context):
            output_chunks.append(chunk)

    def _make_receipt(
        self,
        subtask: SubTask,
        status: str,
        *,
        error: str | None = None,
        duration_ms: int = 0,
        runtime_override: str | None = None,
        output: str = "",
    ) -> ExecutionReceipt:
        """Create an ExecutionReceipt for audit trail."""
        now = datetime.now(UTC).isoformat()
        return ExecutionReceipt(
            runtime_id=runtime_override or subtask.assigned_runtime,
            task_description=subtask.description[:200],
            assigned_reason=f"Best for {subtask.task_type}",
            capability_score=0.0,
            start_time=now,
            end_time=now,
            duration_ms=duration_ms,
            token_count=subtask.estimated_tokens,
            estimated_cost_usd=subtask.estimated_cost_usd,
            status=status,
            output_summary=output[:500] if output else error or "",
            governance_tier="auto",
            approved_by="auto",
            error_detail=error,
        )
