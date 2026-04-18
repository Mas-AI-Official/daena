"""Department state REST endpoints.

Session A of the "Daena as a Living Company" plan. Exposes:

* ``GET /api/v1/department-states`` -- snapshot for the Company
  Dashboard. Returns all 10 canonical departments, materializing
  defaults for any the tenant has not touched yet.
* ``POST /api/v1/department-states/{department}/offline`` -- admin
  kill-switch for a single department.

Writes (mark_working / mark_idle) are NOT exposed via REST -- those
happen inside SwarmExecutor at subtask boundaries. Exposing them
would let a malicious caller corrupt the queue_depth counter.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.department_state_service import (
    _CANONICAL_DEPARTMENTS,
    DepartmentStateService,
)

logger = get_logger(__name__)

router = APIRouter()


@router.get("")
async def list_department_states(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Snapshot of all 10 departments for the Company Dashboard.

    Empty or new tenants get a full 10-department response with every
    department reporting IDLE; the frontend can render without special
    cases for first-time tenants.
    """
    svc = DepartmentStateService(db)
    snap = await svc.snapshot(tenant_id=user.tenant_id)
    return {"success": True, "data": snap}


@router.get("/{department}/peer-signals")
async def get_peer_signals(
    department: str,
    limit: int = 50,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return recent peer signals relevant to this department.

    Populated by the BorderAgent (one per tenant + department) which
    subscribes to the process-wide EventBus and filters by the
    relevance lens in ``border_agent.DEPARTMENT_RELEVANCE``.

    This is what each department's chat room polls to render its
    "Peer Signals" feed -- replacing the deleted DepartmentInbox page
    with a per-department, relevance-filtered view.

    "Daena" is accepted as a special-case department name. She is
    the 11th BorderAgent -- the supervisor/VP the founder talks to --
    with a wildcard relevance lens so her feed contains every signal
    across all 10 departments.
    """
    valid = set(_CANONICAL_DEPARTMENTS) | {"Daena"}
    if department not in valid:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown department '{department}'. Valid: {sorted(valid)}",
        )
    from app.services.departments.border_agent import get_border_agent

    ba = await get_border_agent(
        tenant_id=user.tenant_id, department=department,
    )
    signals = ba.recent_signals(limit=max(1, min(int(limit), 200)))
    return {
        "success": True,
        "data": {
            "department": department,
            "count": len(signals),
            "signals": signals,
        },
    }


@router.post("/{department}/offline")
async def set_department_offline(
    department: str,
    user: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Kill-switch: take a department offline. ADMIN only.

    Accepted department names match the canonical list. Anything else
    is rejected with 404 to avoid seeding garbage rows.
    """
    if department not in _CANONICAL_DEPARTMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown department '{department}'. Valid: {list(_CANONICAL_DEPARTMENTS)}",
        )
    svc = DepartmentStateService(db)
    row = await svc.set_offline(tenant_id=user.tenant_id, department=department)
    return {
        "success": True,
        "data": {
            "department_name": row.department_name,
            "status": row.status,
            "queue_depth": row.queue_depth,
        },
    }
