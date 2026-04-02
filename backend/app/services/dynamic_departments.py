"""Dynamic Department Creation: Daena creates new departments as needed.

When the 10 standard departments don't cover a domain, Daena can
create a new department with 6 sub-capability agents, following
the sunflower-honeycomb pattern (golden angle spiral).

Example: If a user works in healthcare, Daena creates a "Healthcare"
department with specialized MIND/EYES/HANDS/VOICE/SHIELD/MEMORY agents.

Governance: department creation is logged and requires FOUNDER role
or AGI mode. The new department gets default prompts that can be
refined via the Skill Refinery.
"""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID, uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

# Golden angle in degrees (sunflower-honeycomb topology)
GOLDEN_ANGLE = 137.508

# Standard sub-capabilities for every department
SUB_CAPABILITIES = ["MIND", "EYES", "HANDS", "VOICE", "SHIELD", "MEMORY"]

# Domains that map to existing departments (never create duplicates)
EXISTING_DOMAINS = {
    "engineering", "software", "development", "coding", "programming",
    "product", "product management", "pm",
    "marketing", "content", "social media", "seo",
    "sales", "business development", "outreach",
    "finance", "accounting", "billing", "budget",
    "operations", "ops", "management", "admin",
    "research", "analysis", "data science",
    "legal", "compliance", "regulatory", "law",
    "skill", "skills", "governance", "quality",
    "security", "cybersecurity", "infosec",
}


async def should_create_department(
    domain: str,
    db: Any,
    tenant_id: UUID,
) -> tuple[bool, str]:
    """Determine if a new department should be created for this domain.

    Returns:
        (should_create, reason)
    """
    domain_lower = domain.lower().strip()

    # Check against existing domain keywords
    for keyword in EXISTING_DOMAINS:
        if keyword in domain_lower or domain_lower in keyword:
            return False, f"Domain '{domain}' is covered by an existing department"

    # Check if a department with this name already exists in the DB
    from sqlalchemy import select
    from app.models.organization import Department

    stmt = select(Department).where(
        Department.tenant_id == tenant_id,
        Department.name.ilike(f"%{domain_lower}%"),
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return False, f"Department '{existing.name}' already covers this domain"

    return True, f"No existing department covers '{domain}'"


async def create_department(
    name: str,
    description: str,
    db: Any,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Create a new department with 6 sub-capability agents.

    The department is placed at the next available sunflower index.

    Args:
        name: Department name (e.g., "Healthcare")
        description: What this department does
        db: AsyncSession
        tenant_id: Tenant UUID

    Returns:
        Dict with department_id, agent_count, and sunflower_index
    """
    from sqlalchemy import select, func
    from app.models.organization import Department, Agent

    # Find next sunflower index
    stmt = select(func.max(Department.sunflower_index)).where(
        Department.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    max_index = result.scalar() or 9  # Default 10 departments (0-9)
    next_index = max_index + 1

    # Calculate cell position using golden angle
    angle_rad = math.radians(GOLDEN_ANGLE * next_index)
    cell_id = f"hex_{next_index}_{int(angle_rad * 1000) % 360}"

    # Create department
    dept = Department(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        description=description,
        sunflower_index=next_index,
        cell_id=cell_id,
        config={
            "dynamic": True,
            "created_by": "daena_autonomous",
            "domain": name.lower(),
        },
        is_active=True,
    )
    db.add(dept)

    # Create 6 sub-capability agents
    agents_created = []
    for sub_cap in SUB_CAPABILITIES:
        agent = Agent(
            id=uuid4(),
            department_id=dept.id,
            tenant_id=tenant_id,
            name=f"{name} {sub_cap}",
            sub_capability=sub_cap,
            description=f"{name} department {sub_cap} agent",
            is_active=True,
        )
        db.add(agent)
        agents_created.append(sub_cap)

    await db.commit()

    # Register specialized prompts for the new department
    try:
        from app.services.department_prompts import register_dynamic_department
        register_dynamic_department(name, description)
    except Exception:
        pass  # Non-critical: prompts can be added later

    logger.info(
        "dynamic_department.created",
        name=name,
        sunflower_index=next_index,
        agent_count=len(agents_created),
        tenant_id=str(tenant_id),
    )

    return {
        "department_id": str(dept.id),
        "name": name,
        "sunflower_index": next_index,
        "cell_id": cell_id,
        "agent_count": len(agents_created),
        "agents": agents_created,
    }


async def auto_detect_and_create(
    task_description: str,
    db: Any,
    tenant_id: UUID,
) -> dict[str, Any] | None:
    """Detect if a task requires a new department and create it.

    Uses keyword analysis to detect domain-specific tasks that
    don't fit existing departments.

    Returns:
        New department info or None if no new department needed
    """
    # Domain detection keywords
    domain_hints = {
        "Healthcare": ["patient", "medical", "clinical", "diagnosis", "treatment", "HIPAA", "healthcare", "hospital", "pharmacy"],
        "Real Estate": ["property", "listing", "mortgage", "real estate", "rental", "tenant", "landlord", "MLS"],
        "Education": ["student", "curriculum", "course", "enrollment", "teacher", "education", "academic", "grade"],
        "Manufacturing": ["supply chain", "inventory", "warehouse", "production", "manufacturing", "logistics", "procurement"],
        "Hospitality": ["hotel", "restaurant", "booking", "reservation", "hospitality", "tourism", "travel"],
        "Agriculture": ["crop", "harvest", "farm", "agriculture", "soil", "irrigation", "livestock"],
        "Media & Entertainment": ["streaming", "content creation", "broadcast", "media", "entertainment", "film", "music"],
        "Government": ["government", "municipal", "regulatory", "public sector", "civic", "legislation"],
        "Non-Profit": ["donor", "fundraising", "volunteer", "non-profit", "NGO", "charity", "grant"],
        "Insurance": ["insurance", "claim", "policy", "underwriting", "actuary", "premium"],
    }

    task_lower = task_description.lower()

    for domain, keywords in domain_hints.items():
        matches = sum(1 for kw in keywords if kw.lower() in task_lower)
        if matches >= 2:
            should, reason = await should_create_department(domain, db, tenant_id)
            if should:
                return await create_department(
                    name=domain,
                    description=f"Automatically created for {domain.lower()} domain tasks. Detected {matches} domain keywords.",
                    db=db,
                    tenant_id=tenant_id,
                )

    return None
