"""Shared test fixtures for Daena backend tests.

Provides:
- Async test client with httpx
- In-memory SQLite test database with PG type compilation overrides
- Mock user authentication
- Common test data factories
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
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
