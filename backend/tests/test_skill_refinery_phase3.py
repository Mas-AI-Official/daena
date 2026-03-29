"""Tests for Skill Refinery Phase 3: governance integration, usage tracking, health endpoint.

Covers:
- GovernanceEngine.assess_skill_trust_tier
- GovernanceEngine.log_skill_ingestion
- SkillStore.track_usage
- SkillStore.get_usage_stats
- scan_for_updates (news monitor)
- GET /api/v1/skills/refinery/health
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.governance import GovernanceEngine

# ── Governance: skill trust tier ──


class TestSkillTrustTier:
    """GovernanceEngine.assess_skill_trust_tier maps maturity to governance tier."""

    def test_t0_raw_gets_tier_2(self):
        """T0 (raw, untrusted external) should get Tier 2 (logged + notified)."""
        assert GovernanceEngine.assess_skill_trust_tier(0) == 2

    def test_t1_draft_gets_tier_2(self):
        """T1 (draft, partially validated) should get Tier 2."""
        assert GovernanceEngine.assess_skill_trust_tier(1) == 2

    def test_t2_refined_gets_tier_1(self):
        """T2 (refined, passed 3-pass pipeline) should get Tier 1 (log only)."""
        assert GovernanceEngine.assess_skill_trust_tier(2) == 1

    def test_t3_production_gets_tier_1(self):
        """T3 (production grade) should get Tier 1."""
        assert GovernanceEngine.assess_skill_trust_tier(3) == 1

    def test_t4_compound_gets_tier_1(self):
        """T4 (compound, highest trust) should get Tier 1."""
        assert GovernanceEngine.assess_skill_trust_tier(4) == 1


class TestLogSkillIngestion:
    """GovernanceEngine.log_skill_ingestion creates audit entries."""

    @pytest.mark.asyncio
    async def test_logs_extraction_event(self):
        """Skill extraction should be logged as a governance event."""
        mock_db = AsyncMock()
        engine = GovernanceEngine(mock_db)

        # Mock the evaluate method to return a standard decision
        with patch.object(engine, "evaluate", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {
                "allowed": True,
                "governance_tier": 2,
                "risk_level": "LOW",
                "action_type": "SKILL_INGESTION",
            }

            result = await engine.log_skill_ingestion(
                skill_id="skill_test_001",
                title="Test Skill",
                maturity=0,
                source="extract",
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )

            assert result["allowed"] is True
            assert result["governance_tier"] == 2
            mock_eval.assert_called_once()
            call_kwargs = mock_eval.call_args[1]
            assert call_kwargs["action_type"] == "SKILL_INGESTION"
            assert call_kwargs["action_params"]["trust_tier"] == 2

    @pytest.mark.asyncio
    async def test_trusted_skill_gets_lower_tier(self):
        """T2+ skills should have trust_tier=1 in the params."""
        mock_db = AsyncMock()
        engine = GovernanceEngine(mock_db)

        with patch.object(engine, "evaluate", new_callable=AsyncMock) as mock_eval:
            mock_eval.return_value = {"allowed": True, "governance_tier": 1}

            await engine.log_skill_ingestion(
                skill_id="skill_test_002",
                title="Trusted Skill",
                maturity=3,  # T3_PRODUCTION
                source="promote",
                tenant_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )

            call_kwargs = mock_eval.call_args[1]
            assert call_kwargs["action_params"]["trust_tier"] == 1


# ── Usage tracking ──


class TestUsageTracking:
    """SkillStore.track_usage and get_usage_stats."""

    @pytest.fixture
    def mock_skill(self):
        """Create a mock RefinedSkill entry."""
        skill = MagicMock()
        skill.skill_id = "skill_usage_001"
        skill.usage_count = 5
        skill.success_rate = 0.8
        skill.last_validated = datetime.utcnow() - timedelta(days=10)
        skill.improvements_by_daena = []
        return skill

    @pytest.mark.asyncio
    async def test_track_usage_increments_count(self, mock_skill):
        """Usage tracking should increment count and update rate."""
        from app.services.skill_refinery.skill_store import SkillStore

        mock_db = AsyncMock()
        store = SkillStore(mock_db)

        with patch.object(store, "_get_by_skill_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_skill
            result = await store.track_usage(
                skill_id="skill_usage_001",
                tenant_id=uuid.uuid4(),
                success=True,
            )

        assert result["usage_count"] == 6
        assert result["success_rate"] > 0.8  # Was 0.8, adding a success raises it
        assert result["needs_refinement"] is False  # 6 < 10

    @pytest.mark.asyncio
    async def test_track_usage_threshold_flags_refinement(self, mock_skill):
        """After 10 uses, needs_refinement should be True."""
        from app.services.skill_refinery.skill_store import SkillStore

        mock_skill.usage_count = 9  # Will become 10
        mock_db = AsyncMock()
        store = SkillStore(mock_db)

        with patch.object(store, "_get_by_skill_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_skill
            result = await store.track_usage(
                skill_id="skill_usage_001",
                tenant_id=uuid.uuid4(),
                success=True,
            )

        assert result["usage_count"] == 10
        assert result["needs_refinement"] is True

    @pytest.mark.asyncio
    async def test_track_usage_with_feedback(self, mock_skill):
        """Feedback should be stored in improvements_by_daena."""
        from app.services.skill_refinery.skill_store import SkillStore

        mock_db = AsyncMock()
        store = SkillStore(mock_db)

        with patch.object(store, "_get_by_skill_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_skill
            await store.track_usage(
                skill_id="skill_usage_001",
                tenant_id=uuid.uuid4(),
                success=False,
                feedback="Missing edge case handling",
            )

        # Check feedback was appended
        assert len(mock_skill.improvements_by_daena) == 1
        assert "[usage-feedback]" in mock_skill.improvements_by_daena[0]
        assert "Missing edge case" in mock_skill.improvements_by_daena[0]

    @pytest.mark.asyncio
    async def test_get_usage_stats(self, mock_skill):
        """get_usage_stats should return structured stats."""
        from app.services.skill_refinery.skill_store import SkillStore

        mock_skill.improvements_by_daena = [
            "[usage-feedback] Good skill (success=True)",
            "Regular improvement note",
            "[usage-feedback] Needs more examples (success=False)",
        ]
        mock_db = AsyncMock()
        store = SkillStore(mock_db)

        with patch.object(store, "_get_by_skill_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_skill
            result = await store.get_usage_stats(
                skill_id="skill_usage_001",
                tenant_id=uuid.uuid4(),
            )

        assert result["usage_count"] == 5
        assert result["success_rate"] == 0.8
        assert result["feedback_count"] == 2
        assert result["needs_refinement"] is False


# ── News monitor ──


class TestNewsMonitor:
    """scan_for_updates flags stale skills."""

    @pytest.mark.asyncio
    async def test_flags_stale_skill(self):
        """Skills not validated in 90+ days should be flagged."""
        from app.services.skill_refinery.news_monitor import scan_for_updates

        stale_skill = MagicMock()
        stale_skill.skill_id = "skill_stale_001"
        stale_skill.title = "Stale Skill"
        stale_skill.domain = "web_dev"
        stale_skill.maturity = 2
        stale_skill.last_validated = datetime.utcnow() - timedelta(days=100)
        stale_skill.usage_count = 3
        stale_skill.success_rate = 0.9
        stale_skill.source_metadata = {}
        stale_skill.archived_at = None
        stale_skill.tenant_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [stale_skill]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        flagged = await scan_for_updates(
            db=mock_db,
            tenant_id=stale_skill.tenant_id,
        )

        assert len(flagged) == 1
        assert flagged[0]["skill_id"] == "skill_stale_001"
        assert any("not_validated" in r for r in flagged[0]["reasons"])

    @pytest.mark.asyncio
    async def test_flags_low_success_rate(self):
        """Skills with <60% success rate (5+ uses) should be flagged."""
        from app.services.skill_refinery.news_monitor import scan_for_updates

        bad_skill = MagicMock()
        bad_skill.skill_id = "skill_bad_001"
        bad_skill.title = "Bad Skill"
        bad_skill.domain = "coding"
        bad_skill.maturity = 2
        bad_skill.last_validated = datetime.utcnow() - timedelta(days=5)
        bad_skill.usage_count = 8
        bad_skill.success_rate = 0.4
        bad_skill.source_metadata = {}
        bad_skill.archived_at = None
        bad_skill.tenant_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [bad_skill]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        flagged = await scan_for_updates(
            db=mock_db,
            tenant_id=bad_skill.tenant_id,
        )

        assert len(flagged) == 1
        assert any("low_success_rate" in r for r in flagged[0]["reasons"])

    @pytest.mark.asyncio
    async def test_fresh_skill_not_flagged(self):
        """Recently validated, good success rate skills should not be flagged."""
        from app.services.skill_refinery.news_monitor import scan_for_updates

        fresh_skill = MagicMock()
        fresh_skill.skill_id = "skill_fresh_001"
        fresh_skill.title = "Fresh Skill"
        fresh_skill.domain = "design"
        fresh_skill.maturity = 3
        fresh_skill.last_validated = datetime.utcnow() - timedelta(days=5)
        fresh_skill.usage_count = 3
        fresh_skill.success_rate = 0.95
        fresh_skill.source_metadata = {}
        fresh_skill.archived_at = None
        fresh_skill.tenant_id = uuid.uuid4()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fresh_skill]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        flagged = await scan_for_updates(
            db=mock_db,
            tenant_id=fresh_skill.tenant_id,
        )

        assert len(flagged) == 0


# ── Health endpoint (via test client) ──


class TestRefineryHealthEndpoint:
    """GET /api/v1/skills/refinery/health returns library stats."""

    @pytest.mark.asyncio
    async def test_health_endpoint_structure(self):
        """Health response should include total_skills, skills_by_tier, avg confidence."""
        from app.api.v1.skill_refinery import refinery_health

        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()

        # Mock empty database
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        with patch(
            "app.api.v1.skill_refinery.scan_for_updates",
            new_callable=AsyncMock,
        ) as mock_scan:
            mock_scan.return_value = []
            result = await refinery_health(user=mock_user, db=mock_db)

        assert result["success"] is True
        data = result["data"]
        assert data["total_skills"] == 0
        assert data["skills_by_tier"] == {}
        assert data["average_confidence"] == 0.0
        assert data["skills_needing_refresh"] == 0
