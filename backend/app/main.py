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

# Load .env BEFORE any other imports so env vars are available to
# os.environ.get() calls throughout the app (pydantic-settings only
# populates declared Settings fields; custom vars like EVILBOB_KEY
# need to be loaded into the process environment explicitly).
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.is_file():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on process env only

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.startup_state import startup_state

logger = get_logger(__name__)


def _publish_ready_port_file() -> None:
    """Publish frontend proxy port only after FastAPI startup is complete.

    When ``backend/run.py`` is the entry point, ``DAENA_BOUND_PORT`` +
    ``DAENA_PORT_FILE`` are set explicitly (so we capture the
    auto-fallback port from ``find_free_port``). When uvicorn is invoked
    directly (e.g. via the launch.json config), those env vars are
    missing -- in that case we fall back to ``settings.port`` and
    write to ``backend/.daena-port`` so the Vite proxy still self-heals.
    """
    bound_port = os.environ.get("DAENA_BOUND_PORT")
    port_file_raw = os.environ.get("DAENA_PORT_FILE")

    # Fallbacks for direct-uvicorn / IDE launch paths.
    if not bound_port:
        try:
            bound_port = str(get_settings().port)
        except Exception:
            return
    if not port_file_raw:
        port_file_raw = str(Path(__file__).resolve().parent.parent / ".daena-port")

    port_file = Path(port_file_raw)
    tmp_file = port_file.with_suffix(port_file.suffix + ".tmp")
    try:
        port_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file.write_text(bound_port, encoding="utf-8")
        os.replace(tmp_file, port_file)
        # Also export the env vars so the shutdown handler can find them.
        os.environ["DAENA_BOUND_PORT"] = bound_port
        os.environ["DAENA_PORT_FILE"] = str(port_file)
        logger.info("backend_port_file_published", port=bound_port, path=str(port_file))
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "backend_port_file_publish_failed",
            port=bound_port,
            path=str(port_file),
            error=str(exc),
        )


def _clear_ready_port_file() -> None:
    """Remove `.daena-port` on shutdown if it still points to this process."""
    bound_port = os.environ.get("DAENA_BOUND_PORT")
    port_file_raw = os.environ.get("DAENA_PORT_FILE")
    if not bound_port or not port_file_raw:
        return
    port_file = Path(port_file_raw)
    try:
        if port_file.read_text(encoding="utf-8").strip() == bound_port:
            port_file.unlink()
            logger.info("backend_port_file_removed", port=bound_port, path=str(port_file))
    except FileNotFoundError:
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "backend_port_file_remove_failed",
            port=bound_port,
            path=str(port_file),
            error=str(exc),
        )


async def _seed_founder_accounts() -> None:
    """Ensure founder accounts exist so Masoud can log in.

    Reads ``founder_email``, ``founder_personal_email``, and
    ``founder_default_password`` from settings. For each configured
    email, checks if a User row exists; if not, creates a Tenant
    (if the configured tenant slug is new) + User with role=FOUNDER +
    terms_accepted_at set (the founder authored the terms).

    Idempotent. Skips silently when any required field is empty -- the
    repo ships with only emails in .env, not passwords, so operators
    must opt in by setting FOUNDER_DEFAULT_PASSWORD before restart.
    """
    import re
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.core.security import hash_password
    from app.models.identity import Tenant, User

    settings = get_settings()
    emails = [e.strip() for e in (
        settings.founder_email, settings.founder_personal_email,
    ) if e and e.strip()]
    if not emails or not settings.founder_default_password:
        logger.debug(
            "founder_seed_skipped",
            reason="FOUNDER_EMAIL/FOUNDER_PERSONAL_EMAIL/FOUNDER_DEFAULT_PASSWORD not all set",
        )
        return

    tenant_name = settings.founder_tenant_name
    slug = re.sub(r"[^a-z0-9-]", "-", tenant_name.lower()).strip("-") or "mas-ai"

    async with async_session_factory() as db:
        try:
            # Ensure tenant exists (shared across founder emails so both
            # accounts land in the same workspace).
            tenant_row = (await db.execute(
                select(Tenant).where(Tenant.slug == slug)
            )).scalar_one_or_none()
            if tenant_row is None:
                tenant_row = Tenant(name=tenant_name, slug=slug)
                db.add(tenant_row)
                await db.flush()

                # Seed departments for the new founder tenant right away.
                from app.services.agents import AgentService
                svc = AgentService(db)
                await svc.seed_defaults(tenant_id=tenant_row.id)

            seeded_users: list[str] = []
            for email in emails:
                existing = (await db.execute(
                    select(User).where(User.email == email)
                )).scalar_one_or_none()
                if existing is not None:
                    continue
                user = User(
                    tenant_id=tenant_row.id,
                    email=email,
                    password_hash=hash_password(settings.founder_default_password),
                    display_name="Masoud Masoori",
                    role="FOUNDER",
                    email_verified=True,
                    is_active=True,
                    terms_accepted_at=datetime.now(UTC),
                    terms_version="2026-03-22",
                )
                db.add(user)
                seeded_users.append(email)

            if seeded_users:
                await db.commit()
                logger.info(
                    "founder_accounts_seeded",
                    tenant=tenant_name,
                    emails=seeded_users,
                )
            else:
                logger.debug(
                    "founder_accounts_already_exist",
                    emails=emails,
                )
        except Exception as exc:
            await db.rollback()
            logger.warning("founder_seed_failed", error=str(exc))


