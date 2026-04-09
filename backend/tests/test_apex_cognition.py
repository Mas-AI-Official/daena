"""Tests for Apex Cognition -- Abductive, GoalDecomp, Hypothesis, Emergent, Deception."""

import pytest

from app.services.cognition.apex_cognition import (
    AbductiveReasoner,
    Abduction,
    CognitiveDeceptionEngine,
    DeceptionPlan,
    EmergentVuln,
    EmergentVulnFinder,
    GoalDecomposer,
    GoalNode,
    Hypothesis,
    HypothesisTester,
)


class TestAbductiveReasoner:

    def setup_method(self):
        self.reasoner = AbductiveReasoner()

    def test_fast_rejection_implies_proxy_block(self):
        obs = [{"status_code": 403, "response_time_ms": 3, "headers": {}, "body": ""}]
        abductions = self.reasoner.abduce(obs)
        assert any("proxy" in a.inference.lower() or "WAF" in a.inference for a in abductions)

    def test_slow_error_implies_backend_reached(self):
        obs = [{"status_code": 500, "response_time_ms": 2500, "headers": {}, "body": ""}]
        abductions = self.reasoner.abduce(obs)
        assert any("backend" in a.inference.lower() for a in abductions)

    def test_redirect_to_internal_detected(self):
        obs = [{"status_code": 302, "headers": {"location": "http://192.168.1.5:8080/internal"}, "body": ""}]
        abductions = self.reasoner.abduce(obs)
        assert any("internal" in a.inference.lower() for a in abductions)

    def test_file_path_in_error_body(self):
        obs = [{"status_code": 500, "body": "Error at /var/www/app/handler.py line 42", "headers": {}}]
        abductions = self.reasoner.abduce(obs)
        assert any("filesystem" in a.inference.lower() for a in abductions)

    def test_differential_timing_cross_observation(self):
        obs = [
            {"status_code": 200, "response_time_ms": 50, "headers": {}},
            {"status_code": 200, "response_time_ms": 50, "headers": {}},
            {"status_code": 200, "response_time_ms": 3000, "headers": {}},
        ]
        abductions = self.reasoner.abduce(obs)
        assert any("timing" in a.observation.lower() or "code path" in a.inference.lower() for a in abductions)

    def test_multiple_server_headers_detected(self):
        obs = [
            {"status_code": 200, "headers": {"server": "nginx"}, "response_time_ms": 50},
            {"status_code": 200, "headers": {"server": "apache"}, "response_time_ms": 50},
        ]
        abductions = self.reasoner.abduce(obs)
        assert any("multiple" in a.inference.lower() or "backend" in a.inference.lower() for a in abductions)

    def test_sorted_by_confidence(self):
        obs = [
            {"status_code": 500, "response_time_ms": 2500, "headers": {}, "body": "/var/www/app.py"},
            {"status_code": 302, "headers": {"location": "http://10.0.0.1/admin"}, "body": ""},
        ]
        abductions = self.reasoner.abduce(obs)
        if len(abductions) >= 2:
            assert abductions[0].confidence >= abductions[1].confidence

    def test_empty_observations(self):
        assert self.reasoner.abduce([]) == []

    def test_abductions_have_testable_predictions(self):
        obs = [{"status_code": 403, "response_time_ms": 3, "headers": {}, "body": ""}]
        abductions = self.reasoner.abduce(obs)
        for a in abductions:
            assert a.testable_prediction


class TestGoalDecomposer:

    def setup_method(self):
        self.decomposer = GoalDecomposer()

    def test_admin_access_decomposition(self):
        tree = self.decomposer.decompose("Get admin access", "target.com")
        assert tree.goal
        assert tree.approach == "OR"
        assert len(tree.children) >= 2

    def test_data_exfiltration_decomposition(self):
        tree = self.decomposer.decompose("Extract user data", "target.com")
        assert len(tree.children) >= 2

    def test_generic_goal_decomposition(self):
        tree = self.decomposer.decompose("Something unusual", "target.com")
        assert len(tree.children) >= 2

    def test_tree_has_concrete_actions(self):
        tree = self.decomposer.decompose("Get admin access", "target.com")
        actions = self.decomposer.get_next_actions(tree)
        assert len(actions) > 0
        assert any("url" in str(a) for a in actions)

    def test_target_injected_into_urls(self):
        tree = self.decomposer.decompose("Get admin access", "target.com")
        actions = self.decomposer.get_next_actions(tree)
        assert any("target.com" in str(a) for a in actions)

    def test_thinking_log_output(self):
        tree = self.decomposer.decompose("Get admin access", "target.com")
        log = self.decomposer.to_thinking_log(tree)
        assert len(log) > 0
        assert any("admin" in line.lower() for line in log)

    def test_prune_updates_status(self):
        tree = self.decomposer.decompose("Get admin access", "target.com")
        self.decomposer.prune(tree, "/.env", "404 Not Found")
        # At least one node should be failed
        def has_failed(node):
            if node.status == "failed":
                return True
            return any(has_failed(c) for c in node.children)
        assert has_failed(tree)


