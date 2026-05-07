"""Tests for the connector catalog seed function.

Validates that ``_seed_connector_catalog()`` upserts entries
idempotently and that JSON tool metadata flows into the DB row.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import _seed_connector_catalog
from app.models.connections import Connector


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "config"
    / "connector_catalog.json"
)


@pytest.fixture
def catalog_payload() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _patch_factory(monkeypatch, db_session: AsyncSession) -> None:
    """Force the seed function to write into the SQLite test session.

    Same trick as test_founder_seed.py -- the seed reaches for
    async_session_factory at call time, so we swap the binding in
    both modules that import it before invoking the seed.
    """

    @asynccontextmanager
    async def _fake_factory():
        yield db_session

    monkeypatch.setattr(
        "app.core.database.async_session_factory", _fake_factory,
    )
    monkeypatch.setattr(
        "app.main.async_session_factory", _fake_factory, raising=False,
    )


@pytest.mark.asyncio
async def test_seed_is_idempotent(
    db_session: AsyncSession, catalog_payload: dict, monkeypatch
) -> None:
    """Running the seed twice yields the same connector count.

    The shared session-scoped SQLite engine may already contain
    connectors from other test modules. We assert idempotency on the
    delta the seed contributes, not on the absolute row count.
    """
    _patch_factory(monkeypatch, db_session)
    seeded_names = {entry["name"] for entry in catalog_payload["connectors"]}

    async def _count_seeded() -> int:
        rows = (
            await db_session.execute(select(Connector.name))
        ).scalars().all()
        return sum(1 for n in rows if n in seeded_names)

    await _seed_connector_catalog()
    first = await _count_seeded()
    assert first == len(seeded_names)

    await _seed_connector_catalog()
    second = await _count_seeded()
    assert second == first


@pytest.mark.asyncio
async def test_seed_persists_tool_metadata(
    db_session: AsyncSession, monkeypatch
) -> None:
    """Tools list (with descriptions) is stored in the JSONB tools column."""
    _patch_factory(monkeypatch, db_session)

    await _seed_connector_catalog()

    row = (
        await db_session.execute(select(Connector).where(Connector.name == "GitHub"))
    ).scalar_one_or_none()
    assert row is not None
    assert row.category == "Coding"
    assert row.auth_type == "token"

    tools = row.tools or []
    assert isinstance(tools, list)
    assert len(tools) >= 4

    # Each tool dict has both name + description; descriptions came
    # from the legacy SKILL_DESCRIPTIONS map merged into the JSON.
    sample = next((t for t in tools if t.get("name") == "search_repos"), None)
    assert sample is not None
    assert sample["description"]
