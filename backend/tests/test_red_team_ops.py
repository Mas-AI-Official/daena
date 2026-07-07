"""Tests for Red Team Operations -- full operator capabilities."""

import os
import shutil
import tempfile

import pytest

from app.services.security.red_team_ops import (
    LiveTargetMonitor,
    TargetChange,
    SocialEngineeringCrafter,
    PhishingScenario,
    ExfiltrationProver,
    ExfilChannel,
    ImplantSimulator,
    PersistencePlan,
    RedTeamReportGenerator,
)


# =============================================================================
# Live Target Monitor
# =============================================================================

class TestLiveTargetMonitor:

    def test_init(self):
        monitor = LiveTargetMonitor("example.com")
        assert monitor.target == "example.com"

    def test_empty_history(self):
        monitor = LiveTargetMonitor("example.com")
        assert monitor.get_history() == []

    def test_target_change_dataclass(self):
        change = TargetChange(
            change_type="new_endpoint",
            description="New /api/v3 discovered",
            severity="high",
            detected_at=1000.0,
        )
        assert change.change_type == "new_endpoint"
        assert change.severity == "high"

    def test_persist_and_load_baseline(self):
        d = tempfile.mkdtemp(prefix="monitor_test_")
        try:
            monitor = LiveTargetMonitor("example.com")
            monitor._storage_dir = d
            monitor._baseline = {
                "target": "example.com",
                "headers": {"https://example.com": {"server": "nginx"}},
                "endpoints": [{"path": "/api", "status": 200}],
            }
            monitor._persist_baseline()

            # Load in new instance
            monitor2 = LiveTargetMonitor("example.com")
            monitor2._storage_dir = d
            monitor2._load_baseline()
            assert monitor2._baseline["target"] == "example.com"
            assert len(monitor2._baseline["endpoints"]) == 1
        finally:
            shutil.rmtree(d, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_check_for_changes_logs_probe_failures(self, monkeypatch, capsys):
        """Rule-17: a failed probe must be logged, never silently swallowed.

        Forces every network probe inside check_for_changes to raise so the
        header-check, endpoint-discovery, and DNS-change-detection except
        branches all fire. Each must emit a structured warning instead of the
        previous ``except: pass`` (masked-observability / empty-as-clean).

        Daena routes structlog to stdout, so we assert on capsys (matching
        test_cli_runtime_probe.py), not caplog.
        """
        import httpx
        import socket as _socket

        class _RaisingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, *args, **kwargs):
                raise OSError("probe blocked")

        def _dns_boom(*args, **kwargs):
            raise OSError("dns blocked")

        monkeypatch.setattr(httpx, "AsyncClient", _RaisingClient)
        monkeypatch.setattr(_socket, "getaddrinfo", _dns_boom)

        monitor = LiveTargetMonitor("example.com")
        monitor._baseline = {
            "target": "example.com",
            "headers": {"https://example.com": {"server": "nginx"}},
            "endpoints": [{"path": "/", "status": 200}],
            "response_hashes": {},
            "dns_records": {"a": ["1.2.3.4"]},
        }

        changes = await monitor.check_for_changes()

        # Failed probes must NOT be invented as detected changes.
        assert changes == []

        captured = capsys.readouterr()
        logged = captured.out + captured.err
        assert "target_monitor.header_check_failed" in logged
        assert "target_monitor.endpoint_probe_failed" in logged
        assert "target_monitor.dns_change_detection_failed" in logged


# =============================================================================
# Social Engineering Crafter
# =============================================================================

