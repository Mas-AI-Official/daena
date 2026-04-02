"""Tests for LearningService.

Verifies outcome tracking, skill extraction, feedback recording,
and pattern detection.
"""

from __future__ import annotations

import pytest

from app.services.learning_service import ActionOutcome, LearningService


class TestLearningService:
    """Unit tests for LearningService."""

    def setup_method(self):
        self.service = LearningService()

    @pytest.mark.asyncio
    async def test_track_outcome_stores(self):
        outcome = ActionOutcome(
            action_id="test-1",
            session_id="session-1",
            agent="web_crawler",
            operation="extract_page",
            params={"url": "https://example.com"},
            success=True,
            output_preview="Page content...",
            duration_ms=1500,
        )
        await self.service.track_outcome(outcome)
        assert len(self.service._outcomes) == 1
        assert "session-1" in self.service._session_outcomes

    @pytest.mark.asyncio
    async def test_track_multiple_outcomes(self):
        for i in range(5):
            await self.service.track_outcome(ActionOutcome(
                action_id=f"test-{i}",
                session_id="session-1",
                agent="web_crawler",
                operation="extract_page",
                params={"url": f"https://example.com/{i}"},
                success=i < 4,  # 4 successes, 1 failure
                duration_ms=1000,
            ))
        assert len(self.service._outcomes) == 5
        assert len(self.service._session_outcomes["session-1"]) == 5

    @pytest.mark.asyncio
    async def test_track_user_feedback(self):
        await self.service.track_outcome(ActionOutcome(
            action_id="feedback-test",
            session_id="session-1",
            agent="browser",
            operation="navigate",
            params={},
            success=True,
        ))
        await self.service.track_user_feedback("feedback-test", "good")
        assert self.service._outcomes[-1].user_feedback == "good"

    @pytest.mark.asyncio
    async def test_feedback_for_nonexistent_action(self):
        """Feedback for unknown action should not raise."""
        await self.service.track_user_feedback("nonexistent", "bad")

    @pytest.mark.asyncio
    async def test_extract_skills_insufficient_steps(self):
        """No skills extracted with fewer than 3 steps."""
        await self.service.track_outcome(ActionOutcome(
            action_id="test-1",
            session_id="session-short",
            agent="file",
            operation="read_file",
            params={},
            success=True,
        ))
        skills = await self.service.extract_skills_from_session("session-short")
        assert skills == []

    @pytest.mark.asyncio
    async def test_extract_skills_success(self):
        """Skills extracted from successful multi-step session."""
        for i in range(5):
            await self.service.track_outcome(ActionOutcome(
                action_id=f"skill-{i}",
                session_id="session-good",
                agent="web_crawler" if i % 2 == 0 else "file",
                operation="extract_page" if i % 2 == 0 else "read_file",
                params={"url": f"https://example.com/{i}"},
                success=True,
                output_preview=f"Output {i}",
            ))
        skills = await self.service.extract_skills_from_session("session-good")
        assert len(skills) == 1
        skill = skills[0]
        assert skill["source"] == "auto_extracted"
        assert skill["confidence"] == 1.0
        assert len(skill["steps"]) == 5

    @pytest.mark.asyncio
    async def test_extract_skills_low_success_rate(self):
        """No skills when success rate is below threshold."""
        for i in range(5):
            await self.service.track_outcome(ActionOutcome(
                action_id=f"fail-{i}",
                session_id="session-bad",
                agent="terminal",
                operation="execute_command",
                params={},
                success=i < 2,  # Only 40% success
            ))
        skills = await self.service.extract_skills_from_session("session-bad")
        assert skills == []

    def test_get_suggestions_empty(self):
        suggestions = self.service.get_suggestions("web_crawler", "extract_page")
        assert suggestions == []

    @pytest.mark.asyncio
    async def test_get_suggestions_high_failure_rate(self):
        for i in range(10):
            await self.service.track_outcome(ActionOutcome(
                action_id=f"fail-{i}",
                session_id="session-errors",
                agent="browser",
                operation="navigate",
                params={},
                success=i < 3,  # 70% failure rate
                error="Timeout" if i >= 3 else None,
            ))
        suggestions = self.service.get_suggestions("browser", "navigate")
        assert len(suggestions) >= 1
        assert any(s["type"] == "error_pattern" for s in suggestions)

    @pytest.mark.asyncio
    async def test_get_suggestions_slow_actions(self):
        for i in range(10):
            await self.service.track_outcome(ActionOutcome(
                action_id=f"slow-{i}",
                session_id="session-slow",
                agent="web_crawler",
                operation="deep_crawl",
                params={},
                success=True,
                duration_ms=40000 if i < 5 else 1000,  # 50% are slow
            ))
        suggestions = self.service.get_suggestions("web_crawler", "deep_crawl")
        assert any(s["type"] == "performance" for s in suggestions)

    def test_get_session_summary_empty(self):
        summary = self.service.get_session_summary("nonexistent")
        assert summary["actions"] == 0
        assert summary["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_session_summary(self):
        for i in range(3):
            await self.service.track_outcome(ActionOutcome(
                action_id=f"sum-{i}",
                session_id="session-sum",
                agent="file",
                operation="read_file",
                params={},
                success=True,
                duration_ms=500,
            ))
        summary = self.service.get_session_summary("session-sum")
        assert summary["actions"] == 3
        assert summary["success_rate"] == 1.0
        assert "file" in summary["agents_used"]
        assert summary["total_duration_ms"] == 1500

    def test_get_stats_empty(self):
        stats = self.service.get_stats()
        assert stats["total_actions_tracked"] == 0
        assert stats["sessions_tracked"] == 0

    @pytest.mark.asyncio
    async def test_generalize_params(self):
        template = LearningService._generalize_params({
            "url": "https://example.com",
            "email": "user@example.com",
            "count": 5,
            "name": "test",
        })
        assert template["url"] == "{url_or_path}"
        assert template["email"] == "{email}"
        assert template["count"] == "{number}"
        assert template["name"] == "{name}"

    def test_describe_pattern_empty(self):
        desc = LearningService._describe_pattern([])
        assert desc == "Empty pattern"

    def test_describe_pattern_multi_step(self):
        steps = [
            {"agent": "web_crawler", "operation": "extract_page"},
            {"agent": "file", "operation": "write_file"},
        ]
        desc = LearningService._describe_pattern(steps)
        assert "web_crawler" in desc
        assert "file" in desc
