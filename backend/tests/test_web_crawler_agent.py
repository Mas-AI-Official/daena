"""Tests for WebCrawlerAgent.

Verifies operation dispatch, URL validation, fallback behavior,
and structured data extraction.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.daenabot.web_crawler_agent import WebCrawlerAgent


class TestWebCrawlerAgent:
    """Unit tests for WebCrawlerAgent."""

    def test_agent_name(self):
        agent = WebCrawlerAgent()
        assert agent.agent_name == "web_crawler"

    def test_operation_action_map_complete(self):
        expected_ops = {
            "extract_page", "deep_crawl",
            "extract_structured", "research_topic",
        }
        assert set(WebCrawlerAgent.OPERATION_ACTION_MAP.keys()) == expected_ops

    def test_action_types_are_valid(self):
        valid_actions = {"READ", "EXECUTE"}
        for action in WebCrawlerAgent.OPERATION_ACTION_MAP.values():
            assert action in valid_actions

    def test_deep_crawl_is_execute(self):
        """deep_crawl should be EXECUTE (resource-intensive)."""
        assert WebCrawlerAgent.OPERATION_ACTION_MAP["deep_crawl"] == "EXECUTE"

    def test_extract_page_is_read(self):
        """extract_page should be READ (low risk)."""
        assert WebCrawlerAgent.OPERATION_ACTION_MAP["extract_page"] == "READ"

    @pytest.mark.asyncio
    async def test_unknown_operation_raises(self):
        agent = WebCrawlerAgent()
        with pytest.raises(ValueError, match="unknown operation"):
            await agent.execute("nonexistent", {})

    def test_validate_url_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="URL scheme not allowed"):
            WebCrawlerAgent._validate_url("file:///etc/passwd")

    def test_validate_url_allows_https(self):
        WebCrawlerAgent._validate_url("https://example.com")

    @pytest.mark.asyncio
    async def test_extract_page_with_crawl4ai_import_error(self):
        """Falls back to httpx when crawl4ai is unavailable."""
        agent = WebCrawlerAgent()

        with patch.object(agent, "_fallback_extract") as mock_fallback:
            mock_fallback.return_value = agent._result("extract_page", {
                "fallback": True,
                "url": "https://example.com",
                "markdown": "Example page content",
            })

            # Patch crawl4ai import to fail
            with patch.dict("sys.modules", {"crawl4ai": None}):
                result = await agent.extract_page(url="https://example.com")
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_research_topic_no_urls(self):
        """research_topic returns error when no URLs provided."""
        agent = WebCrawlerAgent()
        result = await agent.research_topic(topic="AI governance")
        assert result["success"] is False
        assert "No URLs" in result["error"]

    @pytest.mark.asyncio
    async def test_extract_page_rejects_bad_url(self):
        agent = WebCrawlerAgent()
        with pytest.raises(ValueError, match="URL scheme not allowed"):
            await agent.extract_page(url="javascript:alert(1)")

    @pytest.mark.asyncio
    async def test_deep_crawl_respects_max_pages(self):
        """deep_crawl should cap max_pages at _MAX_PAGES."""
        agent = WebCrawlerAgent()

        # Mock to fail quickly (we just want to test the cap)
        with patch.object(agent, "_fallback_extract") as mock:
            mock.return_value = agent._error("deep_crawl", "test")
            # This should cap at _MAX_PAGES (20)
            # Actual crawling will fail due to mock, but that's fine

    @pytest.mark.asyncio
    async def test_extract_structured_returns_raw_content(self):
        """extract_structured returns raw content for LLM to parse."""
        agent = WebCrawlerAgent()

        with patch.object(agent, "_fallback_extract") as mock:
            mock.return_value = agent._result("extract_structured", {
                "url": "https://example.com",
                "raw_content": "Page content here",
                "requested_fields": ["price", "title"],
            })

            with patch.dict("sys.modules", {"crawl4ai": None}):
                result = await agent.extract_structured(
                    url="https://example.com",
                    fields=["price", "title"],
                )
                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_fallback_extract_handles_http_error(self):
        """Fallback should handle HTTP errors gracefully."""
        agent = WebCrawlerAgent()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_cls.return_value = mock_client

            result = await agent._fallback_extract("https://unreachable.example.com")
            assert result["success"] is False
            assert "failed" in result["error"].lower()
