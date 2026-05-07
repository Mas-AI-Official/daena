"""Tests for the public connector catalog endpoint.

Validates that ``GET /api/v1/connections/catalog`` returns the seeded
catalog in the shape the frontend expects, including the version
string, full tool metadata, and stable (category, name) ordering.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.api.v1.connections import _invalidate_catalog_cache
from app.main import _seed_connector_catalog


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "config"
    / "connector_catalog.json"
)


@pytest.fixture
def catalog_payload() -> dict:
    """Read the bundled catalog JSON once per test."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    """Drop the in-process catalog cache between tests so each test
    sees a clean response shape."""
    _invalidate_catalog_cache()
    yield
    _invalidate_catalog_cache()


@pytest.fixture
async def _seeded(db_session, monkeypatch):
    """Run the seed function against the SQLite test session.

    Mirrors the pattern in test_founder_seed.py: monkeypatch the
    ``async_session_factory`` so the seed writes into the same
    transactional session the FastAPI test client reads from. Without
    this the seed lands in the production engine (an unrelated SQLite
    file) and the API returns an empty list.
    """

    @asynccontextmanager
    async def _fake_factory():
        yield db_session

    monkeypatch.setattr(
        "app.core.database.async_session_factory", _fake_factory,
    )
    # Also patch the imported binding inside app.main so the seed
    # function picks up the override (Python imports by reference).
    monkeypatch.setattr("app.main.async_session_factory", _fake_factory, raising=False)

    await _seed_connector_catalog()
    # Commit through the test session so the rows are visible to
    # subsequent reads in the same transaction.
    await db_session.commit()
    yield


@pytest.mark.asyncio
async def test_catalog_returns_seeded_entries(
    client: AsyncClient, catalog_payload: dict, _seeded
) -> None:
    """The endpoint returns the seeded entries with the expected shape."""
    resp = await client.get("/api/v1/connections/catalog")
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, dict)
    assert "version" in body
    assert "connectors" in body
    assert isinstance(body["connectors"], list)

    # Assert every seeded entry is reachable by name. We cannot assert
    # exact equality on length: the session-scoped SQLite engine
    # accumulates rows from other test modules (test_connections.py
    # creates ad-hoc connectors). The catalog seed is what's under test
    # here, not the full table cardinality.
    returned_names = {row["name"] for row in body["connectors"]}
    for entry in catalog_payload["connectors"]:
        assert entry["name"] in returned_names, (
            f"catalog row {entry['name']!r} missing from API response"
        )

    sample = body["connectors"][0]
    for key in ("id", "name", "description", "category", "auth_type", "icon_url", "tools", "config_schema"):
        assert key in sample, f"missing field {key} on catalog row"
    assert isinstance(sample["tools"], list)


@pytest.mark.asyncio
async def test_catalog_includes_known_connector_with_tools(
    client: AsyncClient, _seeded
) -> None:
    """A well-known entry (GitHub) is present with its tool list."""
    resp = await client.get("/api/v1/connections/catalog")
    assert resp.status_code == 200

    rows = resp.json()["connectors"]
    by_name = {row["name"]: row for row in rows}
    assert "GitHub" in by_name, "GitHub connector should be seeded"

    github = by_name["GitHub"]
    assert github["category"] == "Coding"
    assert github["auth_type"] == "token"

    tool_names = {t["name"] for t in github["tools"] if isinstance(t, dict)}
    assert "search_repos" in tool_names
    assert "create_pr" in tool_names

    # Every tool ships with a description string (merge of the legacy
    # SKILL_DESCRIPTIONS map -- empty fallback is the tool id).
    for tool in github["tools"]:
        assert isinstance(tool, dict)
        assert tool.get("description")


@pytest.mark.asyncio
async def test_catalog_version_matches_seed_file(
    client: AsyncClient, catalog_payload: dict, _seeded
) -> None:
    """The endpoint version mirrors the version in the bundled JSON."""
    resp = await client.get("/api/v1/connections/catalog")
    assert resp.status_code == 200
    assert resp.json()["version"] == catalog_payload["version"]


@pytest.mark.asyncio
async def test_catalog_sorted_by_category_then_name(
    client: AsyncClient, _seeded
) -> None:
    """Connectors are sorted by ``(category, name)`` (case-insensitive)."""
    resp = await client.get("/api/v1/connections/catalog")
    rows = resp.json()["connectors"]
    keys = [
        ((row.get("category") or "").lower(), (row.get("name") or "").lower())
        for row in rows
    ]
    assert keys == sorted(keys), "catalog rows must be sorted by (category, name)"
