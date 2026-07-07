"""PR-8 Tool Registry gate (plan 13.2): tool_records seed + DB-backed discovery.

Proves the four behaviours the plan names as the gate:

* seed is idempotent (re-seeding inserts nothing, no duplicate rows);
* discovery prefers the DB over the in-code TOOL_CATALOG and excludes a tool an
  operator disabled;
* a fresh tenant is bootstrapped from TOOL_CATALOG so day-one behaviour is
  identical, and the seed actually persists;
* web search is honestly unavailable without an injected provider (empty string,
  no placeholder result) and uses the provider when one is wired.

Plus fail-open (Rule 17): a DB error in from_db degrades to the constant catalog
rather than breaking the live cognition path, and re-seeding never clobbers an
operator's enabled=False edit.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.tool import ToolRecord
from app.services.laevateinn.tool_augmented import ToolAugmentedReasoner
from app.services.tool_lifecycle.tool_discovery import (
    TOOL_CATALOG,
    ToolDiscovery,
    seed_tool_records,
)


async def _names(db_session, tenant_id) -> set[str]:
    """All tool_records names persisted for *tenant_id*."""
    rows = await db_session.execute(
        select(ToolRecord.name).where(ToolRecord.tenant_id == tenant_id)
    )
    return set(rows.scalars().all())


async def _get(db_session, tenant_id, name) -> ToolRecord:
    """The single tool_records row (tenant, name)."""
    return (
        await db_session.execute(
            select(ToolRecord).where(
                ToolRecord.tenant_id == tenant_id,
                ToolRecord.name == name,
            )
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session, seed_auth_principal, test_tenant_id):
    """First seed inserts the whole catalog; a second seed inserts nothing."""
    first = await seed_tool_records(db_session, test_tenant_id)
    assert first == len(TOOL_CATALOG)
    assert await _names(db_session, test_tenant_id) == {c.id for c in TOOL_CATALOG}

    second = await seed_tool_records(db_session, test_tenant_id)
    assert second == 0
    # No duplicate rows materialised.
    assert len(await _names(db_session, test_tenant_id)) == len(TOOL_CATALOG)


@pytest.mark.asyncio
async def test_seed_preserves_operator_edits(
    db_session, seed_auth_principal, test_tenant_id
):
    """Re-seeding must not resurrect a tool the operator disabled (Rule 17)."""
    await seed_tool_records(db_session, test_tenant_id)

    jira = await _get(db_session, test_tenant_id, "jira")
    jira.enabled = False
    await db_session.flush()

    inserted = await seed_tool_records(db_session, test_tenant_id)
    assert inserted == 0
    assert (await _get(db_session, test_tenant_id, "jira")).enabled is False


@pytest.mark.asyncio
async def test_from_db_prefers_db_and_excludes_disabled(
    db_session, seed_auth_principal, test_tenant_id
):
    """from_db reads the DB (not the constant) and drops a disabled tool."""
    await seed_tool_records(db_session, test_tenant_id)

    slack = await _get(db_session, test_tenant_id, "slack_mcp")
    slack.enabled = False
    await db_session.flush()

    discovery = await ToolDiscovery.from_db(db_session, test_tenant_id)
    db_ids = {c.id for c in discovery.search("slack messages channels")}
    assert "slack_mcp" not in db_ids

    # The in-code catalog still surfaces it -> proves the DB result differs.
    constant_ids = {c.id for c in ToolDiscovery().search("slack messages channels")}
    assert "slack_mcp" in constant_ids


@pytest.mark.asyncio
async def test_from_db_bootstraps_fresh_tenant(
    db_session, seed_auth_principal, test_tenant_id
):
    """A never-seeded tenant gets the full catalog, and it is persisted."""
    assert await _names(db_session, test_tenant_id) == set()

    discovery = await ToolDiscovery.from_db(db_session, test_tenant_id)
    assert any(c.id == "jira" for c in discovery.search("jira issues"))

    assert len(await _names(db_session, test_tenant_id)) == len(TOOL_CATALOG)


@pytest.mark.asyncio
async def test_from_db_fails_open_on_db_error():
    """A DB fault degrades to the in-code catalog instead of raising (Rule 17)."""

    class _BoomSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("simulated DB failure")

    discovery = await ToolDiscovery.from_db(_BoomSession(), uuid4())
    assert any(c.id == "jira" for c in discovery.search("jira issues"))


@pytest.mark.asyncio
async def test_web_search_honest_unavailable_without_provider():
    """No provider injected -> tool reports unavailable and returns empty."""
    reasoner = ToolAugmentedReasoner()
    assert reasoner.web_search_available is False
    assert await reasoner._web_search("anything at all") == ""


@pytest.mark.asyncio
async def test_web_search_uses_injected_provider():
    """An injected provider is awaited and its result returned."""

    async def provider(query: str) -> str:
        return f"result for {query}"

    reasoner = ToolAugmentedReasoner(web_search=provider)
    assert reasoner.web_search_available is True
    assert await reasoner._web_search("daena") == "result for daena"
