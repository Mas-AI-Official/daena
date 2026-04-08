"""Daena Backend — FastAPI Application Entry Point.

This is the single entry point for the entire backend.
Configures middleware, exception handlers, and mounts API routes.
In production, also serves the compiled frontend SPA.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def _seed_departments_for_all_tenants() -> None:
    """Seed 10 default departments for every tenant that has none.

    Runs once on startup. Idempotent -- skips tenants that already
    have departments. Uses AgentService.seed_defaults() which also
    creates the 60 sub-capability agents per tenant.
    """
    from sqlalchemy import func, select

    from app.core.database import async_session_factory
    from app.models.identity import Tenant
    from app.models.organization import Department
    from app.services.agents import AgentService

    async with async_session_factory() as db:
        try:
            tenants_result = await db.execute(select(Tenant))
            tenants = list(tenants_result.scalars().all())

            seeded = 0
            for tenant in tenants:
                # Always run seed_defaults — it's idempotent and creates
                # any missing departments, agents, AND skills.
                # Previously only ran when dept_count == 0, which meant
                # skills added after initial deployment were never seeded.
                svc = AgentService(db)
                result = await svc.seed_defaults(tenant_id=tenant.id)
                created = (
                    result["departments_created"]
                    + result["agents_created"]
                    + result["skills_created"]
                )
                if created > 0:
                    seeded += 1
                    logger.info(
                        "tenant_seeded",
                        tenant_id=str(tenant.id),
                        departments=result["departments_created"],
                        agents=result["agents_created"],
                        skills=result["skills_created"],
                    )

            await db.commit()
            if seeded:
                logger.info("auto_seed_complete", tenants_seeded=seeded)
            else:
                logger.debug("auto_seed_skipped", reason="all tenants fully seeded")
        except Exception as exc:
            await db.rollback()
            logger.warning("auto_seed_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events.

    Startup:
        - Configures structured logging
        - Checks Redis connectivity (warns if unavailable, does not block)
        - Logs EventBus readiness

    Shutdown:
        - Closes Redis connection pool
        - Logs shutdown
    """
    import time as _time

    settings = get_settings()
    setup_logging(log_level=settings.log_level, json_output=settings.is_production)
    _t0 = _time.perf_counter()
    diagnostics = settings.runtime_diagnostics()
    logger.info(
        "daena_starting",
        app_name=settings.app_name,
        env=settings.app_env,
        debug=settings.debug,
    )
    logger.info(
        "runtime_config_truth",
        app_env=diagnostics["app_env"],
        env_precedence=diagnostics["env_precedence"],
        allows_unsafe_dev_features=diagnostics["allows_unsafe_dev_features"],
        debug=diagnostics["debug"],
        disable_auth=diagnostics["disable_auth"],
        jwt_secret_key=diagnostics["jwt_secret_key"],
        vault_encryption_key=diagnostics["vault_encryption_key"],
        cors_origins=diagnostics["cors_origins"],
        ollama_default_model=diagnostics["ollama_default_model"],
        provider_keys=diagnostics["provider_keys"],
        rate_limit_fail_open=diagnostics["rate_limit_fail_open"],
        env_file=diagnostics["env_file"],
        env_file_present=diagnostics["env_file_present"],
    )

    guardrail_issues = diagnostics["guardrail_issues"]
    if guardrail_issues:
        if settings.allows_unsafe_dev_features and not settings.is_production:
            for issue in guardrail_issues:
                logger.warning("runtime_guardrail_warning", issue=issue)
        else:
            for issue in guardrail_issues:
                logger.critical("runtime_guardrail_failed", issue=issue)
            raise RuntimeError(
                "Unsafe runtime configuration: " + "; ".join(guardrail_issues)
            )

    # --- Auth bypass warning ---
    if settings.disable_auth:
        logger.warning("AUTH_DISABLED — all endpoints return dev user. Do NOT deploy this.")

    # --- Auto-create tables (idempotent — only creates missing tables) ---
    # create_all is safe for both SQLite and PostgreSQL: it checks for
    # existing tables first and only creates those that are missing.
    _skip_auto_create = False  # Always ensure tables exist
    if not _skip_auto_create:
        _ts = _time.perf_counter()
        from app.core.database import engine
        from app.models import Base  # noqa: F401 — triggers all model imports

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Migrate existing memory_entries table: add NBMF columns if missing
            from sqlalchemy import text as _text
            # SQLite doesn't support ALTER COLUMN, but VARCHAR is flexible.
            # For PostgreSQL, we'd need ALTER COLUMN content_type TYPE VARCHAR(30).
            _nbmf_cols = {
                "agent_id": "TEXT",
                "is_quarantined": "BOOLEAN DEFAULT 0",
                "trust_score": "REAL DEFAULT 0.0",
                "content_hash": "VARCHAR(64)",
                "skill_id": "VARCHAR(200)",
                "success_flag": "BOOLEAN",
                "is_sensitive": "BOOLEAN DEFAULT 0",
                "encoding_mode": "VARCHAR(20) DEFAULT 'semantic'",
                "contradiction": "BOOLEAN DEFAULT 0",
            }
            for col_name, col_type in _nbmf_cols.items():
                try:
                    await conn.execute(
                        _text(f"ALTER TABLE memory_entries ADD COLUMN {col_name} {col_type}")
                    )
                except Exception:
                    pass  # Column already exists

        logger.info("dev_tables_created", ms=int((_time.perf_counter() - _ts) * 1000))

        # Auto-seed 10 departments for any tenant missing them
        _ts = _time.perf_counter()
        await _seed_departments_for_all_tenants()
        logger.info("departments_seeded", ms=int((_time.perf_counter() - _ts) * 1000))

    # --- Demo mode seeding ---
    from app.services.demo_mode import is_demo_mode, seed_demo_data

    if is_demo_mode():
        _ts = _time.perf_counter()
        demo_result = await seed_demo_data()
        logger.info("demo_mode.active", ms=int((_time.perf_counter() - _ts) * 1000), **demo_result)
    else:
        logger.debug("demo_mode.inactive")

    # --- Redis connectivity check (non-blocking) ---
    _ts = _time.perf_counter()
    from app.core.redis import check_redis_health, get_redis_client

    redis_ok = await check_redis_health()
    _redis_ms = int((_time.perf_counter() - _ts) * 1000)
    if redis_ok:
        logger.info("redis_connected", ms=_redis_ms)
    else:
        logger.warning("redis_unavailable", ms=_redis_ms, impact="Caching degraded")

    # --- EventBus is a singleton, ready at import ---
    from app.core.events import event_bus

    logger.info("event_bus_ready", subscriptions=len(event_bus._handlers))

    # --- Model Registry (singleton, all providers) ---
    _ts = _time.perf_counter()
    from app.services.model_registry import ModelRegistry

    registry = ModelRegistry()
    await registry.initialize()
    app.state.model_registry = registry
    logger.info(
        "model_registry_ready",
        providers=len(registry._providers),
        ms=int((_time.perf_counter() - _ts) * 1000),
    )

    # --- Ollama warm-up: background task (non-blocking) ---
    # Server accepts requests immediately. First LLM call may be
    # slow if warm-up hasn't finished yet.
    async def _warmup_ollama() -> None:
        _ws = _time.perf_counter()
        try:
            import httpx

            ollama_url = settings.ollama_base_url.rstrip("/")

            # Resolve actual model name (handles "auto" -> best installed)
            from app.services.providers.ollama import OllamaProvider

            _prov = OllamaProvider()
            warmup_model = await _prov._resolve_model(settings.ollama_default_model)
            await _prov.close()

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=5.0),
            ) as warmup_client:
                warmup_resp = await warmup_client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": warmup_model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "keep_alive": "30m",
                        "options": {"num_predict": 1},
                    },
                )
                warmup_resp.raise_for_status()
            logger.info(
                "ollama_warmup_complete",
                model=warmup_model,
                ms=int((_time.perf_counter() - _ws) * 1000),
            )
        except Exception as exc:
            logger.warning(
                "ollama_warmup_failed",
                error=str(exc),
                impact="First request will be slow (model loads on demand)",
            )

    import asyncio

    asyncio.create_task(_warmup_ollama())

    # --- Runtime Registry: discover CLIs, check health, probe subscriptions ---
    _ts = _time.perf_counter()
    from app.core.events import initialize_runtime_registry

    try:
        installed = await initialize_runtime_registry()
        installed_names = [k for k, v in installed.items() if v]
        logger.info(
            "runtime_registry_ready",
            installed=installed_names,
            total=len(installed),
            ms=int((_time.perf_counter() - _ts) * 1000),
        )
    except Exception as rt_exc:
        logger.warning(
            "runtime_registry_init_failed",
            error=str(rt_exc),
            impact="CLI runtimes unavailable until next health check",
        )

    # --- Dream Engine: autonomous memory consolidation ---
    from app.services.dream_engine import get_dream_engine

    dream_engine = get_dream_engine()
    app.state.dream_engine = dream_engine

    # Auto-schedule Dream Engine via APScheduler (every 15 min if idle 5+ min)
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        dream_scheduler = AsyncIOScheduler()

        async def _dream_job():
            if not dream_engine.should_run(idle_seconds=300):
                return
            if dream_engine.is_running:
                return
            try:
                from app.core.database import async_session_factory
                async with async_session_factory() as db_session:
                    report = await dream_engine.run_cycle(
                        db_session=db_session, tenant_id="system"
                    )
                    logger.info(
                        "dream_engine.auto_cycle",
                        **report.summary(),
                    )
            except Exception as dream_exc:
                logger.warning("dream_engine.auto_cycle_failed", error=str(dream_exc))

        dream_scheduler.add_job(
            _dream_job,
            trigger=IntervalTrigger(minutes=15),
            id="dream_engine",
            replace_existing=True,
            max_instances=1,
        )
        dream_scheduler.start()
        app.state.dream_scheduler = dream_scheduler
        logger.info("dream_engine_ready", scheduled=True, interval_min=15)
    except ImportError:
        logger.info("dream_engine_ready", scheduled=False, reason="apscheduler_not_installed")

    # ── Initialize Tool Lifecycle Manager ──
    try:
        from app.services.tool_lifecycle.orchestra_integration import initialize_tlm
        initialize_tlm()
        logger.info("tlm_initialized")
    except Exception as tlm_exc:
        logger.warning("tlm_init_failed", error=str(tlm_exc))

    logger.info("daena_startup_complete", total_ms=int((_time.perf_counter() - _t0) * 1000))

    yield

    # --- Shutdown ---
    # Close WebSocket connections and heartbeat
    from app.api.v1.ws import manager as ws_manager

    try:
        await ws_manager.shutdown()
    except Exception:
        logger.debug("ws_manager_close_skipped")

    # Close model registry (provider HTTP clients)
    try:
        await registry.close()
        logger.info("model_registry_closed")
    except Exception:
        logger.debug("model_registry_close_skipped")

    try:
        client = get_redis_client()
        await client.aclose()
        logger.info("redis_connection_closed")
    except Exception:
        logger.debug("redis_close_skipped", reason="client unavailable")

    logger.info("daena_shutting_down")


