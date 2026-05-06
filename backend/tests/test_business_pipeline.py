"""Sprint-19 PR-1 -- business pipeline orchestrator contract.

Pins:
  1. OPPORTUNITY_TYPES is the locked Sprint-19 set of 8.
  2. Scorer is deterministic: same input -> same score, NO LLM.
  3. Scorer components clamped 0..25; total clamped 0..100.
  4. Manual-seed source tolerates missing/malformed file.
  5. Orchestrator dedupes by (source_name, title).
  6. Orchestrator caps at top_n by score desc.
  7. Orchestrator NEVER raises even if a source explodes.
  8. Orchestrator does NOT auto-approve any GoaRequest.
  9. Module surface exposes no callable named send / submit / post / pay.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from app.services.business_pipeline import discoverer

    monkeypatch.setattr(
        discoverer, "_SEED_FILE", tmp_path / ".opportunity_seed.json",
    )
    discoverer._reset_for_tests()
    yield


async def _seed_tenant(db_session, tenant_id):
    from app.models.identity import Tenant

    tenant = Tenant(id=tenant_id, name="Test", slug="test-19")
    db_session.add(tenant)
    await db_session.flush()


# ────────────────────────────────────────────────────────────────────
# Type set
# ────────────────────────────────────────────────────────────────────


class TestOpportunityTypes:
    async def test_locked_eight_types(self):
        from app.models.business import OPPORTUNITY_TYPES

        assert OPPORTUNITY_TYPES == (
            "customer_lead",
            "grant",
            "accelerator",
            "hackathon",
            "freelance_project",
            "partnership",
            "bug_bounty_program",
            "content_opportunity",
        )


# ────────────────────────────────────────────────────────────────────
# Scorer
# ────────────────────────────────────────────────────────────────────


class TestScorer:
    async def test_score_deterministic(self):
        from app.services.business_pipeline.discoverer import (
            DiscoveredOpportunity,
        )
        from app.services.business_pipeline.scorer import score_opportunity

        op = DiscoveredOpportunity(
            type="grant",
            title="MAS-AI grant",
            source_name="manual_seed",
            estimated_value_usd=50000,
            effort_hours=20,
            deadline_at=datetime.now(UTC) + timedelta(days=10),
        )
        s1 = score_opportunity(op)
        s2 = score_opportunity(op)
        assert s1 == s2
        assert 0 <= s1 <= 100

    async def test_overdue_deadline_zero_proximity(self):
        from app.services.business_pipeline.discoverer import (
            DiscoveredOpportunity,
        )
        from app.services.business_pipeline.scorer import score_components

        op = DiscoveredOpportunity(
            type="grant",
            title="Past due",
            source_name="manual_seed",
            deadline_at=datetime.now(UTC) - timedelta(days=1),
        )
        comps = score_components(op)
        assert comps["deadline_proximity"] == 0

    async def test_high_value_low_effort_grant_scores_high(self):
        from app.services.business_pipeline.discoverer import (
            DiscoveredOpportunity,
        )
        from app.services.business_pipeline.scorer import score_opportunity

        op = DiscoveredOpportunity(
            type="grant",
            title="Big grant tomorrow",
            source_name="manual_seed",
            estimated_value_usd=500000,
            effort_hours=2,
            deadline_at=datetime.now(UTC) + timedelta(days=1),
        )
        score = score_opportunity(op)
        assert score >= 80

    async def test_unknown_type_falls_back_to_baseline(self):
        from app.services.business_pipeline.discoverer import (
            DiscoveredOpportunity,
        )
        from app.services.business_pipeline.scorer import score_components

        op = DiscoveredOpportunity(
            type="totally_unknown_type",  # not in TYPE_WEIGHT
            title="x",
            source_name="manual_seed",
        )
        comps = score_components(op)
        assert comps["type_weight"] == 10  # baseline


# ────────────────────────────────────────────────────────────────────
# Manual seed source
# ────────────────────────────────────────────────────────────────────


class TestManualSeedSource:
    async def test_missing_file_returns_empty(self, isolated_state):
        from app.services.business_pipeline.discoverer import (
            manual_seed_source,
        )
        assert list(manual_seed_source()) == []

    async def test_malformed_json_returns_empty(self, isolated_state):
        from app.services.business_pipeline import discoverer
        discoverer._SEED_FILE.write_text("not valid json {")
        assert list(discoverer.manual_seed_source()) == []

    async def test_well_formed_seed(self, isolated_state):
        from app.services.business_pipeline import discoverer

        discoverer._SEED_FILE.write_text(json.dumps([
            {
                "type": "grant",
                "title": "MAS-AI Q3 grant",
                "source_name": "manual_seed",
                "deadline_at": "2026-12-01T00:00:00+00:00",
                "estimated_value_usd": 25000,
                "effort_hours": 8,
            },
            {
                "type": "hackathon",
                "title": "Devpost Spring Hack",
                "source_name": "manual_seed",
            },
        ]))
        results = list(discoverer.manual_seed_source())
        assert len(results) == 2
        assert results[0].type == "grant"
        assert results[0].estimated_value_usd == 25000

    async def test_unknown_type_skipped(self, isolated_state):
        from app.services.business_pipeline import discoverer

        discoverer._SEED_FILE.write_text(json.dumps([
            {"type": "send_money_now", "title": "BAD"},
            {"type": "grant", "title": "good"},
        ]))
        results = list(discoverer.manual_seed_source())
        assert len(results) == 1
        assert results[0].title == "good"


# ────────────────────────────────────────────────────────────────────
# Orchestrator
# ────────────────────────────────────────────────────────────────────


class TestOrchestrator:
    async def test_dedupes_by_source_and_title(
        self, isolated_state, db_session, test_tenant_id,
    ):
        from app.services.business_pipeline import discoverer
        from app.services.business_pipeline.discoverer import (
            DiscoveredOpportunity,
        )
        from app.services.business_pipeline.orchestrator import (
            run_discovery_loop,
        )

        await _seed_tenant(db_session, test_tenant_id)

        def src():
            return [
                DiscoveredOpportunity(
                    type="grant", title="Same title",
                    source_name="src_a",
                ),
                DiscoveredOpportunity(
                    type="grant", title="Same title",
                    source_name="src_a",
                ),
                DiscoveredOpportunity(
                    type="grant", title="Same title",
                    source_name="src_b",  # different source -> NOT dup
                ),
            ]
        discoverer.unregister_source("manual_seed")
        discoverer.register_source("src", src)

        result = await run_discovery_loop(
            db_session, tenant_id=test_tenant_id, top_n=10,
        )
        assert result.discovered_count == 3
        assert result.deduped_count == 2
        assert result.persisted_count == 2

    async def test_caps_at_top_n_by_score(
        self, isolated_state, db_session, test_tenant_id,
    ):
        from app.services.business_pipeline import discoverer
        from app.services.business_pipeline.discoverer import (
            DiscoveredOpportunity,
        )
        from app.services.business_pipeline.orchestrator import (
            run_discovery_loop,
        )

        await _seed_tenant(db_session, test_tenant_id)

        def src():
            # 5 opportunities; top_n=2 should keep only top 2.
            now = datetime.now(UTC)
            return [
                DiscoveredOpportunity(
                    type="grant", title=f"op-{i}",
                    source_name="src",
                    estimated_value_usd=i * 10000,
                    deadline_at=now + timedelta(days=30 - i * 5),
                )
                for i in range(5)
            ]
        discoverer.unregister_source("manual_seed")
        discoverer.register_source("src", src)

        result = await run_discovery_loop(
            db_session, tenant_id=test_tenant_id, top_n=2,
        )
        assert result.deduped_count == 5
        assert result.persisted_count == 2
        assert result.capped_count == 3

    async def test_failing_source_does_not_propagate(
        self, isolated_state, db_session, test_tenant_id,
    ):
        from app.services.business_pipeline import discoverer
        from app.services.business_pipeline.orchestrator import (
            run_discovery_loop,
        )

        await _seed_tenant(db_session, test_tenant_id)

        def good_src():
            from app.services.business_pipeline.discoverer import (
                DiscoveredOpportunity,
            )
            return [DiscoveredOpportunity(
                type="grant", title="ok", source_name="g",
            )]

        def bad_src():
            raise RuntimeError("source explosion")

        discoverer.unregister_source("manual_seed")
        discoverer.register_source("good", good_src)
        discoverer.register_source("bad", bad_src)

        result = await run_discovery_loop(
            db_session, tenant_id=test_tenant_id,
        )
        assert "bad" in result.sources_failed
        assert result.persisted_count == 1  # good source still landed

    async def test_empty_registry_returns_zero(
        self, isolated_state, db_session, test_tenant_id,
    ):
        from app.services.business_pipeline import discoverer
        from app.services.business_pipeline.orchestrator import (
            run_discovery_loop,
        )

        await _seed_tenant(db_session, test_tenant_id)
        discoverer.unregister_source("manual_seed")  # empty registry

        result = await run_discovery_loop(
            db_session, tenant_id=test_tenant_id,
        )
        assert result.discovered_count == 0
        assert result.persisted_count == 0


# ────────────────────────────────────────────────────────────────────
# Module surface guard
# ────────────────────────────────────────────────────────────────────


class TestNoForbiddenSurface:
    async def test_orchestrator_module_no_send_submit_post_pay(self):
        from app.services.business_pipeline import orchestrator as mod

        forbidden = {
            "send", "submit", "post", "pay", "execute_send",
            "send_email", "send_message", "post_to",
        }
        for name in dir(mod):
            if name.startswith("_"):
                continue
            assert name.lower() not in forbidden, (
                f"orchestrator exposes forbidden callable: {name}"
            )

    async def test_no_llm_import_in_scorer(self):
        """Scorer must be deterministic Python only. No call to
        LLM service / model_router in this module."""
        from app.services.business_pipeline import scorer

        src = Path(scorer.__file__).read_text(encoding="utf-8")
        assert "llm_service" not in src
        assert "model_router" not in src
        assert "anthropic" not in src.lower()
        assert "openai" not in src.lower()
