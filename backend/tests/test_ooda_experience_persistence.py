"""PR-7 Cognition Closure: durable experience_log persistence + rehydration.

These tests pin the fix for *placebo learning*: the OODA-R reflect phase used
to build a fresh in-memory ``LearningService()`` every call and discard it, so
nothing it "learned" survived the request. PR-7 makes the loop durable --
``OODAEngine._store_experience`` writes one ``experience_log`` row per reflect
and ``LearningService.with_experience_history`` rehydrates prior outcomes on the
next request.

Unlike ``test_ooda_engine.py`` (which mocks the DB to test cognitive *flow*),
these use the REAL ``db_session`` + ``seed_auth_principal`` fixtures so the row
actually round-trips through SQLite -- the only way to prove durability and
tenant isolation. They deliberately exercise only the hermetic paths: the
``_reflect`` success branch (KnowledgeHunter/SelfUpgrader gated off at cycle 0)
and the ``_store_experience`` sink directly for the failure path, so no test
touches the web-search / LLM services the conftest guardrails forbid.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.experience import ExperienceLog
from app.models.identity import Tenant, User
from app.services.cognition.ooda_engine import (
    CognitiveState,
    OODAEngine,
    Strategy,
)
from app.services.learning_service import LearningService


async def _fetch_rows(db_session, tenant_id) -> list[ExperienceLog]:
    """All experience_log rows for a tenant (isolation boundary)."""
    result = await db_session.execute(
        select(ExperienceLog).where(ExperienceLog.tenant_id == tenant_id)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_store_experience_persists_success_row(
    db_session, seed_auth_principal, test_user_id, test_tenant_id
) -> None:
    """The sink writes exactly one SAFE-fields row, meta coerced to JSON."""
    engine = OODAEngine(db_session, test_user_id, test_tenant_id)
    state = CognitiveState(task="build the widget")
    state.current_strategy = Strategy(name="first_principles")
    state.problem_type = "creation"
    state.selected_frameworks = ["first_principles", "inversion"]

    await engine._store_experience(state, True, "widget shipped")

    rows = await _fetch_rows(db_session, test_tenant_id)
    assert len(rows) == 1
    row = rows[0]
    assert str(row.tenant_id) == str(test_tenant_id)
    assert str(row.user_id) == str(test_user_id)
    assert row.session_id is None  # SET NULL: a lesson outlives its session
    assert row.phase == "reflect"
    assert row.outcome == "success"
    assert row.reward == 1.0
    assert row.situation == "build the widget"
    assert row.decision == "first_principles"
    assert row.action_taken == "widget shipped"
    assert row.meta["problem_type"] == "creation"
    assert row.meta["frameworks"] == ["first_principles", "inversion"]
    assert row.meta["cycle"] == 0


@pytest.mark.asyncio
async def test_store_experience_persists_failure_row(
    db_session, seed_auth_principal, test_user_id, test_tenant_id
) -> None:
    """Failure path: outcome/reward flip, root_causes kept to the last three."""
    engine = OODAEngine(db_session, test_user_id, test_tenant_id)
    state = CognitiveState(task="deploy to prod")
    state.current_strategy = Strategy(name="direct_execution")
    state.problem_type = "deployment"
    state.selected_frameworks = ["inversion"]
    state.failure_root_causes = [
        "missing env var", "no perms", "disk full", "timeout",
    ]

    await engine._store_experience(state, False, "deploy failed: timeout")

    rows = await _fetch_rows(db_session, test_tenant_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.outcome == "failure"
    assert row.reward == 0.0
    assert row.decision == "direct_execution"
    assert row.action_taken == "deploy failed: timeout"
    assert row.meta["problem_type"] == "deployment"
    # _store_experience keeps only the last 3 root causes (bounded meta).
    assert row.meta["root_causes"] == ["no perms", "disk full", "timeout"]


@pytest.mark.asyncio
async def test_reflect_success_is_durable_across_requests(
    db_session, seed_auth_principal, test_user_id, test_tenant_id
) -> None:
    """The placebo-learning fix end to end: a reflect outcome survives the
    request and rehydrates into the next request's LearningService."""
    engine = OODAEngine(db_session, test_user_id, test_tenant_id)
    state = CognitiveState(task="optimize the query")
    state.current_strategy = Strategy(name="constraint_relaxation")
    state.problem_type = "optimization"
    state.selected_frameworks = ["systems_thinking"]

    # Full reflect (success branch) -> _get_learning_service + _store_experience.
    await engine._reflect(state, True, "query 10x faster", {})

    # OLD placebo behavior: a fresh service each request remembers nothing.
    assert LearningService()._outcomes == []

    # PR-7: the next request rehydrates the durable outcome from experience_log.
    reloaded = await LearningService.with_experience_history(
        db_session, test_tenant_id
    )
    assert len(reloaded._outcomes) == 1
    outcome = reloaded._outcomes[0]
    assert outcome.success is True
    assert outcome.agent == "cognitive_engine"
    assert outcome.operation == "constraint_relaxation"
    assert outcome.params["problem_type"] == "optimization"
    assert outcome.params["frameworks"] == ["systems_thinking"]


