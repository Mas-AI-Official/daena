"""Tests for /3vilbob advanced features:
- Hidden SHIELD activation (offensive department overlays)
- Tool catalog (security tool knowledge base)
- SelfUpgrader wiring (Meta-Harness loop)
- Security dashboard API
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest


# =========================================================================
# 1. HIDDEN SHIELD ACTIVATION TESTS
# =========================================================================

class TestHiddenShieldActivation:
    """Test that SHIELD sub-capabilities switch to offensive when /3vilbob is ON."""

    def test_defensive_shield_when_inactive(self):
        """SHIELD returns defensive prompt when /3vilbob is OFF."""
        from app.services.security import evilbob_mode
        evilbob_mode.deactivate()

        from app.services.department_prompts import get_agent_prompt
        prompt = get_agent_prompt("Engineering", "SHIELD")
        assert "offensive" not in prompt.lower()
        assert "SHIELD" in prompt
        assert "security review" in prompt.lower() or "vulnerabilities" in prompt.lower()

    def test_offensive_shield_when_active(self):
        """SHIELD returns offensive prompt when /3vilbob is ON."""
        from app.services.security import evilbob_mode
        with patch.dict(os.environ, {"EVILBOB_KEY": "test-key"}):
            evilbob_mode.activate(key="test-key")
            try:
                from app.services.department_prompts import get_agent_prompt
                prompt = get_agent_prompt("Engineering", "SHIELD")
                assert "OFFENSIVE MODE" in prompt
                assert "exploit" in prompt.lower()
            finally:
                evilbob_mode.deactivate()

    def test_non_shield_unchanged_when_active(self):
        """MIND/EYES/HANDS/VOICE/MEMORY are NOT affected by /3vilbob."""
        from app.services.security import evilbob_mode
        with patch.dict(os.environ, {"EVILBOB_KEY": "test-key"}):
            evilbob_mode.activate(key="test-key")
            try:
                from app.services.department_prompts import get_agent_prompt
                for sub in ["MIND", "EYES", "HANDS", "VOICE", "MEMORY"]:
                    prompt = get_agent_prompt("Engineering", sub)
                    assert "OFFENSIVE MODE" not in prompt
            finally:
                evilbob_mode.deactivate()

    def test_all_10_departments_have_offensive_shield(self):
        """Every department has an offensive SHIELD overlay."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS, _DEPARTMENT_PROMPTS
        for dept in _DEPARTMENT_PROMPTS:
            assert dept in _OFFENSIVE_SHIELD_PROMPTS, f"{dept} missing offensive SHIELD"
            assert "OFFENSIVE MODE" in _OFFENSIVE_SHIELD_PROMPTS[dept]

    def test_offensive_shield_engineering_exploits(self):
        """Engineering SHIELD focuses on exploit development."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Engineering"]
        assert "exploit" in prompt.lower()
        assert "proof-of-concept" in prompt.lower() or "kill chain" in prompt.lower()

    def test_offensive_shield_sales_social_engineering(self):
        """Sales SHIELD focuses on social engineering."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Sales"]
        assert "social engineering" in prompt.lower()
        assert "pretext" in prompt.lower()

    def test_offensive_shield_research_zero_day(self):
        """Research SHIELD focuses on zero-day discovery."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Research"]
        assert "zero-day" in prompt.lower() or "undiscovered" in prompt.lower()
        assert "fuzzing" in prompt.lower()

    def test_offensive_shield_secops_red_team(self):
        """Security Operations SHIELD coordinates full red team."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Security Operations"]
        assert "red team" in prompt.lower()
        assert "evasion" in prompt.lower()
        assert "master attack plan" in prompt.lower()

    def test_offensive_shield_legal_compliance_gaps(self):
        """Legal SHIELD weaponizes compliance gaps."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Legal & Compliance"]
        assert "GDPR" in prompt or "compliance" in prompt.lower()

    def test_offensive_shield_skill_gov_ai_attacks(self):
        """Skill Governance SHIELD attacks AI/ML systems."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Skill Governance"]
        assert "prompt injection" in prompt.lower()
        assert "model" in prompt.lower()

    def test_get_offensive_shield_status_active(self):
        """get_offensive_shield_status returns all True when active."""
        from app.services.security import evilbob_mode
        with patch.dict(os.environ, {"EVILBOB_KEY": "test-key"}):
            evilbob_mode.activate(key="test-key")
            try:
                from app.services.department_prompts import get_offensive_shield_status
                status = get_offensive_shield_status()
                assert all(v is True for v in status.values())
                assert len(status) == 10
            finally:
                evilbob_mode.deactivate()

    def test_get_offensive_shield_status_inactive(self):
        """get_offensive_shield_status returns all False when inactive."""
        from app.services.security import evilbob_mode
        evilbob_mode.deactivate()
        from app.services.department_prompts import get_offensive_shield_status
        status = get_offensive_shield_status()
        assert all(v is False for v in status.values())

    def test_dynamic_department_shield_not_offensive(self):
        """Dynamic departments do NOT get offensive SHIELD (they have no overlay)."""
        from app.services.security import evilbob_mode
        from app.services.department_prompts import register_dynamic_department, get_agent_prompt
        with patch.dict(os.environ, {"EVILBOB_KEY": "test-key"}):
            evilbob_mode.activate(key="test-key")
            try:
                register_dynamic_department("CustomDept", "Custom department for testing")
                prompt = get_agent_prompt("CustomDept", "SHIELD")
                assert "OFFENSIVE MODE" not in prompt
            finally:
                evilbob_mode.deactivate()

    def test_offensive_shield_marketing_impersonation(self):
        """Marketing SHIELD analyzes impersonation surface."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Marketing"]
        assert "impersonation" in prompt.lower()
        assert "phishing" in prompt.lower() or "spoofing" in prompt.lower()

    def test_offensive_shield_finance_payment_exploits(self):
        """Finance SHIELD targets payment systems."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Finance"]
        assert "payment" in prompt.lower()
        assert "race condition" in prompt.lower() or "exploit" in prompt.lower()

    def test_offensive_shield_operations_lateral_movement(self):
        """Operations SHIELD plans lateral movement."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Operations"]
        assert "lateral movement" in prompt.lower()
        assert "infrastructure" in prompt.lower()

    def test_offensive_shield_product_business_logic(self):
        """Product SHIELD exploits business logic."""
        from app.services.department_prompts import _OFFENSIVE_SHIELD_PROMPTS
        prompt = _OFFENSIVE_SHIELD_PROMPTS["Product"]
        assert "business logic" in prompt.lower()
        assert "IDOR" in prompt or "privilege escalation" in prompt.lower()


# =========================================================================
# 2. TOOL CATALOG TESTS
# =========================================================================

class TestToolCatalog:
    """Test the security tool knowledge base."""

    def test_catalog_has_tools(self):
        """Catalog contains 40+ tools."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        assert catalog.total_tools >= 40

    def test_catalog_has_capabilities(self):
        """Catalog indexes multiple capabilities."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        assert catalog.total_capabilities >= 20

    def test_find_by_capability_subdomain(self):
        """Find tools for subdomain enumeration."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.find_by_capability("subdomain_enumeration")
        names = [t.name for t in tools]
        assert "subfinder" in names
        assert "amass" in names

    def test_find_by_capability_port_scanning(self):
        """Find tools for port scanning."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.find_by_capability("port_scanning")
        names = [t.name for t in tools]
        assert "nmap" in names

    def test_find_by_category_recon(self):
        """Find all recon tools."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.find_by_category("recon")
        assert len(tools) >= 5
        assert all(t.category == "recon" for t in tools)

    def test_search_fuzzy(self):
        """Fuzzy search finds tools by description."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        results = catalog.search("sql injection")
        names = [t.name for t in results]
        assert "sqlmap" in names

    def test_search_by_name(self):
        """Search by tool name."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        results = catalog.search("nmap")
        assert results[0].name == "nmap"

    def test_get_specific_tool(self):
        """Get a specific tool by name."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tool = catalog.get("nuclei")
        assert tool is not None
        assert tool.name == "nuclei"
        assert "vulnerability_scanning" in tool.capabilities

    def test_get_unknown_tool(self):
        """Get returns None for unknown tools."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        assert catalog.get("nonexistent_tool_xyz") is None

    def test_categories(self):
        """Catalog has expected categories."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        cats = catalog.categories
        assert "recon" in cats
        assert "scanning" in cats
        assert "web" in cats
        assert "osint" in cats

    def test_offensive_only_flag(self):
        """Some tools are marked offensive-only."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        sqlmap = catalog.get("sqlmap")
        assert sqlmap is not None
        assert sqlmap.offensive_only is True

        subfinder = catalog.get("subfinder")
        assert subfinder is not None
        assert subfinder.offensive_only is False

    def test_usage_examples(self):
        """Tools have usage examples."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        nmap = catalog.get("nmap")
        assert nmap is not None
        assert len(nmap.usage_examples) >= 3

    def test_get_usage(self):
        """Get usage command for a task."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        cmd = catalog.get_usage("nmap", "service detection")
        assert cmd is not None
        assert "-sV" in cmd

    def test_recommend_for_web_target(self):
        """Recommendations include web tools for web targets."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.recommend_for_target("web_application")
        names = [t.name for t in tools]
        assert any(n in names for n in ["katana", "ffuf", "feroxbuster", "gobuster"])
        assert any(n in names for n in ["nuclei", "nikto"])

    def test_recommend_for_cloud_target(self):
        """Recommendations include cloud tools for cloud targets."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.recommend_for_target("cloud_service")
        names = [t.name for t in tools]
        assert any(n in names for n in ["cloudfox", "prowler", "scoutsuite"])

    def test_recommend_with_waf(self):
        """WAF detected adds anonymity tools."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.recommend_for_target("web_application", waf_detected="cloudflare")
        names = [t.name for t in tools]
        assert any(n in names for n in ["tor", "proxychains"])

    def test_install_plan(self):
        """Get install plan for a capability."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        plan = catalog.get_install_plan("vulnerability_scanning")
        assert isinstance(plan, list)
        # Plan items have name and install_cmd
        for item in plan:
            assert "name" in item
            assert "install_cmd" in item

    def test_recommend_wordpress(self):
        """WordPress technology triggers wpscan recommendation."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        tools = catalog.recommend_for_target(
            "web_application",
            technologies=["WordPress 6.2"],
        )
        names = [t.name for t in tools]
        assert "wpscan" in names


# =========================================================================
# 3. SELF-UPGRADER WIRING TESTS
# =========================================================================

class TestSelfUpgraderWiring:
    """Test that scan traces feed back into the self-improvement loop."""

    def test_self_upgrader_imports(self):
        """SelfUpgrader can be imported."""
        from app.services.cognition.self_upgrader import SelfUpgrader
        upgrader = SelfUpgrader()
        assert upgrader._adoption_threshold == 0.6

    @pytest.mark.asyncio
    async def test_discover_from_history_success_patterns(self):
        """SelfUpgrader finds success patterns in history."""
        from app.services.cognition.self_upgrader import SelfUpgrader
        upgrader = SelfUpgrader()

        # Simulate 5 successes with same strategy
        history = [
            {"success": True, "problem_type": "web_app", "strategy": "dir_brute", "task": f"scan_target_{i}"}
            for i in range(5)
        ]
        candidates = await upgrader.discover_from_history(history)
        assert len(candidates) >= 1
        assert any("web_app" in c.when_to_use for c in candidates)

    @pytest.mark.asyncio
    async def test_discover_from_history_failure_patterns(self):
        """SelfUpgrader finds failure patterns (anti-fragility)."""
        from app.services.cognition.self_upgrader import SelfUpgrader
        upgrader = SelfUpgrader()

        history = [
            {"success": False, "problem_type": "hardened_cloud", "strategy": "nuclei_scan", "task": f"scan_{i}"}
            for i in range(3)
        ]
        candidates = await upgrader.discover_from_history(history)
        avoid_candidates = [c for c in candidates if c.name.startswith("avoid_")]
        assert len(avoid_candidates) >= 1

    @pytest.mark.asyncio
    async def test_learn_from_user(self):
        """SelfUpgrader learns from user instructions."""
        from app.services.cognition.self_upgrader import SelfUpgrader
        upgrader = SelfUpgrader()
        candidate = await upgrader.learn_from_user(
            "When scanning financial APIs, always check for race conditions in payment endpoints",
            problem_type="api_security",
        )
        assert candidate.source == "user_taught"
        assert candidate.backtest_score == 0.8

    def test_cognitive_scan_engine_has_self_upgrade(self):
        """CognitiveScanEngine has _maybe_self_upgrade method."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine()
        assert hasattr(engine, "_maybe_self_upgrade")

    @pytest.mark.asyncio
    async def test_maybe_self_upgrade_no_traces(self):
        """_maybe_self_upgrade is no-op when no traces exist."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine()
        with patch.dict(os.environ, {"DAENA_VAR": tempfile.mkdtemp()}):
            # No trace dir, should return silently
            await engine._maybe_self_upgrade()

    @pytest.mark.asyncio
    async def test_maybe_self_upgrade_insufficient_traces(self):
        """_maybe_self_upgrade skips when fewer than 10 traces."""
        from app.services.security.cognitive_scan_engine import CognitiveScanEngine
        engine = CognitiveScanEngine()

        tmp = tempfile.mkdtemp()
        trace_dir = os.path.join(tmp, "scan_traces")
        os.makedirs(trace_dir)
        # Write 5 traces (less than 10 threshold)
        for i in range(5):
            with open(os.path.join(trace_dir, f"trace_{i}.json"), "w") as f:
                json.dump({"scan_id": f"t{i}", "total_findings": 1}, f)

        with patch.dict(os.environ, {"DAENA_VAR": tmp}):
            await engine._maybe_self_upgrade()  # Should return early
        shutil.rmtree(tmp)


# =========================================================================
# 4. SECURITY DASHBOARD API TESTS
# =========================================================================

class TestSecurityDashboardAPI:
    """Test the /security/* API endpoints."""

    def test_dashboard_status_endpoint_exists(self):
        """Dashboard status endpoint is importable."""
        from app.api.v1.security_dashboard import get_dashboard_status
        assert get_dashboard_status is not None

    def test_tools_endpoint_exists(self):
        """Tools listing endpoint is importable."""
        from app.api.v1.security_dashboard import list_tools
        assert list_tools is not None

    def test_scans_endpoint_exists(self):
        """Scans listing endpoint is importable."""
        from app.api.v1.security_dashboard import list_scans
        assert list_scans is not None

    def test_shields_endpoint_exists(self):
        """Shields detail endpoint is importable."""
        from app.api.v1.security_dashboard import get_shield_details
        assert get_shield_details is not None

    @pytest.mark.asyncio
    async def test_dashboard_status_response(self):
        """Dashboard status returns valid structure."""
        from app.services.security import evilbob_mode
        evilbob_mode.deactivate()

        from app.api.v1.security_dashboard import get_dashboard_status
        status = await get_dashboard_status()
        assert status.evilbob_active is False
        assert isinstance(status.shield_status, dict)
        assert isinstance(status.tool_stats, dict)
        assert isinstance(status.scan_history, list)

    @pytest.mark.asyncio
    async def test_dashboard_status_active(self):
        """Dashboard shows active state when /3vilbob ON."""
        from app.services.security import evilbob_mode
        with patch.dict(os.environ, {"EVILBOB_KEY": "test-key"}):
            evilbob_mode.activate(key="test-key")
            try:
                from app.api.v1.security_dashboard import get_dashboard_status
                status = await get_dashboard_status()
                assert status.evilbob_active is True
                assert len(status.capabilities) > 0
                assert all(v is True for v in status.shield_status.values())
            finally:
                evilbob_mode.deactivate()

    @pytest.mark.asyncio
    async def test_list_tools_all(self):
        """List all tools returns full catalog."""
        from app.api.v1.security_dashboard import list_tools
        tools = await list_tools()
        assert len(tools) >= 40
        assert all(hasattr(t, "name") for t in tools)

    @pytest.mark.asyncio
    async def test_list_tools_by_category(self):
        """Filter tools by category."""
        from app.api.v1.security_dashboard import list_tools
        tools = await list_tools(category="recon")
        assert len(tools) >= 3
        assert all(t.category == "recon" for t in tools)

    @pytest.mark.asyncio
    async def test_list_tools_by_capability(self):
        """Filter tools by capability."""
        from app.api.v1.security_dashboard import list_tools
        tools = await list_tools(capability="port_scanning")
        assert len(tools) >= 2
        names = [t.name for t in tools]
        assert "nmap" in names

    @pytest.mark.asyncio
    async def test_recommend_tools_endpoint(self):
        """Tool recommendations return relevant tools."""
        from app.api.v1.security_dashboard import recommend_tools
        tools = await recommend_tools(target_type="web_application")
        assert len(tools) >= 3

    @pytest.mark.asyncio
    async def test_shields_detail_inactive(self):
        """Shield details when /3vilbob OFF."""
        from app.services.security import evilbob_mode
        evilbob_mode.deactivate()

        from app.api.v1.security_dashboard import get_shield_details
        result = await get_shield_details()
        assert result["evilbob_active"] is False
        assert result["total_offensive"] == 0

    @pytest.mark.asyncio
    async def test_shields_detail_active(self):
        """Shield details when /3vilbob ON."""
        from app.services.security import evilbob_mode
        with patch.dict(os.environ, {"EVILBOB_KEY": "test-key"}):
            evilbob_mode.activate(key="test-key")
            try:
                from app.api.v1.security_dashboard import get_shield_details
                result = await get_shield_details()
                assert result["evilbob_active"] is True
                assert result["total_offensive"] == 10
                assert all(
                    d["mode"] == "offensive"
                    for d in result["departments"].values()
                )
            finally:
                evilbob_mode.deactivate()

    def test_load_scan_history_empty(self):
        """Scan history returns empty list when no traces."""
        from app.api.v1.security_dashboard import _load_scan_history
        # Patch BOTH source dirs: _load_scan_history merges DAENA_VAR/scan_traces
        # AND SECURITY_REPORTS_DIR (default var/security_reports, which holds real
        # report JSON in the repo). Patching only DAENA_VAR still reads real data.
        with patch.dict(os.environ, {
            "DAENA_VAR": tempfile.mkdtemp(),
            "SECURITY_REPORTS_DIR": tempfile.mkdtemp(),
        }):
            result = _load_scan_history()
            assert result == []

    def test_load_scan_history_with_traces(self):
        """Scan history loads and summarizes traces."""
        from app.api.v1.security_dashboard import _load_scan_history

        tmp = tempfile.mkdtemp()
        trace_dir = os.path.join(tmp, "scan_traces")
        os.makedirs(trace_dir)
        with open(os.path.join(trace_dir, "test-scan-1.json"), "w") as f:
            json.dump({
                "scan_id": "test-scan-1",
                "target": "example.com",
                "target_type": "web",
                "total_findings": 5,
                "cycles_used": 3,
                "strategies_tried": ["recon", "nuclei"],
                "offensive_mode": True,
                "exploits_succeeded": 1,
                "waf_detected": "",
            }, f)

        with patch.dict(os.environ, {
            "DAENA_VAR": tmp,
            "SECURITY_REPORTS_DIR": tempfile.mkdtemp(),
        }):
            result = _load_scan_history()
            assert len(result) == 1
            assert result[0]["target"] == "example.com"
            assert result[0]["total_findings"] == 5

        shutil.rmtree(tmp)

    def test_self_improvement_metrics(self):
        """Self-improvement metrics calculate correctly."""
        from app.api.v1.security_dashboard import _get_self_improvement_metrics

        tmp = tempfile.mkdtemp()
        trace_dir = os.path.join(tmp, "scan_traces")
        os.makedirs(trace_dir)
        for i in range(15):
            with open(os.path.join(trace_dir, f"trace_{i}.json"), "w") as f:
                json.dump({"scan_id": f"t{i}"}, f)

        with patch.dict(os.environ, {"DAENA_VAR": tmp}):
            metrics = _get_self_improvement_metrics()
            assert metrics["total_traces"] == 15
            assert metrics["upgrades_triggered"] == 1
            assert metrics["next_upgrade_at"] == 20
            assert metrics["traces_until_next"] == 5

        shutil.rmtree(tmp)


# =========================================================================
# 5. TOOL CATALOG IN OODA LOOP (integration check)
# =========================================================================

class TestToolCatalogIntegration:
    """Test tool catalog can be used by the scan engine."""

    def test_catalog_importable_from_scan_engine(self):
        """Tool catalog is importable from the scan engine context."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        assert catalog.total_tools > 0

    def test_catalog_recommend_uses_target_profile(self):
        """Recommendations adapt to target type."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()

        web_tools = catalog.recommend_for_target("web_application")
        cloud_tools = catalog.recommend_for_target("cloud_service")

        web_names = {t.name for t in web_tools}
        cloud_names = {t.name for t in cloud_tools}

        # Web should have web-specific tools
        assert web_names & {"katana", "ffuf", "feroxbuster", "gobuster"}
        # Cloud should have cloud-specific tools
        assert cloud_names & {"cloudfox", "prowler", "scoutsuite"}

    def test_catalog_all_tools_have_required_fields(self):
        """Every tool has name, category, description, capabilities, install_cmd."""
        from app.services.security.tool_catalog import ToolCatalog
        catalog = ToolCatalog()
        for tool in catalog.get_all():
            assert tool.name, f"Tool missing name"
            assert tool.category, f"{tool.name} missing category"
            assert tool.description, f"{tool.name} missing description"
            assert tool.capabilities, f"{tool.name} missing capabilities"
            assert tool.install_cmd, f"{tool.name} missing install_cmd"
            assert tool.check_cmd, f"{tool.name} missing check_cmd"


# =========================================================================
# 6. ROUTER REGISTRATION
# =========================================================================

class TestRouterRegistration:
    """Test that security_dashboard router is registered."""

    def test_security_dashboard_in_api_init(self):
        """security_dashboard is imported in API v1 init."""
        from app.api.v1 import security_dashboard
        assert hasattr(security_dashboard, "router")

    def test_router_has_endpoints(self):
        """Router has the expected endpoints."""
        from app.api.v1.security_dashboard import router
        paths = [route.path for route in router.routes]
        assert "/status" in paths
        assert "/tools" in paths
        assert "/scans" in paths
        assert "/shields" in paths
