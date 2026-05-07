"""Health check endpoints for monitoring and infrastructure probes.

Performance: Ollama status is cached for 30 seconds.  /health and
/health/detailed return in <50ms on cache hit instead of 5-10s.

Endpoints:
    GET /health           -- Liveness probe (fast, <50ms)
    GET /health/ready     -- Readiness probe (DB + Redis check)
    GET /health/detailed  -- Full diagnostics (Ollama, DB counts, uptime)
    GET /health/runtime   -- Runtime config diagnostics (founder/operator)
    GET /health/version   -- Version + build metadata
"""

from __future__ import annotations

import os
import time as _time
from typing import Any

from fastapi import APIRouter

from app.core.redis import check_redis_health

router = APIRouter()

# Track startup time for uptime calculation
_startup_time = _time.time()
_DAENA_VERSION = os.environ.get("DAENA_VERSION", "2.0.0")

# ── Ollama status cache (30s TTL) ──
_ollama_cache: dict[str, Any] = {}
_ollama_cache_ts: float = 0.0
_OLLAMA_CACHE_TTL = 30.0


async def _get_ollama_status() -> tuple[str, str | None]:
    """Get Ollama status from cache or probe (30s TTL)."""
    global _ollama_cache, _ollama_cache_ts  # noqa: PLW0603

    now = _time.monotonic()
    if _ollama_cache and (now - _ollama_cache_ts) < _OLLAMA_CACHE_TTL:
        return _ollama_cache["status"], _ollama_cache.get("model_loaded")

    status = "unknown"
    model_loaded: str | None = None
    try:
        import httpx

        from app.core.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            )
            if resp.status_code == 200:
                status = "healthy"
                models = resp.json().get("models", [])
                if models:
                    model_loaded = models[0].get("name")
            else:
                status = "degraded"
    except Exception:
        status = "unavailable"

    _ollama_cache = {"status": status, "model_loaded": model_loaded}
    _ollama_cache_ts = now
    return status, model_loaded


@router.get("")
async def health_check() -> dict:
    """Liveness probe. Returns in <50ms. Used by Docker HEALTHCHECK,
    Cloud Run liveness probe, and the frontend ``BackendOfflineBanner``.

    Stabilization 2026-04-30: Status now distinguishes optional vs
    critical degradations. Redis is documented as an OPTIONAL cache
    (CLAUDE.md: "Cache: Redis (optional, graceful fallback)"). When
    Redis is offline the backend remains fully functional, so we no
    longer flag the whole service as ``degraded`` -- which previously
    triggered the red ``BackendOfflineBanner`` and blocked the Autopilot
    button via ``backendBlocksRuntime`` for users running locally
    without Redis. Redis status is still surfaced in ``checks.redis``
    so /health/detailed can show it.

    Status legend:
        starting   -- essentials not ready (table create_all, redis probe)
        warming    -- essentials done, deferred seedings still running
        degraded   -- (reserved) critical subsystem unhealthy
        healthy    -- essentials + seedings done; service fully functional
    """
    from app.core.startup_state import startup_state

    redis_healthy = await check_redis_health()

    if not startup_state.essentials_ready:
        status = "starting"
    elif not startup_state.seedings_complete:
        status = "warming"
    else:
        status = "healthy"

    return {
        "status": status,
        "checks": {
            "redis": "healthy" if redis_healthy else "unavailable",
            "database": "healthy",
            "essentials_ready": startup_state.essentials_ready,
            "seedings_complete": startup_state.seedings_complete,
            "seed_phase": startup_state.seed_phase,
        },
        "version": _DAENA_VERSION,
    }


@router.get("/ready")
async def readiness_check() -> dict:
    """Readiness probe. Verifies DB connection + Redis before accepting traffic.
    Used by Cloud Run startup probe and load balancer.
    """
    import contextlib

    from sqlalchemy import text

    from app.core.database import async_session_factory

    db_ok = False
    with contextlib.suppress(Exception):
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
            db_ok = True

    redis_ok = await check_redis_health()

    ready = db_ok and redis_ok
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": "connected" if db_ok else "unavailable",
            "redis": "connected" if redis_ok else "unavailable",
        },
        "version": _DAENA_VERSION,
    }


@router.get("/version")
async def version_info() -> dict:
    """Build metadata for deployment verification."""
    return {
        "version": _DAENA_VERSION,
        "build_date": os.environ.get("BUILD_DATE", "unknown"),
        "git_sha": os.environ.get("GIT_SHA", "unknown"),
        "app_env": os.environ.get("APP_ENV", "development"),
    }


@router.get("/about")
async def about() -> dict:
    """Daena's identity and self-introduction. Public endpoint for
    integrations, landing pages, and service-to-service handshakes.
    """
    from app.config.founder_accounts import DAENA_IDENTITY

    return {
        "name": DAENA_IDENTITY.display_name,
        "role": DAENA_IDENTITY.role,
        "company": DAENA_IDENTITY.company,
        "email": DAENA_IDENTITY.email,
        "introduction": DAENA_IDENTITY.introduction(),
        "version": _DAENA_VERSION,
    }


@router.get("/detailed")
async def detailed_health_check() -> dict:
    """Detailed health with cached Ollama status (30s TTL)."""
    import contextlib
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.core.database import async_session_factory
    from app.models.chat import ChatMessage, ChatSession

    settings = get_settings()
    redis_healthy = await check_redis_health()
    ollama_status, model_loaded = await _get_ollama_status()

    # --- DB counts ---
    total_sessions = 0
    total_messages = 0
    last_activity: str | None = None
    with contextlib.suppress(Exception):
        async with async_session_factory() as db:
            sess_count = await db.execute(
                select(func.count(ChatSession.id)).where(
                    ChatSession.is_archived.is_(False),
                ),
            )
            total_sessions = sess_count.scalar() or 0

            msg_count = await db.execute(
                select(func.count(ChatMessage.id)),
            )
            total_messages = msg_count.scalar() or 0

            last_msg = await db.execute(
                select(ChatMessage.created_at)
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            row = last_msg.scalar()
            if row:
                last_activity = (
                    row.isoformat()
                    if hasattr(row, "isoformat")
                    else str(row)
                )

    uptime_seconds = int(_time.time() - _startup_time)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    from app.core.startup_state import startup_state

    # /detailed status: redis is optional (cache), ollama is optional
    # (only used when ollama_enabled=true). Only seed completion drives
    # the headline status -- anything else is informational.
    return {
        "status": "healthy" if startup_state.seedings_complete else "warming",
        "uptime": f"{hours}h {minutes}m {secs}s",
        "uptime_seconds": uptime_seconds,
        "ollama": {
            "status": ollama_status,
            "model_loaded": model_loaded,
            "default_model": settings.ollama_default_model,
        },
        "redis": "healthy" if redis_healthy else "unavailable",
        "database": {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "last_activity": last_activity,
        },
        "seedings": startup_state.to_dict(),
        "version": _DAENA_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/runtime")
async def runtime_health_check() -> dict:
    """Redacted runtime configuration truth for founder/operator diagnostics."""
    from app.core.config import get_settings

    settings = get_settings()
    diagnostics = settings.runtime_diagnostics()

    return {
        "status": "healthy" if not diagnostics["guardrail_issues"] else "warning",
        "runtime": diagnostics,
    }
