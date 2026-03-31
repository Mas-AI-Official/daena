"""DepartmentRouter: maps task types to department agents.

Routes subtasks from SwarmPlanner to the appropriate department and
sub-capability agent. This activates the 60-agent organizational model
(10 departments x 6 sub-capabilities: MIND, EYES, HANDS, VOICE, SHIELD, MEMORY).

Architecture:
    SwarmPlanner → "What subtasks?" (task decomposition)
    DepartmentRouter → "Which department agent?" (agent selection)
    SwarmExecutor → "Run them" (parallel execution with dependencies)

Task type to department mapping follows the organizational structure:
    Engineering.HANDS → code_generation, code_editing
    Research.EYES → web_research, data_analysis
    Operations.MIND → complex_reasoning, bulk_operations
    Marketing.VOICE → content creation
    Security.SHIELD → security scanning
    etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Task Type to Department+SubCapability Mapping ──

TASK_DEPARTMENT_MAP: dict[str, tuple[str, str]] = {
    # task_type: (department_name, sub_capability)
    "code_generation": ("Engineering", "HANDS"),
    "code_editing": ("Engineering", "HANDS"),
    "file_operations": ("Engineering", "EYES"),
    "web_research": ("Research", "EYES"),
    "data_analysis": ("Research", "MIND"),
    "complex_reasoning": ("Operations", "MIND"),
    "browser_automation": ("Engineering", "HANDS"),
    "simple_chat": ("Operations", "VOICE"),
    "bulk_operations": ("Operations", "HANDS"),
    "content_creation": ("Marketing", "VOICE"),
    "lead_research": ("Sales", "EYES"),
    "outreach_draft": ("Sales", "VOICE"),
    "cost_analysis": ("Finance", "MIND"),
    "security_scan": ("Security Operations", "SHIELD"),
    "compliance_check": ("Legal & Compliance", "MIND"),
    "skill_extraction": ("Skill Governance", "MIND"),
}


@dataclass
class AgentAssignment:
    """Result of routing a subtask to a department agent."""
    department_name: str
    sub_capability: str
    agent_id: str | None = None
    department_id: str | None = None
    model_preference: str | None = None
    confidence: float = 1.0


class DepartmentRouter:
    """Routes subtasks to the best department agent.

    Loads agent registry from the database (cached) and provides
    fast lookups from task_type to the appropriate department agent.

    Usage::

        router = DepartmentRouter(db, tenant_id)
        await router.load_agents()
        assignment = await router.route(subtask)
        if assignment:
            subtask.metadata['agent_id'] = assignment.agent_id
            subtask.metadata['department'] = assignment.department_name
    """

    def __init__(self, db: Any, tenant_id: UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._agents: dict[tuple[str, str], AgentAssignment] = {}
        self._loaded = False

    async def load_agents(self) -> int:
        """Load department agents from the database.

        Builds a lookup table: (department_name, sub_capability) -> AgentAssignment.
        Returns the number of agents loaded.
        """
        if self._loaded:
            return len(self._agents)

        try:
            from sqlalchemy import select
            from app.models.organization import Department, Agent

            stmt = (
                select(Department, Agent)
                .join(Agent, Agent.department_id == Department.id)
                .where(Department.tenant_id == self._tenant_id)
            )
            result = await self._db.execute(stmt)
            rows = result.all()

            for dept, agent in rows:
                key = (dept.name, agent.sub_capability)
                self._agents[key] = AgentAssignment(
                    department_name=dept.name,
                    sub_capability=agent.sub_capability,
                    agent_id=str(agent.id),
                    department_id=str(dept.id),
                    model_preference=agent.model_preference,
                )

            self._loaded = True
            logger.info(
                "department_router.agents_loaded",
                count=len(self._agents),
                tenant_id=str(self._tenant_id),
            )
            return len(self._agents)

        except Exception as exc:
            logger.warning("department_router.load_failed", error=str(exc))
            self._loaded = True  # Don't retry on every call
            return 0

    async def route(
        self,
        task_type: str,
        *,
        preferred_department: str | None = None,
    ) -> AgentAssignment | None:
        """Route a task type to the best department agent.

        Args:
            task_type: The SwarmPlanner task type (e.g. "code_generation").
            preferred_department: Optional department name to prefer.

        Returns:
            AgentAssignment if a matching agent exists, None otherwise.
        """
        if not self._loaded:
            await self.load_agents()

        # Check if this task type has a department mapping
        mapping = TASK_DEPARTMENT_MAP.get(task_type)
        if not mapping:
            return None

        dept_name, sub_capability = mapping

        # Allow user to override department
        if preferred_department:
            dept_name = preferred_department

        # Look up the agent
        key = (dept_name, sub_capability)
        assignment = self._agents.get(key)

        if assignment:
            logger.debug(
                "department_router.routed",
                task_type=task_type,
                department=dept_name,
                sub_capability=sub_capability,
                agent_id=assignment.agent_id,
            )

        return assignment

    async def route_subtasks(
        self,
        subtasks: list[Any],
    ) -> list[Any]:
        """Route a list of SwarmPlanner subtasks to department agents.

        Modifies subtask metadata in-place with agent assignment info.
        Returns the same list for chaining.
        """
        if not self._loaded:
            await self.load_agents()

        for subtask in subtasks:
            assignment = await self.route(subtask.task_type)
            if assignment:
                subtask.metadata["agent_id"] = assignment.agent_id
                subtask.metadata["department"] = assignment.department_name
                subtask.metadata["sub_capability"] = assignment.sub_capability
                if assignment.model_preference:
                    subtask.metadata["model_preference"] = assignment.model_preference

        routed_count = sum(1 for st in subtasks if "agent_id" in st.metadata)
        logger.info(
            "department_router.subtasks_routed",
            total=len(subtasks),
            routed=routed_count,
        )

        return subtasks

    def get_department_for_task(self, task_type: str) -> str | None:
        """Quick lookup: which department handles this task type?"""
        mapping = TASK_DEPARTMENT_MAP.get(task_type)
        return mapping[0] if mapping else None

    def get_available_departments(self) -> list[str]:
        """List all departments that have loaded agents."""
        return sorted({a.department_name for a in self._agents.values()})
