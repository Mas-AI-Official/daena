"""Routine Autonomy API -- Sprint-18 PR-4 (2026-05-06).

Operator surface over the routine autonomy scheduler. Skeleton
only; no cron daemon is activated in Sprint-18.

Endpoints:

  * GET  /routines                  -- list registered routines
  * GET  /routines/kinds            -- locked Sprint-18 kind set
  * POST /routines/register         -- register a routine
  * POST /routines/{id}/pause       -- pause one routine
  * POST /routines/{id}/resume      -- resume one routine
  * POST /routines/{id}/run-once    -- run once on demand
  * POST /routines/global/pause     -- pause all
  * POST /routines/global/resume    -- resume all
  * GET  /routines/global/state     -- {global_paused: bool}

All endpoints require an authenticated user. Mutations are
audit-logged via the structured logger.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services import routine_autonomy
from app.services.routine_autonomy import ROUTINE_KIND_VALUES, RoutineOutcome

logger = get_logger(__name__)
router = APIRouter()


class RoutineRow(BaseModel):
    id: str
    kind: str
    name: str
    description: str
    paused: bool
    last_run_at: str | None
    last_outcome: str | None


@router.get("/", response_model=list[RoutineRow])
async def list_(
    user: CurrentUser = Depends(get_current_user),
) -> list[RoutineRow]:
    return [
        RoutineRow(
            id=r.id, kind=r.kind, name=r.name, description=r.description,
            paused=r.paused, last_run_at=r.last_run_at,
            last_outcome=r.last_outcome,
        )
        for r in routine_autonomy.list_routines()
    ]


class KindsResponse(BaseModel):
    kinds: list[str]


@router.get("/kinds", response_model=KindsResponse)
async def list_kinds(
    user: CurrentUser = Depends(get_current_user),
) -> KindsResponse:
    return KindsResponse(kinds=sorted(ROUTINE_KIND_VALUES))


class RegisterRequest(BaseModel):
    kind: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


@router.post("/register", response_model=RoutineRow)
async def register(
    body: RegisterRequest,
    user: CurrentUser = Depends(get_current_user),
) -> RoutineRow:
    try:
        r = routine_autonomy.register_routine(
            kind=body.kind, name=body.name, description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RoutineRow(
        id=r.id, kind=r.kind, name=r.name, description=r.description,
        paused=r.paused, last_run_at=r.last_run_at,
        last_outcome=r.last_outcome,
    )


@router.post("/{routine_id}/pause", response_model=RoutineRow)
async def pause(
    routine_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> RoutineRow:
    r = routine_autonomy.pause_routine(routine_id)
    if r is None:
        raise HTTPException(status_code=404, detail="routine_not_found")
    return RoutineRow(
        id=r.id, kind=r.kind, name=r.name, description=r.description,
        paused=r.paused, last_run_at=r.last_run_at,
        last_outcome=r.last_outcome,
    )


@router.post("/{routine_id}/resume", response_model=RoutineRow)
async def resume(
    routine_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> RoutineRow:
    r = routine_autonomy.resume_routine(routine_id)
    if r is None:
        raise HTTPException(status_code=404, detail="routine_not_found")
    return RoutineRow(
        id=r.id, kind=r.kind, name=r.name, description=r.description,
        paused=r.paused, last_run_at=r.last_run_at,
        last_outcome=r.last_outcome,
    )


class RunOnceResponse(BaseModel):
    routine_id: str
    outcome: str
    detail: str | None
    artifacts_created: list[str]
    started_at: str | None
    finished_at: str | None


@router.post("/{routine_id}/run-once", response_model=RunOnceResponse)
async def run_once(
    routine_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunOnceResponse:
    # Pass tenant context so handlers that need DB scope have it.
    # Handlers that don't need it can ignore the kwargs.
    result = await routine_autonomy.run_once(
        routine_id,
        db=db,
        tenant_id=user.tenant_id,
        user_id=user.id,
    )
    if result.outcome == RoutineOutcome.OK:
        await db.commit()
    logger.info(
        "routines.run_once.complete",
        routine_id=routine_id,
        outcome=result.outcome.value,
    )
    return RunOnceResponse(
        routine_id=result.routine_id,
        outcome=result.outcome.value,
        detail=result.detail,
        artifacts_created=result.artifacts_created,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


class GlobalState(BaseModel):
    global_paused: bool


@router.get("/global/state", response_model=GlobalState)
async def global_state(
    user: CurrentUser = Depends(get_current_user),
) -> GlobalState:
    return GlobalState(global_paused=routine_autonomy.is_global_paused())


@router.post("/global/pause", response_model=GlobalState)
async def global_pause(
    user: CurrentUser = Depends(get_current_user),
) -> GlobalState:
    routine_autonomy.pause_all()
    logger.info("routines.global.paused", by=str(user.id))
    return GlobalState(global_paused=True)


@router.post("/global/resume", response_model=GlobalState)
async def global_resume(
    user: CurrentUser = Depends(get_current_user),
) -> GlobalState:
    routine_autonomy.resume_all()
    logger.info("routines.global.resumed", by=str(user.id))
    return GlobalState(global_paused=False)
