"""Tests for CognitiveScanEngine and security constraint decompositions.

Tests cover:
- Security constraint classification (scan_blocked, recon_empty, hardened_target)
- Security constraint decompositions (20+ channels per type)
- Target profiling and classification
- Strategy generation and ordering for different target types
- Failure diagnosis logic
- Proxy/Tor configuration
- VulnScannerAgent cognitive_scan dispatch
"""

import pytest

from app.services.cognition.constraint_probe import ConstraintProbe, Channel
from app.services.security.cognitive_scan_engine import (
    CognitiveScanEngine,
    TargetProfile,
    _passive_osint_strategy,
    _header_analysis_strategy,
    _path_discovery_strategy,
    _targeted_vuln_scan_strategy,
)


# ---- Security Constraint Classification ----

class TestSecurityConstraintClassification:
    """Test that security-specific constraints are classified correctly."""

    def test_classify_waf_blocked(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("WAF blocking requests", "") == "scan_blocked"

    def test_classify_403_forbidden(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("", "403 Forbidden") == "scan_blocked"

    def test_classify_rate_limited(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("rate limit hit", "") == "rate_limited"

    def test_classify_captcha(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("captcha required", "") == "scan_blocked"

    def test_classify_no_findings(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("no findings from scan", "") == "recon_empty"

    def test_classify_empty_results(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("", "0 findings returned") == "recon_empty"

    def test_classify_all_404(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("all 404 responses", "") == "recon_empty"

    def test_classify_hardened_google(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("scanning google target", "") == "hardened_target"

    def test_classify_cloudflare(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("cloudflare protected", "") == "hardened_target"

    def test_classify_aws(self) -> None:
        probe = ConstraintProbe()
        assert probe._classify_constraint("aws infrastructure", "") == "hardened_target"


# ---- Security Constraint Decompositions ----

class TestSecurityConstraintDecomposition:
    """Test that security constraint decompositions produce useful channels."""

    @pytest.mark.asyncio
    async def test_scan_blocked_has_creative_channels(self) -> None:
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Find vulns in target.com",
            constraint="WAF blocking all scan requests",
            error="403 Forbidden on every probe",
        )
        channel_names = [c.name for c in result.decomposed_channels]

        # Should have security-specific channels
        assert "user_agent_rotation" in channel_names
        assert "tor_proxy" in channel_names
        assert "certificate_transparency" in channel_names
        assert "response_header_analysis" in channel_names
        assert "cors_probe" in channel_names
        assert "path_fuzzing" in channel_names
        assert "javascript_analysis" in channel_names
        assert "api_endpoint_discovery" in channel_names

    @pytest.mark.asyncio
    async def test_scan_blocked_has_open_channels(self) -> None:
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Scan target.com",
            constraint="Scanner detected and blocked",
            error="Bot detection triggered",
        )
        # Standard scan is blocked, but many alternative channels should be open
        assert len(result.open_channels) > 5
        assert len(result.blocked_channels) >= 1  # Direct scan blocked

    @pytest.mark.asyncio
    async def test_recon_empty_suggests_osint(self) -> None:
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Find info about target.com",
            constraint="No findings from initial scan",
            error="0 findings returned",
        )
        channel_names = [c.name for c in result.decomposed_channels]

        assert "passive_osint" in channel_names
        assert "github_dork" in channel_names
        assert "google_dork" in channel_names
        assert "certificate_history" in channel_names
        assert "wayback_machine" in channel_names
        assert "cve_intelligence" in channel_names

    @pytest.mark.asyncio
    async def test_hardened_target_suggests_logic_flaws(self) -> None:
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Find vulns in hardened cloud target",
            constraint="Target is well-protected Google infrastructure",
            error="",
        )
        channel_names = [c.name for c in result.decomposed_channels]

        assert "business_logic" in channel_names
        assert "authentication_bypass" in channel_names
        assert "api_abuse" in channel_names
        assert "ssrf_probe" in channel_names
        assert "race_condition" in channel_names
        assert "graphql_introspection" in channel_names

    @pytest.mark.asyncio
    async def test_probe_recommends_best_path(self) -> None:
        probe = ConstraintProbe()
        result = await probe.probe(
            task="Scan blocked by WAF",
            constraint="firewall blocking scanner",
            error="403",
        )
        assert result.recommended_path is not None
        # Should recommend an alternative/indirect path, not the direct blocked one
        assert result.recommended_path.category in ("alternative", "indirect", "workaround")


# ---- Target Classification ----

class TestTargetClassification:
    """Test target profiling and classification."""

    def test_classify_google_as_hardened(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="cloud.google.com")
        assert engine._classify_target(profile) == "hardened_cloud"

    def test_classify_aws_as_hardened(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="console.aws.amazon.com")
        assert engine._classify_target(profile) == "hardened_cloud"

    def test_classify_microsoft_as_hardened(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="portal.azure.com")
        # azure.com should match
        assert engine._classify_target(profile) == "hardened_cloud"

    def test_classify_waf_protected(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="example.com", waf_detected="cloudflare")
        assert engine._classify_target(profile) == "waf_protected"

    def test_classify_modern(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="startup.io", http_version="HTTP/3")
        assert engine._classify_target(profile) == "modern_infrastructure"

    def test_classify_large_surface(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="big.corp", subdomains=["a"] * 51)
        assert engine._classify_target(profile) == "large_surface"

    def test_classify_unknown(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(domain="mystery.local")
        assert engine._classify_target(profile) == "unknown"


# ---- Strategy Generation ----

class TestStrategyGeneration:
    """Test strategy generation and ordering."""

    @pytest.mark.asyncio
    async def test_hardened_target_orders_passive_first(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(
            domain="cloud.google.com",
            subdomains=["a.cloud.google.com"],
            live_hosts=[{"url": "https://a.cloud.google.com"}],
            target_type="hardened_cloud",
        )
        strategies = await engine._generate_strategies("cloud.google.com", profile, [])
        names = [s.name for s in strategies]

        # Passive should come first for hardened targets
        assert names[0] == "passive_osint"
        # Standard vuln scan should be LAST
        assert names[-1] == "targeted_vuln_scan"

    @pytest.mark.asyncio
    async def test_standard_target_has_all_strategies(self) -> None:
        engine = CognitiveScanEngine()
        profile = TargetProfile(
            domain="example.com",
            subdomains=["www.example.com"],
            live_hosts=[{"url": "https://www.example.com"}],
            target_type="standard",
        )
        strategies = await engine._generate_strategies("example.com", profile, [])
        names = [s.name for s in strategies]

        assert "passive_osint" in names
        assert "header_analysis" in names
        assert "path_discovery" in names
        assert "targeted_vuln_scan" in names

    def test_passive_strategy_is_zero_contact(self) -> None:
        strategy = _passive_osint_strategy("example.com")
        assert strategy.stealth_level == "passive"
        assert strategy.confidence >= 0.7


# ---- Failure Diagnosis ----

class TestFailureDiagnosis:
    """Test failure diagnosis logic."""

    def test_diagnose_waf(self) -> None:
        from app.services.security.cognitive_scan_engine import ScanStrategy, ScanCycleResult
        engine = CognitiveScanEngine()
        strategy = ScanStrategy(name="test", description="", steps=[])
        cycle = ScanCycleResult(cycle=1, strategy_name="test", raw_results=[
            {"output": {"results": [{"status_code": 403}, {"status_code": 403}]}}
        ])
        profile = TargetProfile(domain="target.com", waf_detected="cloudflare")

        diagnosis = engine._diagnose_failure(strategy, cycle, profile)
        assert "WAF" in diagnosis or "cloudflare" in diagnosis

    def test_diagnose_all_404(self) -> None:
        from app.services.security.cognitive_scan_engine import ScanStrategy, ScanCycleResult
        engine = CognitiveScanEngine()
        strategy = ScanStrategy(name="test", description="", steps=[])
        cycle = ScanCycleResult(cycle=1, strategy_name="test", raw_results=[
            {"output": {"results": [{"status_code": 404}, {"status_code": 404}]}}
        ])
        profile = TargetProfile(domain="target.com")

        diagnosis = engine._diagnose_failure(strategy, cycle, profile)
        assert "404" in diagnosis

    def test_diagnose_rate_limit(self) -> None:
        from app.services.security.cognitive_scan_engine import ScanStrategy, ScanCycleResult
        engine = CognitiveScanEngine()
        strategy = ScanStrategy(name="test", description="", steps=[])
        cycle = ScanCycleResult(cycle=1, strategy_name="test", raw_results=[
            {"output": {"results": [{"status_code": 429}]}}
        ])
        profile = TargetProfile(domain="target.com")

        diagnosis = engine._diagnose_failure(strategy, cycle, profile)
        assert "429" in diagnosis or "Rate limiting" in diagnosis


# ---- Probe-failure visibility (Rule 17 / ADR-001: "all crashed" != "found nothing") ----

class TestProbeFailureVisibility:
    """Lock the P4 item 5-9 fix: a swept probe that CRASHES must not be reported
    as a clean "0 found". The crashed-probe count must surface in the summary as
    INCONCLUSIVE; a genuinely empty (all-404) sweep must NOT carry that caveat.

    _path_fuzz is the representative site -- the other four (_forgotten_infra_scan,
    _canary_echo, _cost_amplification) share the identical loop shape and counter.
    """

    @pytest.mark.asyncio
    async def test_path_fuzz_all_probes_crash_is_inconclusive(self, monkeypatch) -> None:
        """Every per-path probe raises -> summary must flag INCONCLUSIVE, not "0 found"."""
        class _BoomClient:
            def __init__(self, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc) -> bool:
                return False

            async def get(self, url, headers=None):
                raise RuntimeError("connection reset by peer")

        monkeypatch.setattr("httpx.AsyncClient", _BoomClient)

        engine = CognitiveScanEngine()
        result = await engine._path_fuzz("https://target.example", agent=None)

        assert result["findings"] == []
        # The fix: a crashed sweep is honestly flagged, never silently "clean".
        assert "INCONCLUSIVE" in result["summary"]
        assert "probes errored" in result["summary"]

    @pytest.mark.asyncio
    async def test_path_fuzz_clean_empty_is_not_inconclusive(self, monkeypatch) -> None:
        """All probes return 404 (genuinely nothing) -> no INCONCLUSIVE caveat."""
        class _NotFoundResponse:
            status_code = 404
            content = b""

        class _NotFoundClient:
            def __init__(self, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc) -> bool:
                return False

            async def get(self, url, headers=None):
                return _NotFoundResponse()

        monkeypatch.setattr("httpx.AsyncClient", _NotFoundClient)

        engine = CognitiveScanEngine()
        result = await engine._path_fuzz("https://target.example", agent=None)

        assert result["findings"] == []
        # No probe crashed, so the honest summary stays caveat-free.
        assert "INCONCLUSIVE" not in result["summary"]
        assert "0 accessible paths found" in result["summary"]


# ---- Proxy / Tor ----

class TestProxyConfiguration:
    """Test proxy and Tor configuration."""

    def test_proxy_args_subfinder(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        args = VulnScannerAgent._proxy_args_for_tool("subfinder", "socks5://127.0.0.1:9050")
        assert args == ["-proxy", "socks5://127.0.0.1:9050"]

    def test_proxy_args_httpx(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        args = VulnScannerAgent._proxy_args_for_tool("httpx", "socks5://127.0.0.1:9050")
        assert args == ["-proxy", "socks5://127.0.0.1:9050"]

    def test_proxy_args_nuclei(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        args = VulnScannerAgent._proxy_args_for_tool("nuclei", "http://proxy:8080")
        assert args == ["-proxy", "http://proxy:8080"]

    def test_proxy_args_nmap(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        args = VulnScannerAgent._proxy_args_for_tool("nmap", "socks5://127.0.0.1:9050")
        assert args == ["--proxies", "socks5://127.0.0.1:9050"]

    def test_no_proxy_returns_empty(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        args = VulnScannerAgent._proxy_args_for_tool("subfinder", "")
        assert args == []


# ---- Agent Dispatch ----

class TestCognitiveScanDispatch:
    """Test VulnScannerAgent registers cognitive_scan operation."""

    def test_cognitive_scan_registered(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        agent = VulnScannerAgent()
        assert "cognitive_scan" in agent.OPERATION_ACTION_MAP
        assert agent.OPERATION_ACTION_MAP["cognitive_scan"] == "EXECUTE"

    def test_cognitive_scan_timeout(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        agent = VulnScannerAgent()
        assert agent._TIMEOUTS["cognitive_scan"] == 900  # 15 minutes
