"""System self-diagnostic endpoint.

PR-DAENA-SELF-DIAGNOSTIC-RUNTIME-AWARENESS (Sprint-6 PR-7, 2026-05-04).

Single read-only endpoint that aggregates the operator-visible
"is everything OK?" picture so Daena can speak to her own runtime
state in chat without dumping individual subsystem checks.

What the endpoint returns
-------------------------

A structured diagnostic with:

  * ``overall_status``: ``healthy`` / ``warning`` / ``blocked``
    -- conservative aggregator, the worst sub-status wins.
  * ``timestamp``: ISO-8601 UTC.
  * ``checks``: per-subsystem dict (each carries ``status`` +
    ``detail`` only -- no secrets, no env values, no token state).
  * ``recommended_actions``: ordered list of plain-English strings.
    Deterministic given the same checks payload (fixture-friendly).

Honesty rules
-------------

* Absolutely no secret read or print. Every check verifies presence
  via ``getattr(settings, "...")`` and emits only the boolean
  presence bit -- the actual value never leaves the process.
* Frontend reachable check is a localhost-only HTTP HEAD with a
  short timeout. If it fails (frontend stopped, port renumbered),
  the field is just ``reachable=False`` -- not an error that
  poisons the whole diagnostic.
* No automatic fix actions. Per the Sprint-6 brief, this PR makes
  Daena AWARE of her runtime state but never modifies system
  settings, kills processes, or runs migrations on the operator's
  behalf. Recommended actions are advisory text the operator (or
  a future approval-gated automation) acts on.
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.connection_v2.marketplace_service import MarketplaceService


logger = get_logger(__name__)
router = APIRouter()


# ── Sprint-12A PR-1/2: runtime + router readiness ────────────────────


@router.get("/runtime-readiness")
async def runtime_readiness(
    refresh: bool = False,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the readiness inventory + router summary.

    Aggregates ``runtime_truth_registry`` items (CLIs, local LLM
    endpoints, API providers) with the operational overlay
    (cost_class, recommended_role, readiness_state). NEVER returns
    secret values.

    Query param:
        refresh: when true, re-discover items first. Default false
            so the endpoint stays cheap.
    """
    from app.services.runtime_readiness import get_runtime_readiness
    return {"success": True, "data": await get_runtime_readiness(refresh=refresh)}


@router.get("/router-readiness")
async def router_readiness(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return only the router_summary slice -- 'who would Daena pick
    for each role right now'. Lightweight surface for chat / status
    pills that don't need the full inventory."""
    from app.services.runtime_readiness import get_runtime_readiness
    full = await get_runtime_readiness(refresh=False)
    return {"success": True, "data": full.get("router_summary")}


@router.get("/router-policy")
async def router_policy(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the static router policy matrix (no I/O).

    Lets the UI render "where would Daena route X" without first
    refreshing the truth registry.
    """
    from app.services.runtime_readiness import get_router_policy
    return {"success": True, "data": get_router_policy()}


# Stable status taxonomy. The worst status anywhere in `checks` becomes
# overall_status (warning > healthy; blocked > warning).
STATUS_HEALTHY = "healthy"
STATUS_WARNING = "warning"
STATUS_BLOCKED = "blocked"

_STATUS_RANK = {
    STATUS_HEALTHY: 0,
    STATUS_WARNING: 1,
    STATUS_BLOCKED: 2,
}


def _worst(*statuses: str) -> str:
    """Return the most severe status in the input list."""
    if not statuses:
        return STATUS_HEALTHY
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, 0))


# ──────────────────────────────────────────────────────────────────
# Sub-checks
# ──────────────────────────────────────────────────────────────────


async def _check_backend() -> dict[str, Any]:
    """Trivially healthy if the function executes -- the FastAPI
    router can only run if the process is up. Captured so the
    payload always has a backend entry."""
    return {
        "status": STATUS_HEALTHY,
        "detail": "backend process responsive",
    }


async def _check_database(db: AsyncSession) -> dict[str, Any]:
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        return {"status": STATUS_HEALTHY, "detail": "select 1 ok"}
    except Exception as exc:
        return {
            "status": STATUS_BLOCKED,
            "detail": f"db_query_failed: {type(exc).__name__}",
        }


async def _check_migration_head(db: AsyncSession) -> dict[str, Any]:
    """Read alembic_version.version_num. Absent table = migrations
    haven't been initialized; surfaced as warning (dev SQLite via
    create_all is fine but not ideal)."""
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.scalar_one_or_none()
        if row is None:
            return {
                "status": STATUS_WARNING,
                "detail": "alembic_version table empty",
            }
        return {
            "status": STATUS_HEALTHY,
            "detail": "head present",
            "current": str(row),
        }
    except Exception as exc:
        # Table absent on dev SQLite via create_all path -- not a
        # blocker, just an indicator that migrations haven't been
        # explicitly run.
        return {
            "status": STATUS_WARNING,
            "detail": (
                f"alembic_version unreadable: {type(exc).__name__} "
                "(typical on dev SQLite via create_all)"
            ),
        }


async def _check_frontend_reachable() -> dict[str, Any]:
    """HEAD localhost:5173 with a short timeout. Frontend is
    optional from the backend's POV; reachable=False is informational
    not an error."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.request(
                "GET", "http://127.0.0.1:5173/",
            )
            ok = 200 <= resp.status_code < 500
            return {
                "status": STATUS_HEALTHY if ok else STATUS_WARNING,
                "detail": (
                    f"vite responded {resp.status_code}" if ok
                    else f"vite responded {resp.status_code} (unexpected)"
                ),
                "reachable": ok,
            }
    except Exception:
        return {
            "status": STATUS_WARNING,
            "detail": "vite not reachable on 127.0.0.1:5173",
            "reachable": False,
        }


