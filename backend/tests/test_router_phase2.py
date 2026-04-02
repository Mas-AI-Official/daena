"""Tests for DaenaBotRouter Phase 2 patterns.

Verifies that vision_browser and web_crawler patterns are correctly
matched and prioritized in the routing system.
"""

from __future__ import annotations

import pytest

from app.services.daenabot.router import DaenaBotRouter


class TestVisionBrowserPatterns:
    """Test vision_browser routing patterns."""

    def test_research_url(self):
        call = DaenaBotRouter.match("research https://example.com")
        assert call is not None
        assert call.tool_name == "vision_browser.research_url"
        assert call.params["url"] == "https://example.com"

    def test_analyze_website(self):
        call = DaenaBotRouter.match("analyze website https://perplexity.ai")
        assert call is not None
        assert call.tool_name == "vision_browser.research_url"
        assert call.params["url"] == "https://perplexity.ai"

    def test_study_page(self):
        call = DaenaBotRouter.match("study https://manus.im")
        assert call is not None
        assert call.tool_name == "vision_browser.research_url"

    def test_whats_on_url(self):
        call = DaenaBotRouter.match("what's on https://example.com")
        assert call is not None
        assert call.tool_name == "vision_browser.research_url"
        assert "What is on this page" in call.params["question"]

    def test_fill_form(self):
        call = DaenaBotRouter.match("fill out the form at https://pear.vc/apply")
        assert call is not None
        assert call.tool_name == "vision_browser.fill_form_smart"
        assert call.params["url"] == "https://pear.vc/apply"

    def test_browse_and_act(self):
        call = DaenaBotRouter.match(
            "browse https://producthunt.com and find top AI products"
        )
        assert call is not None
        assert call.tool_name == "vision_browser.browse_and_act"
        assert call.params["url"] == "https://producthunt.com"
        assert "find top AI products" in call.params["goal"]

    def test_act_on_url(self):
        call = DaenaBotRouter.match(
            "on https://example.com, extract pricing details"
        )
        assert call is not None
        assert call.tool_name == "vision_browser.browse_and_act"


class TestWebCrawlerPatterns:
    """Test web_crawler routing patterns."""

    def test_crawl_site(self):
        call = DaenaBotRouter.match("crawl https://example.com")
        assert call is not None
        assert call.tool_name == "web_crawler.deep_crawl"
        assert call.params["url"] == "https://example.com"

    def test_deep_crawl(self):
        call = DaenaBotRouter.match("deep crawl https://docs.example.com")
        assert call is not None
        assert call.tool_name == "web_crawler.deep_crawl"

    def test_scrape_site(self):
        call = DaenaBotRouter.match("scrape site https://competitor.com")
        assert call is not None
        assert call.tool_name == "web_crawler.deep_crawl"

    def test_extract_data(self):
        call = DaenaBotRouter.match("extract data from https://api.example.com/docs")
        assert call is not None
        assert call.tool_name == "web_crawler.extract_page"

    def test_get_info(self):
        call = DaenaBotRouter.match("get information from https://example.com")
        assert call is not None
        assert call.tool_name == "web_crawler.extract_page"

    def test_read_page(self):
        call = DaenaBotRouter.match("read page from https://example.com/about")
        assert call is not None
        assert call.tool_name == "web_crawler.extract_page"

    def test_research_topic(self):
        call = DaenaBotRouter.match(
            "research AI governance from https://example.com, https://other.com"
        )
        assert call is not None
        assert call.tool_name == "web_crawler.research_topic"
        assert call.params["topic"] == "AI governance"
        assert len(call.params["urls"]) == 2


class TestPatternPriority:
    """Test that pattern priority is correct."""

    def test_terminal_before_browser(self):
        """Terminal patterns should match before browser."""
        call = DaenaBotRouter.match("run 'curl https://example.com'")
        assert call is not None
        assert call.tool_name == "terminal.execute_command"

    def test_vision_browser_research_before_basic_browser(self):
        """Vision browser 'research' should match before basic browser 'open'."""
        call = DaenaBotRouter.match("research https://example.com")
        assert call is not None
        assert call.tool_name == "vision_browser.research_url"

    def test_basic_navigate_still_works(self):
        """Basic browser 'go to' should still work for simple navigation."""
        call = DaenaBotRouter.match("go to https://example.com")
        assert call is not None
        assert call.tool_name == "browser.navigate"

    def test_empty_message_returns_none(self):
        assert DaenaBotRouter.match("") is None

    def test_no_match_returns_none(self):
        assert DaenaBotRouter.match("what is the meaning of life") is None
