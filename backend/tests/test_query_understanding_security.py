"""Tests for SECURITY_SCAN intent + multi-kind scan-target extraction.

Covers URL, bare domain, IP, CIDR, host:port, Android package,
APK/IPA/AAB binary, and git repo detection. Also verifies the intent
classifier requires BOTH a scan verb AND a concrete target before
flagging SECURITY_SCAN, so informational queries ("what is pentest?")
stay classified correctly.
"""

from __future__ import annotations

import pytest

from app.core.constants import ChatMode, GovernanceMode
from app.services.query_understanding import (
    IntentType,
    QueryInput,
    QueryUnderstandingService,
    ScanTarget,
    _extract_scan_targets,
)


@pytest.fixture
def svc() -> QueryUnderstandingService:
    return QueryUnderstandingService()


# ----------------------------------------------------------------------
# Target extraction (unit)
# ----------------------------------------------------------------------


def test_extract_full_url():
    targets = _extract_scan_targets("scan https://example.com for vulns")
    assert any(t.kind == "url" and t.value == "https://example.com" for t in targets)


def test_extract_bare_domain():
    targets = _extract_scan_targets("audit example.com please")
    assert any(t.kind == "domain" and t.value == "example.com" for t in targets)


def test_extract_ipv4():
    targets = _extract_scan_targets("scan 192.168.1.1")
    assert any(t.kind == "ip" and t.value == "192.168.1.1" for t in targets)


def test_extract_cidr():
    targets = _extract_scan_targets("network scan 10.0.0.0/24")
    assert any(t.kind == "cidr" and t.value == "10.0.0.0/24" for t in targets)


def test_extract_host_port():
    targets = _extract_scan_targets("probe 10.0.0.5:8080 for open services")
    assert any(t.kind == "host_port" and t.value == "10.0.0.5:8080" for t in targets)


def test_extract_android_package():
    targets = _extract_scan_targets("audit com.example.myapp for permissions")
    assert any(
        t.kind == "app_package" and t.value == "com.example.myapp"
        for t in targets
    )


def test_extract_mobile_binary_apk():
    targets = _extract_scan_targets("scan MyBankApp.apk for secrets")
    assert any(
        t.kind == "mobile_binary" and t.value == "MyBankApp.apk"
        for t in targets
    )


def test_extract_mobile_binary_ipa():
    targets = _extract_scan_targets("analyze TargetGame.ipa")
    assert any(
        t.kind == "mobile_binary" and t.value == "TargetGame.ipa"
        for t in targets
    )


def test_extract_git_repo():
    targets = _extract_scan_targets("pentest https://github.com/acme/svc code")
    assert any(t.kind == "repo" for t in targets)


def test_extract_no_target_in_plain_prose():
    """Plain text with no concrete target returns empty list."""
    targets = _extract_scan_targets("what is a pentest?")
    assert targets == []


# ----------------------------------------------------------------------
# SECURITY_SCAN intent classification
# ----------------------------------------------------------------------


def test_scan_verb_plus_url_classifies_security_scan(svc):
    q = QueryInput(raw_message="scan https://example.com for vulnerabilities")
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN
    assert r.scan_dispatch_requested is True
    assert len(r.detected_targets) >= 1
    assert any(t.kind == "url" for t in r.detected_targets)


def test_scan_verb_plus_domain_classifies_security_scan(svc):
    q = QueryInput(raw_message="find vulnerabilities in example.com")
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN
    assert r.scan_dispatch_requested is True


def test_scan_verb_plus_apk_classifies_security_scan(svc):
    q = QueryInput(raw_message="audit MyBankApp.apk for hardcoded secrets")
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN
    assert any(t.kind == "mobile_binary" for t in r.detected_targets)


def test_scan_verb_plus_android_package_classifies_security_scan(svc):
    q = QueryInput(
        raw_message="security scan com.example.myapp for permission leaks"
    )
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN
    assert any(t.kind == "app_package" for t in r.detected_targets)


def test_scan_verb_plus_cidr_classifies_security_scan(svc):
    q = QueryInput(raw_message="probe 10.0.0.0/24 for open services")
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN
    assert any(t.kind == "cidr" for t in r.detected_targets)


def test_scan_verb_plus_git_repo_classifies_security_scan(svc):
    q = QueryInput(
        raw_message="audit https://github.com/acme/service for vulns"
    )
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN
    assert any(t.kind == "repo" for t in r.detected_targets)


# ----------------------------------------------------------------------
# Non-SECURITY_SCAN safety checks
# ----------------------------------------------------------------------


def test_bare_url_no_verb_not_security_scan(svc):
    """URL without a scan verb gets targets populated but is NOT SECURITY_SCAN."""
    q = QueryInput(raw_message="Check out https://example.com, it's cool")
    r = svc.analyze(q)
    assert r.intent != IntentType.SECURITY_SCAN
    assert len(r.detected_targets) >= 1  # URL still extracted
    assert r.scan_dispatch_requested is False


def test_informational_pentest_query_not_security_scan(svc):
    """'What is pentest?' stays on the informational path."""
    q = QueryInput(raw_message="What is a pentest?")
    r = svc.analyze(q)
    assert r.intent != IntentType.SECURITY_SCAN
    assert r.scan_dispatch_requested is False


def test_https_definition_query_stays_simple(svc):
    """Regression: 'what is HTTPS?' must not misclassify."""
    q = QueryInput(raw_message="what is HTTPS?")
    r = svc.analyze(q)
    assert r.intent != IntentType.SECURITY_SCAN
    assert r.scan_dispatch_requested is False


# ----------------------------------------------------------------------
# Detected-urls backward compat
# ----------------------------------------------------------------------


def test_detected_urls_backward_compat_alias(svc):
    q = QueryInput(
        raw_message="scan https://a.example.com and audit b.example.com"
    )
    r = svc.analyze(q)
    # Only URL-kind targets show up in the legacy alias.
    assert "https://a.example.com" in r.detected_urls
    assert all(v.startswith("http") for v in r.detected_urls)
    # But both targets are present in the richer list.
    assert any(t.kind == "domain" for t in r.detected_targets)


# ----------------------------------------------------------------------
# Priority / precedence sanity
# ----------------------------------------------------------------------


def test_security_scan_beats_tool_use_when_both_match(svc):
    """'scan https://x.com and open a file' should stay SECURITY_SCAN."""
    q = QueryInput(
        raw_message="scan https://example.com for vulnerabilities then open file"
    )
    r = svc.analyze(q)
    assert r.intent == IntentType.SECURITY_SCAN


def test_dangerous_still_wins_over_security_scan(svc):
    """'rm -rf / then scan example.com' must still route to DANGEROUS."""
    q = QueryInput(
        raw_message="rm -rf / and scan https://example.com",
        execution_mode=ChatMode.EXE,
    )
    r = svc.analyze(q)
    assert r.intent == IntentType.DANGEROUS
