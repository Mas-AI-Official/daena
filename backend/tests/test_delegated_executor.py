"""P1 real executor contract: delegated-llm-v1.

``ExecutionService._background_run`` branches on the delegation envelope:
tasks with ``checkpoint_data.delegation.origin == "delegated"`` run through
``delegated_executor.execute_delegated_step`` (one governed model call ->
work-product artifact in ``task.result``); everything else has NO
executor wired and fails honestly, never a fabricated completion.

Contracts pinned here:

* ``build_step_prompt`` is PURE and deterministic, and the system prompt
  pins the no-tools honesty clause (an approved outward step yields a
  ready-to-send artifact, never a false "sent it" claim).
* HONEST FAILURE (ADR-001 / Rule 17): empty artifact, timeout, and
  missing registry all RAISE; through ``run_task`` that lands the task in
  FAILED with the error recorded -- never a fake COMPLETED.
* The executor result dict carries the audit fields (executor tag, model,
  provider, tokens, cost) and ``_background_run`` stamps ``executed_at``.
* Non-delegated tasks never reach the real executor; with no executor
  wired they land FAILED honestly, never a fake COMPLETED.
* Phase 11 pin: the delegated path still emits the ``task_complete``
  notification with the executor's summary as the message.

The LLM boundary is faked at the documented test seams (``llm_service``
kwarg for unit tests; ``app.services.delegated_executor
.execute_delegated_step`` module attribute for lifecycle tests --
execution_service imports it lazily inside ``_background_run``, so the
patched attribute is exactly what gets picked up).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.core.constants import ModelProvider
from app.models.execution import Task
from app.models.notification import Notification
from app.services import delegated_executor
from app.services.daena_vp import VPSubtask
from app.services.delegated_executor import (
    EXECUTOR_NAME,
    build_step_prompt,
    execute_delegated_step,
)
from app.services.delegated_goals import DelegatedGoalService
from app.services.execution_service import ExecutionService
from app.services.providers.base import LLMResponse

from tests.test_delegated_goals import _plan, _seed, _wait_terminal


async def _drain_bg(timeout: float = 12.0) -> None:
    """Wait for detached ``_background_run`` tasks to finish."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        pending = [
            t for t in asyncio.all_tasks()
            if not t.done()
            and "_background_run"
            in getattr(t.get_coro(), "__qualname__", "")
        ]
        if not pending:
            return
        await asyncio.sleep(0.05)


@pytest.fixture(autouse=True)
async def _drain_background_runs():
    """Same guard as test_delegated_goals: let run_task's detached
    ``_background_run`` finish before the test ends so its final commit
    cannot interleave with the next test's cleanup on the shared
    in-memory StaticPool connection."""
    yield
    await _drain_bg()


@pytest.fixture(autouse=True)
def _capture_artifact_ingest(monkeypatch):
    """P2 seam guard + recorder: after COMPLETED commits, the delegated
    branch hands the result to ``schedule_task_artifact_ingest`` (lazily
    imported, so patching the module attribute intercepts). Recording it
    keeps every test here offline -- no file writes under var/ and no
    ragx HTTP -- and lets the seam tests assert the handoff contract."""
    calls: list[dict] = []

    def _record(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.services.dept_knowledge_ingest.schedule_task_artifact_ingest",
        _record,
    )
    return calls


