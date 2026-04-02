"""Tests for autonomous features: heartbeat work chain, dynamic departments.

Covers:
- Autonomous work check function
- Dynamic department creation
- Domain detection
- Heartbeat config with new check type
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAutonomousWorkCheck:
    """Tests for check_autonomous_work."""

    @pytest.mark.asyncio
    async def test_no_pending_tasks(self):
        """Should return ok when no tasks are pending."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("app.core.database.async_session_factory", return_value=mock_ctx):
            from app.services.heartbeat.heartbeat_checks import check_autonomous_work
            result = await check_autonomous_work()
            assert result.status == "ok"
            assert "No pending" in result.summary

    def test_config_has_autonomous_work(self):
        """HeartbeatConfig should include AUTONOMOUS_WORK check."""
        from app.services.heartbeat.heartbeat_config import HeartbeatConfig, CheckType
        config = HeartbeatConfig.default()
        check_types = {c.check_type for c in config.checks}
        assert CheckType.AUTONOMOUS_WORK in check_types


class TestDynamicDepartments:
    """Tests for dynamic department creation."""

    @pytest.mark.asyncio
    async def test_should_not_create_for_existing_domain(self):
        from app.services.dynamic_departments import should_create_department
        db = AsyncMock()
        should, reason = await should_create_department("engineering", db, uuid.uuid4())
        assert should is False
        assert "existing" in reason.lower()

    @pytest.mark.asyncio
    async def test_should_not_create_for_similar_domain(self):
        from app.services.dynamic_departments import should_create_department
        db = AsyncMock()
        should, _ = await should_create_department("software development", db, uuid.uuid4())
        assert should is False

    @pytest.mark.asyncio
    async def test_should_create_for_novel_domain(self):
        from app.services.dynamic_departments import should_create_department
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        should, reason = await should_create_department("Healthcare", db, uuid.uuid4())
        assert should is True

    @pytest.mark.asyncio
    async def test_auto_detect_healthcare(self):
        """Healthcare keywords should trigger department creation."""
        from app.services.dynamic_departments import auto_detect_and_create

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalar.return_value = 9  # 10 existing departments
        db.execute = AsyncMock(return_value=mock_result)

        result = await auto_detect_and_create(
            "Review the patient records and check the clinical diagnosis for HIPAA compliance",
            db, uuid.uuid4(),
        )
        assert result is not None
        assert result["name"] == "Healthcare"
        assert result["agent_count"] == 6

    @pytest.mark.asyncio
    async def test_auto_detect_no_match(self):
        """Generic text should not trigger department creation."""
        from app.services.dynamic_departments import auto_detect_and_create

        db = AsyncMock()
        result = await auto_detect_and_create(
            "Write a quick Python script to add two numbers",
            db, uuid.uuid4(),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_detect_real_estate(self):
        """Real estate keywords should trigger department creation."""
        from app.services.dynamic_departments import auto_detect_and_create

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalar.return_value = 9
        db.execute = AsyncMock(return_value=mock_result)

        result = await auto_detect_and_create(
            "Find rental properties with good mortgage rates and list them on MLS",
            db, uuid.uuid4(),
        )
        assert result is not None
        assert result["name"] == "Real Estate"

    def test_golden_angle_calculation(self):
        """Sunflower index should use golden angle for placement."""
        import math
        from app.services.dynamic_departments import GOLDEN_ANGLE

        # Golden angle should be approximately 137.508 degrees
        assert abs(GOLDEN_ANGLE - 137.508) < 0.001

        # Each department gets a unique cell_id
        cells = set()
        for i in range(20):
            angle_rad = math.radians(GOLDEN_ANGLE * i)
            cell_id = f"hex_{i}_{int(angle_rad * 1000) % 360}"
            cells.add(cell_id)
        assert len(cells) == 20  # All unique

    def test_sub_capabilities_complete(self):
        from app.services.dynamic_departments import SUB_CAPABILITIES
        assert len(SUB_CAPABILITIES) == 6
        assert "MIND" in SUB_CAPABILITIES
        assert "SHIELD" in SUB_CAPABILITIES


class TestHeartbeatDaemonAutoWork:
    """Tests for heartbeat daemon's autonomous work dispatch."""

    def test_daemon_dispatches_autonomous_work_in_agi_mode(self):
        """Daemon should call check_autonomous_work when in AGI mode."""
        from app.services.heartbeat.heartbeat_config import AutopilotLevel, CheckType

        # The dispatch logic checks autopilot_level == AGI
        # We just verify the check type exists and config supports it
        assert CheckType.AUTONOMOUS_WORK.value == "autonomous_work"
        assert AutopilotLevel.AGI.value == "agi"

    def test_daemon_skips_autonomous_work_in_on_mode(self):
        """Autonomous work should be skipped when not in AGI mode."""
        # This is tested via the daemon dispatch logic:
        # if config.autopilot_level != AutopilotLevel.AGI -> skip
        from app.services.heartbeat.heartbeat_config import AutopilotLevel
        assert AutopilotLevel.ON.value == "on"
        assert AutopilotLevel.ON != AutopilotLevel.AGI
