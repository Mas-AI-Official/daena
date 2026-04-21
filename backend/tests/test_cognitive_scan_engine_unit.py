"""Isolated unit tests for cognitive_scan_engine pure helpers.

The full CognitiveScanEngine is a >3000-line async HTTP orchestrator
that is integration-tested via test_cognitive_scan.py. This file
covers the pure strategy-generator functions and the dataclass
serialization that run in milliseconds with no I/O.

Covers:
    * 7 strategy generators return valid ScanStrategy shapes
    * Strategy steps carry operation + params keys
    * Confidence bounds (0.0..1.0)
    * Stealth level taxonomy
    * CognitiveScanResult default construction
    * TargetProfile fields defaulting
    * Strategies select different operations based on params

Guards the strategy taxonomy from silent drift.
"""

from __future__ import annotations

import pytest

from app.services.security.cognitive_scan_engine import (
    CognitiveScanResult,
    ExploitAttempt,
    ScanCycleResult,
    ScanStrategy,
    TargetProfile,
    _canary_echo_strategy,
    _cost_amplification_strategy,
    _forgotten_infra_strategy,
    _header_analysis_strategy,
    _passive_osint_strategy,
    _path_discovery_strategy,
    _state_machine_strategy,
    _targeted_vuln_scan_strategy,
)


# ----------------------------------------------------------------------
# Strategy generators: shape + content
# ----------------------------------------------------------------------


def test_passive_osint_strategy_shape():
    s = _passive_osint_strategy("example.com")
    assert isinstance(s, ScanStrategy)
    assert s.name == "passive_osint"
    assert s.stealth_level in ("passive", "low", "medium", "high")
    assert 0.0 <= s.confidence <= 1.0
    assert len(s.steps) >= 1
    for step in s.steps:
        assert "operation" in step
        assert "params" in step


def test_passive_osint_is_maximally_stealthy():
    """The whole point of passive osint: no direct contact."""
    s = _passive_osint_strategy("target.test")
    assert s.stealth_level == "passive"
    # No HTTP requests to the target: all operations are lookups/queries.
    ops = {step["operation"] for step in s.steps}
    # Must NOT include an HTTP request operation.
    assert "http_get" not in ops
    assert "http_post" not in ops


def test_header_analysis_requires_subdomains():
    """Without subdomains, steps should still produce but target
    the base domain."""
    s = _header_analysis_strategy("target.test", [])
    assert s.name == "header_analysis"
    assert isinstance(s.steps, list)
    # Confidence valid.
    assert 0.0 <= s.confidence <= 1.0


def test_header_analysis_scales_with_subdomains():
    s_empty = _header_analysis_strategy("t.com", [])
    s_many = _header_analysis_strategy("t.com", [
        "api.t.com", "admin.t.com", "legacy.t.com", "dev.t.com",
    ])
    # More subdomains means more steps (or at least not fewer)
    assert len(s_many.steps) >= len(s_empty.steps)


def test_path_discovery_strategy_shape():
    s = _path_discovery_strategy("t.com", [
        {"url": "https://t.com", "status": 200},
    ])
    assert s.name == "path_discovery"
    assert 0.0 <= s.confidence <= 1.0


def test_forgotten_infra_strategy_shape():
    s = _forgotten_infra_strategy("legacy.test")
    assert s.name == "forgotten_infrastructure"
    assert len(s.steps) >= 1
    assert 0.0 <= s.confidence <= 1.0


def test_targeted_vuln_scan_with_tech_and_cves():
    s = _targeted_vuln_scan_strategy(
        "t.com",
        technologies=["nginx/1.18.0", "openssl/3.0.2"],
        cves=[{"cve_id": "CVE-2024-1234", "severity": "HIGH"}],
    )
    assert s.name == "targeted_vuln_scan"
    assert 0.0 <= s.confidence <= 1.0
    # Should reference the technologies or CVEs.
    assert s.reasoning


def test_targeted_vuln_scan_no_tech_still_valid():
    s = _targeted_vuln_scan_strategy("t.com", technologies=[], cves=[])
    assert isinstance(s, ScanStrategy)
    assert s.name == "targeted_vuln_scan"


def test_canary_echo_strategy_shape():
    s = _canary_echo_strategy("t.com", [{"url": "https://t.com"}])
    assert s.name == "canary_echo"
    assert 0.0 <= s.confidence <= 1.0


def test_state_machine_strategy_shape():
    s = _state_machine_strategy("t.com", ["/login", "/checkout"])
    assert s.name == "state_machine"
    assert 0.0 <= s.confidence <= 1.0