async def _wait_for_calls(
    calls: list, n: int = 1, timeout: float = 8.0
) -> None:
    """The COMPLETED row commits BEFORE the ingest handoff fires inside
    ``_background_run``, so ``_wait_terminal`` alone cannot prove the
    handoff happened yet -- poll the recorder."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if len(calls) >= n:
            return
        await asyncio.sleep(0.05)


# ── fakes at the documented seams ───────────────────────────────────


def _response(content: str = "## Draft\n\nThe artifact body.") -> LLMResponse:
    return LLMResponse(
        content=content,
        model_id="fake-model-1",
        provider=ModelProvider.OLLAMA,
        token_count_input=42,
        token_count_output=17,
        cost_usd=0.0,
        latency_ms=12,
    )


class FakeLLMService:
    """Stands in for LLMService at the ``llm_service`` test seam.

    Captures the GenerateRequest so tests can assert the prompt/metadata
    contract that actually crosses the LLM boundary.
    """

    def __init__(self, response: LLMResponse | None = None):
        self.response = response or _response()
        self.requests: list = []

    async def generate_direct(self, request):
        self.requests.append(request)
        return self.response


_DELEGATION = {
    "origin": "delegated",
    "goal": "Understand churn and brief investors",
    "department": "Engineering",
    "classification": "free",
    "step_index": 0,
}


# ── 1. build_step_prompt: pure, deterministic, honest ───────────────


class TestBuildStepPrompt:
    def test_deterministic(self):
        a = build_step_prompt(
            name="Analyze churn", description="Analyze the churn data",
            delegation=dict(_DELEGATION),
        )
        b = build_step_prompt(
            name="Analyze churn", description="Analyze the churn data",
            delegation=dict(_DELEGATION),
        )
        assert a == b
        assert isinstance(a, tuple) and len(a) == 2

    def test_system_prompt_pins_no_tools_honesty(self):
        system, _ = build_step_prompt(
            name="x", description="x", delegation=dict(_DELEGATION),
        )
        assert "Engineering department" in system
        assert "never claim to have sent" in system
        assert "## Blocked" in system

    def test_user_prompt_carries_envelope_fields(self):
        _, user = build_step_prompt(
            name="Analyze churn",
            description="Analyze the churn data from March",
            delegation=dict(_DELEGATION),
        )
        assert "# Assigned step: Analyze churn" in user
        assert "Understand churn and brief investors" in user
        assert "Step index in the plan: 0" in user
        assert "Governance classification: free" in user
        assert "## Step description" in user
        assert "Analyze the churn data from March" in user

    def test_description_section_omitted_when_same_as_name(self):
        _, user = build_step_prompt(
            name="Analyze churn", description="Analyze churn",
            delegation=dict(_DELEGATION),
        )
        assert "## Step description" not in user

    def test_defaults_for_sparse_envelope(self):
        system, user = build_step_prompt(
            name="Do the thing", description="", delegation={},
        )
        assert "General department" in system
        assert "Governance classification: free" in user
        assert "Step index" not in user


# ── 2. execute_delegated_step unit contract (llm_service seam) ─────


@pytest.mark.asyncio
async def test_execute_returns_artifact_and_audit_fields():
    fake = FakeLLMService()
    tenant = uuid.uuid4()
    result = await execute_delegated_step(
        name="Analyze churn",
        description="Analyze the churn data",
        delegation=dict(_DELEGATION),
        tenant_id=tenant,
        llm_service=fake,
    )
    assert result["executor"] == EXECUTOR_NAME == "delegated-llm-v1"
    assert result["summary"] == "[Engineering] Analyze churn"
    assert result["artifact"] == "## Draft\n\nThe artifact body."
    assert result["artifact_format"] == "markdown"
    assert result["model_id"] == "fake-model-1"
    assert result["provider"] == "OLLAMA"
    assert result["classification"] == "free"
    assert result["step_index"] == 0
    assert result["tokens_input"] == 42
    assert result["tokens_output"] == 17

    # The request that crossed the boundary carried the contract.
    assert len(fake.requests) == 1
    req = fake.requests[0]
    assert req.system_prompt and "never claim to have sent" in req.system_prompt
    assert req.metadata["origin"] == "delegated"
    assert req.metadata["executor"] == EXECUTOR_NAME
    assert req.metadata["tenant_id"] == str(tenant)
    assert req.messages[0].role == "user"


@pytest.mark.asyncio
async def test_empty_artifact_raises_honest_failure():
    fake = FakeLLMService(response=_response(content="   \n  "))
    with pytest.raises(RuntimeError, match="empty artifact"):
        await execute_delegated_step(
            name="x", description="x", delegation=dict(_DELEGATION),
            tenant_id=uuid.uuid4(), llm_service=fake,
        )


@pytest.mark.asyncio
async def test_timeout_raises_honest_failure(monkeypatch):
    class HangingService:
        async def generate_direct(self, request):
            await asyncio.sleep(5)

    monkeypatch.setattr(delegated_executor, "_STEP_TIMEOUT_S", 0.05)
    with pytest.raises(RuntimeError, match="timed out"):
        await execute_delegated_step(
            name="x", description="x", delegation=dict(_DELEGATION),
            tenant_id=uuid.uuid4(), llm_service=HangingService(),
        )


@pytest.mark.asyncio
async def test_no_registry_raises_retryable_error(monkeypatch):
    async def _no_registry():
        return None

    monkeypatch.setattr(delegated_executor, "_get_registry", _no_registry)
    with pytest.raises(RuntimeError, match="registry unavailable"):
        await execute_delegated_step(
            name="x", description="x", delegation=dict(_DELEGATION),
            tenant_id=uuid.uuid4(),
        )


# ── 3. lifecycle through run_task (module-attribute seam) ──────────


async def _materialize_free_task(db):
    tid, uid, _ = await _seed(db)
    await DelegatedGoalService(db).materialize_plan(
        _plan(
            [
                VPSubtask(
                    description="Summarize the Q2 board report",
                    department="Engineering",
                )
            ]
        ),
        tenant_id=tid,
        user_id=uid,
    )
    task = (
        await db.execute(select(Task).where(Task.tenant_id == tid))
    ).scalar_one()
    return tid, uid, task.id


@pytest.mark.asyncio
async def test_delegated_task_completes_with_real_executor_result(
    db_session, monkeypatch,
):
    calls: list[dict] = []

    async def _fake_execute(**kwargs):
        calls.append(kwargs)
        return {
            "executor": EXECUTOR_NAME,
            "summary": "[Engineering] Summarize the Q2 board report",
            "artifact": "## Q2 Summary\n\nRevenue up.",
            "artifact_format": "markdown",
        }

    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step",
        _fake_execute,
    )
    tid, uid, task_id = await _materialize_free_task(db_session)
    result = await ExecutionService(db_session).run_task(task_id, tid)
    assert result["status"] == "RUNNING"
    assert await _wait_terminal(db_session, task_id) == "COMPLETED"

    db_session.expire_all()
    row = (
        await db_session.execute(select(Task).where(Task.id == task_id))
    ).scalar_one()
    assert row.progress == 100
    assert row.result["executor"] == "delegated-llm-v1"
    assert row.result["artifact"] == "## Q2 Summary\n\nRevenue up."
    assert row.result["executed_at"], "bg runner must stamp executed_at"

    # The branch passed the captured envelope through untouched.
    assert len(calls) == 1
    assert calls[0]["delegation"]["origin"] == "delegated"
    assert calls[0]["tenant_id"] == tid


@pytest.mark.asyncio
async def test_delegated_executor_failure_marks_task_failed(
    db_session, monkeypatch,
):
    async def _boom(**kwargs):
        raise RuntimeError("provider down: all backends unavailable")

    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step", _boom,
    )
    tid, uid, task_id = await _materialize_free_task(db_session)
    await ExecutionService(db_session).run_task(task_id, tid)
    assert await _wait_terminal(db_session, task_id) == "FAILED"

    db_session.expire_all()
    row = (
        await db_session.execute(select(Task).where(Task.id == task_id))
    ).scalar_one()
    assert "provider down" in (row.error or "")
    assert row.result is None, "honest failure must not fake a result"


@pytest.mark.asyncio
async def test_non_delegated_task_fails_honestly_without_executor(
    db_session, monkeypatch,
):
    """A plain task must not invoke the real executor NOR fabricate
    success: with no executor wired it lands FAILED (retryable)."""

    async def _must_not_run(**kwargs):
        raise AssertionError("real executor invoked for a plain task")

    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step",
        _must_not_run,
    )
    tid, uid, _ = await _seed(db_session)
    task_id = uuid.uuid4()
    task = Task(
        id=task_id,
        tenant_id=tid,
        user_id=uid,
        name="Plain operator task",
        description="No delegation envelope",
        status="PENDING",
    )
    db_session.add(task)
    await db_session.commit()

    await ExecutionService(db_session).run_task(task_id, tid)
    assert await _wait_terminal(db_session, task_id) == "FAILED"
    db_session.expire_all()
    row = (
        await db_session.execute(select(Task).where(Task.id == task_id))
    ).scalar_one()
    assert "no executor" in (row.error or "").lower()
    assert row.result is None, "honest failure must not fake a result"


@pytest.mark.asyncio
async def test_delegated_completion_still_emits_notification(
    db_session, monkeypatch,
):
    """Phase 11 pin: the new branch shares the task_complete emit path,
    and the notification message is the executor's summary."""

    async def _fake_execute(**kwargs):
        return {
            "executor": EXECUTOR_NAME,
            "summary": "[Engineering] Summarize the Q2 board report",
            "artifact": "body",
            "artifact_format": "markdown",
        }

    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step",
        _fake_execute,
    )
    tid, uid, task_id = await _materialize_free_task(db_session)
    await ExecutionService(db_session).run_task(task_id, tid)
    assert await _wait_terminal(db_session, task_id) == "COMPLETED"

    db_session.expire_all()
    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.tenant_id == tid,
                Notification.type == "task_complete",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].message == "[Engineering] Summarize the Q2 board report"
    assert rows[0].source == "execution_service.background_run"


