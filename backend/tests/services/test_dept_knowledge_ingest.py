"""Tests for the PR-6b department-knowledge ingest write path.

These cover the EXE -> dept-collection memory loop end to end at the service
boundary, with two external edges faked:

  * ragx HTTP is mocked with a URL-keyed recorder. The index route carries the
    collection in the URL PATH (body is just ``{"sources": [...]}``), so we
    assert on the URL, which is where tenant isolation actually lives.
  * the knowledge directory is redirected to a pytest tmp_path so the real
    backend/var/dept_knowledge tree is never touched.

The DB is real (the shared in-memory SQLite ``test_engine`` from conftest, with
FK enforcement ON). We seed the full Tenant -> User -> Department -> ChatSession
-> ToolExecution chain and inject a committing ``session_factory`` into
``ingest_execution`` (the request-time conftest override only rebinds
``get_db``, not ``async_session_factory``, so the service exposes this seam for
exactly this purpose).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.chat import ChatSession
from app.models.execution import ToolExecution
from app.models.identity import Tenant, User
from app.models.organization import Department
from app.services.dept_knowledge_ingest import (
    ingest_execution,
    ingest_task_artifact,
)
from app.services.ragx_bridge import RAGX_URL, department_collection_name

# Naive (SQLite stores DateTime without tz); fixed so rendered content is
# byte-stable across runs and across repeated ingests of the same row.
_FIXED_TS = datetime(2026, 1, 1, 12, 0, 0)

# Two tenants, fully distinct id space per entity so the FK chain is valid for
# both and the two-tenant test can seed both at once.
_TENANT_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER_A = UUID("a1111111-1111-1111-1111-111111111111")
_DEPT_A = UUID("a2222222-2222-2222-2222-222222222222")
_SESSION_A = UUID("a3333333-3333-3333-3333-333333333333")
_EXEC_A = UUID("a4444444-4444-4444-4444-444444444444")

_TENANT_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
_USER_B = UUID("b1111111-1111-1111-1111-111111111111")
_DEPT_B = UUID("b2222222-2222-2222-2222-222222222222")
_SESSION_B = UUID("b3333333-3333-3333-3333-333333333333")
_EXEC_B = UUID("b4444444-4444-4444-4444-444444444444")


@pytest.fixture
def ingest_factory(test_engine):
    """A committing session factory bound to the shared test engine, injected
    into ingest_execution in place of the real async_session_factory."""
    return async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest.fixture
def ingest_env(monkeypatch, tmp_path):
    """Fake ragx HTTP + redirect the knowledge dir to tmp_path.

    Returns a dict with:
      * ``calls``: list of {"url", "json"} recorded per index POST
      * ``state``: mutable {"status_code", "raise_exc"} to drive failure modes
      * ``dir``: the tmp_path the service writes summary files under
    """
    calls: list[dict] = []
    state: dict = {"status_code": 200, "raise_exc": None}

    class _Resp:
        def __init__(self, code: int) -> None:
            self.status_code = code

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> bool:
            return False

        async def post(self, url, json=None):
            calls.append({"url": url, "json": json})
            if state["raise_exc"] is not None:
                raise state["raise_exc"]
            return _Resp(state["status_code"])

    monkeypatch.setattr(
        "app.services.dept_knowledge_ingest.httpx.AsyncClient", _Client
    )
    monkeypatch.setattr(
        "app.services.dept_knowledge_ingest._knowledge_dir", lambda: tmp_path
    )
    return {"calls": calls, "state": state, "dir": tmp_path}


async def _seed_chain(
    factory,
    *,
    tenant_id: UUID,
    tenant_slug: str,
    user_id: UUID,
    dept_id: UUID,
    dept_name: str,
    session_id: UUID,
    execution_id: UUID,
    department_on_session: bool = True,
    tool_result=None,
) -> None:
    """Seed Tenant -> User -> Department -> ChatSession -> ToolExecution and
    commit, so ingest_execution's own session reads them on the shared
    StaticPool connection.

    We flush per dependency layer rather than adding all five and committing
    once. ToolExecution and ChatSession carry only bare ForeignKey columns to
    their parents (no ORM relationship() between those mappers), so SQLAlchemy's
    unit-of-work, which orders a flush by relationship() edges, has nothing
    forcing the parent INSERT before the child within one flush. With PRAGMA
    foreign_keys=ON that can emit the tool_executions INSERT before its
    chat_sessions row exists and trip a FK error. Explicit per-layer flushes
    pin the statement order. Production never hits this: the session is already
    committed by a prior request before any execution references it."""
    async with factory() as s:
        s.add(Tenant(id=tenant_id, name="Acme", slug=tenant_slug, settings={}))
        await s.flush()
        s.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=f"{user_id}@example.com",
                role="FOUNDER",
            )
        )
        s.add(
            Department(
                id=dept_id,
                tenant_id=tenant_id,
                name=dept_name,
                sunflower_index=0,
                config={},
            )
        )
        await s.flush()
        s.add(
            ChatSession(
                id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                department_id=dept_id if department_on_session else None,
            )
        )
        await s.flush()
        s.add(
            ToolExecution(
                id=execution_id,
                tenant_id=tenant_id,
                session_id=session_id,
                tool_name="search_web",
                tool_result=tool_result,
                status="COMPLETED",
                created_at=_FIXED_TS,
            )
        )
        await s.commit()


@pytest.mark.asyncio
async def test_ingest_writes_file_and_indexes_to_scoped_collection(
    ingest_factory, ingest_env
) -> None:
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
        tool_result={"answer": "rate is 5 percent", "hits": 3},
    )

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )

    collection = department_collection_name("Finance", _TENANT_A)
    assert collection == f"daena-dept-{_TENANT_A.hex}-finance"

    # Exactly one index POST, to the tenant-scoped collection's URL, with the
    # file path in the body (NOT the collection).
    calls = ingest_env["calls"]
    assert len(calls) == 1
    assert calls[0]["url"] == f"{RAGX_URL}/collections/{collection}/index"
    sources = calls[0]["json"]["sources"]
    assert len(sources) == 1

    # The summary file was written under the scoped collection dir and carries
    # the captured execution facts.
    path = ingest_env["dir"] / collection / f"exec-{_EXEC_A}.md"
    assert path.exists()
    assert sources[0] == str(path)
    content = path.read_text(encoding="utf-8")
    assert "Finance" in content
    assert "search_web" in content
    assert "COMPLETED" in content


@pytest.mark.asyncio
async def test_ingest_skips_when_session_has_no_department(
    ingest_factory, ingest_env
) -> None:
    # Company-wide session (department_id NULL): must SKIP, never fall back to a
    # global collection (leak guard).
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
        department_on_session=False,
    )

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )

    assert ingest_env["calls"] == []
    assert not any(ingest_env["dir"].iterdir())


@pytest.mark.asyncio
async def test_ingest_skips_when_no_session_id(ingest_factory, ingest_env) -> None:
    # A session-less execution has no department to scope to -> skip.
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
    )

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=None,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )

    assert ingest_env["calls"] == []
    assert not any(ingest_env["dir"].iterdir())


@pytest.mark.asyncio
async def test_ingest_skips_when_execution_missing(
    ingest_factory, ingest_env
) -> None:
    # Empty DB (cleaned between tests): the execution lookup returns None and
    # nothing is written or indexed.
    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )

    assert ingest_env["calls"] == []
    assert not any(ingest_env["dir"].iterdir())


@pytest.mark.asyncio
async def test_two_tenant_isolation_distinct_collections(
    ingest_factory, ingest_env
) -> None:
    # Same department name under two tenants must write to two disjoint
    # collections, so tenant B can never recall tenant A's EXE knowledge.
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
    )
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_B,
        tenant_slug="acme-b",
        user_id=_USER_B,
        dept_id=_DEPT_B,
        dept_name="Finance",
        session_id=_SESSION_B,
        execution_id=_EXEC_B,
    )

    calls = ingest_env["calls"]

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )
    assert len(calls) == 1
    url_a = calls[0]["url"]

    calls.clear()
    await ingest_execution(
        execution_id=_EXEC_B,
        session_id=_SESSION_B,
        tenant_id=_TENANT_B,
        session_factory=ingest_factory,
    )
    assert len(calls) == 1
    url_b = calls[0]["url"]

    assert url_a != url_b
    assert _TENANT_A.hex in url_a
    assert _TENANT_B.hex in url_b
    # Neither write ever names the other tenant's collection.
    assert _TENANT_B.hex not in url_a
    assert _TENANT_A.hex not in url_b


@pytest.mark.asyncio
async def test_ingest_fail_open_when_ragx_unreachable(
    ingest_factory, ingest_env
) -> None:
    # ragx transport error: must NOT raise, and the summary file must still be
    # on disk for a later cron re-index.
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
    )
    ingest_env["state"]["raise_exc"] = httpx.ConnectError("ragx down")

    # Must not raise.
    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )

    collection = department_collection_name("Finance", _TENANT_A)
    path = ingest_env["dir"] / collection / f"exec-{_EXEC_A}.md"
    assert path.exists()
    # The POST was attempted exactly once before failing.
    assert len(ingest_env["calls"]) == 1


@pytest.mark.asyncio
async def test_ingest_fail_open_on_http_error(ingest_factory, ingest_env) -> None:
    # Non-200 from ragx: same fail-open contract (file persisted, no raise).
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
    )
    ingest_env["state"]["status_code"] = 500

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )

    collection = department_collection_name("Finance", _TENANT_A)
    path = ingest_env["dir"] / collection / f"exec-{_EXEC_A}.md"
    assert path.exists()
    assert len(ingest_env["calls"]) == 1


@pytest.mark.asyncio
async def test_ingest_is_idempotent_same_bytes_same_url(
    ingest_factory, ingest_env
) -> None:
    # Re-running ingest for the same execution must produce a byte-identical
    # file at the same path and POST the same URL: identical bytes -> identical
    # SHA -> ragx skips the re-index (path-keyed dedupe).
    await _seed_chain(
        ingest_factory,
        tenant_id=_TENANT_A,
        tenant_slug="acme-a",
        user_id=_USER_A,
        dept_id=_DEPT_A,
        dept_name="Finance",
        session_id=_SESSION_A,
        execution_id=_EXEC_A,
        tool_result={"answer": "rate is 5 percent", "hits": 3},
    )

    collection = department_collection_name("Finance", _TENANT_A)
    path = ingest_env["dir"] / collection / f"exec-{_EXEC_A}.md"

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )
    first_bytes = path.read_bytes()

    await ingest_execution(
        execution_id=_EXEC_A,
        session_id=_SESSION_A,
        tenant_id=_TENANT_A,
        session_factory=ingest_factory,
    )
    second_bytes = path.read_bytes()

    assert first_bytes == second_bytes
    calls = ingest_env["calls"]
    assert len(calls) == 2
    assert calls[0]["url"] == calls[1]["url"]


# ── ingest_task_artifact: delegated-step artifact -> dept knowledge ──────────
# Session-free by contract: _background_run passes the already-persisted
# task.result values in, so these tests need only the ingest_env fixture
# (fake httpx client + tmp knowledge dir) -- no DB chain to seed.

_TASK_A = UUID("aaaa1111-2222-3333-4444-555566667777")

# Fixed strings throughout so the rendered file is byte-stable across runs
# (the idempotency test below depends on that).
_TASK_RESULT = {
    "executor": "delegated-llm-v1",
    "goal": "Summarize Q2 revenue drivers",
    "model_id": "qwen3-8b",
    "executed_at": "2026-01-01T12:00:00",
    "artifact": "## Q2 Summary\n\nRevenue up 12 percent, driven by PRO tier.",
}


@pytest.mark.asyncio
async def test_task_artifact_writes_file_and_indexes(ingest_env) -> None:
    await ingest_task_artifact(
        task_id=_TASK_A,
        tenant_id=_TENANT_A,
        department="Finance",
        result=dict(_TASK_RESULT),
    )

    collection = department_collection_name("Finance", _TENANT_A)
    path = ingest_env["dir"] / collection / f"task-{_TASK_A}.md"
    assert path.exists()

    content = path.read_text(encoding="utf-8")
    assert _TASK_RESULT["artifact"] in content
    assert "- department: Finance" in content
    assert "- executor: delegated-llm-v1" in content
    assert "- goal: Summarize Q2 revenue drivers" in content

    calls = ingest_env["calls"]
    assert len(calls) == 1
    assert calls[0]["url"] == f"{RAGX_URL}/collections/{collection}/index"
    assert calls[0]["json"] == {"sources": [str(path)]}


@pytest.mark.asyncio
async def test_task_artifact_skips_without_department(ingest_env) -> None:
    # Leak guard: no department -> SKIP entirely, never a global collection.
    await ingest_task_artifact(
        task_id=_TASK_A,
        tenant_id=_TENANT_A,
        department=None,
        result=dict(_TASK_RESULT),
    )
    await ingest_task_artifact(
        task_id=_TASK_A,
        tenant_id=_TENANT_A,
        department="",
        result=dict(_TASK_RESULT),
    )

    assert ingest_env["calls"] == []
    assert list(ingest_env["dir"].iterdir()) == []


@pytest.mark.asyncio
async def test_task_artifact_skips_empty_artifact(ingest_env) -> None:
    for result in (
        {},
        {"executor": "delegated-llm-v1"},
        {**_TASK_RESULT, "artifact": ""},
        {**_TASK_RESULT, "artifact": "   \n  "},
    ):
        await ingest_task_artifact(
            task_id=_TASK_A,
            tenant_id=_TENANT_A,
            department="Finance",
            result=result,
        )

    assert ingest_env["calls"] == []
    assert list(ingest_env["dir"].iterdir()) == []


@pytest.mark.asyncio
async def test_task_artifact_fails_open_when_ragx_unreachable(
    ingest_env,
) -> None:
    # ragx outage must never raise into the (already-committed) task path;
    # the summary file stays on disk for a later cron re-index.
    ingest_env["state"]["raise_exc"] = httpx.ConnectError("boom")

    await ingest_task_artifact(
        task_id=_TASK_A,
        tenant_id=_TENANT_A,
        department="Finance",
        result=dict(_TASK_RESULT),
    )

    collection = department_collection_name("Finance", _TENANT_A)
    path = ingest_env["dir"] / collection / f"task-{_TASK_A}.md"
    assert path.exists()
    assert len(ingest_env["calls"]) == 1


@pytest.mark.asyncio
async def test_task_artifact_is_idempotent_same_bytes_same_url(
    ingest_env,
) -> None:
    # Content is keyed only on persisted result values (never now()), so a
    # re-ingest produces identical bytes -> identical SHA -> ragx dedupes.
    collection = department_collection_name("Finance", _TENANT_A)
    path = ingest_env["dir"] / collection / f"task-{_TASK_A}.md"

    await ingest_task_artifact(
        task_id=_TASK_A,
        tenant_id=_TENANT_A,
        department="Finance",
        result=dict(_TASK_RESULT),
    )
    first_bytes = path.read_bytes()

    await ingest_task_artifact(
        task_id=_TASK_A,
        tenant_id=_TENANT_A,
        department="Finance",
        result=dict(_TASK_RESULT),
    )
    second_bytes = path.read_bytes()

    assert first_bytes == second_bytes
    calls = ingest_env["calls"]
    assert len(calls) == 2
    assert calls[0]["url"] == calls[1]["url"]


# ── feeder seam: execute_tool success -> schedule_execution_ingest ───────────


@pytest.mark.asyncio
async def test_execute_tool_success_schedules_execution_ingest(
    db_session, monkeypatch
) -> None:
    """Feeder seam: a COMPLETED execute_tool hands off to
    schedule_execution_ingest (lazily imported at call time, so patching the
    module attribute intercepts) with the committed execution's ids."""
    from app.services.execution_service import ExecutionService
    from tests.test_permission_dispatch_integration import (
        _seed_tenant_user_session,
    )

    tenant_id, user_id, session_id = await _seed_tenant_user_session(db_session)

    async def _fake_dispatch(self, tool_name, params, user_id=None):
        return {"content": "file body"}

    monkeypatch.setattr(ExecutionService, "_dispatch_tool", _fake_dispatch)

    recorded: list[dict] = []
    monkeypatch.setattr(
        "app.services.dept_knowledge_ingest.schedule_execution_ingest",
        lambda **kw: recorded.append(kw),
    )

    # read_file has no per-tool preference seeded here, so BALANCED allows it.
    outcome = await ExecutionService(db_session).execute_tool(
        tool_name="read_file",
        params={"path": "notes.txt"},
        session_id=session_id,
        user_id=user_id,
        tenant_id=tenant_id,
        governance_mode="BALANCED",
        actor_role="OPERATOR",
    )
    assert outcome["status"] == "COMPLETED"

    assert len(recorded) == 1
    handoff = recorded[0]
    assert str(handoff["execution_id"]) == outcome["execution_id"]
    assert handoff["session_id"] == session_id
    assert handoff["tenant_id"] == tenant_id
