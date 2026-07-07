"""Tests for POST /api/v1/graph/search (PR-4 ragx-highlight pattern).

Coverage:
- Unauthenticated requests get 401 (mirrors PR-1).
- A seeded Department whose name overlaps a ragx citation snippet gets
  highlighted via the bidirectional label/blob match.
- When ragx is offline (available=False) the response surfaces that
  honestly per Rule 17 instead of pretending nothing matched.
- Two-tenant isolation: another tenant's nodes never appear in the
  matched ids, even when the query would match their label.

Mocking note: ``semantic_search`` imports ``query_ragx`` directly into
the ``app.services.graph_service`` module namespace, so the patch site
is ``app.services.graph_service.query_ragx`` -- patching at the bridge
module path would not intercept the call.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.identity import Tenant
from app.models.organization import Department
from app.services.ragx_bridge import RagxCitation, RagxResult


@pytest.mark.asyncio
async def test_graph_search_requires_auth(client):
    r = await client.post("/api/v1/graph/search", json={"q": "finance"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_graph_search_matches_seeded_department(
    client, auth_headers, seed_auth_principal, db_session, monkeypatch
):
    """A ragx citation that mentions Finance surfaces the Finance node id."""
    tid = seed_auth_principal["tenant_id"]
    d = Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    )
    db_session.add(d)
    await db_session.flush()

    async def fake_query(q, collections=None, k=4, timeout_s=6.0):
        return RagxResult(
            citations=[
                RagxCitation(
                    chunk_id="c1",
                    source_path="finance/budget.md",
                    score=0.9,
                    snippet="The finance team approved the Q4 budget.",
                    collection="daena-docs",
                )
            ],
            abstained_collections=[],
            elapsed_ms=12.0,
            available=True,
        )

    monkeypatch.setattr(
        "app.services.graph_service.query_ragx", fake_query
    )

    r = await client.post(
        "/api/v1/graph/search",
        headers=auth_headers,
        json={"q": "budget approval"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["available"] is True
    assert f"department:{d.id}" in data["matched_node_ids"]


@pytest.mark.asyncio
async def test_graph_search_ragx_offline_honest(
    client, auth_headers, seed_auth_principal, db_session, monkeypatch
):
    """ragx offline -> available=False so the UI can show the honest pill."""
    tid = seed_auth_principal["tenant_id"]
    db_session.add(
        Department(
            id=uuid.uuid4(),
            tenant_id=tid,
            name="Finance",
            sunflower_index=0,
        )
    )
    await db_session.flush()

    async def fake_query(q, collections=None, k=4, timeout_s=6.0):
        return RagxResult(
            citations=[],
            abstained_collections=list(collections or []),
            elapsed_ms=0.0,
            available=False,
        )

    monkeypatch.setattr(
        "app.services.graph_service.query_ragx", fake_query
    )

    r = await client.post(
        "/api/v1/graph/search",
        headers=auth_headers,
        json={"q": "finance"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["available"] is False  # Rule 17: honesty in, honesty out


@pytest.mark.asyncio
async def test_graph_search_two_tenant_isolation(
    client, auth_headers, seed_auth_principal, db_session, monkeypatch
):
    """Another tenant's matching label must never appear in our results."""
    tid = seed_auth_principal["tenant_id"]
    other = uuid.uuid4()
    db_session.add(
        Tenant(
            id=other,
            name="Other Tenant",
            slug=f"other-{other.hex[:8]}",
            settings={},
        )
    )
    db_session.add(
        Department(
            id=uuid.uuid4(),
            tenant_id=tid,
            name="MineFinance",
            sunflower_index=0,
        )
    )
    db_session.add(
        Department(
            id=uuid.uuid4(),
            tenant_id=other,
            name="NotMineFinance",
            sunflower_index=1,
        )
    )
    await db_session.flush()

    async def fake_query(q, collections=None, k=4, timeout_s=6.0):
        return RagxResult(
            citations=[],
            abstained_collections=[],
            elapsed_ms=0.0,
            available=True,
        )

    monkeypatch.setattr(
        "app.services.graph_service.query_ragx", fake_query
    )

    r = await client.post(
        "/api/v1/graph/search",
        headers=auth_headers,
        json={"q": "finance"},
    )
    assert r.status_code == 200
    ids = r.json()["data"]["matched_node_ids"]
    assert not any("NotMineFinance" in nid for nid in ids)