# ── 4. P2 knowledge loop: completed artifact -> dept ingest seam ────


@pytest.mark.asyncio
async def test_delegated_completion_schedules_artifact_ingest(
    db_session, monkeypatch, _capture_artifact_ingest,
):
    """After COMPLETED commits, _background_run hands the persisted result
    to schedule_task_artifact_ingest scoped to the delegation's department."""

    async def _fake_execute(**kwargs):
        return {
            "executor": EXECUTOR_NAME,
            "summary": "[Engineering] Summarize the Q2 board report",
            "artifact": "## Q2 Summary\n\nRevenue up.",
            "artifact_format": "markdown",
        }

    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step",
        _fake_execute,
    )
    tid, uid, task_id = await _materialize_free_task(db_session)
    await ExecutionService(db_session).run_task(task_id, tid)
    assert await _wait_terminal(db_session, task_id) == "COMPLETED"

    await _wait_for_calls(_capture_artifact_ingest)
    assert len(_capture_artifact_ingest) == 1
    call = _capture_artifact_ingest[0]
    assert call["task_id"] == task_id
    assert call["tenant_id"] == tid
    assert call["department"] == "Engineering"
    assert call["result"]["artifact"] == "## Q2 Summary\n\nRevenue up."
    assert call["result"]["executed_at"], "handoff carries the stamped result"


