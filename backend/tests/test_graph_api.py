"""Tests for the read-only Mission Control graph projection (PR-1).

Uses the verified conftest fixtures: ``client`` (AsyncClient), ``db_session``,
``auth_headers`` (FOUNDER JWT for tenant 1111.../user 2222...),
``seed_auth_principal`` (opt-in tenant+user seed). ``_clean_db_between_tests``
(autouse) means each test starts from an empty DB.

Schema note: ``Department.sunflower_index`` is NOT NULL with no default, so
every Department(...) here supplies it explicitly.
"""

import uuid

import pytest

from app.models.chat import ChatSession
from app.models.execution import Task, ToolExecution
from app.models.identity import Tenant
from app.models.organization import Department


@pytest.mark.asyncio
async def test_graph_requires_auth(client):
    r = await client.get("/api/v1/graph")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_graph_shape(client, auth_headers, seed_auth_principal, db_session):
    tid = seed_auth_principal["tenant_id"]
    db_session.add(Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    ))
    await db_session.flush()
    r = await client.get("/api/v1/graph", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert {"nodes", "edges", "stats"} <= data.keys()
    labels = {n["label"] for n in data["nodes"]}
    assert "Finance" in labels
    assert any(n["id"] == "daena:root" for n in data["nodes"])
    # root -> department contains edge exists
    rels = {e["rel"] for e in data["edges"]}
    assert "contains" in rels


@pytest.mark.asyncio
async def test_graph_faculties_default_on(
    client, auth_headers, seed_auth_principal, db_session
):
    """Daena's six cognitive faculties (the SubCapability constant) project as
    default-on faculty nodes, each with an embodies edge from the root. They
    are an architectural constant, not tenant rows, so they appear even when no
    department exists."""
    from app.core.constants import SubCapability

    r = await client.get("/api/v1/graph", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    faculty = [n for n in data["nodes"] if n["kind"] == "faculty"]
    assert len(faculty) == len(list(SubCapability)) == 6
    # provenance is explicit (Rule 17): no fabricated org rows
    assert all(n["meta"]["source"] == "architectural_constant" for n in faculty)
    # every faculty hangs off the root via an embodies edge
    embodies = {
        e["target"] for e in data["edges"]
        if e["source"] == "daena:root" and e["rel"] == "embodies"
    }
    assert {n["id"] for n in faculty} == embodies


@pytest.mark.asyncio
async def test_graph_kinds_filter_excludes_faculties(
    client, auth_headers, seed_auth_principal, db_session
):
    """?kinds=department gates the faculty layer off: the six faculties only
    project alongside the root, never in a structure-only view."""
    tid = seed_auth_principal["tenant_id"]
    db_session.add(Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    ))
    await db_session.flush()
    r = await client.get("/api/v1/graph?kinds=department", headers=auth_headers)
    kinds = {n["kind"] for n in r.json()["data"]["nodes"]}
    assert "faculty" not in kinds


@pytest.mark.asyncio
async def test_graph_two_tenant_isolation(
    client, auth_headers, seed_auth_principal, db_session
):
    tid = seed_auth_principal["tenant_id"]
    other = uuid.uuid4()
    # departments.tenant_id FKs to tenants, so the other tenant must exist
    # for its department to insert. We then prove the projection still
    # excludes it (the real isolation guard).
    db_session.add(Tenant(
        id=other, name="Other Tenant", slug=f"other-{other.hex[:8]}", settings={},
    ))
    db_session.add(Department(
        id=uuid.uuid4(), tenant_id=tid, name="Mine", sunflower_index=0,
    ))
    db_session.add(Department(
        id=uuid.uuid4(), tenant_id=other, name="NotMine", sunflower_index=1,
    ))
    await db_session.flush()
    r = await client.get("/api/v1/graph", headers=auth_headers)
    labels = {n["label"] for n in r.json()["data"]["nodes"]}
    assert "Mine" in labels
    assert "NotMine" not in labels  # tenant leak guard


@pytest.mark.asyncio
async def test_graph_kinds_filter(
    client, auth_headers, seed_auth_principal, db_session
):
    tid = seed_auth_principal["tenant_id"]
    db_session.add(Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    ))
    await db_session.flush()
    r = await client.get("/api/v1/graph?kinds=department", headers=auth_headers)
    kinds = {n["kind"] for n in r.json()["data"]["nodes"]}
    assert kinds <= {"department"}  # root excluded when not requested


@pytest.mark.asyncio
async def test_graph_center_depth(
    client, auth_headers, seed_auth_principal, db_session
):
    tid = seed_auth_principal["tenant_id"]
    d = Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    )
    db_session.add(d)
    await db_session.flush()
    r = await client.get(
        f"/api/v1/graph?center=department:{d.id}&depth=1", headers=auth_headers
    )
    assert r.status_code == 200
    ids = {n["id"] for n in r.json()["data"]["nodes"]}
    assert f"department:{d.id}" in ids