async def _seed_connector_catalog() -> None:
    """Seed the global ``connectors`` table from the bundled JSON catalog.

    The frontend Plugins tab used to hardcode a ~110 entry CONNECTORS
    array; this function migrates that list into the existing
    ``Connector`` model so the catalog can grow without a frontend
    release. Idempotent: each run upserts by ``Connector.name`` (which
    is unique per the model). Fail-safe: any error is logged + we
    continue startup so a malformed JSON file never bricks the app.
    """
    import json
    from pathlib import Path

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.connections import Connector

    catalog_path = Path(__file__).resolve().parent / "config" / "connector_catalog.json"
    if not catalog_path.is_file():
        logger.debug(
            "connector_catalog_seed_skipped",
            reason="connector_catalog.json missing",
            path=str(catalog_path),
        )
        return

    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(
            "connector_catalog_seed_failed_parse",
            error=str(exc),
            path=str(catalog_path),
        )
        return

    version = payload.get("version", "unknown")
    raw_entries = payload.get("connectors") or []
    if not isinstance(raw_entries, list):
        logger.warning(
            "connector_catalog_seed_failed_shape",
            reason="connectors key must be a list",
        )
        return

    upserted = 0
    skipped = 0
    async with async_session_factory() as db:
        try:
            for entry in raw_entries:
                if not isinstance(entry, dict):
                    continue
                name = (entry.get("name") or "").strip()
                if not name:
                    continue
                desired = {
                    "description": entry.get("description"),
                    "auth_type": (entry.get("auth_type") or "none").strip(),
                    "config_schema": entry.get("config_schema") or {},
                    "tools": entry.get("tools") or [],
                    "icon_url": entry.get("icon_url"),
                    "category": entry.get("category"),
                }

                existing = (
                    await db.execute(select(Connector).where(Connector.name == name))
                ).scalar_one_or_none()

                if existing is None:
                    db.add(Connector(name=name, **desired))
                    upserted += 1
                    continue

                # Update only when something actually changed -- keeps
                # the audit log quiet on no-op restarts.
                changed = False
                for field, new_value in desired.items():
                    if getattr(existing, field) != new_value:
                        setattr(existing, field, new_value)
                        changed = True
                if changed:
                    upserted += 1
                else:
                    skipped += 1

            await db.commit()
            logger.info(
                "connector_catalog_seeded",
                version=version,
                count=upserted,
                unchanged=skipped,
                total=len(raw_entries),
            )
        except Exception as exc:
            await db.rollback()
            logger.warning(
                "connector_catalog_seed_failed",
                error=str(exc),
                version=version,
            )