async def _check_local_models() -> dict[str, Any]:
    """Probe the two configured local model endpoints (Ollama +
    llama-server / vLLM). Either being down is a warning, not a
    blocker -- Daena routes around them via cloud providers."""
    settings = get_settings()
    ollama_url = getattr(settings, "ollama_base_url", None)
    vllm_url = getattr(settings, "vllm_base_url", None)
    ollama_enabled = getattr(settings, "ollama_enabled", False)

    async def _probe(url: str | None, path: str) -> bool:
        if not url:
            return False
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(url.rstrip("/") + path)
                return 200 <= resp.status_code < 500
        except Exception:
            return False

    ollama_up = await _probe(ollama_url, "/api/tags") if ollama_enabled else False
    vllm_up = await _probe(vllm_url, "/models")

    if not ollama_enabled and not vllm_up:
        # User has disabled Ollama and no llama-server is up -- routes
        # will fall through to cloud providers, which is fine. Surface
        # as warning so the operator knows nothing local is online.
        return {
            "status": STATUS_WARNING,
            "detail": "ollama disabled, llama-server unreachable",
            "ollama_enabled": ollama_enabled,
            "ollama_up": False,
            "vllm_up": vllm_up,
        }
    if ollama_enabled and not ollama_up and not vllm_up:
        return {
            "status": STATUS_WARNING,
            "detail": "both ollama and vllm probes failed",
            "ollama_enabled": ollama_enabled,
            "ollama_up": False,
            "vllm_up": False,
        }
    return {
        "status": STATUS_HEALTHY,
        "detail": "at least one local endpoint responding",
        "ollama_enabled": ollama_enabled,
        "ollama_up": ollama_up,
        "vllm_up": vllm_up,
    }


async def _check_connector_callability(
    db: AsyncSession, tenant_id,
) -> dict[str, Any]:
    """Reuse the PR-2 marketplace diagnostic. Slimmer surface so
    the self-diagnostic stays under a couple hundred lines of JSON."""
    try:
        svc = MarketplaceService(db, tenant_id=tenant_id)
        summary = await svc.diagnostic_summary()
        totals = summary.get("totals", {})
        callable_count = totals.get("callable", 0)
        catalog = totals.get("catalog", 0)
        blocked = totals.get("blocked", 0)
        # 0 callable is the dominant local-laptop state; still useful
        # info but not a "blocked" status (Daena is fully usable for
        # chat without callable connectors).
        status = STATUS_HEALTHY if callable_count > 0 else STATUS_WARNING
        # Top blocker reason for the recommendations.
        top_blockers = summary.get("top_blockers", [])
        top_reason = top_blockers[0]["reason"] if top_blockers else None
        return {
            "status": status,
            "detail": f"{callable_count}/{catalog} callable; {blocked} blocked",
            "callable": callable_count,
            "catalog": catalog,
            "blocked": blocked,
            "top_blocker_reason": top_reason,
        }
    except Exception as exc:
        return {
            "status": STATUS_WARNING,
            "detail": f"diagnostic_summary failed: {type(exc).__name__}",
        }


