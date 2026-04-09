"""Tests for Beyond Mythos capabilities -- ErrorOracle, AdversarialSimulator, CompositionalPlanner.

These capabilities go beyond constraint decomposition into
defender simulation, error intelligence extraction, and
compositional attack planning.
"""

import pytest

from app.services.cognition.beyond_mythos import (
    AdversarialSimulator,
    CompositionalPlanner,
    CompositionalPlan,
    CompositeStep,
    DefenderPrediction,
    ErrorIntelligence,
    ErrorOracle,
)


# -----------------------------------------------------------------------
# Error Oracle
# -----------------------------------------------------------------------

class TestErrorOracle:
    """Tests for extracting intelligence from failures."""

    def setup_method(self):
        self.oracle = ErrorOracle()

    # -- Status code intelligence --

    def test_403_reveals_path_exists(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/admin",
            status_code=403,
            headers={},
            body="Forbidden",
        )
        assert intel.error_type == "forbidden"
        assert intel.inferred_facts.get("path_exists") is True
        assert intel.inferred_facts.get("requires_auth") is True
        assert any("EXISTS" in i for i in intel.intelligence)

    def test_401_reveals_auth_required(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/api/v1/users",
            status_code=401,
            headers={},
            body='{"detail": "Not authenticated"}',
        )
        assert intel.inferred_facts.get("auth_required") is True
        assert intel.inferred_facts.get("path_exists") is True

    def test_500_reveals_input_reaches_backend(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/api/search",
            status_code=500,
            headers={},
            body="Internal Server Error",
        )
        assert intel.inferred_facts.get("input_reaches_backend") is True
        assert intel.inferred_facts.get("potential_crash_bug") is True

    def test_405_reveals_method_restriction(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/api/data",
            status_code=405,
            headers={},
            body="Method Not Allowed",
        )
        assert intel.inferred_facts.get("method_restricted") is True
        assert intel.inferred_facts.get("path_exists") is True

    def test_429_reveals_rate_limit(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/api",
            status_code=429,
            headers={"retry-after": "60"},
            body="Too Many Requests",
        )
        assert intel.inferred_facts.get("rate_limit_active") is True

    def test_502_reveals_reverse_proxy(self):
        intel = self.oracle.analyze_response(
            url="https://target.com",
            status_code=502,
            headers={},
            body="Bad Gateway",
        )
        assert intel.inferred_facts.get("reverse_proxy_present") is True

    # -- Header intelligence --

    def test_server_header_reveals_software(self):
        intel = self.oracle.analyze_response(
            url="https://target.com",
            status_code=200,
            headers={"Server": "nginx/1.21.6", "X-Powered-By": "Express"},
            body="",
        )
        assert intel.inferred_facts.get("server_software") == "nginx/1.21.6"
        assert intel.inferred_facts.get("framework") == "Express"

    def test_cloudflare_header_detected(self):
        intel = self.oracle.analyze_response(
            url="https://target.com",
            status_code=200,
            headers={"cf-ray": "abc123-IAD"},
            body="",
        )
        assert "cf-ray" in intel.inferred_facts.get("waf_indicators", [])

    def test_rate_limit_headers_extracted(self):
        intel = self.oracle.analyze_response(
            url="https://target.com",
            status_code=200,
            headers={"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "42"},
            body="",
        )
        assert "rate_limit_config" in intel.inferred_facts

    def test_cors_wildcard_detected(self):
        intel = self.oracle.analyze_response(
            url="https://target.com",
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*"},
            body="",
        )
        assert intel.inferred_facts.get("cors_wildcard") is True

    def test_internal_url_in_redirect(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/old",
            status_code=302,
            headers={"Location": "http://192.168.1.10:8080/new"},
            body="",
        )
        assert intel.inferred_facts.get("internal_url_leaked") == "http://192.168.1.10:8080/new"

    # -- Body intelligence --

    def test_stack_trace_in_body(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/api",
            status_code=500,
            headers={},
            body="Traceback (most recent call last):\n  File /var/www/app.py line 42",
        )
        assert intel.inferred_facts.get("stack_trace_exposed") is True
        assert intel.inferred_facts.get("file_path_exposed") is True

    def test_sql_error_in_body(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/search",
            status_code=500,
            headers={},
            body='SQL syntax error near "SELECT * FROM users WHERE id ="',
        )
        assert intel.inferred_facts.get("database_error_exposed") is True

    def test_django_tech_detected(self):
        intel = self.oracle.analyze_response(
            url="https://target.com",
            status_code=500,
            headers={},
            body="DjangoDebug at /admin/",
        )
        assert "django" in intel.inferred_facts.get("technologies", [])

    def test_json_api_format_detected(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/api",
            status_code=400,
            headers={},
            body='{"detail": "Invalid input", "status": 400}',
        )
        assert intel.inferred_facts.get("api_format") == "json"

    # -- Timing intelligence --

    def test_slow_response_noted(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/heavy",
            status_code=200,
            headers={},
            body="",
            response_time_ms=8000,
        )
        assert intel.inferred_facts.get("slow_endpoint") is True

    def test_instant_response_noted(self):
        intel = self.oracle.analyze_response(
            url="https://target.com/blocked",
            status_code=403,
            headers={},
            body="",
            response_time_ms=2,
        )
        assert intel.inferred_facts.get("proxy_rejection_likely") is True

    # -- Differential analysis --

    def test_compare_status_codes(self):
        responses = [
            {"status_code": 200, "body": "user data", "body_length": 500},
            {"status_code": 404, "body": "not found", "body_length": 20},
        ]
        insights = self.oracle.compare_responses(responses)
        assert any("Enumeration" in i for i in insights)

    def test_compare_response_sizes(self):
        responses = [
            {"status_code": 200, "body_length": 5000},
            {"status_code": 200, "body_length": 100},
        ]
        insights = self.oracle.compare_responses(responses)
        assert any("size" in i.lower() for i in insights)

    def test_compare_timing_anomaly(self):
        responses = [
            {"status_code": 200, "response_time_ms": 50},
            {"status_code": 200, "response_time_ms": 50},
            {"status_code": 200, "response_time_ms": 5000},
        ]
        insights = self.oracle.compare_responses(responses)
        assert any("timing" in i.lower() or "Timing" in i for i in insights)

    def test_compare_single_response_no_insight(self):
        insights = self.oracle.compare_responses([{"status_code": 200}])
        assert insights == []

    # -- Confidence --

    def test_confidence_scales_with_intelligence(self):
        intel_low = self.oracle.analyze_response(
            url="https://target.com",
            status_code=200,
            headers={},
            body="OK",
        )
        intel_high = self.oracle.analyze_response(
            url="https://target.com",
            status_code=500,
            headers={"Server": "nginx", "X-Powered-By": "PHP/7.4"},
            body="SQL syntax error near\nTraceback (most recent call last):\n  File /var/www",
        )
        assert intel_high.confidence > intel_low.confidence


# -----------------------------------------------------------------------
# Adversarial Simulator
# -----------------------------------------------------------------------

class TestAdversarialSimulator:
    """Tests for defender perspective simulation."""

    def setup_method(self):
        self.sim = AdversarialSimulator()

    def test_clean_request_low_risk(self):
        pred = self.sim.predict_detection(
            operation="http_request",
            params={"url": "https://target.com/", "method": "GET"},
        )
        assert pred.risk_score < 0.3
        assert pred.predicted_detection in ("undetected", "logged")

    def test_vuln_scan_high_risk(self):
        pred = self.sim.predict_detection(
            operation="vuln_scan",
            params={"target": "target.com"},
            target_defenses=["WAF: cloudflare"],
        )
        assert pred.risk_score >= 0.7
        assert pred.predicted_detection in ("alerted", "blocked")

    def test_tool_signature_detected(self):
        pred = self.sim.predict_detection(
            operation="http_request",
            params={"url": "https://target.com", "headers": {"User-Agent": "sqlmap/1.5"}},
        )
        assert pred.risk_score >= 0.7
        assert any("signature" in r.lower() for r in pred.detection_reasons)

    def test_sql_injection_payload_detected(self):
        pred = self.sim.predict_detection(
            operation="http_request",
            params={"url": "https://target.com/search?q=' OR 1=1--"},
        )
        assert pred.risk_score >= 0.9

    def test_high_request_count_flagged(self):
        pred = self.sim.predict_detection(
            operation="http_request",
            params={"url": "https://target.com"},
            request_count_so_far=150,
        )
        assert pred.risk_score >= 0.5
        assert any("request count" in r.lower() for r in pred.detection_reasons)

    def test_waf_path_monitoring(self):
        pred = self.sim.predict_detection(
            operation="http_request",
            params={"url": "https://target.com/.env"},
            target_defenses=["WAF: cloudflare"],
        )
        assert pred.risk_score >= 0.3

    def test_evasion_suggestions_for_risky_action(self):
        pred = self.sim.predict_detection(
            operation="vuln_scan",
            params={"target": "target.com"},
            target_defenses=["WAF: akamai"],
            request_count_so_far=80,
        )
        assert len(pred.evasion_suggestions) > 0

    def test_passive_operation_low_noise(self):
        pred = self.sim.predict_detection(
            operation="cve_search",
            params={"keyword": "nginx"},
        )
        assert pred.risk_score < 0.2

    def test_adjust_for_stealth_adds_headers(self):
        pred = DefenderPrediction(
            action_description="GET https://target.com",
            predicted_detection="logged",
            risk_score=0.3,
        )
        adjusted = self.sim.adjust_for_stealth(
            "http_request",
            {"url": "https://target.com", "method": "GET"},
            pred,
        )
        assert "headers" in adjusted
        assert "User-Agent" in adjusted["headers"]
        assert "Mozilla" in adjusted["headers"]["User-Agent"]

    def test_adjust_preserves_existing_headers(self):
        pred = DefenderPrediction(
            action_description="test",
            predicted_detection="undetected",
            risk_score=0.1,
        )
        adjusted = self.sim.adjust_for_stealth(
            "http_request",
            {"url": "https://target.com", "headers": {"Authorization": "Bearer xyz"}},
            pred,
        )
        # Should keep existing headers
        assert adjusted["headers"]["Authorization"] == "Bearer xyz"


# -----------------------------------------------------------------------
# Compositional Planner
# -----------------------------------------------------------------------

class TestCompositionalPlanner:
    """Tests for compositional attack planning."""

    def setup_method(self):
        self.planner = CompositionalPlanner()

    def test_auth_bypass_composition(self):
        plan = self.planner.plan_composition(
            objective="Bypass authentication on admin panel",
            blocked_action="direct login brute force",
            target_url="https://target.com",
        )
        assert len(plan.steps) > 0
        assert plan.total_risk < 0.5
        assert plan.why_composition_works

    def test_data_extraction_composition(self):
        plan = self.planner.plan_composition(
            objective="Extract user data via IDOR",
            blocked_action="direct data access",
            target_url="https://target.com",
        )
        assert len(plan.steps) > 0
        assert any("idor" in s.purpose.lower() or "adjacent" in s.purpose.lower() for s in plan.steps)

    def test_service_enumeration_composition(self):
        plan = self.planner.plan_composition(
            objective="Enumerate all services on target",
            blocked_action="port scan blocked",
            target_url="https://target.com",
        )
        assert len(plan.steps) > 0

    def test_generic_composition_fallback(self):
        plan = self.planner.plan_composition(
            objective="Something unusual",
            blocked_action="anything",
            target_url="https://target.com",
        )
        # Should fall back to generic 3-step plan
        assert len(plan.steps) >= 3

    def test_steps_have_appearances(self):
        """Every step must describe what it looks like to the defender."""
        plan = self.planner.plan_composition(
            objective="Bypass auth",
            blocked_action="login blocked",
            target_url="https://target.com",
        )
        for step in plan.steps:
            assert step.appears_as, f"Step {step.operation} missing appears_as"
            assert step.purpose, f"Step {step.operation} missing purpose"

    def test_decompose_waf_blocked_scan(self):
        plan = self.planner.decompose_blocked_scan(
            scan_strategy_name="targeted_vuln_scan",
            failure_reason="WAF (cloudflare) filtering scan traffic; all 403",
            target="target.com",
        )
        assert len(plan.steps) >= 3
        assert plan.total_risk < 0.3
        assert "waf" in plan.why_direct_fails.lower() or "403" in plan.why_direct_fails

    def test_decompose_rate_limited_scan(self):
        plan = self.planner.decompose_blocked_scan(
            scan_strategy_name="path_discovery",
            failure_reason="Rate limiting detected (429)",
            target="target.com",
        )
        assert len(plan.steps) >= 1
        assert plan.total_risk < 0.2
        # Should include passive approach
        assert any("passive" in s.purpose.lower() or "cve" in s.operation.lower()
                    for s in plan.steps)

    def test_decompose_generic_failure(self):
        plan = self.planner.decompose_blocked_scan(
            scan_strategy_name="header_analysis",
            failure_reason="Unknown failure",
            target="target.com",
        )
        assert len(plan.steps) >= 2

    def test_steps_have_valid_operations(self):
        plan = self.planner.decompose_blocked_scan(
            scan_strategy_name="test",
            failure_reason="blocked",
            target="target.com",
        )
        valid_ops = {"http_request", "tcp_connect", "ssh_connect", "db_connect",
                     "db_query", "enumerate_service", "cve_search"}
        for step in plan.steps:
            assert step.operation in valid_ops, f"Invalid operation: {step.operation}"

    def test_compositional_plan_dataclass(self):
        plan = CompositionalPlan(
            objective="test",
            steps=[
                CompositeStep(
                    operation="http_request",
                    params={"url": "https://t.com"},
                    appears_as="Normal visit",
                    purpose="Recon",
                ),
            ],
            why_direct_fails="blocked",
            why_composition_works="stealth",
            total_risk=0.2,
        )
        assert plan.objective == "test"
        assert len(plan.steps) == 1
        assert plan.steps[0].appears_as == "Normal visit"

    def test_url_scheme_added_if_missing(self):
        plan = self.planner.plan_composition(
            objective="Enumerate services",
            blocked_action="blocked",
            target_url="target.com",  # No scheme
        )
        for step in plan.steps:
            url = step.params.get("url", "")
            if url:
                assert url.startswith("https://"), f"URL missing scheme: {url}"