@pytest.mark.asyncio
async def test_artifactless_delegated_completion_skips_ingest(
    db_session, monkeypatch, _capture_artifact_ingest,
):
    """No artifact -> nothing to index; the handoff must not fire."""

    async def _fake_execute(**kwargs):
        return {
            "executor": EXECUTOR_NAME,
            "summary": "[Engineering] Summarize the Q2 board report",
        }

    monkeypatch.setattr(
        "app.services.delegated_executor.execute_delegated_step",
        _fake_execute,
    )
    tid, uid, task_id = await _materialize_free_task(db_session)
    await ExecutionService(db_session).run_task(task_id, tid)
    assert await _wait_terminal(db_session, task_id) == "COMPLETED"
    await _drain_bg()
    assert _capture_artifact_ingest == []


@pytest.mark.asyncio
async def test_non_delegated_run_skips_ingest(
    db_session, _capture_artifact_ingest,
):
    """The no-executor failure path never feeds department knowledge."""
    tid, uid, _ = await _seed(db_session)
    task_id = uuid.uuid4()
    db_session.add(
        Task(
            id=task_id,
            tenant_id=tid,
            user_id=uid,
            name="Plain operator task",
            description="No delegation envelope",
            status="PENDING",
        )
    )
    await db_session.commit()

    await ExecutionService(db_session).run_task(task_id, tid)
    assert await _wait_terminal(db_session, task_id) == "FAILED"
    await _drain_bg()
    assert _capture_artifact_ingest == []