@pytest.mark.asyncio
async def test_experience_history_is_tenant_isolated(
    db_session, seed_auth_principal, test_user_id, test_tenant_id
) -> None:
    """Tenant A's history never seeds tenant B, and vice versa."""
    # Tenant A is the seeded principal; create B as a second FK-valid principal.
    tenant_b = uuid4()
    user_b = uuid4()
    db_session.add(
        Tenant(id=tenant_b, name="Tenant B", slug="tenant-b-iso", settings={})
    )
    await db_session.flush()
    db_session.add(
        User(
            id=user_b, tenant_id=tenant_b, email="tenant-b@example.com",
            password_hash="x", role="FOUNDER", is_active=True,
        )
    )
    await db_session.flush()

    state_a = CognitiveState(task="A task")
    state_a.current_strategy = Strategy(name="strategy_alpha")
    state_a.problem_type = "creation"
    await OODAEngine(
        db_session, test_user_id, test_tenant_id
    )._store_experience(state_a, True, "A ok")

    state_b = CognitiveState(task="B task")
    state_b.current_strategy = Strategy(name="strategy_beta")
    state_b.problem_type = "debugging"
    await OODAEngine(
        db_session, user_b, tenant_b
    )._store_experience(state_b, False, "B broke")

    hist_a = await LearningService.with_experience_history(
        db_session, test_tenant_id
    )
    hist_b = await LearningService.with_experience_history(db_session, tenant_b)

    assert len(hist_a._outcomes) == 1
    assert hist_a._outcomes[0].operation == "strategy_alpha"
    assert hist_a._outcomes[0].success is True

    assert len(hist_b._outcomes) == 1
    assert hist_b._outcomes[0].operation == "strategy_beta"
    assert hist_b._outcomes[0].success is False


@pytest.mark.asyncio
async def test_experience_persisted_when_memory_subsystem_disabled(
    db_session, seed_auth_principal, test_user_id, test_tenant_id, monkeypatch
) -> None:
    """Experience persistence is decoupled from the NBMF memory toggle.

    Hard-disable the memory subsystem (and ResourceFinder, the other external
    observe dependency) so the recall path is provably dead, then run a real
    observe -> reflect. The durable experience row must still be written: a
    cognitive outcome is operational telemetry, recorded whether or not recall
    is enabled. This also guards the decoupling -- if reflect persistence ever
    starts constructing MemoryService, that construction would raise into the
    best-effort sink and the row would silently vanish, failing this test.
    """
    import app.services.cognition.resource_finder as rf_mod
    import app.services.memory as memory_mod

    class _Dead:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("subsystem disabled")

    monkeypatch.setattr(memory_mod, "MemoryService", _Dead)
    monkeypatch.setattr(rf_mod, "ResourceFinder", _Dead)

    engine = OODAEngine(db_session, test_user_id, test_tenant_id)
    state = CognitiveState(task="ship with memory off")
    state.current_strategy = Strategy(name="direct_execution")
    state.problem_type = "creation"

    # Observe genuinely exercises the dead memory path (recall yields nothing).
    state = await engine._observe(state, {})
    assert state.observation.memory_context == []

    # Reflect still persists despite memory being unavailable.
    await engine._reflect(state, True, "shipped", {})

    rows = await _fetch_rows(db_session, test_tenant_id)
    assert len(rows) == 1
    assert rows[0].outcome == "success"
    assert rows[0].decision == "direct_execution"
