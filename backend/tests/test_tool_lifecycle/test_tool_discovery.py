"""Tests for Tool Discovery + Auto Scanner -- the learning layer of TLM."""

from __future__ import annotations

import pytest

from app.services.tool_lifecycle.tool_discovery import (
    TOOL_CATALOG,
    ToolCandidate,
    ToolDiscovery,
)
from app.services.tool_lifecycle.auto_scanner import (
    AutoScanner,
    ScanConfig,
    ScanResult,
)


@pytest.fixture
def discovery() -> ToolDiscovery:
    return ToolDiscovery()


@pytest.fixture
def scanner() -> AutoScanner:
    return AutoScanner(ScanConfig(enabled=False))


# ── Discovery Tests ───────────────────────────────────────────

class TestDiscoverySearch:
    def test_search_jira(self, discovery: ToolDiscovery):
        results = discovery.search("jira ticket management")
        assert len(results) >= 1
        assert results[0].id == "jira"

    def test_search_pdf(self, discovery: ToolDiscovery):
        results = discovery.search("read pdf document extract text")
        ids = [r.id for r in results]
        assert "pdf_reader" in ids

    def test_search_github(self, discovery: ToolDiscovery):
        results = discovery.search("github pull request code review")
        ids = [r.id for r in results]
        assert "github_mcp" in ids

    def test_search_with_category_filter(self, discovery: ToolDiscovery):
        results = discovery.search("manage", category="crm")
        for r in results:
            assert r.category == "crm"

    def test_search_excludes_installed(self, discovery: ToolDiscovery):
        results = discovery.search("jira", exclude_ids=["jira"])
        ids = [r.id for r in results]
        assert "jira" not in ids

    def test_search_max_results(self, discovery: ToolDiscovery):
        results = discovery.search("tool", max_results=3)
        assert len(results) <= 3

    def test_search_no_match_returns_empty(self, discovery: ToolDiscovery):
        results = discovery.search("xyznonexistent123")
        assert results == []

    def test_search_by_need(self, discovery: ToolDiscovery):
        """When LLM requests 'jira_api', find candidates."""
        results = discovery.search_by_need("jira_api")
        assert len(results) >= 1
        assert "jira" in results[0].id or "jira" in results[0].name.lower()


class TestDiscoveryCategories:
    def test_get_categories(self, discovery: ToolDiscovery):
        categories = discovery.get_categories()
        assert "code" in categories
        assert "comms" in categories
        assert "storage" in categories

    def test_get_by_category(self, discovery: ToolDiscovery):
        code_tools = discovery.get_by_category("code")
        assert len(code_tools) >= 2
        assert all(t.category == "code" for t in code_tools)


class TestDepartmentSuggestions:
    def test_engineering_suggestions(self, discovery: ToolDiscovery):
        tools = discovery.suggest_for_department("engineering")
        categories = {t.category for t in tools}
        assert "code" in categories

    def test_sales_suggestions(self, discovery: ToolDiscovery):
        tools = discovery.suggest_for_department("sales")
        categories = {t.category for t in tools}
        assert "crm" in categories

    def test_unknown_department_gets_defaults(self, discovery: ToolDiscovery):
        tools = discovery.suggest_for_department("unknown_dept")
        assert len(tools) > 0  # still gets default suggestions


class TestCatalogQuality:
    def test_catalog_has_enough_tools(self):
        assert len(TOOL_CATALOG) >= 25

    def test_all_tools_have_required_fields(self):
        for tool in TOOL_CATALOG:
            assert tool.id, f"Tool missing id"
            assert tool.name, f"Tool {tool.id} missing name"
            assert tool.description, f"Tool {tool.id} missing description"
            assert tool.source, f"Tool {tool.id} missing source"
            assert tool.install_method, f"Tool {tool.id} missing install_method"
            assert 0 <= tool.compatibility <= 1.0
            assert 0 <= tool.security_score <= 1.0

    def test_ranking_returns_relevant_results(self, discovery: ToolDiscovery):
        results = discovery.search("manage project tasks")
        assert len(results) >= 1
        # All results should have some relevance to the query
        for r in results:
            combined = f"{r.id} {r.name} {r.description} {r.category}".lower()
            assert any(w in combined for w in ["manage", "project", "task"]), \
                f"Result '{r.name}' not relevant to 'manage project tasks'"