async def _seed_departments_for_all_tenants() -> None:
    """Seed 10 default departments for every tenant that has none.

    Runs once on startup. Idempotent -- skips tenants that already
    have departments. Uses AgentService.seed_defaults() which also
    creates the 60 sub-capability agents per tenant.

    Stabilization 2026-04-29: Demoted ``tenant_seeded`` to DEBUG when
    nothing was created (the loop fired ``tenant_seeded`` per tenant on
    every restart, even on no-ops, producing the "tons of tenant
    hydration lines" log spam the user reported).
    """
    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.identity import Tenant
    from app.services.agents import AgentService

    async with async_session_factory() as db:
        try:
            tenants_result = await db.execute(select(Tenant))
            tenants = list(tenants_result.scalars().all())

            seeded_any = 0
            noop = 0
            for tenant in tenants:
                # Always run seed_defaults -- it's idempotent and creates
                # any missing departments, agents, AND skills. Previously
                # only ran when dept_count == 0, which meant skills added
                # after initial deployment were never seeded.
                svc = AgentService(db)
                result = await svc.seed_defaults(tenant_id=tenant.id)
                created = (
                    result["departments_created"]
                    + result["agents_created"]
                    + result["skills_created"]
                )
                if created > 0:
                    seeded_any += 1
                    logger.info(
                        "tenant_seeded",
                        tenant_id=str(tenant.id),
                        departments=result["departments_created"],
                        agents=result["agents_created"],
                        skills=result["skills_created"],
                    )
                else:
                    noop += 1

            await db.commit()
            if seeded_any:
                logger.info(
                    "auto_seed_complete",
                    tenants_seeded=seeded_any,
                    tenants_noop=noop,
                    tenants_total=len(tenants),
                )
            else:
                # Quiet path -- everything was already seeded. Single DEBUG
                # line replaces the per-tenant info spam.
                logger.debug(
                    "auto_seed_skipped",
                    reason="all tenants fully seeded",
                    tenants=len(tenants),
                )
        except Exception as exc:
            await db.rollback()
            logger.warning("auto_seed_failed", error=str(exc))