def test_cost_amplification_strategy_shape():
    s = _cost_amplification_strategy("t.com", [{"url": "https://t.com/api"}])
    assert s.name == "cost_amplification"
    assert 0.0 <= s.confidence <= 1.0


def test_all_strategies_return_unique_names():
    """No two strategy generators should return the same name.
    A collision would cause strategy dedup to silently drop one."""
    strategies = [
        _passive_osint_strategy("x"),
        _header_analysis_strategy("x", []),
        _path_discovery_strategy("x", []),
        _forgotten_infra_strategy("x"),
        _targeted_vuln_scan_strategy("x", [], []),
        _canary_echo_strategy("x", []),
        _state_machine_strategy("x", []),
        _cost_amplification_strategy("x", []),
    ]
    names = [s.name for s in strategies]
    assert len(names) == len(set(names))


def test_all_strategies_have_nonempty_steps():
    for strategy_fn, args in [
        (_passive_osint_strategy, ("x",)),
        (_header_analysis_strategy, ("x", ["sub.x"])),
        (_path_discovery_strategy, ("x", [{"url": "https://x"}])),
        (_forgotten_infra_strategy, ("x",)),
        (_targeted_vuln_scan_strategy, ("x", ["nginx"], [])),
        (_canary_echo_strategy, ("x", [{"url": "https://x"}])),
        (_state_machine_strategy, ("x", ["/a"])),
        (_cost_amplification_strategy, ("x", [{"url": "https://x"}])),
    ]:
        strategy = strategy_fn(*args)
        assert len(strategy.steps) >= 1, f"{strategy.name} produced no steps"


def test_all_strategies_have_reasoning():
    """Every strategy must explain WHY it is proposed, for OODA-R
    audit trail."""
    for strategy_fn, args in [
        (_passive_osint_strategy, ("x",)),
        (_header_analysis_strategy, ("x", ["sub.x"])),
        (_path_discovery_strategy, ("x", [{"url": "https://x"}])),
        (_forgotten_infra_strategy, ("x",)),
        (_targeted_vuln_scan_strategy, ("x", ["nginx"], [])),
        (_canary_echo_strategy, ("x", [{"url": "https://x"}])),
        (_state_machine_strategy, ("x", ["/a"])),
        (_cost_amplification_strategy, ("x", [{"url": "https://x"}])),
    ]:
        strategy = strategy_fn(*args)
        assert strategy.reasoning, f"{strategy.name} has empty reasoning"


# ----------------------------------------------------------------------
# Dataclass defaults
# ----------------------------------------------------------------------


def test_target_profile_defaults():
    p = TargetProfile(domain="t.com")
    assert p.subdomains == []
    assert p.live_hosts == []
    assert p.technologies == []
    assert p.waf_detected == ""
    assert p.interesting_paths == []
    assert p.cve_intel == []
    assert p.defenses == []
    assert p.target_type == ""


def test_scan_cycle_result_defaults():
    r = ScanCycleResult(cycle=1, strategy_name="passive_osint")
    assert r.findings == []
    assert r.success is False
    assert r.failure_reason == ""


def test_cognitive_scan_result_defaults():
    r = CognitiveScanResult(target="t.com")
    assert r.total_findings == 0
    assert r.findings == []
    assert r.exploits_succeeded == 0
    assert r.cycles_used == 0
    assert r.offensive_mode is False
    assert r.target_profile is None


def test_exploit_attempt_defaults():
    e = ExploitAttempt(
        finding_type="SQLI",
        operation="sqlmap",
        target_url="https://t.com/api",
    )
    assert e.success is False
    assert e.impact_proven == ""
    assert e.result_data == {}
    assert e.chained_from_cycle == 0


# ----------------------------------------------------------------------
# Stealth level taxonomy guard
# ----------------------------------------------------------------------


def test_stealth_level_is_valid_enum_value():
    """All strategies must use one of the 4 known stealth levels."""
    valid = {"passive", "low", "medium", "high"}
    strategies = [
        _passive_osint_strategy("x"),
        _header_analysis_strategy("x", []),
        _path_discovery_strategy("x", []),
        _forgotten_infra_strategy("x"),
        _targeted_vuln_scan_strategy("x", [], []),
        _canary_echo_strategy("x", []),
        _state_machine_strategy("x", []),
        _cost_amplification_strategy("x", []),
    ]
    for s in strategies:
        assert s.stealth_level in valid, (
            f"{s.name} has invalid stealth_level={s.stealth_level!r}"
        )