def create_app() -> FastAPI:
    """Factory function to create the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Governed Multi-Agent LLM Orchestration Platform",
        version="0.1.0",
        lifespan=lifespan,
        default_response_class=JSONResponse,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # --- CORS ---
    cors_origins = settings.cors_origins
    if settings.is_production and "*" in cors_origins:
        raise RuntimeError(
            "CORS wildcard '*' is not allowed in production. "
            "Set CORS_ORIGINS to specific domains (e.g. 'https://daena.mas-ai.co')."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Custom Middleware ---
    # Order: request_id (outermost) → rate_limit → tenant (innermost)
    # Starlette is LIFO: last added = outermost. Add in reverse.
    from app.middleware.rate_limit import RateLimitMiddleware
    from app.middleware.request_id import RequestIDMiddleware
    from app.middleware.tenant import TenantMiddleware

    app.add_middleware(TenantMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # --- Exception Handlers ---
    from app.core.exceptions import DaenaError

    @app.exception_handler(DaenaError)
    async def daena_error_handler(request: Request, exc: DaenaError) -> JSONResponse:
        """Handle all custom Daena exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all: never leak internal error messages to users."""
        from app.core.logging import get_logger
        _log = get_logger("error_handler")
        _log.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Something went wrong. Please try again.",
                },
            },
        )

    # --- Routes ---
    from app.api.v1 import router as v1_router
    app.include_router(v1_router, prefix="/api/v1")

    # --- DaenaBot Bridge WebSocket ---
    from app.api.v1.bridge import router as bridge_router
    app.include_router(bridge_router)

    # --- Health Check (root) ---
    _version = os.environ.get("DAENA_VERSION", "2.0.0")

    @app.get("/health", tags=["system"])
    async def health_check() -> dict:
        """Root liveness probe (Docker HEALTHCHECK + Cloud Run)."""
        return {
            "status": "healthy",
            "service": "daena-backend",
            "version": _version,
            "app_env": settings.app_env,
        }

    # --- Production: Serve Frontend SPA ---
    # In production, the Vite build output is copied to /app/static
    # during the Docker multi-stage build. FastAPI serves it directly.
    _static_dir = Path(os.environ.get("STATIC_DIR", "/app/static"))
    if settings.is_production and _static_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        _index_html = _static_dir / "index.html"

        # Serve static assets (JS, CSS, images) under /assets
        _assets_dir = _static_dir / "assets"
        if _assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(_assets_dir)),
                name="frontend-assets",
            )

        # Serve other static root files (favicon, manifest, robots.txt)
        @app.get("/favicon.ico", include_in_schema=False)
        @app.get("/manifest.json", include_in_schema=False)
        @app.get("/robots.txt", include_in_schema=False)
        async def static_root_files(request: Request) -> FileResponse:
            """Serve root-level static files."""
            filename = request.url.path.lstrip("/")
            file_path = _static_dir / filename
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(_index_html))

        # SPA catch-all: any route not matched above returns index.html
        # so React Router handles client-side navigation.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            """Catch-all route for SPA client-side routing."""
            file_path = _static_dir / full_path
            if file_path.is_file() and ".." not in full_path:
                return FileResponse(str(file_path))
            return FileResponse(str(_index_html))

        logger.info(
            "frontend_spa_mounted",
            static_dir=str(_static_dir),
            has_index=_index_html.is_file(),
        )

    return app


# Application instance (uvicorn entry point)
app = create_app()