class TestHypothesisTester:

    def setup_method(self):
        self.tester = HypothesisTester()

    def test_django_generates_hypotheses(self):
        obs = {"technologies": ["Django/4.2"]}
        hypotheses = self.tester.generate_hypotheses(obs)
        assert any("admin" in h.statement.lower() or "django" in h.statement.lower() for h in hypotheses)

    def test_express_generates_hypotheses(self):
        obs = {"technologies": ["Express"]}
        hypotheses = self.tester.generate_hypotheses(obs)
        assert any("express" in h.statement.lower() or "stack" in h.statement.lower() for h in hypotheses)

    def test_waf_generates_hypotheses(self):
        obs = {"waf_detected": "cloudflare", "technologies": []}
        hypotheses = self.tester.generate_hypotheses(obs)
        assert any("waf" in h.statement.lower() for h in hypotheses)

    def test_api_versioned_generates_hypotheses(self):
        obs = {"technologies": [], "api_patterns": ["/api/v2/users"]}
        hypotheses = self.tester.generate_hypotheses(obs)
        assert any("old" in h.statement.lower() or "v1" in h.statement.lower() for h in hypotheses)

    def test_update_confirmed_increases_confidence(self):
        h = Hypothesis(
            statement="Test", reasoning="Test", prediction="Test",
            confidence_before=0.5,
        )
        h = self.tester.update_hypothesis(h, {"status_code": 200, "success": True})
        assert h.result == "confirmed"
        assert h.confidence_after > h.confidence_before

    def test_update_refuted_decreases_confidence(self):
        h = Hypothesis(
            statement="Test", reasoning="Test", prediction="Test",
            confidence_before=0.5,
        )
        h = self.tester.update_hypothesis(h, {"status_code": 404, "success": True})
        assert h.result == "refuted"
        assert h.confidence_after < h.confidence_before

    def test_update_403_partial(self):
        h = Hypothesis(
            statement="Test", reasoning="Test", prediction="Test",
            confidence_before=0.5,
        )
        h = self.tester.update_hypothesis(h, {"status_code": 403, "success": True})
        assert h.result == "partial"

    def test_hypotheses_have_spawned(self):
        obs = {"technologies": ["Django/4.2"]}
        hypotheses = self.tester.generate_hypotheses(obs)
        django_hyp = [h for h in hypotheses if "admin" in h.statement.lower() or "django" in h.statement.lower()]
        if django_hyp:
            assert django_hyp[0].spawned_hypotheses


class TestEmergentVulnFinder:

    def setup_method(self):
        self.finder = EmergentVulnFinder()

    def test_find_ssrf_pattern(self):
        vulns = self.finder.find_emergent_vulns(
            components=["webhook configuration", "internal API gateway"],
            technologies=["express"],
            findings=[{"type": "api_exposure", "url": "/api/webhooks"}],
        )
        assert any("ssrf" in v.vulnerability.lower() for v in vulns)

    def test_find_stored_xss_pattern(self):
        vulns = self.finder.find_emergent_vulns(
            components=["user registration", "admin dashboard"],
            technologies=["django"],
            findings=[],
        )
        assert any("xss" in v.vulnerability.lower() or "stored" in v.vulnerability.lower() for v in vulns)

    def test_find_race_condition(self):
        vulns = self.finder.find_emergent_vulns(
            components=["balance check", "transaction execution"],
            technologies=[],
            findings=[{"type": "api_exposure", "url": "/api/transfer"}],
        )
        assert any("race" in v.vulnerability.lower() or "toctou" in v.vulnerability.lower() for v in vulns)

    def test_find_mass_assignment(self):
        vulns = self.finder.find_emergent_vulns(
            components=["user profile update endpoint", "role permission model"],
            technologies=["express"],
            findings=[{"type": "api_exposure", "url": "/api/profile", "info": {"name": "profile update"}}],
        )
        assert any("role=admin" in v.vulnerability.lower() or "mass assignment" in v.vulnerability.lower() for v in vulns)

    def test_no_matches_returns_empty(self):
        vulns = self.finder.find_emergent_vulns(
            components=["completely unrelated"],
            technologies=[],
            findings=[],
        )
        assert len(vulns) == 0

    def test_vulns_have_proof_concept(self):
        vulns = self.finder.find_emergent_vulns(
            components=["webhook", "internal service"],
            technologies=[],
            findings=[],
        )
        for v in vulns:
            assert v.proof_concept


class TestCognitiveDeceptionEngine:

    def setup_method(self):
        self.engine = CognitiveDeceptionEngine()

    def test_plan_has_decoys_and_real(self):
        plan = self.engine.plan_deception(
            real_objective="Test admin API endpoint",
            target="target.com",
            defenses=["WAF"],
        )
        assert len(plan.decoy_actions) >= 2
        assert plan.real_action
        assert plan.real_action.get("url")

    def test_decoys_are_noisy(self):
        plan = self.engine.plan_deception("admin access", "target.com", [])
        # Decoys should contain obvious attack patterns
        decoy_str = str(plan.decoy_actions)
        assert "admin" in decoy_str.lower() or "OR 1=1" in decoy_str

    def test_real_probe_is_subtle(self):
        plan = self.engine.plan_deception("admin access", "target.com", [])
        real_url = plan.real_action.get("url", "")
        # Real probe should NOT contain obvious attack patterns
        assert "OR 1=1" not in real_url
        assert "wp-admin" not in real_url

    def test_timing_explanation(self):
        plan = self.engine.plan_deception("data access", "target.com", [])
        assert plan.timing
        assert "decoy" in plan.timing.lower() or "real" in plan.timing.lower()

    def test_data_objective_selects_data_probe(self):
        plan = self.engine.plan_deception("extract data from database", "target.com", [])
        assert "export" in plan.real_action.get("url", "") or "api" in plan.real_action.get("url", "")

    def test_url_has_scheme(self):
        plan = self.engine.plan_deception("test", "target.com", [])
        assert plan.real_action["url"].startswith("https://")
        for d in plan.decoy_actions:
            assert d["url"].startswith("https://")