# ── Auto Scanner Tests ────────────────────────────────────────

class TestAutoScanner:
    def test_scan_now(self, scanner: AutoScanner):
        result = scanner.scan_now()
        assert isinstance(result, ScanResult)
        assert result.scan_id.startswith("scan-")

    def test_scan_discovers_tools(self, scanner: AutoScanner):
        result = scanner.scan_now()
        assert len(result.tools_discovered) > 0

    def test_scan_excludes_installed(self, scanner: AutoScanner):
        scanner.set_installed_tools(["jira", "github_mcp", "slack_mcp"])
        result = scanner.scan_now()
        discovered_ids = {t.id for t in result.tools_discovered}
        assert "jira" not in discovered_ids
        assert "github_mcp" not in discovered_ids

    def test_scan_respects_user_focus(self, scanner: AutoScanner):
        scanner.set_user_focus(["code"])
        result = scanner.scan_now()
        # Should find code-related tools
        has_code = any(t.category == "code" for t in result.tools_discovered)
        assert has_code

    def test_scan_suggestions_limited(self, scanner: AutoScanner):
        scanner.config.max_suggestions = 3
        result = scanner.scan_now()
        assert len(result.tools_suggested) <= 3


class TestAutoInstall:
    def test_auto_install_off_by_default(self, scanner: AutoScanner):
        result = scanner.scan_now()
        assert result.auto_installed == []

    def test_auto_install_when_enabled(self):
        scanner = AutoScanner(ScanConfig(
            enabled=True,
            auto_install=True,
            max_suggestions=5,
        ))
        result = scanner.scan_now()
        # Should auto-install high-quality tools
        if result.tools_suggested:
            assert len(result.auto_installed) <= 2  # max 2 per scan

    def test_auto_install_requires_quality(self):
        """Only auto-install tools with high security + compatibility."""
        scanner = AutoScanner(ScanConfig(auto_install=True))
        result = scanner.scan_now()
        for tool_id in result.auto_installed:
            tool = next(t for t in result.tools_discovered if t.id == tool_id)
            assert tool.security_score >= 0.85
            assert tool.compatibility >= 0.85


class TestScanHistory:
    def test_history_tracked(self, scanner: AutoScanner):
        scanner.scan_now()
        scanner.scan_now()
        assert len(scanner.get_scan_history()) == 2

    def test_last_scan(self, scanner: AutoScanner):
        scanner.scan_now()
        last = scanner.get_last_scan()
        assert last is not None

    def test_clear_history(self, scanner: AutoScanner):
        scanner.scan_now()
        scanner.clear_history()
        assert scanner.get_last_scan() is None


class TestScanConfig:
    def test_default_config(self):
        config = ScanConfig()
        assert config.enabled is False
        assert config.interval_hours == 168.0  # weekly
        assert config.auto_install is False

    def test_custom_config(self):
        config = ScanConfig(
            enabled=True,
            interval_hours=24.0,  # daily
            auto_install=True,
            scan_categories=["code", "data"],
        )
        assert config.enabled is True
        assert config.interval_hours == 24.0


# ── Integration: Discovery -> Scanner -> Governance ───────────

class TestDiscoveryPipeline:
    def test_full_discovery_pipeline(self):
        """Simulate: LLM needs 'jira' -> discover -> rank -> suggest."""
        discovery = ToolDiscovery()

        # Step 1: LLM requested a tool that doesn't exist
        requested = "jira_api"
        candidates = discovery.search_by_need(requested, max_results=3)
        assert len(candidates) >= 1

        # Step 2: Rank by quality (already sorted by search)
        best = candidates[0]
        assert best.compatibility > 0.5
        assert best.security_score > 0.5

        # Step 3: Would go to governance here (tested elsewhere)
        # Supervised mode: show to user with install button
        # AGI mode: auto-install if governance approves

    def test_user_niche_detection(self):
        """User who does mostly web design -> scanner focuses on design tools."""
        scanner = AutoScanner(ScanConfig(enabled=True))
        scanner.set_user_focus(["design", "code"])
        scanner.set_installed_tools(["terminal", "file_system", "browser"])

        result = scanner.scan_now()
        categories = {t.category for t in result.tools_discovered}
        assert "design" in categories or "code" in categories
