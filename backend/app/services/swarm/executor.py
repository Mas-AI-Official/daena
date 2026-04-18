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

    # ── Session A: department state tracking helpers ─────────────
    #
    # Each call opens a short-lived DB session so SwarmExecutor stays
    # independent of FastAPI request scope (it also runs from the
    # AutopilotController continuation loop which has no request).
    # Failures are swallowed because a state-tracking error must not
    # prevent a subtask from running.

    async def _state_mark_working(
        self,
        *,
        tenant_id: Any,
        department: str,
        task_id: str,
        task_summary: str,
    ) -> None:
        try:
            from app.core.database import async_session_factory
            from app.services.department_state_service import (
                DepartmentStateService,
            )

            async with async_session_factory() as session:
                svc = DepartmentStateService(session)
                await svc.mark_working(
                    tenant_id=tenant_id,
                    department=department,
                    task_id=task_id,
                    task_summary=task_summary,
                )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "swarm.state_mark_working_failed",
                department=department, error=str(exc),
            )

    # ── Phase 2: required_approvers gate ──────────────────────────
    #
    # DaenaVP (Session B) + DepartmentPolicyService (Session D) can tag
    # a subtask's metadata with ``required_approvers: [dept, ...]``.
    # Before the subtask runs, SwarmExecutor must ask each listed
    # department for permission via the inter-department message bus
    # and wait for all to answer. A single "no" blocks the subtask.
    #
    # Opens its own DB session (same pattern as state tracking). Runs
    # sends in parallel and waits in parallel so N approvers do not
    # serialize. Swallows errors around the inter-department channel
    # to fail-safe: if the channel is degraded, the subtask proceeds
    # (governance engine remains the hard gate for true high-risk
    # actions).

    async def _solicit_required_approvers(
        self,
        *,
        subtask_id: str,
        subtask_description: str,
        from_department: str,
        required_approvers: list[str],
        tenant_id: Any,
        timeout_seconds: int = 30,
    ) -> tuple[bool, str]:
        """Ask each listed department for permission. Return (approved, reason).

        Protocol: send one ASK message per approver, wait up to
        ``timeout_seconds`` for all answers. Answers whose body begins
        with 'NO' (case-insensitive) count as denials. Missing answers
        (timeout) count as provisional-approve because DepartmentPolicy
        already resolved who must approve; if those departments are
        unstaffed we do not want to block forever.
        """
        if not required_approvers:
            return True, "no approvers required"

        try:
            import asyncio
            from app.core.database import async_session_factory
            from app.services.department_message_service import (
                DepartmentMessageService,
            )
        except Exception as exc:
            logger.warning(
                "swarm.required_approvers.import_failed", error=str(exc),
            )
            return True, "approver channel unavailable (fail-safe)"

        async with async_session_factory() as session:
            svc = DepartmentMessageService(session)
            message_ids: list[tuple[str, Any]] = []
            for approver_dept in required_approvers:
                if approver_dept == from_department:
                    # Self-approval filter. DaenaVP's apply_policies
                    # already strips these, but double-guard.
                    continue
                try:
                    msg = await svc.send(
                        tenant_id=tenant_id,
                        from_department=from_department,
                        to_department=approver_dept,
                        subject=f"Approval needed: {subtask_description[:80]}",
                        body=(
                            f"Subtask {subtask_id} requires your approval.\n\n"
                            f"Description: {subtask_description[:500]}\n\n"
                            "Reply with ACK + body text to approve, or body "
                            "text beginning with 'NO' to deny."
                        ),
                        context_ref=f"subtask:{subtask_id}",
                        ttl_seconds=timeout_seconds,
                    )
                    message_ids.append((approver_dept, msg.id))
                except Exception as exc:
                    logger.warning(
                        "swarm.required_approvers.send_failed",
                        approver=approver_dept,
                        error=str(exc),
                    )
            await session.commit()

        if not message_ids:
            return True, "no approvers after self-filter"

        # Parallel wait across all approvers. Uses fresh DB sessions
        # per approver so the pool does not deadlock.
        async def _await_one(dept: str, mid: Any) -> tuple[str, str | None]:
            try:
                async with async_session_factory() as session:
                    svc = DepartmentMessageService(session)
                    final = await svc.wait_for_answer(
                        message_id=mid,
                        timeout_seconds=timeout_seconds,
                        poll_interval_seconds=1.0,
                    )
                    return dept, (final.body if final and final.status == "ANSWERED" else None)
            except Exception as exc:
                logger.warning(
                    "swarm.required_approvers.wait_failed",
                    approver=dept, error=str(exc),
                )
                return dept, None

        answers = await asyncio.gather(
            *[_await_one(dept, mid) for dept, mid in message_ids],
            return_exceptions=False,
        )

        denials: list[str] = []
        for dept, body in answers:
            if body is None:
                # Timeout / missing. Fail-safe: treat as provisional approve.
                continue
            if body.strip().upper().startswith("NO"):
                denials.append(f"{dept}: {body.strip()[:80]}")

        if denials:
            return False, "Denied by " + "; ".join(denials)
        return True, "all approvers green or provisionally approved"

    async def _state_mark_idle(
        self,
        *,
        tenant_id: Any,
        department: str,
    ) -> None:
        try:
            from app.core.database import async_session_factory
            from app.services.department_state_service import (
                DepartmentStateService,
            )

            async with async_session_factory() as session:
                svc = DepartmentStateService(session)
                await svc.mark_idle(
                    tenant_id=tenant_id,
                    department=department,
                )
                await session.commit()
        except Exception as exc:
            logger.warning(
                "swarm.state_mark_idle_failed",
                department=department, error=str(exc),
            )

    async def execute_plan(
        self,
        subtasks: list[SubTask],
        context: dict[str, Any] | None = None,
    ) -> list[ExecutionReceipt]:
        """Execute a plan of subtasks respecting dependencies.

        Args:
            subtasks: List of SubTask objects from SwarmPlanner.
            context: Execution context (governance_mode, user_id, etc.).

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
            2. Mark the assigned department WORKING in state registry
            3. Execute on assigned runtime
            4. On failure, try fallback runtime
            5. Mark department IDLE (success or failure path)
            6. Return receipt

        Session A wire-in: department state registry tracks live
        availability so Daena VP (Session B) can route based on
        current load.
        """
        subtask.status = "running"
        start = time.perf_counter()

        # Session A: grab the department for state tracking. Missing
        # metadata or tenant_id = skip silently so this never breaks
        # non-company execution paths.
        department = subtask.metadata.get("department") if subtask.metadata else None
        tenant_id = context.get("tenant_id")
        state_tracked = bool(department and tenant_id)
        if state_tracked:
            await self._state_mark_working(
                tenant_id=tenant_id,
                department=department,
                task_id=subtask.id,
                task_summary=subtask.description,
            )
            # Emit a peer-visible lifecycle event via the BorderAgent so
            # every subscribing department sees that this dept just
            # picked up work. Fail-safe: never block the subtask if the
            # bus is unavailable.
            try:
                from app.services.departments.border_agent import (
                    DepartmentEvent,
                    get_border_agent,
                )
                ba = await get_border_agent(tenant_id=tenant_id, department=department)
                await ba.emit(
                    DepartmentEvent.TASK_STARTED,
                    payload={
                        "task_id": subtask.id,
                        "task_summary": subtask.description[:200],
                        "task_type": subtask.task_type,
                    },
                )
            except Exception as exc:
                logger.debug(
                    "swarm.border_emit_task_started_failed",
                    department=department, error=str(exc),
                )

        try:
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
                        governance_slider=context.get("governance_mode", "BALANCED"),
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

            # Phase 2: required_approvers gate (inter-department ask).
            # DaenaVP + DepartmentPolicyService populate
            # subtask.metadata["required_approvers"] when policy demands
            # sign-off from other departments (e.g. Finance must approve
            # expenses > $500 before Marketing executes an ad buy).
            required_approvers = (
                subtask.metadata.get("required_approvers") if subtask.metadata else None
            ) or []
            if required_approvers and tenant_id:
                approved, reason = await self._solicit_required_approvers(
                    subtask_id=subtask.id,
                    subtask_description=subtask.description,
                    from_department=department or "Daena",
                    required_approvers=list(required_approvers),
                    tenant_id=tenant_id,
                    timeout_seconds=int(context.get("approver_timeout_seconds", 30)),
                )
                if not approved:
                    subtask.status = "rejected"
                    duration = int((time.perf_counter() - start) * 1000)
                    receipt = self._make_receipt(
                        subtask, "rejected",
                        error=f"Required approvers blocked: {reason}",
                        duration_ms=duration,
                    )
                    subtask.receipt = receipt
                    logger.info(
                        "swarm.required_approvers.blocked",
                        subtask_id=subtask.id,
                        reason=reason,
                    )
                    return receipt

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
        finally:
            # Session A: always mark idle, regardless of outcome. Without
            # this, a crashed subtask would leave queue_depth incremented
            # forever and eventually flip the dept to OVERLOADED.
            if state_tracked:
                await self._state_mark_idle(
                    tenant_id=tenant_id,
                    department=department,
                )
                # Emit the matching completion event. Status reflects how
                # the subtask actually ended so peers can react
                # differently to complete vs failed vs rejected.
                try:
                    from app.services.departments.border_agent import (
                        DepartmentEvent,
                        get_border_agent,
                    )
                    ba = await get_border_agent(tenant_id=tenant_id, department=department)
                    status = getattr(subtask, "status", "unknown")
                    evt_type = {
                        "complete": DepartmentEvent.TASK_COMPLETED,
                        "rejected": DepartmentEvent.TASK_REJECTED,
                        "failed": DepartmentEvent.TASK_FAILED,
                    }.get(status, DepartmentEvent.TASK_COMPLETED)
                    await ba.emit(
                        evt_type,
                        payload={
                            "task_id": subtask.id,
                            "task_summary": subtask.description[:200],
                            "status": status,
                        },
                    )
                except Exception as exc:
                    logger.debug(
                        "swarm.border_emit_completion_failed",
                        department=department, error=str(exc),
                    )

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
