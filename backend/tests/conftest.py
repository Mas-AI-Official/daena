"""Shared test fixtures for Daena backend tests.

Provides:
- Async test client with httpx
- In-memory SQLite test database with PG type compilation overrides
- Mock user authentication
- Common test data factories

TEST-HYGIENE GUARDRAILS (2026-06-01, learned from two real suite-hang
incidents that stalled the full run at ~72%):

1. NEVER let a unit test invoke a real network scanner / external
   subprocess. ScanWorkflow.start_scan, for URL targets, shells out to
   live tools (nuclei, etc.) - one ARCHITECT-tier test ran nuclei for 270s.
   Stub the I/O boundary instead (see test_scan_workflow.py's
   ``_stub_real_scanner`` autouse fixture for the canonical pattern:
   monkeypatch ``scan_workflow._real_scan_target`` to a fast ScanOutcome).

2. NEVER leak a fire-and-forget asyncio task past the test. start_scan
   does ``asyncio.create_task(self._execute_scan(job))`` (correct in prod -
   the route returns the job id immediately). A test that does not drain
   that task leaves it running into pytest-asyncio's event-loop teardown,
   where ``_cancel_all_tasks`` can hang on a non-cancellable IOCP wait.
   Either drain it (poll to completion) or stub the work to a no-op.

3. The ``--timeout=120 --timeout-method=thread`` addopts in pyproject.toml
   is the backstop: any hang becomes a named FAILED with a stack dump
   instead of a silent stall. Do not rely on it as a substitute for (1)/(2).

4. Tests start from a CLEAN DB every time (see _clean_db_between_tests).
   Do not depend on rows another test created. If an endpoint writes a
   tenant/actor-FK'd row, seed the principal first (see seed_auth_principal).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.models.base import Base
from app.services import controlled_execution_dispatch as _ce_dispatch

# ---------------------------------------------------------------------------
# Controlled-execution handler registry: snapshot + restore (test hygiene).
# test_controlled_execution_dispatch.py::test_no_handlers_registered_yet calls
# reset_handlers_for_tests() (i.e. _TOOL_HANDLERS.clear()) and never restores
# it. In the full suite that leaves the registry empty for every handler-
# registry / dispatch test that runs afterwards (they pass in isolation only
# because importing the package populated it). Re-importing the package does
# NOT help: it is cached in sys.modules, so the side-effect registration will
# not re-run. So snapshot the populated dict once here and restore it between
# tests.
# ---------------------------------------------------------------------------
try:
    import app.services.controlled_execution_handlers  # noqa: F401  (side-effect registration)

    _HANDLER_REGISTRY_SNAPSHOT: dict = dict(_ce_dispatch._TOOL_HANDLERS)
except Exception:  # pragma: no cover - handlers package optional in some envs
    _HANDLER_REGISTRY_SNAPSHOT = {}


@pytest.fixture(autouse=True)
def _restore_handler_registry():
    """Restore the controlled-execution handler registry after each test.

    Guards against the reset_handlers_for_tests() polluter so later tests
    always observe the populated registry. No-op when nothing changed.
    """
    yield
    if (
        _HANDLER_REGISTRY_SNAPSHOT
        and _ce_dispatch._TOOL_HANDLERS != _HANDLER_REGISTRY_SNAPSHOT
    ):
        _ce_dispatch._TOOL_HANDLERS.clear()
        _ce_dispatch._TOOL_HANDLERS.update(_HANDLER_REGISTRY_SNAPSHOT)

# ---------------------------------------------------------------------------
# SQLite compatibility: compile PostgreSQL types for SQLite test engine
# ---------------------------------------------------------------------------

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    """Render JSONB as JSON for SQLite."""
    return "JSON"


@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    """Render PG UUID as CHAR(36) for SQLite."""
    return "CHAR(36)"


# Use in-memory SQLite for tests (fast, no external deps)
TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine with SQLite.

    Server defaults using gen_random_uuid() won't work on SQLite,
    so the models must also have a Python-side default=uuid.uuid4
    or tests must supply IDs explicitly.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Enable FK enforcement in SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_db_between_tests(test_engine) -> AsyncGenerator[None, None]:
    """Reset the shared in-memory DB to empty before every test.

    Root cause of the bulk of the 2026-06-01 backend test-health cluster
    (159 ``UNIQUE constraint failed: tenants.id`` + connectors.name errors,
    concentrated in test_department_* and test_connection_v2_*): the
    ``test_engine`` is session-scoped, so the schema + any COMMITTED rows
    live for the whole run. The ``db_session`` fixture only ``rollback()``s,
    which cannot undo a ``commit()`` (API endpoints like /auth/register and
    many tests commit a tenant with the shared fixed id
    ``11111111-1111-1111-1111-111111111111``). The first such test passes;
    the next one inserting that id collides at setup -> ERROR. Each file
    passes in isolation (fresh DB) but errors in the full run.

    Fix: wipe all tables BEFORE each test (setup-time, not teardown, so we
    never contend with a still-open db_session for the SQLite write lock).
    Children-first (reversed dependency order) honors the FK pragma. This
    makes every test start from a clean slate regardless of what committed
    before it. No test in this suite relies on cross-test DB state (the only
    non-function-scoped fixtures are event_loop, test_engine, and an env-var
    bypass in test_3vilbob_e2e -- none seed rows), so this is pure isolation
    with no behavioral change to passing tests.
    """
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session.

    Each test gets its own transaction that is rolled back after.
    """
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    """Create a test FastAPI application with DB override."""
    test_app = create_app()

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_tenant_id() -> uuid.UUID:
    """Fixed tenant ID for tests."""
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Fixed user ID for tests."""
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def auth_headers(test_user_id: uuid.UUID, test_tenant_id: uuid.UUID) -> dict[str, str]:
    """Authorization headers with a valid JWT for tests."""
    token = create_access_token(
        user_id=str(test_user_id),
        tenant_id=str(test_tenant_id),
        role="FOUNDER",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_auth_principal(
    db_session: AsyncSession,
    test_tenant_id: uuid.UUID,
    test_user_id: uuid.UUID,
):
    """Persist the canonical auth_headers Tenant + User into the (now clean)
    DB so endpoints that write tenant/actor-FK'd rows (e.g. the goa_audit_events
    audit row on a blocked integration call) have valid FK targets.

    Opt-in (NOT autouse): tests that drive a tenant-scoped HTTP endpoint with
    ``auth_headers`` but do not otherwise seed their principal should request
    this. It is deliberately NOT autouse because many tests create their OWN
    tenant with this same fixed id (e.g. via /auth/register) and a global
    pre-seed would re-introduce the UNIQUE-collision this suite's
    _clean_db_between_tests fixture just removed.

    Before _clean_db_between_tests landed (2026-06-01), these tests passed
    only because a prior test had leaked the same tenant/user row into the
    shared DB. Cleaning between tests correctly exposed the missing seed;
    this fixture is the proper, explicit replacement for that accidental
    leak. Returns the (tenant_id, user_id) for convenience.
    """
    from app.models.identity import Tenant, User

    existing_t = (
        await db_session.execute(select(Tenant).where(Tenant.id == test_tenant_id))
    ).scalar_one_or_none()
    if existing_t is None:
        db_session.add(Tenant(
            id=test_tenant_id, name="Test Tenant", slug="test-tenant", settings={},
        ))
        await db_session.flush()
    existing_u = (
        await db_session.execute(select(User).where(User.id == test_user_id))
    ).scalar_one_or_none()
    if existing_u is None:
        db_session.add(User(
            id=test_user_id, tenant_id=test_tenant_id,
            email="test-principal@example.com", password_hash="x",
            role="FOUNDER", is_active=True,
        ))
        await db_session.flush()
    return {"tenant_id": test_tenant_id, "user_id": test_user_id}