class TestSocialEngineeringCrafter:

    def test_craft_for_engineer(self):
        crafter = SocialEngineeringCrafter()
        scenarios = crafter.craft_scenarios(
            target_person="John Smith",
            target_role="Senior Software Engineer",
            target_company="TechCorp",
        )
        assert len(scenarios) >= 1
        for s in scenarios:
            assert isinstance(s, PhishingScenario)
            assert s.target_person == "John Smith"
            assert s.message_draft  # Not empty

    def test_craft_for_cfo(self):
        crafter = SocialEngineeringCrafter()
        scenarios = crafter.craft_scenarios(
            target_person="Jane Doe",
            target_role="CFO",
            target_company="FinCorp",
        )
        assert len(scenarios) >= 1
        # Executive scenarios should be high risk
        assert any(s.risk_level == "high" for s in scenarios)

    def test_craft_for_hr(self):
        crafter = SocialEngineeringCrafter()
        scenarios = crafter.craft_scenarios(
            target_person="Alice",
            target_role="HR Director",
            target_company="BigCo",
        )
        assert len(scenarios) >= 1

    def test_craft_with_osint_data(self):
        crafter = SocialEngineeringCrafter()
        scenarios = crafter.craft_scenarios(
            target_person="Bob Dev",
            target_role="DevOps Engineer",
            target_company="CloudCorp",
            osint_data={
                "technologies": ["kubernetes", "terraform", "aws"],
                "sources_used": ["apollo", "github"],
            },
        )
        assert len(scenarios) >= 1
        # Should reference real technology
        assert any("kubernetes" in s.message_draft or "kubernetes" in s.pretext for s in scenarios)

    def test_message_draft_personalized(self):
        crafter = SocialEngineeringCrafter()
        scenarios = crafter.craft_scenarios(
            target_person="Charlie Brown",
            target_role="IT Administrator",
            target_company="PeanutsCorp",
        )
        for s in scenarios:
            assert "Charlie" in s.message_draft

    def test_assess_human_attack_surface(self):
        crafter = SocialEngineeringCrafter()
        assessment = crafter.assess_human_attack_surface({
            "verified_emails": ["a@test.com", "b@test.com"],
            "phone_numbers": ["+1-555-0100"],
            "social_profiles": {"linkedin": "https://linkedin.com/in/test"},
        })
        assert assessment["risk_level"] in ["critical", "high"]
        assert len(assessment["attack_vectors"]) >= 2
        assert len(assessment["recommendations"]) >= 1

    def test_assess_low_exposure(self):
        crafter = SocialEngineeringCrafter()
        assessment = crafter.assess_human_attack_surface({})
        assert assessment["risk_level"] == "low"

    def test_phishing_scenario_dataclass(self):
        scenario = PhishingScenario(
            pretext="CVE update required",
            target_person="Test User",
            target_role="Engineer",
            attack_vector="email",
            message_draft="Hi Test...",
            urgency_trigger="24h deadline",
            trust_anchor="Real CVE reference",
        )
        assert scenario.risk_level == "medium"  # Default


# =============================================================================
# Exfiltration Prover
# =============================================================================

class TestExfiltrationProver:

    def test_database_finding_creates_channel(self):
        prover = ExfiltrationProver()
        channels = prover.analyze_exfil_channels("target.com", [
            {"type": "database_exposure", "url": "/api/data", "info": {"name": "Exposed DB", "severity": "critical"}},
        ])
        assert len(channels) >= 1
        db_channels = [c for c in channels if c.channel_type == "database"]
        assert len(db_channels) >= 1

    def test_api_finding_creates_channel(self):
        prover = ExfiltrationProver()
        channels = prover.analyze_exfil_channels("target.com", [
            {"type": "unauthorized_access", "url": "/api/users", "info": {"name": "Unauth API"}},
        ])
        http_channels = [c for c in channels if c.channel_type == "http"]
        assert len(http_channels) >= 1
        assert http_channels[0].dlp_bypass is True

    def test_credential_finding_creates_chain(self):
        prover = ExfiltrationProver()
        channels = prover.analyze_exfil_channels("target.com", [
            {"type": "credential_exposure", "url": "/.env", "info": {"name": "Exposed .env"}},
        ])
        cred_channels = [c for c in channels if c.channel_type == "credential_chain"]
        assert len(cred_channels) >= 1

    def test_dns_tunneling_always_available(self):
        prover = ExfiltrationProver()
        channels = prover.analyze_exfil_channels("target.com", [
            {"type": "info_disclosure", "url": "/", "info": {"name": "Info leak"}},
        ])
        dns_channels = [c for c in channels if c.channel_type == "dns_tunneling"]
        assert len(dns_channels) >= 1
        assert dns_channels[0].dlp_bypass is True
        assert dns_channels[0].stealth == "high"

    def test_empty_findings_no_channels(self):
        prover = ExfiltrationProver()
        channels = prover.analyze_exfil_channels("target.com", [])
        assert channels == []

    def test_impact_report(self):
        prover = ExfiltrationProver()
        channels = [
            ExfilChannel("http", "API access", "high", "medium", True, "test"),
            ExfilChannel("dns_tunneling", "DNS tunnel", "low", "high", True, "test"),
        ]
        report = prover.generate_impact_report("target.com", channels)
        assert report["total_channels"] == 2
        assert report["dlp_bypass_count"] == 2
        assert "worst_case_scenario" in report
        assert len(report["recommendations"]) >= 1


