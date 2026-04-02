"""Tests for VisionBrowserAgent.

Verifies operation dispatch, URL validation, result extraction,
and fallback behavior when browser-use is unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.daenabot.vision_browser_agent import VisionBrowserAgent


class TestVisionBrowserAgent:
    """Unit tests for VisionBrowserAgent."""

    def test_agent_name(self):
        agent = VisionBrowserAgent()
        assert agent.agent_name == "vision_browser"

    def test_operation_action_map_complete(self):
        expected_ops = {
            "browse_and_act", "research_url", "screenshot_analyze",
            "fill_form_smart", "multi_step_task",
        }
        assert set(VisionBrowserAgent.OPERATION_ACTION_MAP.keys()) == expected_ops

    def test_action_types_are_valid(self):
        valid_actions = {"READ", "EXECUTE", "WRITE_FILE", "POST_PUBLIC"}
        for action in VisionBrowserAgent.OPERATION_ACTION_MAP.values():
            assert action in valid_actions

    @pytest.mark.asyncio
    async def test_unknown_operation_raises(self):
        agent = VisionBrowserAgent()
        with pytest.raises(ValueError, match="unknown operation"):
            await agent.execute("nonexistent", {})

    def test_validate_url_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="URL scheme not allowed"):
            VisionBrowserAgent._validate_url("file:///etc/passwd")

    def test_validate_url_rejects_javascript(self):
        with pytest.raises(ValueError, match="URL scheme not allowed"):
            VisionBrowserAgent._validate_url("javascript:alert(1)")

    def test_validate_url_allows_http(self):
        VisionBrowserAgent._validate_url("http://example.com")

    def test_validate_url_allows_https(self):
        VisionBrowserAgent._validate_url("https://example.com")

    def test_extract_result_handles_none(self):
        result = VisionBrowserAgent._extract_result(None)
        assert result["success"] is False
        assert result["steps_taken"] == 0

    def test_extract_result_handles_string(self):
        result = VisionBrowserAgent._extract_result("some output text")
        assert result["success"] is True
        assert "some output text" in result["content"]

    def test_extract_result_caps_content_size(self):
        long_text = "x" * 10000
        result = VisionBrowserAgent._extract_result(long_text)
        assert len(result["content"]) <= 5000

    @pytest.mark.asyncio
    async def test_research_url_fallback_on_import_error(self):
        """When browser-use is not available, falls back to Playwright."""
        agent = VisionBrowserAgent()

        # Mock _get_agent to raise ImportError
        async def mock_get_agent():
            raise ImportError("browser-use not installed")

        agent._get_agent = mock_get_agent

        # Mock the fallback
        with patch.object(agent, "_fallback_research") as mock_fallback:
            mock_fallback.return_value = agent._result("research_url", {
                "fallback": True, "url": "https://example.com",
            })
            result = await agent.research_url(
                url="https://example.com",
                question="What is this?",
            )
            assert result["success"] is True
            assert result["output"]["fallback"] is True

    @pytest.mark.asyncio
    async def test_browse_and_act_timeout(self):
        """browse_and_act returns error on timeout."""
        agent = VisionBrowserAgent()

        import asyncio

        async def slow_run(**kwargs):
            await asyncio.sleep(999)

        mock_agent = MagicMock()
        mock_agent.run = slow_run

        async def mock_get_agent():
            return mock_agent

        agent._get_agent = mock_get_agent

        # Patch the timeout to be very short
        with patch("app.services.daenabot.vision_browser_agent._TASK_TIMEOUT", 0.01):
            result = await agent.browse_and_act(goal="test", url="https://example.com")
            assert result["success"] is False
            assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_fill_form_smart_rejects_bad_url(self):
        agent = VisionBrowserAgent()
        with pytest.raises(ValueError, match="URL scheme not allowed"):
            await agent.fill_form_smart(
                url="ftp://evil.com",
                form_data={"name": "test"},
            )

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """close() should not raise when nothing was initialized."""
        agent = VisionBrowserAgent()
        await agent.close()  # Should not raise
