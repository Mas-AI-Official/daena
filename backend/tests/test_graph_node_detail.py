"""Tests for GET /api/v1/graph/node/{kind}/{node_id} (PR-5 node detail).

Coverage:
- Unauthenticated requests get 401 (before any service work).
- A seeded Department returns the expected node shape, a "contains" edge
  back to daena:root, AI Access scope "tenant", and -- with ragx mocked
  offline -- AI Context available=False (Rule 17 honest pill).
- An MCP server node renders its persisted tools (the plan's verify gate:
  "click Notion-MCP node -> tool list renders").
- Activity is node-SPECIFIC: a department only shows audit events from its
  own ChatSessions, never another department's (a flat tenant list would be
  fake scoping, Rule 17).
- Two-tenant isolation: another tenant's node id resolves to 404, never a
  cross-tenant read.
- An unknown id is 404.

Mocking note: ``_node_ai_context`` calls ``query_ragx`` imported into the
``app.services.graph_service`` namespace, so the patch site is
``app.services.graph_service.query_ragx`` (mirrors test_graph_search.py).
The 401 and 404 paths short-circuit before that call, so they need no patch.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.chat import ChatSession
from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant
from app.models.mcp_server import McpServer
from app.models.organization import Department
from app.services.ragx_bridge import RagxResult


async def _offline_ragx(q, collections=None, k=5, timeout_s=4.0):
    """Stand-in for query_ragx that reports honest-offline (Rule 17)."""
    return RagxResult(
        citations=[],
        abstained_collections=list(collections or []),
        elapsed_ms=0.0,
        available=False,
    )


@pytest.mark.asyncio
async def test_node_detail_requires_auth(client):
    r = await client.get(f"/api/v1/graph/node/department/{uuid.uuid4()}")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_node_detail_department_shape(
    client, auth_headers, seed_auth_principal, db_session, monkeypatch
):
    """A department node: shape, root neighbor, tenant access, honest context."""
    monkeypatch.setattr("app.services.graph_service.query_ragx", _offline_ragx)
    tid = seed_auth_principal["tenant_id"]
    d = Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    )
    db_session.add(d)
    await db_session.flush()

    r = await client.get(
        f"/api/v1/graph/node/department/{d.id}", headers=auth_headers
    )
    assert r.status_code == 200
    data = r.json()["data"]

    assert data["node"]["id"] == f"department:{d.id}"
    assert data["node"]["label"] == "Finance"

    # daena:root --contains--> department, so from the department it is an
    # inbound "contains" edge.
    root_nb = next(
        (n for n in data["neighbors"] if n["id"] == "daena:root"), None
    )
    assert root_nb is not None
    assert root_nb["rel"] == "contains"
    assert root_nb["direction"] == "in"

    assert data["ai_access"]["scope"] == "tenant"
    assert data["ai_context"]["available"] is False  # Rule 17


@pytest.mark.asyncio
async def test_node_detail_mcp_tools_render(
    client, auth_headers, seed_auth_principal, db_session, monkeypatch
):
    """The PR-5 verify gate: an MCP server node renders its tool list."""
    monkeypatch.setattr("app.services.graph_service.query_ragx", _offline_ragx)
    tid = seed_auth_principal["tenant_id"]
    srv = McpServer(
        id=uuid.uuid4(),
        tenant_id=tid,
        server_key="notion",
        display_name="Notion",
        status="ACTIVE",
        extra_metadata={
            "tools": [
                {"name": "search", "description": "Search Notion"},
                {"name": "fetch", "description": "Fetch a page"},
            ]
        },
    )
    db_session.add(srv)
    await db_session.flush()

    r = await client.get(
        f"/api/v1/graph/node/mcp_server/{srv.id}", headers=auth_headers
    )
    assert r.status_code == 200
    access = r.json()["data"]["ai_access"]
    assert access["scope"] == "self"
    names = {t["name"] for t in access["mcp_tools"]}
    assert {"search", "fetch"} <= names


@pytest.mark.asyncio
async def test_node_detail_activity_is_department_scoped(
    client, auth_headers, seed_auth_principal, db_session, monkeypatch
):
    """A department shows only its own sessions' audit events, not another's."""
    monkeypatch.setattr("app.services.graph_service.query_ragx", _offline_ragx)
    tid = seed_auth_principal["tenant_id"]
    uid = seed_auth_principal["user_id"]
    d1 = Department(id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0)
    d2 = Department(id=uuid.uuid4(), tenant_id=tid, name="Ops", sunflower_index=1)
    db_session.add_all([d1, d2])
    await db_session.flush()

    s1 = ChatSession(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid, department_id=d1.id
    )
    s2 = ChatSession(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid, department_id=d2.id
    )
    db_session.add_all([s1, s2])
    await db_session.flush()

    def _event(session_id, action_type):
        return GoaAuditEvent(
            id=uuid.uuid4(),
            tenant_id=tid,
            actor_type="agent",
            action_type=action_type,
            result="allow",
            risk_level="low",
            governance_tier=0,
            entry_hash=f"h-{uuid.uuid4().hex}",
            session_id=session_id,
        )

    db_session.add_all(
        [_event(s1.id, "finance.posted"), _event(s2.id, "ops.deployed")]
    )
    await db_session.flush()

    r = await client.get(
        f"/api/v1/graph/node/department/{d1.id}", headers=auth_headers
    )
    assert r.status_code == 200
    actions = {a["action_type"] for a in r.json()["data"]["activity"]}
    assert "finance.posted" in actions
    assert "ops.deployed" not in actions  # node-specific scoping (Rule 17)


@pytest.mark.asyncio
async def test_node_detail_two_tenant_isolation(
    client, auth_headers, seed_auth_principal, db_session
):
    """Another tenant's node id resolves to 404, never a cross-tenant read."""
    other = uuid.uuid4()
    db_session.add(
        Tenant(
            id=other,
            name="Other Tenant",
            slug=f"other-{other.hex[:8]}",
            settings={},
        )
    )
    other_dept = Department(
        id=uuid.uuid4(), tenant_id=other, name="NotMine", sunflower_index=0
    )
    db_session.add(other_dept)
    await db_session.flush()

    r = await client.get(
        f"/api/v1/graph/node/department/{other_dept.id}", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_node_detail_not_found(client, auth_headers, seed_auth_principal):
    r = await client.get(
        f"/api/v1/graph/node/department/{uuid.uuid4()}", headers=auth_headers
    )
    assert r.status_code == 404
