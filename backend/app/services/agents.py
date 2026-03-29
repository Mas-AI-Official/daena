"""Agent service: department and agent management.

Implements CRUD for the Sunflower-Honeycomb organizational structure.
10 departments x 6 sub-capabilities = 60 agents per tenant.

Patent-pending: Sunflower-Honeycomb Architecture.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from app.core.constants import DEFAULT_DEPARTMENTS, SubCapability
from app.core.exceptions import ConflictError, ValidationError
from app.models.organization import Agent, Department
from app.services._base import BaseService


class AgentService(BaseService):
    """CRUD + seed operations for departments and agents.

    Usage::

        svc = AgentService(db)
        deps = await svc.list_departments(tenant_id=tid)
        agent = await svc.create_agent(
            tenant_id=tid,
            department_id=dep_id,
            name="Research-MIND",
            sub_capability="MIND",
        )
    """

    # ── Departments ──

    async def list_departments(
        self,
        *,
        tenant_id: UUID,
        include_inactive: bool = False,
    ) -> list[dict]:
        """List all departments for a tenant.

        Args:
            tenant_id: Tenant UUID.
            include_inactive: Include deactivated departments.

        Returns:
            List of department dicts with agent_count.
        """
        stmt = (
            select(Department)
            .where(Department.tenant_id == tenant_id)
            .order_by(Department.sunflower_index)
        )
        if not include_inactive:
            stmt = stmt.where(Department.is_active.is_(True))

        result = await self.db.execute(stmt)
        departments = list(result.scalars().all())

        # Batch-fetch agent counts
        count_stmt = (
            select(
                Agent.department_id,
                func.count(Agent.id).label("cnt"),
            )
            .where(Agent.tenant_id == tenant_id)
            .group_by(Agent.department_id)
        )
        count_result = await self.db.execute(count_stmt)
        counts = {row.department_id: row.cnt for row in count_result}

        return [
            self._dept_to_dict(dept, agent_count=counts.get(dept.id, 0))
            for dept in departments
        ]

    async def get_department(
        self,
        *,
        department_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Get a single department by ID.

        Args:
            department_id: Department UUID.
            tenant_id: Tenant UUID.

        Returns:
            Department dict with agent_count.

        Raises:
            NotFoundError: If department doesn't exist for tenant.
        """
        dept = await self._get_or_404(
            Department, department_id, "Department", tenant_id=tenant_id
        )

        # Count agents
        count_stmt = (
            select(func.count(Agent.id))
            .where(
                Agent.department_id == department_id,
                Agent.tenant_id == tenant_id,
            )
        )
        count_result = await self.db.execute(count_stmt)
        agent_count = count_result.scalar() or 0

        return self._dept_to_dict(dept, agent_count=agent_count)

    async def create_department(
        self,
        *,
        tenant_id: UUID,
        name: str,
        description: str | None = None,
        sunflower_index: int,
        cell_id: str | None = None,
        config: dict | None = None,
    ) -> dict:
        """Create a new department.

        Args:
            tenant_id: Tenant UUID.
            name: Department name.
            description: Optional description.
            sunflower_index: Position in the Sunflower spiral.
            cell_id: Optional honeycomb cell ID.
            config: Additional configuration.

        Returns:
            Created department dict.

        Raises:
            ConflictError: If department name already exists for tenant.
        """
        # Check uniqueness
        existing_stmt = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.name == name,
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Department '{name}' already exists for this tenant"
            )

        dept = Department(
            tenant_id=tenant_id,
            name=name,
            description=description,
            sunflower_index=sunflower_index,
            cell_id=cell_id,
            config=config or {},
            is_active=True,
        )
        self.db.add(dept)
        await self.db.flush()
        await self.db.refresh(dept)

        return self._dept_to_dict(dept, agent_count=0)

    # ── Agents ──

    async def list_agents(
        self,
        *,
        tenant_id: UUID,
        department_id: UUID | None = None,
        include_inactive: bool = False,
    ) -> list[dict]:
        """List agents, optionally filtered by department.

        Args:
            tenant_id: Tenant UUID.
            department_id: Optional department filter.
            include_inactive: Include deactivated agents.

        Returns:
            List of agent dicts.
        """
        stmt = (
            select(Agent)
            .where(Agent.tenant_id == tenant_id)
            .order_by(Agent.name)
        )
        if department_id is not None:
            stmt = stmt.where(Agent.department_id == department_id)
        if not include_inactive:
            stmt = stmt.where(Agent.is_active.is_(True))

        result = await self.db.execute(stmt)
        agents = list(result.scalars().all())

        return [self._agent_to_dict(a) for a in agents]

    async def get_agent(
        self,
        *,
        agent_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Get a single agent by ID.

        Args:
            agent_id: Agent UUID.
            tenant_id: Tenant UUID.

        Returns:
            Agent dict.

        Raises:
            NotFoundError: If agent doesn't exist for tenant.
        """
        agent = await self._get_or_404(
            Agent, agent_id, "Agent", tenant_id=tenant_id
        )
        return self._agent_to_dict(agent)

    async def create_agent(
        self,
        *,
        tenant_id: UUID,
        department_id: UUID,
        name: str,
        sub_capability: str,
        description: str | None = None,
        model_preference: str | None = None,
        config: dict | None = None,
    ) -> dict:
        """Create a new agent within a department.

        Args:
            tenant_id: Tenant UUID.
            department_id: Parent department UUID.
            name: Agent name.
            sub_capability: One of MIND/EYES/HANDS/VOICE/SHIELD/MEMORY.
            description: Optional description.
            model_preference: Preferred LLM model name.
            config: Additional configuration.

        Returns:
            Created agent dict.

        Raises:
            ValidationError: If sub_capability is invalid.
            NotFoundError: If department doesn't exist.
            ConflictError: If sub_capability already assigned in department.
        """
        # Validate sub-capability
        valid_caps = {cap.value for cap in SubCapability}
        if sub_capability not in valid_caps:
            raise ValidationError(
                f"Invalid sub_capability '{sub_capability}'. "
                f"Must be one of: {', '.join(sorted(valid_caps))}"
            )

        # Verify department exists
        await self._get_or_404(
            Department, department_id, "Department", tenant_id=tenant_id
        )

        # Check uniqueness (department + sub_capability)
        existing_stmt = select(Agent).where(
            Agent.department_id == department_id,
            Agent.sub_capability == sub_capability,
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Sub-capability '{sub_capability}' already assigned "
                f"in this department"
            )

        agent = Agent(
            tenant_id=tenant_id,
            department_id=department_id,
            name=name,
            sub_capability=sub_capability,
            description=description,
            model_preference=model_preference,
            config=config or {},
            is_active=True,
        )
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)

        return self._agent_to_dict(agent)

    # ── Seed ──

    async def seed_defaults(self, *, tenant_id: UUID) -> dict:
        """Bootstrap the 10 default departments + 60 agents.

        Creates the full Sunflower-Honeycomb structure for a new tenant.
        Idempotent: skips departments that already exist (by name).

        Args:
            tenant_id: Tenant UUID.

        Returns:
            Summary dict with counts.
        """
        departments_created = 0
        agents_created = 0

        for dept_def in DEFAULT_DEPARTMENTS:
            # Check if department already exists
            existing_stmt = select(Department).where(
                Department.tenant_id == tenant_id,
                Department.name == dept_def["name"],
            )
            existing_result = await self.db.execute(existing_stmt)
            dept = existing_result.scalar_one_or_none()

            if dept is None:
                dept = Department(
                    tenant_id=tenant_id,
                    name=str(dept_def["name"]),
                    description=str(dept_def.get("description", "")),
                    sunflower_index=int(dept_def["sunflower_index"]),
                    config={},
                    is_active=True,
                )
                self.db.add(dept)
                await self.db.flush()
                await self.db.refresh(dept)
                departments_created += 1

            # Create 6 sub-capability agents for this department
            for cap in SubCapability:
                existing_agent_stmt = select(Agent).where(
                    Agent.department_id == dept.id,
                    Agent.sub_capability == cap.value,
                )
                agent_result = await self.db.execute(existing_agent_stmt)
                if agent_result.scalar_one_or_none() is None:
                    agent = Agent(
                        tenant_id=tenant_id,
                        department_id=dept.id,
                        name=f"{dept.name}-{cap.value}",
                        sub_capability=cap.value,
                        description=(
                            f"{cap.value} capability for {dept.name} department"
                        ),
                        config={},
                        is_active=True,
                    )
                    self.db.add(agent)
                    agents_created += 1

        await self.db.flush()

        return {
            "departments_created": departments_created,
            "agents_created": agents_created,
            "total_departments": len(DEFAULT_DEPARTMENTS),
            "total_agents": len(DEFAULT_DEPARTMENTS) * len(SubCapability),
        }

    # ── Serialization ──

    @staticmethod
    def _dept_to_dict(dept: Department, *, agent_count: int = 0) -> dict:
        """Convert Department model to response dict.

        Args:
            dept: Department ORM instance.
            agent_count: Number of agents in the department.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(dept.id),
            "tenant_id": str(dept.tenant_id),
            "name": dept.name,
            "description": dept.description,
            "sunflower_index": dept.sunflower_index,
            "cell_id": dept.cell_id,
            "config": dept.config or {},
            "is_active": dept.is_active,
            "agent_count": agent_count,
            "created_at": (
                dept.created_at.isoformat() if dept.created_at else None
            ),
            "updated_at": (
                dept.updated_at.isoformat() if dept.updated_at else None
            ),
        }

    @staticmethod
    def _agent_to_dict(agent: Agent) -> dict:
        """Convert Agent model to response dict.

        Args:
            agent: Agent ORM instance.

        Returns:
            Serializable dict.
        """
        return {
            "id": str(agent.id),
            "tenant_id": str(agent.tenant_id),
            "department_id": str(agent.department_id),
            "name": agent.name,
            "sub_capability": agent.sub_capability,
            "description": agent.description,
            "model_preference": agent.model_preference,
            "config": agent.config or {},
            "is_active": agent.is_active,
            "created_at": (
                agent.created_at.isoformat() if agent.created_at else None
            ),
            "updated_at": (
                agent.updated_at.isoformat() if agent.updated_at else None
            ),
        }