async def _run_deferred_initialization(app: FastAPI) -> None:
    """Run all idempotent seedings + slow registry hydrations in the background.

    Stabilization 2026-04-29: This function used to be inline in `lifespan()`,
    which made cold-start take 10-30s and meant `.daena-port` was never
    published if any step raised. Now we publish the port file the moment
    essentials complete (Redis health + tables) and run everything else
    here, in parallel with FastAPI serving requests.

    Order constraints:
      * founder_seed must run before dept_seed (dept seed walks every
        tenant; founder seed may create the MAS-AI tenant on first boot)
      * everything else is independent

    All errors are caught + recorded to ``startup_state``; nothing here
    can break the running server.
    """
    import asyncio
    import time as _time

    settings = get_settings()

    async def _step(name: str, coro_factory) -> None:
        """Run one deferred step, log timing, record errors to startup_state."""
        startup_state.set_seed_phase(name)
        _ts = _time.perf_counter()
        try:
            await coro_factory()
            logger.info(
                f"deferred.{name}.complete",
                ms=int((_time.perf_counter() - _ts) * 1000),
            )
        except Exception as exc:
            logger.warning(
                f"deferred.{name}.failed",
                error=str(exc),
                ms=int((_time.perf_counter() - _ts) * 1000),
            )
            startup_state.record_seed_error(name, str(exc))

    # 1. Founder accounts (before any tenant-walking step)
    await _step("founder_seed", _seed_founder_accounts)

    # 2. Departments for every tenant
    await _step("dept_seed", _seed_departments_for_all_tenants)

    # 3. Connector catalog (independent of tenants)
    await _step("connector_catalog", _seed_connector_catalog)

    # 4. Demo mode seeding (gated on env)
    async def _demo_seed() -> None:
        from app.services.demo_mode import is_demo_mode, seed_demo_data

        if is_demo_mode():
            demo_result = await seed_demo_data()
            logger.info("demo_mode.active", **demo_result)
        else:
            logger.debug("demo_mode.inactive")

    await _step("demo_mode", _demo_seed)

    # 5. Company context (soul vault hydrate)
    async def _company_context() -> None:
        from pathlib import Path

        from app.services.company_context import company_context_store

        _soul_root = Path(__file__).resolve().parent / "soul"
        _hydrated = company_context_store.hydrate_from_disk(_soul_root)
        logger.info(
            "company_context.hydrated",
            count=_hydrated,
            soul_root=str(_soul_root),
        )

    await _step("company_context", _company_context)

    # 6. Ollama warm-up (gated on flag, fire-and-forget so a slow
    # warm-up doesn't gate other deferred steps)
    if settings.ollama_enabled:
        async def _warmup_ollama() -> None:
            import httpx

            from app.services.providers.ollama import (
                OllamaProvider,
                resolve_ollama_base_url,
            )

            ollama_url = resolve_ollama_base_url(
                settings.ollama_base_url
            ).rstrip("/")
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
            logger.info("ollama_warmup_complete", model=warmup_model)

        # Fire-and-forget: don't await, this can take a while.
        asyncio.create_task(_warmup_ollama())
    else:
        logger.info(
            "ollama.disabled_by_config",
            hint="Set OLLAMA_ENABLED=true in .env to re-enable.",
        )

    # 7. Runtime registry (CLI discovery + health + subscriptions)
    async def _runtime_registry_init() -> None:
        from app.core.events import initialize_runtime_registry

        installed = await initialize_runtime_registry()
        installed_names = [k for k, v in installed.items() if v]
        logger.info(
            "runtime_registry_ready",
            installed=installed_names,
            total=len(installed),
        )

    await _step("runtime_registry", _runtime_registry_init)

    # 8. MCP Registry hydrate
    async def _mcp_init() -> None:
        from app.services.mcp_registry import init_mcp_registry

        mcp_count = await init_mcp_registry(app)
        logger.info("mcp_registry_ready", count=mcp_count)

    await _step("mcp_registry", _mcp_init)

    # 9. Background queue + cron scheduler + dream engine + TLM + evilbob
    async def _background_queue() -> None:
        from app.services.autopilot import init_background_queue

        await init_background_queue(app)

    await _step("background_queue", _background_queue)

    async def _cron_scheduler() -> None:
        from app.core.events import get_runtime_registry
        from app.services.heartbeat.cron_scheduler import (
            set_runtime_registry_resolver,
            start_cron_scheduler,
        )

        set_runtime_registry_resolver(get_runtime_registry)
        await start_cron_scheduler()

    await _step("cron_scheduler", _cron_scheduler)

    # PR-HB-DAEMON-WIRE (2026-05-02): start the HeartbeatDaemon so the
    # SettingsHeartbeat Pause / Resume / Stop / Run-now controls reflect
    # a real loop instead of a decorative absence (Backlog P0-09;
    # Atlas Appendix B.3; Rule 17). The daemon's start() is idempotent
    # against task aliveness so a repeat lifespan boot or stray operator
    # call cannot duplicate the loop. Default check set is hardened to
    # cheap local probes only (TEST_SUITE / GITHUB_ISSUES /
    # OLLAMA_* / DAILY_REPORT / DEPARTMENT_WORKFLOWS / AUTONOMOUS_WORK
    # are all enabled=False by default per HeartbeatConfig.default()),
    # so auto-start does not begin spending money or making external
    # calls until the operator opts in via SettingsHeartbeat.tsx.
    async def _heartbeat_daemon() -> None:
        from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon

        daemon = HeartbeatDaemon.get_instance()
        await daemon.start()
        app.state.heartbeat_daemon = daemon
        logger.info(
            "heartbeat_daemon_ready",
            interval_minutes=daemon.config.interval_minutes,
            autopilot_level=daemon.config.autopilot_level.value,
            checks_enabled=[
                c.check_type.value for c in daemon.config.checks if c.enabled
            ],
        )

    await _step("heartbeat_daemon", _heartbeat_daemon)

    async def _dream_engine() -> None:
        from app.services.dream_engine import get_dream_engine

        dream_engine = get_dream_engine()
        app.state.dream_engine = dream_engine

        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            logger.info("dream_engine_ready", scheduled=False, reason="apscheduler_not_installed")
            return

        dream_scheduler = AsyncIOScheduler()

        async def _dream_job() -> None:
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
                    logger.info("dream_engine.auto_cycle", **report.summary())
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

    await _step("dream_engine", _dream_engine)

    async def _tlm_init() -> None:
        from app.services.tool_lifecycle.orchestra_integration import initialize_tlm

        initialize_tlm()
        logger.info("tlm_initialized")

    await _step("tlm", _tlm_init)

    async def _provider_v2_seed() -> None:
        """Phase 7-A + PR-CONN-V2-SEED-IMPORT: install probes always; seed
        per the V2 flag.

        Probes are installed unconditionally so the manual
        ``POST /api/v1/connections/v2/discovery/refresh`` endpoint can
        immediately probe newly-imported rows (otherwise every probe
        returns ``probe_unavailable``). Probe registration is in-process
        and side-effect-free; it does not write to disk or hit the
        network.

        The bulk seeding step (auto-creating provider rows for every
        tenant) stays gated on USE_CONNECTION_REGISTRY_V2 to keep
        production safe. In dev, operators trigger discovery on demand
        via the new endpoint, which calls ``ConnectionDiscoveryService``
        for the caller's tenant only.
        """
        from app.services.connection_v2.probes import install_all_probes

        # Install real probes unconditionally so the discovery endpoint
        # in dev can immediately probe newly-imported rows. Idempotent.
        install_all_probes()

        from app.core.config import get_settings as _gs
        if not _gs().use_connection_registry_v2:
            logger.info(
                "provider_v2_seed_skipped",
                reason="USE_CONNECTION_REGISTRY_V2=false",
                probes_installed=True,
            )
            return

        from app.core.database import async_session_factory
        from app.services.connection_v2.provider_seeder import (
            seed_providers_all_tenants,
        )

        try:
            async with async_session_factory() as db:
                reports = await seed_providers_all_tenants(db)
                if reports:
                    await db.commit()
            total_created = sum(len(r.created) for r in reports)
            total_existing = sum(len(r.skipped_existing) for r in reports)
            total_unconfigured = sum(
                len(r.skipped_unconfigured) for r in reports
            )
            logger.info(
                "provider_v2_seed_complete",
                tenants=len(reports),
                created=total_created,
                existing=total_existing,
                unconfigured=total_unconfigured,
            )
        except Exception as exc:  # noqa: BLE001 - never break startup
            logger.warning(
                "provider_v2_seed_failed",
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )

    await _step("provider_v2_seed", _provider_v2_seed)

    async def _evilbob_init() -> None:
        from app.services.security.evilbob_mode import auto_activate_if_configured

        evilbob_state = auto_activate_if_configured()
        if evilbob_state and evilbob_state.active:
            logger.info("evilbob_auto_active", capabilities=len(evilbob_state.capabilities))

    await _step("evilbob", _evilbob_init)

    # All deferred steps done.
    startup_state.mark_seedings_complete()
    logger.info(
        "deferred_initialization_complete",
        seed_errors=len(startup_state.seed_errors),
        snapshot=startup_state.to_dict(),
    )

    # Notify any consumer that strictly needs seed data to be ready.
    try:
        from app.core.events import event_bus

        await event_bus.publish(
            "daena.seedings_complete",
            **startup_state.to_dict(),
        )
    except Exception as exc:
        logger.debug("seedings_complete_emit_failed", error=str(exc))

    # Periodic runtime rescan loop (lifelong) -- separate from the
    # one-shot deferred init.
    async def _periodic_runtime_rescan() -> None:
        from app.core.events import get_runtime_registry
        from app.services.providers.ollama import (
            invalidate_ollama_resolver_cache,
        )

        while True:
            try:
                await asyncio.sleep(60)
                try:
                    rt_registry = get_runtime_registry()
                    await rt_registry.rediscover_all()
                except Exception as _r_exc:
                    logger.debug("runtime_rescan_failed", error=str(_r_exc))
                try:
                    invalidate_ollama_resolver_cache()
                except Exception:
                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("runtime_rescan_loop_error")

    asyncio.create_task(_periodic_runtime_rescan())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: split into essentials + deferred phases.

    ESSENTIALS (sync, must complete before serving):
        - Structured logging
        - Guardrail validation
        - Auto-create tables + ALTER TABLE migrations
        - Redis connectivity probe (timeout-bounded)
        - ModelRegistry instantiation (no health probes)
        - EventBus readiness log

    Once essentials complete, ``.daena-port`` is published and lifespan
    yields -- uvicorn starts accepting requests within ~1s of `python run.py`.

    DEFERRED (background, runs concurrently with serving):
        - Founder seed, department seed, connector catalog, demo mode
        - Company context hydrate, Ollama warmup, runtime registry,
          MCP registry, background queue, cron scheduler, dream engine,
          TLM, evilbob auto-activate

    SHUTDOWN:
        - Clear .daena-port (if owned by this process)
        - Cancel deferred task
        - Stop cron scheduler, background queue
        - Close model registry, Redis pool
    """
    import asyncio
    import time as _time

    startup_state.mark_started()
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

    # Sprint-14 PR-2 (2026-05-06): side-effect-import the controlled
    # execution handlers package so each handler registers itself with
    # the dispatcher's _TOOL_HANDLERS registry before the first request.
    # The import does not run any handler -- it just makes the registry
    # non-empty for tools the operator unlocked in WRITE_TOOLS.
    try:
        import app.services.controlled_execution_handlers  # noqa: F401
        logger.info("controlled_execution.handlers.registered")
    except Exception as exc:  # noqa: BLE001 -- best-effort
        logger.error(
            "controlled_execution.handlers.import_failed",
            error=str(exc),
        )

    # === ESSENTIALS START ===

    # --- Vault V2 KEK validation (Phase 4a-2) ---
    # Refuse-to-boot in production if DAENA_KEK is missing or invalid.
    # In dev mode, fall back to a deterministic dev KEK with a warning.
    # Per ADR-002 D-003. Never logs the KEK itself, only its 8-hex
    # sha256 prefix as an identity fingerprint.
    _ts = _time.perf_counter()
    from app.core.vault_boot import (
        RefuseToBoot,
        kek_sha256_prefix,
        load_kek_from_env,
    )

    try:
        _kek = load_kek_from_env(is_production=settings.is_production)
    except RefuseToBoot as exc:
        logger.critical("vault.kek_missing_in_production", reason=str(exc))
        raise
    app.state.daena_kek = _kek
    logger.info(
        "vault.kek_loaded",
        sha256_prefix=kek_sha256_prefix(_kek),
        is_production=settings.is_production,
        ms=int((_time.perf_counter() - _ts) * 1000),
    )
    del _kek  # Reduce time it sits in a local; app.state holds the canonical ref.

    # --- Auto-create tables (idempotent) + ALTER TABLE migrations ---
    # Production refuses to boot on SQLite (state would be ephemeral on
    # Cloud Run). In production, the schema is owned by Alembic; create_all
    # + hand-rolled ALTERs are dev-only. See:
    #   docs/Ultraview/PRODUCTION_DB_AND_SECRET_ROTATION_PLAN.md
    _ts = _time.perf_counter()
    if settings.is_production and settings.database_url.startswith("sqlite"):
        logger.critical(
            "production_database_url_is_sqlite",
            impact="State is ephemeral; refusing to boot.",
        )
        raise RuntimeError(
            "Production refuses to boot with a SQLite DATABASE_URL. "
            "Bind DATABASE_URL to Cloud SQL via Secret Manager."
        )
    from app.core.database import engine
    from app.models import Base  # noqa: F401 -- triggers all model imports

    async with engine.begin() as conn:
        if not settings.is_production:
            # Dev convenience: idempotent CREATE TABLE IF NOT EXISTS so
            # rapid iteration works without alembic. NEVER runs in
            # production -- production schema must come from Alembic
            # via the start.sh entrypoint.
            await conn.run_sync(Base.metadata.create_all)
        else:
            # Production sanity: assert alembic_version table exists +
            # has a row. start.sh ran `alembic upgrade head` before
            # uvicorn, so this is just a belt-and-suspenders check.
            from sqlalchemy import text as _text
            result = await conn.execute(
                _text("SELECT version_num FROM alembic_version")
            )
            current = result.scalar_one_or_none()
            if current is None:
                raise RuntimeError(
                    "Production schema check failed: alembic_version is "
                    "empty. Container start.sh should have run "
                    "`alembic upgrade head` before this lifespan ran."
                )
            logger.info("essentials.alembic_at", version=current)

        if not settings.is_production:
            from sqlalchemy import text as _text
            # SQLite doesn't support ALTER COLUMN, but VARCHAR is flexible.
            # These ALTERs are duplicates of Alembic 004 / 006 migrations
            # for dev convenience; production gets them via alembic.
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

            _chat_session_cols = {
                "governance_mode": "VARCHAR(20) DEFAULT 'BALANCED'",
            }
            for col_name, col_type in _chat_session_cols.items():
                try:
                    await conn.execute(
                        _text(f"ALTER TABLE chat_sessions ADD COLUMN {col_name} {col_type}")
                    )
                except Exception:
                    pass

    logger.info("essentials.tables_ready", ms=int((_time.perf_counter() - _ts) * 1000))

    # --- Redis connectivity check (timeout-bounded, fail-open) ---
    _ts = _time.perf_counter()
    from app.core.redis import check_redis_health, get_redis_client

    try:
        redis_ok = await asyncio.wait_for(check_redis_health(), timeout=1.0)
    except asyncio.TimeoutError:
        redis_ok = False
        logger.warning("essentials.redis_timeout", impact="Caching degraded; continuing")
    _redis_ms = int((_time.perf_counter() - _ts) * 1000)
    if redis_ok:
        logger.info("essentials.redis_connected", ms=_redis_ms)
    else:
        logger.warning("essentials.redis_unavailable", ms=_redis_ms, impact="Caching degraded")

    # --- EventBus is a singleton, ready at import ---
    from app.core.events import event_bus

    logger.info("essentials.event_bus_ready", subscriptions=len(event_bus._handlers))

    # --- Model Registry instantiation (no health probes here) ---
    _ts = _time.perf_counter()
    from app.services.model_registry import ModelRegistry

    # PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT (2026-05-03): hydrate
    # runtime-pasted provider keys onto the live settings instance
    # BEFORE ModelRegistry.initialize() reads them. Without this, a key
    # the operator saved via /account/provider-keys would be lost on
    # every restart and the marketplace would flip back to Configure.
    # NOTE: do NOT add `from app.core.config import get_settings` here
    # -- it shadows the module-level import for the rest of this
    # function and breaks downstream references. get_settings is
    # already imported at the top of this module.
    try:
        from app.services.integrations.provider_keys_store import (
            hydrate_settings as _hydrate_provider_keys,
        )
        _applied = _hydrate_provider_keys(get_settings())
        if _applied:
            logger.info(
                "essentials.provider_keys_hydrated",
                fields=_applied,
                count=len(_applied),
            )
    except Exception:
        # Hydration is best-effort; the operator can still re-save
        # in-product if the override file is unreadable.
        logger.exception("essentials.provider_keys_hydration_failed")

    registry = ModelRegistry()
    await registry.initialize()
    app.state.model_registry = registry
    logger.info(
        "essentials.model_registry_ready",
        providers=len(registry._providers),
        ms=int((_time.perf_counter() - _ts) * 1000),
    )

    # === ESSENTIALS COMPLETE ===
    startup_state.mark_essentials_ready()
    logger.info(
        "daena_essentials_ready",
        total_ms=int((_time.perf_counter() - _t0) * 1000),
    )
    # Publish .daena-port now: frontend proxy can follow within 2s.
    _publish_ready_port_file()

    # === DEFERRED START (background) ===
    deferred_task = asyncio.create_task(_run_deferred_initialization(app))
    logger.info("deferred_initialization_scheduled")

    yield

    # === SHUTDOWN ===
    _clear_ready_port_file()

    # Cancel deferred task if still running.
    if not deferred_task.done():
        deferred_task.cancel()
        try:
            await asyncio.wait_for(deferred_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    # WebSocket placeholder route removed 2026-04-29 (no consumers).
    # ConnectionManager retained at app/core/websocket.py for future use.
    # voice_ws does not use ConnectionManager, so no shutdown call needed here.

    # Stop the cron scheduler singleton.
    try:
        from app.services.heartbeat.cron_scheduler import stop_cron_scheduler

        await stop_cron_scheduler()
        logger.info("cron_scheduler_stopped")
    except Exception:
        logger.debug("cron_scheduler_stop_skipped")

    # PR-HB-DAEMON-WIRE (2026-05-02): stop the heartbeat daemon if it
    # was started by deferred init. Mirrors the cron scheduler shutdown
    # pattern: try the call, swallow exceptions so a missed start does
    # not stall shutdown.
    try:
        daemon_ref = getattr(app.state, "heartbeat_daemon", None)
        if daemon_ref is not None:
            await daemon_ref.stop()
            logger.info("heartbeat_daemon_stopped")
    except Exception:
        logger.debug("heartbeat_daemon_stop_skipped")

    # Stop the background queue worker.
    try:
        from app.services.autopilot import shutdown_background_queue

        await shutdown_background_queue(app)
        logger.info("background_queue_stopped")
    except Exception:
        logger.debug("background_queue_stop_skipped")

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
        import traceback as _tb
        from app.core.logging import get_logger
        _log = get_logger("error_handler")
        _log.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            error=str(exc),
            traceback=_tb.format_exc(),
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