# ---------------------------------------------------------------------------
# PR-6 continuity layer: session / execution kinds default-on, capped and
# tenant-scoped, with belongs_to / spawned_by / part_of edges from existing
# FKs (zero migrations).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_session_node_default_on(
    client, auth_headers, seed_auth_principal, db_session
):
    """A ChatSession projects a default-on session node with a belongs_to edge
    to its department (PR-6 continuity layer, no kinds param needed)."""
    tid = seed_auth_principal["tenant_id"]
    uid = seed_auth_principal["user_id"]
    d = Department(
        id=uuid.uuid4(), tenant_id=tid, name="Finance", sunflower_index=0,
    )
    db_session.add(d)
    await db_session.flush()
    s = ChatSession(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid,
        department_id=d.id, title="Q4 planning",
    )
    db_session.add(s)
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    node = next(
        (n for n in data["nodes"] if n["id"] == f"session:{s.id}"), None
    )
    assert node is not None
    assert node["kind"] == "session"
    assert node["label"] == "Q4 planning"
    edge = next(
        (e for e in data["edges"]
         if e["source"] == f"session:{s.id}" and e["rel"] == "belongs_to"),
        None,
    )
    assert edge is not None
    assert edge["target"] == f"department:{d.id}"


@pytest.mark.asyncio
async def test_graph_execution_from_task_spawned_by_session(
    client, auth_headers, seed_auth_principal, db_session
):
    """A Task projects an execution node linked to the session that spawned it."""
    tid = seed_auth_principal["tenant_id"]
    uid = seed_auth_principal["user_id"]
    s = ChatSession(id=uuid.uuid4(), tenant_id=tid, user_id=uid)
    db_session.add(s)
    await db_session.flush()
    t = Task(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid,
        name="Ingest dept docs", session_id=s.id,
    )
    db_session.add(t)
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    data = r.json()["data"]
    node = next(
        (n for n in data["nodes"] if n["id"] == f"execution:{t.id}"), None
    )
    assert node is not None
    assert node["kind"] == "execution"
    assert node["label"] == "Ingest dept docs"
    assert node["meta"]["source"] == "task"
    edge = next(
        (e for e in data["edges"]
         if e["id"] == f"execution:{t.id}->__session:{s.id}__spawned_by"),
        None,
    )
    assert edge is not None
    assert edge["rel"] == "spawned_by"


@pytest.mark.asyncio
async def test_graph_tool_execution_part_of_task(
    client, auth_headers, seed_auth_principal, db_session
):
    """A ToolExecution projects an execution node, part_of its parent Task and
    spawned_by its session. Task and ToolExecution share the execution
    namespace but carry distinct UUIDs, so the two nodes never collide."""
    tid = seed_auth_principal["tenant_id"]
    uid = seed_auth_principal["user_id"]
    s = ChatSession(id=uuid.uuid4(), tenant_id=tid, user_id=uid)
    db_session.add(s)
    await db_session.flush()
    t = Task(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid,
        name="Parent task", session_id=s.id,
    )
    db_session.add(t)
    await db_session.flush()
    te = ToolExecution(
        id=uuid.uuid4(), tenant_id=tid, tool_name="ragx.query",
        task_id=t.id, session_id=s.id,
    )
    db_session.add(te)
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    data = r.json()["data"]
    node = next(
        (n for n in data["nodes"] if n["id"] == f"execution:{te.id}"), None
    )
    assert node is not None
    assert node["label"] == "ragx.query"
    assert node["meta"]["source"] == "tool_execution"
    edge_ids = {e["id"] for e in data["edges"]}
    assert f"execution:{te.id}->__execution:{t.id}__part_of" in edge_ids
    assert f"execution:{te.id}->__session:{s.id}__spawned_by" in edge_ids


@pytest.mark.asyncio
async def test_graph_continuity_two_tenant_isolation(
    client, auth_headers, seed_auth_principal, db_session
):
    """Another tenant's sessions never appear in the projection (continuity
    layer obeys the same tenant guard as the org structure)."""
    tid = seed_auth_principal["tenant_id"]
    uid = seed_auth_principal["user_id"]
    other = uuid.uuid4()
    db_session.add(Tenant(
        id=other, name="Other Tenant", slug=f"other-{other.hex[:8]}", settings={},
    ))
    await db_session.flush()
    mine = ChatSession(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid, title="Mine",
    )
    theirs = ChatSession(
        id=uuid.uuid4(), tenant_id=other, user_id=uid, title="Theirs",
    )
    db_session.add_all([mine, theirs])
    await db_session.flush()

    r = await client.get("/api/v1/graph", headers=auth_headers)
    ids = {n["id"] for n in r.json()["data"]["nodes"]}
    assert f"session:{mine.id}" in ids
    assert f"session:{theirs.id}" not in ids  # continuity tenant guard


@pytest.mark.asyncio
async def test_graph_kinds_filter_excludes_continuity(
    client, auth_headers, seed_auth_principal, db_session
):
    """?kinds=department gates the continuity layer off: a seeded session does
    not appear, proving session/execution stay opt-out-able."""
    tid = seed_auth_principal["tenant_id"]
    uid = seed_auth_principal["user_id"]
    s = ChatSession(
        id=uuid.uuid4(), tenant_id=tid, user_id=uid, title="Hidden",
    )
    db_session.add(s)
    await db_session.flush()
    r = await client.get("/api/v1/graph?kinds=department", headers=auth_headers)
    ids = {n["id"] for n in r.json()["data"]["nodes"]}
    assert f"session:{s.id}" not in ids
