"""Tests for the typed ontology CRUD + graph projection (PR-3).

Coverage:
- All six typed entities (workflow / sop / document / decision / risk / kpi)
  project into the graph with the right kind and root-anchored rel.
- An EntityLink between two existing entities appears as an edge.
- An EntityLink whose endpoint is missing is filtered out (dangling-safe).
- Two-tenant isolation: another tenant's entities never leak.
- CRUD POST + GET roundtrip for an entity (commit path).
- CRUD POST + GET roundtrip for an EntityLink (commit path).
- Unknown ontology kind returns 404 on both GET and POST.

Uses conftest fixtures: ``client`` (AsyncClient), ``db_session``,
``auth_headers`` (FOUNDER JWT for tenant 1111.../user 2222...),
``seed_auth_principal`` (opt-in tenant + user seed). The autouse
``_clean_db_between_tests`` wipes all rows before each test, and the SQLite
FK pragma is ON, so every tenant-scoped insert must seed a Tenant first.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.identity import Tenant
from app.models.ontology import (
    Decision,
    Document,
    EntityLink,
    Kpi,
    Risk,
    Sop,
    Workflow,
)

# (url_kind, model, projection rel from daena:root)
ONTOLOGY_KINDS = [
    ("workflow", Workflow, "defines"),
    ("sop", Sop, "documents"),
    ("document", Document, "stores"),
    ("decision", Decision, "records"),
    ("risk", Risk, "tracks"),
    ("kpi", Kpi, "measures"),
]


@pytest.mark.asyncio
async def test_all_six_kinds_project(
    client, auth_headers, seed_auth_principal, db_session
):
    """All six typed entities appear in the graph with root-anchored rels."""
    tid = seed_auth_principal["tenant_id"]
    for kind, model, _rel in ONTOLOGY_KINDS:
        db_session.add(
            model(
                id=uuid.uuid4(),
                tenant_id=tid,
                name=f"My {kind.capitalize()}",
            )
        )
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]

    kinds_seen = {n["kind"] for n in data["nodes"]}
    for kind, _model, _rel in ONTOLOGY_KINDS:
        assert kind in kinds_seen, f"missing kind {kind!r} in projection"

    labels = {n["label"] for n in data["nodes"]}
    for kind, _model, _rel in ONTOLOGY_KINDS:
        assert f"My {kind.capitalize()}" in labels

    rels_seen = {e["rel"] for e in data["edges"]}
    for _kind, _model, rel in ONTOLOGY_KINDS:
        assert rel in rels_seen, f"missing root-anchored rel {rel!r}"


@pytest.mark.asyncio
async def test_entity_link_projects_when_endpoints_present(
    client, auth_headers, seed_auth_principal, db_session
):
    """A link between two existing entities appears as a graph edge."""
    tid = seed_auth_principal["tenant_id"]
    wf = Workflow(id=uuid.uuid4(), tenant_id=tid, name="Onboarding Workflow")
    sop = Sop(id=uuid.uuid4(), tenant_id=tid, name="Onboarding SOP")
    db_session.add(wf)
    db_session.add(sop)
    db_session.add(
        EntityLink(
            id=uuid.uuid4(),
            tenant_id=tid,
            src_kind="workflow",
            src_id=str(wf.id),
            dst_kind="sop",
            dst_id=str(sop.id),
            rel="references",
            weight=1.0,
        )
    )
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    edges = r.json()["data"]["edges"]
    expected_id = f"workflow:{wf.id}->__sop:{sop.id}__references"
    assert expected_id in {e["id"] for e in edges}


@pytest.mark.asyncio
async def test_entity_link_filtered_when_endpoint_missing(
    client, auth_headers, seed_auth_principal, db_session
):
    """A link whose endpoint is absent from the projection is dropped."""
    tid = seed_auth_principal["tenant_id"]
    wf = Workflow(id=uuid.uuid4(), tenant_id=tid, name="Lonely Workflow")
    db_session.add(wf)
    db_session.add(
        EntityLink(
            id=uuid.uuid4(),
            tenant_id=tid,
            src_kind="workflow",
            src_id=str(wf.id),
            dst_kind="sop",
            dst_id=str(uuid.uuid4()),  # never inserted
            rel="references",
        )
    )
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    rels_seen = {e["rel"] for e in r.json()["data"]["edges"]}
    assert "references" not in rels_seen


@pytest.mark.asyncio
async def test_two_tenant_isolation(
    client, auth_headers, seed_auth_principal, db_session
):
    """Another tenant's typed entities never appear in this tenant's graph."""
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
        Workflow(id=uuid.uuid4(), tenant_id=tid, name="MineWorkflow")
    )
    db_session.add(
        Workflow(id=uuid.uuid4(), tenant_id=other, name="NotMineWorkflow")
    )
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    labels = {n["label"] for n in r.json()["data"]["nodes"]}
    assert "MineWorkflow" in labels
    assert "NotMineWorkflow" not in labels


@pytest.mark.asyncio
async def test_crud_entity_post_then_get(
    client, auth_headers, seed_auth_principal
):
    """POST creates a typed entity and GET lists it (commit path)."""
    post = await client.post(
        "/api/v1/ontology/entities/workflow",
        headers=auth_headers,
        json={"name": "Hiring Workflow", "description": "End-to-end hiring."},
    )
    assert post.status_code == 200
    body = post.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Hiring Workflow"
    assert body["data"]["kind"] == "workflow"
    assert body["data"]["id"]
    assert body["data"]["created_at"] is not None

    listed = await client.get(
        "/api/v1/ontology/entities/workflow", headers=auth_headers
    )
    assert listed.status_code == 200
    names = {row["name"] for row in listed.json()["data"]}
    assert "Hiring Workflow" in names


@pytest.mark.asyncio
async def test_crud_link_post_then_get(
    client, auth_headers, seed_auth_principal
):
    """POST creates an EntityLink and GET lists it (commit path)."""
    payload = {
        "src_kind": "workflow",
        "src_id": str(uuid.uuid4()),
        "dst_kind": "kpi",
        "dst_id": str(uuid.uuid4()),
        "rel": "drives",
        "weight": 2.5,
    }
    post = await client.post(
        "/api/v1/ontology/links", headers=auth_headers, json=payload
    )
    assert post.status_code == 200
    assert post.json()["success"] is True

    listed = await client.get("/api/v1/ontology/links", headers=auth_headers)
    assert listed.status_code == 200
    rels = [row["rel"] for row in listed.json()["data"]]
    assert "drives" in rels


@pytest.mark.asyncio
async def test_unknown_kind_404_get(client, auth_headers, seed_auth_principal):
    r = await client.get(
        "/api/v1/ontology/entities/widget", headers=auth_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unknown_kind_404_post(client, auth_headers, seed_auth_principal):
    r = await client.post(
        "/api/v1/ontology/entities/widget",
        headers=auth_headers,
        json={"name": "x"},
    )
    assert r.status_code == 404
