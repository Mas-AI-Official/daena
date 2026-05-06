"""Sprint-19 PR-6 -- business routine wiring contract.

Pins:
  1. Importing business_pipeline registers the
     opportunity_discovery handler.
  2. Running the routine handler with a real DB session +
     manual-seed source produces persisted opportunities.
  3. Routine handler initiates with initiator='scheduler' --
     trust auto-approval CANNOT fire for any GoaRequest produced
     downstream (proven separately in PR-4/5 tests).
  4. Routine handler NEVER raises even with bad inputs.
  5. routine_autonomy.run_once forwards db/tenant_id/user_id
     kwargs to the handler.
"""

from __future__ import annotations

import json
import uuid

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services.business_pipeline import discoverer, routine_handler
    from app.services import routine_autonomy

    monkeypatch.setattr(
        discoverer, "_SEED_FILE", tmp_path / ".opportunity_seed.json",
    )
    monkeypatch.setattr(
        routine_autonomy, "_STATE_FILE",
        tmp_path / ".routine_autonomy.json",
    )
    discoverer._reset_for_tests()
    routine_autonomy._HANDLERS.clear()
    # Re-register so the handler is fresh.
    routine_handler.register()
    yield


async def _seed_tenant(db_session, tenant_id):
    from sqlalchemy import select
    from app.models.identity import Tenant

    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        import uuid as _uuid
        tenant = Tenant(
            id=tenant_id, name="T",
            slug=f"sprint19-pr6-{_uuid.uuid4().hex[:6]}",
        )
        db_session.add(tenant)
    await db_session.flush()


# ────────────────────────────────────────────────────────────────────


class TestHandlerRegistered:
    async def test_opportunity_discovery_handler_in_registry(
        self, isolated_state,
    ):
        from app.services.routine_autonomy import registered_handler_kinds

        assert "opportunity_discovery" in registered_handler_kinds()


class TestHandlerProducesArtifacts:
    async def test_seeded_file_persists_opportunities(
        self, isolated_state, db_session, test_tenant_id,
    ):
        from app.services.business_pipeline import discoverer
        from app.services.business_pipeline.routine_handler import (
            opportunity_discovery_handler,
        )

        await _seed_tenant(db_session, test_tenant_id)
        discoverer._SEED_FILE.write_text(json.dumps([
            {"type": "grant", "title": "Routine grant",
             "source_name": "manual_seed"},
        ]))

        artifacts, detail = await opportunity_discovery_handler(
            db=db_session, tenant_id=test_tenant_id,
            user_id=uuid.uuid4(), top_n=10,
        )
        assert any("persisted" in a for a in artifacts)
        assert "discovered=1" in detail


class TestNeverRaises:
    async def test_missing_context_returns_typed_result(
        self, isolated_state,
    ):
        from app.services.business_pipeline.routine_handler import (
            opportunity_discovery_handler,
        )

        # No db / tenant_id -> graceful return, no raise.
        artifacts, detail = await opportunity_discovery_handler(
            db=None, tenant_id=None,
        )
        assert artifacts == []
        assert "missing" in detail


class TestRunOnceForwardsContext:
    """routine_autonomy.run_once forwards db/tenant_id/user_id
    kwargs to the registered handler. Without that wiring, business
    routines cannot run."""

    async def test_run_once_passes_context(
        self, isolated_state, db_session, test_tenant_id,
    ):
        from app.services import routine_autonomy
        from app.services.routine_autonomy import register_routine

        await _seed_tenant(db_session, test_tenant_id)
        r = register_routine(
            kind="opportunity_discovery",
            name="Daily discovery",
        )
        # No source registered AND we're calling without the seed
        # file so discovered_count=0, but the handler still runs OK.
        result = await routine_autonomy.run_once(
            r.id,
            db=db_session,
            tenant_id=test_tenant_id,
            user_id=uuid.uuid4(),
        )
        assert result.outcome.value == "ok"
        # detail carries discovered=0
        assert result.detail and "discovered=0" in result.detail
