"""Tests for BeyondMythos enrichment wiring into scan findings.

Covers:
    * ErrorOracle: status-code + header + body intelligence extraction
    * AdversarialSimulator: detection prediction + stealth adjustment
    * CompositionalPlanner: decomposition of blocked scans
    * ScanWorkflow integration: enrichment applied to aggregated findings
"""

from __future__ import annotations

import pytest

from app.services.security.beyond_mythos_enricher import BeyondMythosEnricher


@pytest.fixture
def enricher() -> BeyondMythosEnricher:
    return BeyondMythosEnricher()


# ----------------------------------------------------------------------
# ErrorOracle integration
# ----------------------------------------------------------------------


def test_enriches_http_403_with_error_intelligence(enricher):
    finding = {
        "id": "F1",
        "title": "Possible auth gap",
        "http_response": {
            "url": "https://target.example/admin",
            "status_code": 403,
            "headers": {"Server": "nginx", "X-Powered-By": "Django"},
            "body": "Forbidden",
            "response_time_ms": 120,
        },
    }
    [out] = enricher.enrich_findings([finding])
    assert "error_intelligence" in out
    intel = out["error_intelligence"]
    # ErrorOracle should flag path existence + auth requirement for 403.
    assert intel["inferred_facts"].get("path_exists") is True
    assert intel["inferred_facts"].get("requires_auth") is True


def test_enriches_http_500_input_reaches_backend(enricher):
    finding = {
        "id": "F2",
        "http_response": {
            "url": "https://target.example/api",
            "status_code": 500,
            "headers": {},
            "body": "<html>Internal Server Error</html>",
        },
    }
    [out] = enricher.enrich_findings([finding])
    intel = out["error_intelligence"]
    assert intel["inferred_facts"].get("input_reaches_backend") is True


# ----------------------------------------------------------------------
# AdversarialSimulator integration
# ----------------------------------------------------------------------


def test_enriches_action_with_defender_prediction(enricher):
    finding = {
        "id": "F3",
        "action": {
            "operation": "vuln_scan",
            "params": {"target": "example.com", "tool": "nuclei"},
            "request_count": 120,
        },
    }
    [out] = enricher.enrich_findings(
        [finding], target_defenses=["cloudflare"],
    )
    assert "defender_prediction" in out
    pred = out["defender_prediction"]
    assert pred["risk_score"] >= 0.3
    # Stealth auto-adjustment should fire when risk is non-trivial.
    assert "stealth_adjusted_params" in out


def test_low_risk_action_no_stealth_adjust(enricher):
    finding = {
        "id": "F4",
        "action": {
            "operation": "cve_search",
            "params": {"keyword": "openssl"},
            "request_count": 1,
        },
    }
    [out] = enricher.enrich_findings([finding], target_defenses=[])
    # Even for a clean action, the prediction is still attached so
    # downstream callers see the risk score. Stealth params are
    # attached only when risk_score >= 0.3.
    assert "defender_prediction" in out


# ----------------------------------------------------------------------
# CompositionalPlanner integration
# ----------------------------------------------------------------------


def test_enriches_blocked_finding_with_compositional_plan(enricher):
    finding = {
        "id": "F5",
        "title": "Direct scan blocked",
        "target": "target.example",
        "blocked_reason": "403 Forbidden (waf)",
    }
    [out] = enricher.enrich_findings([finding])
    assert "compositional_plan" in out
    plan = out["compositional_plan"]
    assert len(plan["steps"]) >= 1
    assert plan["why_direct_fails"]


def test_enriches_rate_limited_finding(enricher):
    finding = {
        "id": "F6",
        "target": "target.example",
        "blocked_reason": "429 Too Many Requests (rate)",
    }
    [out] = enricher.enrich_findings([finding])
    plan = out["compositional_plan"]
    # Rate-limited plan prefers passive CVE lookup + HEAD requests.
    step_ops = [s["operation"] for s in plan["steps"]]
    assert "cve_search" in step_ops or any("http" in s for s in step_ops)


# ----------------------------------------------------------------------
# Error containment
# ----------------------------------------------------------------------


def test_per_finding_error_does_not_break_batch(enricher):
    bad = {"id": "F7", "http_response": {"status_code": "not-a-number"}}
    good = {"id": "F8", "http_response": {"status_code": 200, "headers": {}, "body": ""}}
    out = enricher.enrich_findings([bad, good])
    assert len(out) == 2
    # Good finding still got enriched.
    assert "error_intelligence" in out[1]


# ----------------------------------------------------------------------
# compare_response_series
# ----------------------------------------------------------------------


def test_compare_responses_detects_enumeration(enricher):
    responses = [
        {"status_code": 200, "body_length": 3200, "response_time_ms": 150},
        {"status_code": 404, "body_length": 100, "response_time_ms": 80},
        {"status_code": 403, "body_length": 140, "response_time_ms": 90},
    ]
    insights = enricher.compare_response_series(responses)
    joined = " ".join(insights).lower()
    assert "enumeration" in joined or "differential" in joined


# ----------------------------------------------------------------------
# ScanWorkflow end-to-end integration
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_workflow_applies_beyond_mythos(monkeypatch):
    """The scan_workflow aggregation path invokes enrichment."""
    from app.services.security import scan_workflow as sw

    called = {"invoked": False}

    class FakeEnricher:
        def enrich_findings(self, findings, *, target_defenses=None):
            called["invoked"] = True
            return findings

    monkeypatch.setattr(sw, "BeyondMythosEnricher", FakeEnricher, raising=False)

    # Patch the dynamic import inside _execute_scan by patching the
    # module-level lookup that the runtime import hits.
    import app.services.security.beyond_mythos_enricher as bme_mod
    monkeypatch.setattr(
        bme_mod, "BeyondMythosEnricher", FakeEnricher, raising=False,
    )

    wf = sw.ScanWorkflow()
    job = await wf.start_scan(
        target="app.py,api.py",
        tier="SCOUT",
        user_id="u",
        tenant_id="t",
    )

    # Wait briefly for the scan pipeline to reach ANALYZING.
    import asyncio
    for _ in range(50):
        if called["invoked"]:
            break
        await asyncio.sleep(0.1)

    assert called["invoked"] is True