# =============================================================================
# Implant Simulator
# =============================================================================

class TestImplantSimulator:

    def test_credential_persistence(self):
        sim = ImplantSimulator()
        plans = sim.map_persistence([
            {"type": "credential_exposure", "url": "/.env", "info": {"name": "Exposed creds"}},
        ])
        assert len(plans) >= 1
        assert any("T1078" in p.technique for p in plans)

    def test_api_persistence(self):
        sim = ImplantSimulator()
        plans = sim.map_persistence([
            {"type": "api_exposure", "url": "/api/admin", "info": {"name": "Admin API"}},
        ])
        assert len(plans) >= 1

    def test_no_findings_no_plans(self):
        sim = ImplantSimulator()
        plans = sim.map_persistence([])
        assert plans == []

    def test_persistence_report(self):
        sim = ImplantSimulator()
        plans = [
            PersistencePlan(
                technique="T1078",
                location="Stolen credentials",
                survival="Indefinite",
                detection_risk="low",
                c2_channel="HTTPS",
                evidence="Valid creds found",
            ),
        ]
        report = sim.generate_persistence_report("target.com", plans)
        assert report["total_techniques"] == 1
        assert report["low_detection_risk"] == 1
        assert "T1078" in report["mitre_techniques"]

    def test_persistence_plan_dataclass(self):
        plan = PersistencePlan(
            technique="T1053",
            location="Cron job",
            survival="Survives reboots",
            detection_risk="medium",
            c2_channel="Reverse shell",
        )
        assert plan.prerequisites == []


# =============================================================================
# Red Team Report Generator
# =============================================================================

class TestRedTeamReportGenerator:

    def test_empty_report(self):
        gen = RedTeamReportGenerator()
        report = gen.generate("target.com")
        assert report["target"] == "target.com"
        assert "executive_summary" in report

    def test_full_report(self):
        gen = RedTeamReportGenerator()
        report = gen.generate(
            "target.com",
            scan_result={"findings": [
                {"type": "xss", "info": {"severity": "high"}},
                {"type": "sqli", "info": {"severity": "critical"}},
            ]},
            social_scenarios=[
                PhishingScenario("test", "John", "Eng", "email", "msg", "urgency", "trust", risk_level="high"),
            ],
            exfil_channels=[
                ExfilChannel("http", "API", "high", "medium", True, "test"),
            ],
            persistence_plans=[
                PersistencePlan("T1078", "creds", "indefinite", "low", "https"),
            ],
        )
        assert "technical" in report["sections"]
        assert "social_engineering" in report["sections"]
        assert "exfiltration" in report["sections"]
        assert "persistence" in report["sections"]
        assert report["sections"]["technical"]["critical"] == 1
        assert report["sections"]["technical"]["high"] == 1

    def test_report_with_monitoring(self):
        gen = RedTeamReportGenerator()
        report = gen.generate(
            "target.com",
            monitor_changes=[
                TargetChange("new_endpoint", "/api/v3 found", severity="high"),
                TargetChange("dns_change", "New IP", severity="high"),
            ],
        )
        assert report["sections"]["monitoring"]["changes_detected"] == 2
        assert report["sections"]["monitoring"]["high_severity"] == 2
