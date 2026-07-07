"""Tests for the kind="tool" projection in GET /api/v1/graph (PR-8, plan 13.2).

The plan's Mission Control gate: "graph projects ``kind="tool"`` nodes from
ToolDefinition" (the backing ``tool_records`` table, ToolRecord here).

Coverage:
- An enabled ToolRecord projects a ``tool:<id>`` node anchored to daena:root by
  a "provides" edge, with status "active" and its display name from meta.
- A disabled tool is still PROJECTED (status "inactive"), not hidden, so the
  operator kill switch is visible in Mission Control rather than silently
  dropped (Rule 17 -- "how does the user see it fail?").
- The node label falls back to the stable slug when meta carries no "name".
- Two-tenant isolation: another tenant's tool never appears in our graph.

These hit the real route end to end (API -> GraphService.build_graph ->
schema), so they also guard the schema.graph kind-comment wiring. ``kinds`` is
scoped to ``daena,tool`` so the root node exists (the provides edge needs it)
while keeping the response small. build_graph does not touch ragx, so -- unlike
search / node-detail -- no query_ragx patch is needed.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.identity import Tenant
from app.models.tool import ToolRecord


def _node(data, node_id):
    return next((n for n in data["nodes"] if n["id"] == node_id), None)


def _has_edge(data, source, target, rel):
    return any(
        e["source"] == source and e["target"] == target and e["rel"] == rel
        for e in data["edges"]
    )


@pytest.mark.asyncio
async def test_graph_projects_enabled_tool(
    client, auth_headers, seed_auth_principal, db_session
):
    """Enabled tool -> active node + provides edge from root, label from meta."""
    tid = seed_auth_principal["tenant_id"]
    rec = ToolRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        name="jira",
        kind="mcp",
        description="Jira issues",
        enabled=True,
        source_ref="atlassian",
        meta={"name": "Jira Cloud"},
    )
    db_session.add(rec)
    await db_session.flush()

    r = await client.get(
        "/api/v1/graph", headers=auth_headers, params={"kinds": "daena,tool"}
    )
    assert r.status_code == 200
    data = r.json()["data"]

    node = _node(data, f"tool:{rec.id}")
    assert node is not None
    assert node["kind"] == "tool"
    assert node["label"] == "Jira Cloud"  # display name from meta
    assert node["status"] == "active"
    assert node["meta"]["tool_kind"] == "mcp"
    assert _has_edge(data, "daena:root", f"tool:{rec.id}", "provides")


@pytest.mark.asyncio
async def test_graph_projects_disabled_tool_visible_inactive(
    client, auth_headers, seed_auth_principal, db_session
):
    """Disabled tool stays visible as inactive (Rule 17), label falls back to slug."""
    tid = seed_auth_principal["tenant_id"]
    rec = ToolRecord(
        id=uuid.uuid4(),
        tenant_id=tid,
        name="slack_mcp",
        kind="mcp",
        enabled=False,
        meta={},  # no display name -> label is the stable slug
    )
    db_session.add(rec)
    await db_session.flush()

    r = await client.get(
        "/api/v1/graph", headers=auth_headers, params={"kinds": "daena,tool"}
    )
    assert r.status_code == 200
    data = r.json()["data"]

    node = _node(data, f"tool:{rec.id}")
    assert node is not None  # kill-switched, not hidden
    assert node["status"] == "inactive"
    assert node["label"] == "slack_mcp"


@pytest.mark.asyncio
async def test_graph_tool_two_tenant_isolation(
    client, auth_headers, seed_auth_principal, db_session
):
    """Another tenant's tool must never appear in our graph."""
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
    mine = ToolRecord(id=uuid.uuid4(), tenant_id=tid, name="mine", kind="builtin")
    theirs = ToolRecord(
        id=uuid.uuid4(), tenant_id=other, name="theirs", kind="builtin"
    )
    db_session.add_all([mine, theirs])
    await db_session.flush()

    r = await client.get(
        "/api/v1/graph", headers=auth_headers, params={"kinds": "daena,tool"}
    )
    assert r.status_code == 200
    data = r.json()["data"]

    assert _node(data, f"tool:{mine.id}") is not None
    assert _node(data, f"tool:{theirs.id}") is None  # cross-tenant never leaks
