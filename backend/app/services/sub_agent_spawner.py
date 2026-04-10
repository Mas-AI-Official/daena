"""Dynamic Sub-Agent Spawner: departments spawn N task-specific agents.

Architecture:
    Each department has 6 PERMANENT agents (MIND, EYES, HANDS, VOICE, SHIELD, MEMORY).
    These are the department's nervous system -- always present.

    When a complex task arrives, the department's MIND agent decides to
    spawn N temporary sub-agents. Each sub-agent:
    - Inherits the parent agent's capabilities and prompts
    - Works on ONE slice of the task
    - Runs in parallel with other sub-agents
    - Dissolves after completing its slice
    - Reports results back to the parent agent

    Example: Security department gets "scan this 50-file codebase"
    - Security.SHIELD spawns 50 sub-agents
    - Each sub-agent scans 1 file through the Laevateinn pipeline
    - Results merge through Consensus Gradient
    - Sub-agents dissolve
    - Cost = tokens consumed by sub-agents

Capacity:
    MAX_TOTAL_SUB_AGENTS = 10,000 (system-wide limit)
    MAX_PER_DEPARTMENT = 1,000
    MAX_PER_TASK = 500

Integration:
    SwarmPlanner -> SubAgentSpawner -> DepartmentRouter -> SwarmExecutor
    The spawner sits between planning and routing. It takes a task decomposition
    and, if any subtask requires parallelism, spawns sub-agents to handle it.

Cross-Department Knowledge:
    Sub-agents from different departments share a KnowledgeBus.
    Marketing knows what Engineering is building. Finance knows what Sales is closing.
    This is the shared-consciousness layer that makes the company self-aware.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Capacity limits ────────────────────────────────────────────
MAX_TOTAL_SUB_AGENTS = 10_000
MAX_PER_DEPARTMENT = 1_000
MAX_PER_TASK = 500
DEFAULT_CONCURRENCY = 50  # How many sub-agents run in parallel


class SubAgentStatus(str, Enum):
    """Lifecycle states for a sub-agent."""
    SPAWNING = "SPAWNING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    DISSOLVED = "DISSOLVED"


@dataclass
class SubAgent:
    """A temporary task-specific agent spawned by a department agent.

    Sub-agents are ephemeral: created for a task, executed, results
    collected, then dissolved. They do NOT persist in the database.
    They exist only in memory during execution.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    parent_agent_id: str = ""
    parent_department: str = ""
    parent_capability: str = ""  # MIND, EYES, HANDS, etc.
    task_slice: str = ""         # What this sub-agent is responsible for
    task_type: str = ""
    status: SubAgentStatus = SubAgentStatus.SPAWNING
    result: str = ""
    error: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    spawned_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def dissolve(self) -> dict[str, Any]:
        """Dissolve the sub-agent and return its final report."""
        self.status = SubAgentStatus.DISSOLVED
        self.completed_at = time.time()
        return {
            "id": self.id,
            "parent": f"{self.parent_department}.{self.parent_capability}",
            "task_slice": self.task_slice[:100],
            "status": self.status.value,
            "result_length": len(self.result),
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "duration_ms": int((self.completed_at - self.spawned_at) * 1000),
        }


@dataclass
class SpawnPlan:
    """Plan for spawning sub-agents for a task."""
    task_id: str
    department: str
    capability: str
    total_slices: int
    concurrency: int
    slices: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class SpawnResult:
    """Result of spawning and executing sub-agents."""
    task_id: str
    department: str
    sub_agents_spawned: int
    sub_agents_completed: int
    sub_agents_failed: int
    merged_result: str = ""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    sub_agent_reports: list[dict] = field(default_factory=list)