def _recommended_actions(checks: dict[str, dict[str, Any]]) -> list[str]:
    """Deterministic list of next-step strings derived from the
    checks payload. Order: most actionable first.

    The text NEVER includes secret values. Each string is a
    recommendation the operator (or a future approval-gated
    automation) can act on.
    """
    out: list[str] = []
    db = checks.get("database") or {}
    if db.get("status") == STATUS_BLOCKED:
        out.append(
            "Database is unreachable. Check the .env DATABASE_URL "
            "and verify the service is running."
        )

    migration = checks.get("migration_head") or {}
    if migration.get("status") == STATUS_WARNING:
        out.append(
            "Run `alembic upgrade head` to bring the migration chain "
            "up to date (or seed the alembic_version table on a "
            "fresh dev SQLite if you want explicit version tracking)."
        )

    frontend = checks.get("frontend") or {}
    if not frontend.get("reachable", True):
        out.append(
            "Frontend is not reachable on http://127.0.0.1:5173. "
            "Run `scripts\\start-frontend-dev.bat` to start Vite."
        )

    local = checks.get("local_models") or {}
    if local.get("status") == STATUS_WARNING:
        if not local.get("ollama_enabled") and not local.get("vllm_up"):
            out.append(
                "No local LLM endpoint is online. Start "
                "llama-server.exe with a GGUF in MODELS_ROOT/gguf/, or "
                "set OLLAMA_ENABLED=true and start Ollama."
            )
        elif local.get("ollama_enabled") and not local.get("ollama_up"):
            out.append(
                "Ollama is enabled but its /api/tags probe failed. "
                "Confirm `ollama serve` is running."
            )

    callability = checks.get("connector_callability") or {}
    if callability.get("status") == STATUS_WARNING:
        catalog = callability.get("catalog", 0)
        callable_count = callability.get("callable", 0)
        if catalog > 0 and callable_count == 0:
            top = callability.get("top_blocker_reason") or "missing setup"
            out.append(
                f"{catalog} connectors in catalog, 0 callable. Top blocker: "
                f"{top}. Open Connections > Plugins to install or connect one."
            )

    if not out:
        out.append(
            "All checks pass. Daena's local runtime is healthy."
        )
    return out


# ──────────────────────────────────────────────────────────────────
# HTTP endpoint
# ──────────────────────────────────────────────────────────────────


@router.get("/self-diagnostic")
async def system_self_diagnostic(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return Daena's self-diagnostic snapshot.

    Auth-required (the diagnostic surfaces tenant-scoped connector
    counts via the marketplace summary). Read-only -- never modifies
    settings, never kills processes, never runs migrations.
    """
    started = _time.monotonic()

    checks = {}
    # Run the network probes concurrently to keep the endpoint snappy
    # (~1.5s timeout each, but several can race).
    backend, database, migration, frontend, local_models, callability = await asyncio.gather(
        _check_backend(),
        _check_database(db),
        _check_migration_head(db),
        _check_frontend_reachable(),
        _check_local_models(),
        _check_connector_callability(db, user.tenant_id),
    )
    checks["backend"] = backend
    checks["database"] = database
    checks["migration_head"] = migration
    checks["frontend"] = frontend
    checks["local_models"] = local_models
    checks["connector_callability"] = callability

    overall = _worst(*[c["status"] for c in checks.values()])

    payload = {
        "data": {
            "overall_status": overall,
            "timestamp": datetime.now(UTC).isoformat(),
            "elapsed_ms": int((_time.monotonic() - started) * 1000),
            "checks": checks,
            "recommended_actions": _recommended_actions(checks),
            # Standing safety statement so any UI that surfaces this
            # never has to fabricate the boundary.
            "boundary_notice": (
                "Daena diagnoses local runtime state but does not "
                "modify OS / cloud / secrets without explicit "
                "operator approval."
            ),
        },
    }
    return JSONResponse(content=payload)


__all__ = ["router"]
