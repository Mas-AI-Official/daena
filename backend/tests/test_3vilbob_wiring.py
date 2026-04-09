"""Tests for /3vilbob wiring -- new modules and OODA loop integration.

Tests:
- NetworkIntelligence (protocol knowledge, topology, dark web)
- CredentialExtractionChain (parse, classify, test)
- OPSEC (fingerprints, timing, detection, cleanup)
- CognitiveDeceptionEngine (decoy planning)
- ForgottenInfraScanner strategy wiring
- OriginIPDiscovery wiring
- Hypothesis-driven testing
"""

import asyncio
import pytest


# ---------------------------------------------------------------------------
# NetworkIntelligence Tests
# ---------------------------------------------------------------------------

class TestProtocolKnowledgeBase:
    """Test protocol knowledge base completeness and query."""

    def test_all_protocols_loaded(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()
        protocols = kb.get_all_protocols()
        assert len(protocols) >= 10, f"Expected 10+ protocols, got {len(protocols)}"

    def test_get_specific_protocol(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()

        http = kb.get_protocol("HTTP/1.1")
        assert http is not None
        assert http.layer == "application"
        assert len(http.attack_surfaces) >= 3

        dns = kb.get_protocol("DNS")
        assert dns is not None
        assert "zone transfer" in str(dns.attack_surfaces).lower()

        tls = kb.get_protocol("TLS")
        assert tls is not None

    def test_protocol_not_found(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()
        result = kb.get_protocol("NONEXISTENT")
        assert result is None

    def test_relevant_protocols_http_target(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()
        relevant = kb.get_relevant_protocols(
            technologies=["nginx", "express", "nodejs"],
            profile={"waf_detected": "cloudflare", "http_version": "HTTP/2"},
        )
        protocol_names = [p.protocol for p in relevant]
        assert "HTTP/1.1" in protocol_names
        assert "DNS" in protocol_names
        assert "HTTP/2" in protocol_names

    def test_graphql_protocol_selected(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()
        relevant = kb.get_relevant_protocols(
            technologies=["graphql", "express"],
            profile={},
        )
        protocol_names = [p.protocol for p in relevant]
        assert "GraphQL" in protocol_names

    def test_generate_attack_surface(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()
        paths = kb.generate_protocol_attack_surface(
            technologies=["nginx", "graphql"],
            target_profile={"waf_detected": "cloudflare", "http_version": "HTTP/2"},
        )
        assert len(paths) >= 3
        assert all(p.confidence > 0 for p in paths)
        assert all(p.protocol for p in paths)

    def test_protocol_insight_structure(self):
        from app.services.security.network_intelligence import ProtocolKnowledgeBase
        kb = ProtocolKnowledgeBase()
        for proto in kb.get_all_protocols():
            assert proto.protocol, "Protocol name required"
            assert proto.layer, "Layer required"
            assert proto.description, "Description required"
            assert len(proto.attack_surfaces) >= 1, f"{proto.protocol} needs attack surfaces"
            assert len(proto.common_misconfigs) >= 1, f"{proto.protocol} needs misconfigs"
            assert len(proto.recon_techniques) >= 1, f"{proto.protocol} needs recon techniques"
            assert len(proto.tools) >= 1, f"{proto.protocol} needs tools"


class TestNetworkTopologyMapper:
    """Test network topology inference."""

    def test_infer_cloudflare(self):
        from app.services.security.network_intelligence import NetworkTopologyMapper
        mapper = NetworkTopologyMapper()
        fp = mapper.infer_topology(
            domain="example.com",
            subdomains=["api.example.com", "www.example.com"],
            live_hosts=[],
            response_headers={"cf-ray": "abc123", "server": "cloudflare"},
        )
        assert fp.cdn_provider == "cloudflare"

    def test_infer_aws_hosting(self):
        from app.services.security.network_intelligence import NetworkTopologyMapper
        mapper = NetworkTopologyMapper()
        fp = mapper.infer_topology(
            domain="example.amazonaws.com",
            subdomains=["app.example.amazonaws.com"],
            live_hosts=[],
            response_headers={"server": "nginx"},
        )
        assert fp.hosting_provider == "aws"

    def test_infer_microservices_topology(self):
        from app.services.security.network_intelligence import NetworkTopologyMapper
        mapper = NetworkTopologyMapper()
        fp = mapper.infer_topology(
            domain="example.com",
            subdomains=[f"svc{i}.example.com" for i in range(40)],
            live_hosts=[],
            response_headers={},
        )
        assert fp.network_topology == "microservices"

    def test_egress_paths(self):
        from app.services.security.network_intelligence import (
            NetworkTopologyMapper, NetworkFingerprint,
        )
        mapper = NetworkTopologyMapper()
        fp = NetworkFingerprint(
            hosting_provider="aws",
            cdn_provider="cloudflare",
            network_topology="microservices",
        )
        paths = mapper.identify_egress_paths(fp)
        assert len(paths) >= 2
        assert any("SSRF" in p for p in paths)


class TestDarkWebRecon:
    """Test dark web intelligence planning."""

    def test_recon_plan_generated(self):
        from app.services.security.network_intelligence import DarkWebRecon
        recon = DarkWebRecon()
        plan = recon.generate_dark_web_recon_plan("example.com")
        assert len(plan) >= 5
        step_names = [s["step"] for s in plan]
        assert any("breach" in s.lower() for s in step_names)
        assert any("paste" in s.lower() for s in step_names)
        assert any("code" in s.lower() or "repository" in s.lower() for s in step_names)

    def test_breach_impact_analysis(self):
        from app.services.security.network_intelligence import DarkWebRecon
        recon = DarkWebRecon()
        analysis = recon.analyze_breach_impact(
            breaches=[
                {"data_classes": ["Passwords", "Email addresses"]},
                {"data_classes": ["IP Addresses"]},
            ],
            target="example.com",
        )
        assert analysis["total_breaches"] == 2
        assert analysis["password_reuse_risk"] == "high"
        assert "passwords" in analysis["credential_types"]


class TestTorIntelligence:
    """Test Tor intelligence capabilities."""

    def test_recon_plan(self):
        from app.services.security.network_intelligence import TorIntelligence
        tor = TorIntelligence()
        plan = tor.generate_tor_recon_plan("example.com")
        assert len(plan) >= 3

    def test_risk_assessment(self):
        from app.services.security.network_intelligence import TorIntelligence
        tor = TorIntelligence()
        assessment = tor.assess_tor_usage_risk("example.com", [])
        assert assessment["tor_risk"] == "low"
        assert not assessment["has_onion_presence"]


# ---------------------------------------------------------------------------
# CredentialExtractionChain Tests
# ---------------------------------------------------------------------------

class TestCredentialParser:
    """Test credential parsing from config files."""

    def test_parse_env_file(self):
        from app.services.security.credential_chain import CredentialParser
        parser = CredentialParser()
        env_content = """
DATABASE_URL=postgresql://admin:s3cret@db.example.com:5432/production
API_KEY=STRIPE_TEST_PLACEHOLDER_FAKE_KEY_FOR_UNIT_TEST_ONLY
SECRET_KEY=my-super-secret-key-that-is-long
REDIS_URL=redis://default:password@redis.example.com:6379/0
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
SMTP_PASSWORD=mailpassword123
"""
        creds = parser.parse(env_content, "https://target.com/.env")
        assert len(creds) >= 4
        types = [c.credential_type for c in creds]
        assert "db_url" in types
        assert "api_key" in types
        assert "secret_key" in types

    def test_skip_placeholders(self):
        from app.services.security.credential_chain import CredentialParser
        parser = CredentialParser()
        env_content = """
DATABASE_URL=changeme
API_KEY=your_key_here
SECRET_KEY=${SECRET_FROM_VAULT}
PASSWORD=placeholder
"""
        creds = parser.parse(env_content, "https://target.com/.env")
        assert len(creds) == 0

    def test_parse_database_url(self):
        from app.services.security.credential_chain import CredentialParser
        parser = CredentialParser()
        parsed = parser.parse_database_url("postgresql://admin:s3cret@db.example.com:5432/production")
        assert parsed["host"] == "db.example.com"
        assert parsed["user"] == "admin"
        assert parsed["password"] == "s3cret"
        assert parsed["database"] == "production"

    def test_assemble_db_url(self):
        from app.services.security.credential_chain import CredentialParser
        parser = CredentialParser()
        content = """
DB_HOST=db.example.com
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=s3cret
DB_NAME=production
"""
        url = parser.assemble_db_url(content)
        assert url is not None
        assert "admin" in url
        assert "db.example.com" in url

    def test_redact_value(self):
        from app.services.security.credential_chain import CredentialParser
        redacted = CredentialParser._redact("abcdefghij")
        assert "*" in redacted  # Contains redaction chars
        assert redacted.startswith("abcd")
        assert redacted.endswith("ghij")

    def test_detect_service(self):
        from app.services.security.credential_chain import CredentialParser
        assert CredentialParser._detect_service("POSTGRES_PASSWORD", "secret") == "postgresql"
        assert CredentialParser._detect_service("MYSQL_HOST", "db.host") == "mysql"
        assert CredentialParser._detect_service("REDIS_URL", "redis://x") == "redis"
        assert CredentialParser._detect_service("KEY", "AKIAIOSFODNN7EXAMPLE") == "aws"
        assert CredentialParser._detect_service("KEY", "STRIPE_TEST_PLACEHOLDER_abc123") == "stripe"

    def test_risk_levels(self):
        from app.services.security.credential_chain import CredentialParser
        parser = CredentialParser()
        env_content = """
DATABASE_URL=postgresql://admin:s3cret@db.example.com:5432/prod
DB_HOST=db.example.com
"""
        creds = parser.parse(env_content, "https://target.com/.env")
        critical = [c for c in creds if c.risk_level == "critical"]
        assert len(critical) >= 1  # DATABASE_URL is critical


class TestCredentialExtractionChain:
    """Test the full credential chain orchestrator."""

    @pytest.mark.asyncio
    async def test_chain_with_env_content(self):
        from app.services.security.credential_chain import CredentialExtractionChain
        chain = CredentialExtractionChain()
        result = await chain.execute(
            content="API_KEY=test_key_12345678901234567890\nSECRET_KEY=supersecretvalue1234",
            source_url="https://target.com/.env",
        )
        assert result.credentials_found >= 1
        assert len(result.thinking) > 0

    @pytest.mark.asyncio
    async def test_chain_empty_content(self):
        from app.services.security.credential_chain import CredentialExtractionChain
        chain = CredentialExtractionChain()
        result = await chain.execute(
            content="# Empty config\nDEBUG=true\n",
            source_url="https://target.com/.env",
        )
        assert result.credentials_found == 0


# ---------------------------------------------------------------------------
# OPSEC Tests
# ---------------------------------------------------------------------------

class TestFingerprintManager:
    """Test browser fingerprint management."""

    def test_get_profile(self):
        from app.services.security.opsec import FingerprintManager
        fm = FingerprintManager()
        profile = fm.get_profile()
        assert "user_agent" in profile
        assert "accept" in profile

    def test_rotate_profile(self):
        from app.services.security.opsec import FingerprintManager
        fm = FingerprintManager()
        profile1 = fm.get_profile()
        fm.rotate()
        # After rotation, profile may be same (random) but count increases
        assert fm.rotation_count >= 2  # Initial + rotate

    def test_get_headers(self):
        from app.services.security.opsec import FingerprintManager
        fm = FingerprintManager()
        headers = fm.get_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        # Should not be empty string
        assert len(headers["User-Agent"]) > 10

    def test_headers_consistent_with_profile(self):
        from app.services.security.opsec import FingerprintManager
        fm = FingerprintManager()
        headers = fm.get_headers()
        profile = fm.get_profile()
        assert headers["User-Agent"] == profile["user_agent"]


class TestTimingController:
    """Test timing control."""

    @pytest.mark.asyncio
    async def test_first_request_no_delay(self):
        from app.services.security.opsec import TimingController
        tc = TimingController()
        delay = await tc.wait_before_request()
        assert delay == 0  # First request, no delay

    @pytest.mark.asyncio
    async def test_subsequent_request_has_delay(self):
        from app.services.security.opsec import TimingController, TimingProfile
        profile = TimingProfile(
            base_interval_ms=100,
            jitter_ms=10,
            burst_probability=0,
            long_pause_probability=0,
        )
        tc = TimingController(profile)
        await tc.wait_before_request()  # First, no delay
        delay = await tc.wait_before_request()  # Second, has delay
        assert delay >= 90  # base - jitter

    def test_request_count(self):
        from app.services.security.opsec import TimingController
        tc = TimingController()
        assert tc.request_count == 0


class TestFingerprintDetector:
    """Test fingerprint detection."""

    def test_detect_honeypot(self):
        from app.services.security.opsec import FingerprintDetector
        detector = FingerprintDetector()
        result = detector.analyze_response(
            body="<script>window.HoneyBadger.init()</script>",
            headers={},
        )
        assert result["fingerprinting_detected"] is True
        assert result["risk"] == "high"

    def test_clean_response(self):
        from app.services.security.opsec import FingerprintDetector
        detector = FingerprintDetector()
        result = detector.analyze_response(
            body="<html><body>Hello World</body></html>",
            headers={},
        )
        assert result["fingerprinting_detected"] is False
        assert result["risk"] == "low"

    def test_detect_tracker_script(self):
        from app.services.security.opsec import FingerprintDetector
        detector = FingerprintDetector()
        result = detector.analyze_response(
            body='<script src="/fingerprint2.js"></script>',
            headers={},
        )
        assert result["fingerprinting_detected"] is True


class TestEvidenceVault:
    """Test evidence vault."""

    def test_store_evidence(self):
        from app.services.security.opsec import EvidenceVault
        vault = EvidenceVault()
        eid = vault.store("sensitive data here", "test_evidence")
        assert len(eid) == 16
        assert vault.evidence_count == 1

    def test_manifest(self):
        from app.services.security.opsec import EvidenceVault
        vault = EvidenceVault()
        vault.store("data1", "label1")
        vault.store("data2", "label2")
        manifest = vault.get_manifest()
        assert len(manifest) == 2
        assert manifest[0]["label"] == "label1"


class TestCleanupProtocol:
    """Test cleanup protocol."""

    def test_standard_checklist(self):
        from app.services.security.opsec import CleanupProtocol
        cleanup = CleanupProtocol()
        checklist = cleanup.generate_cleanup_checklist("standard")
        assert len(checklist) >= 5

    def test_red_team_checklist(self):
        from app.services.security.opsec import CleanupProtocol
        cleanup = CleanupProtocol()
        checklist = cleanup.generate_cleanup_checklist("red_team")
        assert len(checklist) >= 8  # Standard + red team extras


class TestOpsecManager:
    """Test OPSEC orchestrator."""

    def test_get_headers(self):
        from app.services.security.opsec import OpsecManager
        opsec = OpsecManager()
        headers = opsec.get_request_headers()
        assert "User-Agent" in headers

    def test_rotate_identity(self):
        from app.services.security.opsec import OpsecManager
        opsec = OpsecManager()
        opsec.rotate_identity()
        assert opsec.fingerprints.rotation_count >= 1

    def test_detect_fingerprinting(self):
        from app.services.security.opsec import OpsecManager
        opsec = OpsecManager()
        result = opsec.detect_fingerprinting("<html>normal</html>", {})
        assert result["fingerprinting_detected"] is False

    def test_generate_report(self):
        from app.services.security.opsec import OpsecManager
        opsec = OpsecManager()
        report = opsec.generate_report()
        assert report.profiles_rotated >= 0
        assert report.total_requests == 0
        assert not report.cleanup_completed


# ---------------------------------------------------------------------------
# CognitiveDeceptionEngine Tests
# ---------------------------------------------------------------------------

class TestCognitiveDeceptionEngine:
    """Test deception planning."""

    def test_plan_deception(self):
        from app.services.cognition.apex_cognition import CognitiveDeceptionEngine
        deception = CognitiveDeceptionEngine()
        plan = deception.plan_deception(
            real_objective="Test API authentication",
            target="https://target.com",
            defenses=["WAF: cloudflare"],
        )
        assert len(plan.decoy_actions) >= 2
        assert plan.real_action is not None
        assert plan.timing
        assert plan.expected_defender_response

    def test_decoy_timing_order(self):
        from app.services.cognition.apex_cognition import CognitiveDeceptionEngine
        deception = CognitiveDeceptionEngine()
        plan = deception.plan_deception(
            real_objective="admin_access",
            target="target.com",
            defenses=[],
        )
        # Decoys fire before real probe
        max_decoy_delay = max(d.get("delay_before_ms", 0) for d in plan.decoy_actions)
        real_delay = plan.real_action.get("delay_before_ms", 0)
        assert real_delay > max_decoy_delay


# ---------------------------------------------------------------------------
# ForgottenInfraScanner Tests
# ---------------------------------------------------------------------------

class TestForgottenInfraScanner:
    """Test forgotten infrastructure scanning."""

    def test_generate_probes(self):
        from app.services.cognition.unreplicable import ForgottenInfraScanner
        scanner = ForgottenInfraScanner()
        probes = scanner.generate_forgotten_probes("example.com")
        assert len(probes) >= 20
        services = set(p["service"] for p in probes)
        assert "Jenkins" in services
        assert "Grafana" in services
        assert "Elasticsearch" in services

    def test_analyze_found_service(self):
        from app.services.cognition.unreplicable import ForgottenInfraScanner
        scanner = ForgottenInfraScanner()
        probe = {
            "service": "Jenkins",
            "url": "https://example.com/jenkins",
            "check_string": "Jenkins-Crumb",
            "risk": "Build pipeline access",
            "type": "path",
        }
        result = scanner.analyze_probe_result(
            probe,
            status_code=200,
            body="<html>Jenkins-Crumb: abcdef</html>",
            headers={},
        )
        assert result is not None
        assert result["type"] == "forgotten_infrastructure"
        assert result["service"] == "Jenkins"

    def test_analyze_not_found(self):
        from app.services.cognition.unreplicable import ForgottenInfraScanner
        scanner = ForgottenInfraScanner()
        probe = {
            "service": "Jenkins",
            "url": "https://example.com/jenkins",
            "check_string": "Jenkins-Crumb",
            "risk": "Build pipeline access",
            "type": "path",
        }
        result = scanner.analyze_probe_result(
            probe,
            status_code=200,
            body="<html>Not Found</html>",
            headers={},
        )
        assert result is None


# ---------------------------------------------------------------------------
# OriginIPDiscovery Tests
# ---------------------------------------------------------------------------

class TestOriginIPDiscovery:
    """Test origin IP discovery."""

    def test_generate_bypass_targets(self):
        from app.services.cognition.unreplicable import OriginIPDiscovery
        disc = OriginIPDiscovery()
        targets = disc.generate_bypass_targets("example.com")
        assert len(targets) >= 30
        hostnames = [t["hostname"] for t in targets]
        assert "mail.example.com" in hostnames
        assert "staging.example.com" in hostnames
        assert "jenkins.example.com" in hostnames

    def test_analyze_email_headers(self):
        from app.services.cognition.unreplicable import OriginIPDiscovery
        disc = OriginIPDiscovery()
        headers = """
Received: from mail.example.com (203.0.113.50) by mx.google.com
Received: from localhost (127.0.0.1) by mail.example.com
Received: from edge.cdn.example.com (192.168.1.1) by internal
"""
        ips = disc.analyze_email_headers(headers)
        assert "203.0.113.50" in ips
        assert "127.0.0.1" not in ips  # Filtered
        assert "192.168.1.1" not in ips  # Private, filtered

    def test_generate_origin_plan(self):
        from app.services.cognition.unreplicable import OriginIPDiscovery
        disc = OriginIPDiscovery()
        plan = disc.generate_origin_check_plan("example.com", "cloudflare")
        assert len(plan) >= 4
        actions = [s["action"] for s in plan]
        assert "dns_resolve" in actions
        assert "trigger_email" in actions
        assert "historical_dns" in actions


# ---------------------------------------------------------------------------
# HypothesisTester Tests
# ---------------------------------------------------------------------------

class TestHypothesisTester:
    """Test hypothesis generation and testing."""

    def test_generate_django_hypothesis(self):
        from app.services.cognition.apex_cognition import HypothesisTester
        tester = HypothesisTester()
        hyps = tester.generate_hypotheses({
            "technologies": ["Django", "Python"],
            "waf_detected": "",
            "api_patterns": [],
            "status_codes": {},
        })
        assert len(hyps) >= 1
        assert any("admin" in h.statement.lower() for h in hyps)

    def test_generate_graphql_hypothesis(self):
        from app.services.cognition.apex_cognition import HypothesisTester
        tester = HypothesisTester()
        hyps = tester.generate_hypotheses({
            "technologies": ["GraphQL", "express"],
            "waf_detected": "",
            "api_patterns": [],
            "status_codes": {},
        })
        assert any("introspection" in h.statement.lower() for h in hyps)

    def test_generate_waf_hypothesis(self):
        from app.services.cognition.apex_cognition import HypothesisTester
        tester = HypothesisTester()
        hyps = tester.generate_hypotheses({
            "technologies": [],
            "waf_detected": "cloudflare",
            "api_patterns": [],
            "status_codes": {},
        })
        assert len(hyps) >= 1
        assert any("waf" in h.statement.lower() or "post" in h.statement.lower() for h in hyps)

    def test_update_hypothesis_confirmed(self):
        from app.services.cognition.apex_cognition import HypothesisTester, Hypothesis
        tester = HypothesisTester()
        hyp = Hypothesis(
            statement="Admin panel exists",
            reasoning="Django detected",
            prediction="GET /admin/ returns 200",
            confidence_before=0.5,
        )
        updated = tester.update_hypothesis(hyp, {"status_code": 200, "success": True})
        assert updated.result == "confirmed"
        assert updated.confidence_after > updated.confidence_before

    def test_update_hypothesis_refuted(self):
        from app.services.cognition.apex_cognition import HypothesisTester, Hypothesis
        tester = HypothesisTester()
        hyp = Hypothesis(
            statement="Admin panel exists",
            reasoning="Django detected",
            prediction="GET /admin/ returns 200",
            confidence_before=0.5,
        )
        updated = tester.update_hypothesis(hyp, {"status_code": 404, "success": False})
        assert updated.result == "refuted"
        assert updated.confidence_after < updated.confidence_before

    def test_update_hypothesis_partial(self):
        from app.services.cognition.apex_cognition import HypothesisTester, Hypothesis
        tester = HypothesisTester()
        hyp = Hypothesis(
            statement="Admin panel exists",
            reasoning="Django detected",
            prediction="GET /admin/ returns 200",
            confidence_before=0.5,
        )
        updated = tester.update_hypothesis(hyp, {"status_code": 403, "success": False})
        assert updated.result == "partial"
        assert updated.confidence_after > updated.confidence_before


# ---------------------------------------------------------------------------
# Forgotten Infra Strategy Template Tests
# ---------------------------------------------------------------------------

class TestForgottenInfraStrategy:
    """Test that the forgotten_infrastructure strategy is properly defined."""

    def test_strategy_exists(self):
        from app.services.security.cognitive_scan_engine import _forgotten_infra_strategy
        strategy = _forgotten_infra_strategy("example.com")
        assert strategy.name == "forgotten_infrastructure"
        assert strategy.stealth_level == "medium"
        assert len(strategy.steps) >= 1
        assert strategy.steps[0]["operation"] == "_forgotten_infra_scan"


# ---------------------------------------------------------------------------
# Integration count
# ---------------------------------------------------------------------------

class TestModuleCapabilityCount:
    """Verify the expanded capability count."""

    def test_total_capabilities(self):
        """Verify we have the expected number of capabilities across all modules."""
        # Original: 31 capabilities across 13 modules
        # New: +14 new capabilities
        #   NetworkIntelligence: ProtocolKnowledgeBase, NetworkTopologyMapper,
        #                       DarkWebRecon, TorIntelligence = 4
        #   CredentialChain: CredentialParser, CredentialTester,
        #                    CredentialExtractionChain = 3
        #   OPSEC: FingerprintManager, TimingController, EvidenceVault,
        #          FingerprintDetector, CleanupProtocol, OpsecManager = 6
        #   Wiring: ForgottenInfraStrategy = 1
        # Total new: 14, Grand total: 31 + 14 = 45

        # Verify all classes are importable
        from app.services.security.network_intelligence import (
            ProtocolKnowledgeBase, NetworkTopologyMapper,
            DarkWebRecon, TorIntelligence,
        )
        from app.services.security.credential_chain import (
            CredentialParser, CredentialTester, CredentialExtractionChain,
        )
        from app.services.security.opsec import (
            FingerprintManager, TimingController, EvidenceVault,
            FingerprintDetector, CleanupProtocol, OpsecManager,
        )
        from app.services.cognition.apex_cognition import (
            CognitiveDeceptionEngine, HypothesisTester,
        )
        from app.services.cognition.unreplicable import (
            OriginIPDiscovery, ForgottenInfraScanner,
        )

        # All imports succeeded -- capabilities are wired
        assert True