class KnowledgeBus:
    """Cross-department shared knowledge layer.

    Every department can publish knowledge and subscribe to other
    departments' outputs. This is what makes the company self-aware:
    Marketing knows what Engineering is building. Finance knows costs.

    Knowledge entries are ephemeral (within a session/task) and
    persistent (via NBMF memory tiers).
    """

    def __init__(self) -> None:
        self._bus: dict[str, list[dict[str, Any]]] = {}
        self._subscribers: dict[str, list[str]] = {}

    def publish(
        self,
        department: str,
        knowledge_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Publish knowledge from a department to the bus."""
        entry = {
            "department": department,
            "type": knowledge_type,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        if department not in self._bus:
            self._bus[department] = []
        self._bus[department].append(entry)

        logger.debug(
            "knowledge_bus.published",
            department=department,
            knowledge_type=knowledge_type,
            content_length=len(content),
        )

    def query(
        self,
        requesting_department: str,
        source_department: str | None = None,
        knowledge_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query knowledge from other departments.

        Args:
            requesting_department: Who is asking.
            source_department: Specific department to query (None = all).
            knowledge_type: Filter by type (None = all types).
            limit: Max entries to return.
        """
        results: list[dict[str, Any]] = []

        sources = (
            [source_department] if source_department
            else [k for k in self._bus if k != requesting_department]
        )

        for dept in sources:
            entries = self._bus.get(dept, [])
            for entry in reversed(entries):
                if knowledge_type and entry["type"] != knowledge_type:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break

        return results

    def get_company_state(self) -> dict[str, int]:
        """Get a summary of all knowledge on the bus."""
        return {dept: len(entries) for dept, entries in self._bus.items()}

    def clear(self) -> None:
        """Clear all ephemeral knowledge (end of session)."""
        self._bus.clear()


class SubAgentSpawner:
    """Spawns and manages dynamic sub-agents for departments.

    This is the engine that lets 60 permanent agents become 10,000+
    when a complex task demands it. The permanent agents are the
    department's nervous system. Sub-agents are the workforce.

    Usage::

        spawner = SubAgentSpawner(knowledge_bus)

        # Plan how to split a task
        plan = spawner.plan_spawn(
            task="Scan 50 Python files for vulnerabilities",
            department="Security Operations",
            capability="SHIELD",
            items=file_list,
        )

        # Execute with sub-agents
        result = await spawner.spawn_and_execute(
            plan,
            executor_fn=my_scan_function,
        )

    Args:
        knowledge_bus: Shared knowledge layer for cross-department awareness.
        max_concurrency: Maximum parallel sub-agents.
    """

    def __init__(
        self,
        knowledge_bus: KnowledgeBus | None = None,
        max_concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._knowledge = knowledge_bus or KnowledgeBus()
        self._max_concurrency = max_concurrency
        self._active_sub_agents: dict[str, SubAgent] = {}
        self._total_spawned = 0
        self._total_dissolved = 0

    @property
    def active_count(self) -> int:
        """Number of currently active sub-agents."""
        return len(self._active_sub_agents)

    @property
    def knowledge_bus(self) -> KnowledgeBus:
        """Access the knowledge bus for cross-department queries."""
        return self._knowledge

    def plan_spawn(
        self,
        task: str,
        department: str,
        capability: str,
        items: list[str],
        *,
        task_type: str = "analysis",
        parent_agent_id: str = "",
    ) -> SpawnPlan:
        """Plan how many sub-agents to spawn for a task.

        Args:
            task: Description of the overall task.
            department: Department name.
            capability: Sub-capability (MIND, EYES, etc.).
            items: List of items to process (files, URLs, records, etc.).
            task_type: Type of task for each sub-agent.
            parent_agent_id: ID of the parent permanent agent.

        Returns:
            SpawnPlan with slicing strategy.
        """
        total = len(items)

        # Cap at limits
        if total > MAX_PER_TASK:
            logger.warning(
                "sub_agent_spawner.capped",
                requested=total,
                max=MAX_PER_TASK,
            )
            total = MAX_PER_TASK
            items = items[:MAX_PER_TASK]

        # Estimate tokens (rough: 1000 tokens per item for analysis)
        est_tokens = total * 1000
        est_cost = est_tokens * 0.000003  # ~$3 per 1M tokens (Ollama = free)

        concurrency = min(self._max_concurrency, total)

        plan = SpawnPlan(
            task_id=str(uuid.uuid4())[:8],
            department=department,
            capability=capability,
            total_slices=total,
            concurrency=concurrency,
            slices=items,
            estimated_tokens=est_tokens,
            estimated_cost_usd=round(est_cost, 4),
        )

        logger.info(
            "sub_agent_spawner.planned",
            task_id=plan.task_id,
            department=department,
            capability=capability,
            slices=total,
            concurrency=concurrency,
            est_tokens=est_tokens,
        )

        return plan

    async def spawn_and_execute(
        self,
        plan: SpawnPlan,
        executor_fn: Any,
        *,
        timeout: float = 300.0,
        parent_agent_id: str = "",
    ) -> SpawnResult:
        """Spawn sub-agents and execute them in parallel.

        Args:
            plan: SpawnPlan from plan_spawn().
            executor_fn: Async function that takes (task_slice: str) -> str.
                         Each sub-agent calls this with its slice.
            timeout: Per-sub-agent timeout in seconds.
            parent_agent_id: ID of the parent permanent agent.

        Returns:
            SpawnResult with merged results from all sub-agents.
        """
        start = time.perf_counter()
        semaphore = asyncio.Semaphore(plan.concurrency)
        sub_agents: list[SubAgent] = []
        results: list[str] = []

        # Create sub-agents
        for i, slice_item in enumerate(plan.slices):
            sa = SubAgent(
                parent_agent_id=parent_agent_id,
                parent_department=plan.department,
                parent_capability=plan.capability,
                task_slice=slice_item,
                task_type=f"{plan.capability.lower()}_sub_{i}",
            )
            sub_agents.append(sa)
            self._active_sub_agents[sa.id] = sa
            self._total_spawned += 1

        logger.info(
            "sub_agent_spawner.spawned",
            task_id=plan.task_id,
            count=len(sub_agents),
            department=plan.department,
        )

        # Execute all sub-agents in parallel with concurrency control
        async def _run_sub_agent(sa: SubAgent) -> None:
            async with semaphore:
                sa.status = SubAgentStatus.RUNNING
                try:
                    sa.result = await asyncio.wait_for(
                        executor_fn(sa.task_slice),
                        timeout=timeout,
                    )
                    sa.status = SubAgentStatus.COMPLETE
                except asyncio.TimeoutError:
                    sa.status = SubAgentStatus.FAILED
                    sa.error = f"Timeout after {timeout}s"
                except Exception as exc:
                    sa.status = SubAgentStatus.FAILED
                    sa.error = str(exc)

        await asyncio.gather(
            *[_run_sub_agent(sa) for sa in sub_agents],
            return_exceptions=True,
        )

        # Collect results and dissolve
        reports = []
        completed = 0
        failed = 0
        total_tokens = 0

        for sa in sub_agents:
            if sa.status == SubAgentStatus.COMPLETE:
                completed += 1
                results.append(sa.result)
                total_tokens += sa.tokens_used
            else:
                failed += 1

            report = sa.dissolve()
            reports.append(report)
            del self._active_sub_agents[sa.id]
            self._total_dissolved += 1

        # Merge results
        merged = "\n---\n".join(results) if results else "No results collected"

        # Publish to knowledge bus
        self._knowledge.publish(
            department=plan.department,
            knowledge_type="task_result",
            content=f"Completed {completed}/{len(sub_agents)} slices for {plan.task_id}",
            metadata={
                "task_id": plan.task_id,
                "completed": completed,
                "failed": failed,
                "result_preview": merged[:200],
            },
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        result = SpawnResult(
            task_id=plan.task_id,
            department=plan.department,
            sub_agents_spawned=len(sub_agents),
            sub_agents_completed=completed,
            sub_agents_failed=failed,
            merged_result=merged,
            total_tokens=total_tokens,
            total_cost_usd=round(total_tokens * 0.000003, 4),
            total_duration_ms=elapsed_ms,
            sub_agent_reports=reports,
        )

        logger.info(
            "sub_agent_spawner.completed",
            task_id=plan.task_id,
            spawned=len(sub_agents),
            completed=completed,
            failed=failed,
            duration_ms=elapsed_ms,
        )

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get spawner statistics."""
        return {
            "active_sub_agents": self.active_count,
            "total_spawned": self._total_spawned,
            "total_dissolved": self._total_dissolved,
            "knowledge_bus_state": self._knowledge.get_company_state(),
            "max_concurrency": self._max_concurrency,
        }
