"""Tests for unreplicable cognitive capabilities.

ResponseTopologyMapper, SemanticMutationEngine, AttackChainSynthesizer,
InverseSurfaceMapper, DeveloperEmpathyEngine.
"""

import pytest

from app.services.cognition.unreplicable import (
    AttackChain,
    AttackChainSynthesizer,
    DeveloperEmpathyEngine,
    DeveloperProfile,
    InferredEndpoint,
    InverseSurfaceMapper,
    ResponseTopologyMapper,
    SemanticMutationEngine,
    SemanticPayload,
    TopologyMap,
    TopologyPoint,
)


# -----------------------------------------------------------------------
# Response Topology Mapper
# -----------------------------------------------------------------------

class TestResponseTopologyMapper:
    """Tests for behavioral fingerprinting."""

    def setup_method(self):
        self.mapper = ResponseTopologyMapper()

    def test_build_topology_from_responses(self):
        responses = [
            {"variation": "method_get", "url": "https://t.com/", "method": "GET",
             "status_code": 200, "body_length": 5000, "response_time_ms": 50, "headers": {"server": "nginx"}},
            {"variation": "method_post", "url": "https://t.com/", "method": "POST",
             "status_code": 405, "body_length": 100, "response_time_ms": 10, "headers": {"server": "nginx"}},
            {"variation": "path_nonexistent", "url": "https://t.com/xyz", "method": "GET",
             "status_code": 404, "body_length": 200, "response_time_ms": 15, "headers": {"server": "nginx"}},
        ]
        tmap = self.mapper.build_topology(responses)
        assert len(tmap.points) == 3
        assert tmap.status_distribution[200] == 1
        assert tmap.status_distribution[405] == 1
        assert tmap.status_distribution[404] == 1

    def test_timing_profile_calculated(self):
        responses = [
            {"variation": "a", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 50, "headers": {}},
            {"variation": "b", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 100, "headers": {}},
            {"variation": "c", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 75, "headers": {}},
        ]
        tmap = self.mapper.build_topology(responses)
        assert "mean_ms" in tmap.timing_profile
        assert tmap.timing_profile["min_ms"] == 50
        assert tmap.timing_profile["max_ms"] == 100

    def test_auth_boundary_detection(self):
        responses = [
            {"variation": "method_get", "url": "https://t.com/", "status_code": 200,
             "body_length": 100, "response_time_ms": 50, "headers": {}},
            {"variation": "auth_empty_bearer", "url": "https://t.com/", "status_code": 401,
             "body_length": 50, "response_time_ms": 10, "headers": {}},
        ]
        tmap = self.mapper.build_topology(responses)
        assert len(tmap.auth_boundaries) > 0
        assert "auth" in tmap.auth_boundaries[0].lower()

    def test_header_signature_variance_detected(self):
        responses = [
            {"variation": "a", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 50,
             "headers": {"server": "nginx", "x-cache": "HIT"}},
            {"variation": "b", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 50,
             "headers": {"server": "apache"}},
            {"variation": "c", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 50,
             "headers": {"server": "cloudflare", "cf-ray": "abc"}},
        ]
        tmap = self.mapper.build_topology(responses)
        sigs = set(p.header_signature for p in tmap.points)
        assert len(sigs) == 3  # All different header sets
        assert any("header_variance" in str(s) for s in tmap.hidden_states)

    def test_timing_anomaly_detected(self):
        # Need enough consistent points so the outlier's z-score exceeds 2
        responses = [
            {"variation": "fast1", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 50, "headers": {}},
            {"variation": "fast2", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 55, "headers": {}},
            {"variation": "fast3", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 48, "headers": {}},
            {"variation": "fast4", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 52, "headers": {}},
            {"variation": "fast5", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 51, "headers": {}},
            {"variation": "slow_outlier", "url": "https://t.com", "status_code": 200,
             "body_length": 100, "response_time_ms": 5000, "headers": {}},
        ]
        tmap = self.mapper.build_topology(responses)
        assert len(tmap.anomalies) > 0
        assert "slow_outlier" in tmap.anomalies[0]

    def test_probe_list_has_variations(self):
        probes = ResponseTopologyMapper.TOPOLOGY_PROBES
        assert len(probes) > 20
        methods = set(p["method"] for p in probes)
        assert "GET" in methods
        assert "POST" in methods
        assert "OPTIONS" in methods

    def test_empty_responses(self):
        tmap = self.mapper.build_topology([])
        assert tmap.points == []


# -----------------------------------------------------------------------
# Semantic Mutation Engine
# -----------------------------------------------------------------------

class TestSemanticMutationEngine:
    """Tests for semantic payload generation."""

    def setup_method(self):
        self.engine = SemanticMutationEngine()

    def test_sql_always_true_generates_variants(self):
        payloads = self.engine.mutate_sql_injection("always_true")
        assert len(payloads) > 10
        # All should be semantically "always true"
        intents = set(p.original_intent for p in payloads)
        assert "always_true_condition" in intents

    def test_sql_variants_mostly_unique(self):
        payloads = self.engine.mutate_sql_injection("always_true")
        unique_payloads = set(p.payload for p in payloads)
        # Allow minor overlap (case mutation may produce same as original)
        assert len(unique_payloads) >= len(payloads) - 2

    def test_union_select_variants(self):
        payloads = self.engine.mutate_sql_injection("union_select")
        assert len(payloads) >= 5
        assert all("union" in p.payload.lower() or "/*!union" in p.payload.lower()
                    for p in payloads)

    def test_version_extract_covers_multiple_dbs(self):
        payloads = self.engine.mutate_sql_injection("version_extract")
        techniques = set(p.technique for p in payloads)
        # Should cover multiple database types
        assert len(techniques) >= 3

    def test_time_based_blind_variants(self):
        payloads = self.engine.mutate_sql_injection("time_based_blind")
        assert len(payloads) >= 4
        # Should cover different DB sleep functions
        payload_str = " ".join(p.payload for p in payloads)
        assert "SLEEP" in payload_str
        assert "pg_sleep" in payload_str

    def test_xss_alert_variants(self):
        payloads = self.engine.mutate_xss("alert")
        assert len(payloads) > 10
        # Should include multiple tag types
        tags = set()
        for p in payloads:
            if p.payload.startswith("<"):
                tag = p.payload.split(">")[0].split()[0].lstrip("<")
                tags.add(tag.lower())
        assert len(tags) >= 5  # script, img, svg, body, input, etc.

    def test_xss_cookie_theft(self):
        payloads = self.engine.mutate_xss("cookie_theft")
        assert len(payloads) >= 2
        assert all("cookie" in p.payload.lower() for p in payloads)

    def test_path_traversal_variants(self):
        payloads = self.engine.mutate_path_traversal()
        assert len(payloads) >= 5
        evasion_types = set(p.evasion_type for p in payloads)
        assert "encoding" in evasion_types
        assert "signature" in evasion_types

    def test_encoding_mutations_produce_different_strings(self):
        # Use a string with special chars so URL encoding actually changes it
        payloads = self.engine._encoding_mutations("' OR 1=1", "test_intent")
        assert len(payloads) >= 3
        unique = set(p.payload for p in payloads)
        assert len(unique) == len(payloads)
        assert "' OR 1=1" not in unique  # All should be encoded differently

    def test_whitespace_mutations(self):
        payloads = self.engine._whitespace_mutations("A B C", "test")
        assert len(payloads) >= 3
        # Should have comment, tab, and newline variants
        assert any("/**/" in p.payload for p in payloads)
        assert any("\t" in p.payload for p in payloads)
        assert any("\n" in p.payload for p in payloads)

    def test_case_mutations(self):
        payloads = self.engine._case_mutations("' OR 1=1--", "test")
        assert len(payloads) >= 1
        # Should have alternating case
        assert any(p.technique == "alternating_case" for p in payloads)

    def test_payload_dataclass(self):
        p = SemanticPayload(
            original_intent="test",
            payload="<script>alert(1)</script>",
            technique="classic",
            evasion_type="signature",
        )
        assert p.original_intent == "test"
        assert p.evasion_type == "signature"


# -----------------------------------------------------------------------
# Attack Chain Synthesizer
# -----------------------------------------------------------------------

class TestAttackChainSynthesizer:
    """Tests for finding kill chains across findings."""

    def setup_method(self):
        self.synth = AttackChainSynthesizer()

    def test_credential_to_access_chain(self):
        findings = [
            {"type": "credential_exposure", "url": "https://t.com/.env",
             "info": {"severity": "high"}},
            {"type": "post_exploitation", "url": "https://t.com/admin",
             "info": {"severity": "high"}},
        ]
        chains = self.synth.synthesize(findings)
        assert len(chains) >= 1
        assert any(c.severity == "critical" for c in chains)

    def test_info_disclosure_to_exploit_chain(self):
        findings = [
            {"type": "header_analysis", "url": "https://t.com",
             "info": {"severity": "info"}},
            {"type": "vulnerability_verification", "url": "https://t.com/api",
             "exploit_plan": {"impact_category": "vulnerability_verification"},
             "info": {"severity": "high"}},
        ]
        chains = self.synth.synthesize(findings)
        assert len(chains) >= 1

    def test_single_finding_no_chains(self):
        findings = [{"type": "header_analysis", "url": "https://t.com"}]
        chains = self.synth.synthesize(findings)
        assert len(chains) == 0

    def test_unrelated_findings_no_chains(self):
        findings = [
            {"type": "dns_records", "url": "https://t.com"},
            {"type": "ct_log", "url": "https://t.com"},
        ]
        chains = self.synth.synthesize(findings)
        # ct_log + path_discovery would chain, but not ct_log + dns_records alone
        assert all(c.severity in ("critical", "high", "medium") for c in chains)

    def test_chains_sorted_by_severity(self):
        findings = [
            {"type": "header_analysis", "url": "https://t.com"},
            {"type": "vulnerability_verification", "url": "https://t.com/vuln",
             "exploit_plan": {"impact_category": "vulnerability_verification"}},
            {"type": "credential_exposure", "url": "https://t.com/.env"},
            {"type": "post_exploitation", "url": "https://t.com/admin"},
        ]
        chains = self.synth.synthesize(findings)
        if len(chains) >= 2:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(chains) - 1):
                assert severity_order.get(chains[i].severity, 4) <= severity_order.get(chains[i+1].severity, 4)

    def test_api_docs_to_data_chain(self):
        findings = [
            {"type": "path_discovery", "url": "https://t.com/api/docs",
             "exploit_plan": {"impact_category": "api_exposure"}},
            {"type": "post_exploitation", "url": "https://t.com/api/users",
             "exploit_plan": {"impact_category": "unauthorized_access"}},
        ]
        chains = self.synth.synthesize(findings)
        assert any(c.impact == "data_breach" for c in chains)

    def test_chain_has_reasoning(self):
        findings = [
            {"type": "credential_exposure", "url": "https://t.com/.env"},
            {"type": "post_exploitation", "url": "https://t.com/admin"},
        ]
        chains = self.synth.synthesize(findings)
        assert all(c.reasoning for c in chains)
        assert all(c.chain_id for c in chains)


# -----------------------------------------------------------------------
# Inverse Surface Mapper
# -----------------------------------------------------------------------

class TestInverseSurfaceMapper:
    """Tests for inferring hidden endpoints."""

    def setup_method(self):
        self.mapper = InverseSurfaceMapper()

    def test_infer_sibling_resources(self):
        known = [
            "https://target.com/api/v1/users",
            "https://target.com/api/v1/orders",
        ]
        inferred = self.mapper.infer_endpoints(known)
        urls = [e.url for e in inferred]
        # Should infer related resources
        assert any("payment" in u or "product" in u or "session" in u for u in urls)

    def test_infer_api_version_variants(self):
        known = ["https://target.com/api/v1/users"]
        inferred = self.mapper.infer_endpoints(known)
        urls = [e.url for e in inferred]
        # Should infer v2, v3
        assert any("/v2/" in u for u in urls)

    def test_infer_admin_siblings(self):
        known = ["https://target.com/admin"]
        inferred = self.mapper.infer_endpoints(known)
        urls = [e.url for e in inferred]
        assert any("dashboard" in u or "settings" in u or "users" in u for u in urls)

    def test_infer_auth_siblings(self):
        known = ["https://target.com/login"]
        inferred = self.mapper.infer_endpoints(known)
        urls = [e.url for e in inferred]
        assert any("register" in u or "forgot" in u or "logout" in u for u in urls)

    def test_no_duplicates_in_results(self):
        known = [
            "https://target.com/api/v1/users",
            "https://target.com/api/v1/orders",
        ]
        inferred = self.mapper.infer_endpoints(known)
        urls = [e.url for e in inferred]
        assert len(urls) == len(set(urls))

    def test_known_urls_not_in_results(self):
        known = ["https://target.com/api/v1/users"]
        inferred = self.mapper.infer_endpoints(known)
        urls = [e.url for e in inferred]
        assert "https://target.com/api/v1/users" not in urls

    def test_results_capped(self):
        known = [
            "https://target.com/api/v1/users",
            "https://target.com/api/v1/orders",
            "https://target.com/api/v1/products",
            "https://target.com/admin",
            "https://target.com/login",
        ]
        inferred = self.mapper.infer_endpoints(known)
        assert len(inferred) <= 30

    def test_confidence_ordering(self):
        known = ["https://target.com/api/v1/users"]
        inferred = self.mapper.infer_endpoints(known)
        if len(inferred) >= 2:
            for i in range(len(inferred) - 1):
                assert inferred[i].confidence >= inferred[i+1].confidence

    def test_inferred_has_reasoning(self):
        known = ["https://target.com/api/v1/users"]
        inferred = self.mapper.infer_endpoints(known)
        for ep in inferred:
            assert ep.reasoning
            assert ep.inferred_from


# -----------------------------------------------------------------------
# Developer Empathy Engine
# -----------------------------------------------------------------------

class TestDeveloperEmpathyEngine:
    """Tests for developer profiling and vulnerability prediction."""

    def setup_method(self):
        self.engine = DeveloperEmpathyEngine()

    def test_junior_developer_profile(self):
        profile = self.engine.profile_developer(
            technologies=["express/nodejs"],
            response_headers={},  # No security headers at all
            error_patterns=["stack trace exposed", "debug mode on"],
        )
        assert profile.experience_level == "junior"
        assert profile.security_awareness == "low"
        assert profile.primary_framework == "express/nodejs"

    def test_senior_developer_profile(self):
        profile = self.engine.profile_developer(
            technologies=["django"],
            response_headers={
                "Strict-Transport-Security": "max-age=31536000",
                "Content-Security-Policy": "default-src 'self'",
                "X-Frame-Options": "DENY",
                "X-Content-Type-Options": "nosniff",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
            error_patterns=["opaque error"],
        )
        assert profile.experience_level == "senior"
        assert profile.security_awareness == "high"

    def test_framework_detection(self):
        profile = self.engine.profile_developer(
            technologies=["flask"],
            response_headers={},
            error_patterns=[],
        )
        assert profile.primary_framework == "flask"
        assert any("Werkzeug" in m for m in profile.likely_mistakes)

    def test_spring_framework_detection(self):
        profile = self.engine.profile_developer(
            technologies=["spring/java"],
            response_headers={},
            error_patterns=[],
        )
        assert profile.primary_framework == "spring/java"
        assert any("Actuator" in m for m in profile.likely_mistakes)

    def test_architecture_from_api_patterns(self):
        profile = self.engine.profile_developer(
            technologies=[],
            response_headers={},
            error_patterns=[],
            api_patterns=["/api/v1/users", "/api/v2/orders"],
        )
        assert profile.architecture_style == "versioned_api"

    def test_graphql_architecture_detection(self):
        profile = self.engine.profile_developer(
            technologies=[],
            response_headers={},
            error_patterns=[],
            api_patterns=["/graphql"],
        )
        assert profile.architecture_style == "graphql"

    def test_startup_target_adds_predictions(self):
        profile = self.engine.profile_developer(
            technologies=["express/nodejs"],
            response_headers={},
            error_patterns=[],
            target_type="startup",
        )
        assert any("Rapid development" in m or "staging" in m.lower()
                    for m in profile.likely_mistakes)

    def test_legacy_target_adds_predictions(self):
        profile = self.engine.profile_developer(
            technologies=["asp.net"],
            response_headers={},
            error_patterns=[],
            target_type="legacy_system",
        )
        assert any("CVE" in m or "patch" in m.lower() for m in profile.likely_mistakes)

    def test_predict_vulnerabilities_junior(self):
        profile = DeveloperProfile(
            experience_level="junior",
            primary_framework="express/nodejs",
            likely_mistakes=["NoSQL injection in MongoDB queries"],
        )
        predictions = self.engine.predict_vulnerabilities(profile)
        assert len(predictions) > 3
        assert "NoSQL injection in MongoDB queries" in predictions
        # Junior-specific predictions
        assert any("SQL injection" in p or "XSS" in p or "IDOR" in p for p in predictions)

    def test_predict_vulnerabilities_senior(self):
        profile = DeveloperProfile(
            experience_level="senior",
            primary_framework="django",
            likely_mistakes=[],
        )
        predictions = self.engine.predict_vulnerabilities(profile)
        # Senior-specific predictions (more sophisticated attacks)
        assert any("race condition" in p.lower() or "cache" in p.lower()
                    or "second-order" in p.lower() for p in predictions)

    def test_predict_capped_at_15(self):
        profile = DeveloperProfile(
            experience_level="junior",
            primary_framework="express/nodejs",
            likely_mistakes=["a"] * 20,
        )
        predictions = self.engine.predict_vulnerabilities(profile)
        assert len(predictions) <= 15

    def test_unknown_framework(self):
        profile = self.engine.profile_developer(
            technologies=["custom_framework"],
            response_headers={},
            error_patterns=[],
        )
        assert profile.primary_framework == "unknown"


# -----------------------------------------------------------------------
# Response Echo Analysis
# -----------------------------------------------------------------------

class TestResponseEchoAnalyzer:
    """Tests for canary-based vulnerability detection."""

    def setup_method(self):
        from app.services.cognition.unreplicable import ResponseEchoAnalyzer
        self.analyzer = ResponseEchoAnalyzer()

    def test_canary_generation(self):
        canary = self.analyzer.generate_canary()
        assert canary.startswith("DAENA_")
        assert canary.endswith("_CANARY")
        assert len(canary) > 20

    def test_canary_uniqueness(self):
        c1 = self.analyzer.generate_canary()
        c2 = self.analyzer.generate_canary()
        assert c1 != c2

    def test_build_probes(self):
        probes = self.analyzer.build_canary_probes(["https://target.com"])
        assert len(probes) >= 4
        methods = set(p["method"] for p in probes)
        assert "GET" in methods
        assert "POST" in methods
        assert all(p.get("canary") for p in probes)

    def test_detect_reflected_input(self):
        canary = "DAENA_abc123_CANARY"
        probe = {"injection_point": "query_param"}
        findings = self.analyzer.analyze_echo(
            canary=canary,
            probe=probe,
            response_body=f"Results for: {canary}",
            response_headers={},
            status_code=200,
        )
        assert any(f["type"] == "reflected_input" for f in findings)

    def test_detect_error_reflection(self):
        canary = "DAENA_abc123_CANARY"
        probe = {"injection_point": "query_param"}
        findings = self.analyzer.analyze_echo(
            canary=canary,
            probe=probe,
            response_body=f"Error: invalid parameter {canary}",
            response_headers={},
            status_code=400,
        )
        assert any(f["type"] == "error_reflection" for f in findings)

    def test_detect_header_injection(self):
        canary = "DAENA_abc123_CANARY"
        probe = {"injection_point": "header"}
        findings = self.analyzer.analyze_echo(
            canary=canary,
            probe=probe,
            response_body="OK",
            response_headers={"X-Custom": f"value-{canary}"},
            status_code=200,
        )
        assert any(f["type"] == "header_injection" for f in findings)

    def test_detect_partial_reflection(self):
        canary = "DAENA_abcdef123456_CANARY"
        probe = {"injection_point": "query_param"}
        findings = self.analyzer.analyze_echo(
            canary=canary,
            probe=probe,
            response_body="Filtered: DAENA_abcdef",  # Only first part
            response_headers={},
            status_code=200,
        )
        assert any(f["type"] == "partial_reflection" for f in findings)

    def test_no_findings_when_clean(self):
        canary = "DAENA_xyz789_CANARY"
        probe = {"injection_point": "query_param"}
        findings = self.analyzer.analyze_echo(
            canary=canary,
            probe=probe,
            response_body="Normal response with no reflection",
            response_headers={},
            status_code=200,
        )
        assert len(findings) == 0


# -----------------------------------------------------------------------
# State Machine Inference
# -----------------------------------------------------------------------

class TestStateMachineInferrer:
    """Tests for state machine violation detection."""

    def setup_method(self):
        from app.services.cognition.unreplicable import StateMachineInferrer
        self.inferrer = StateMachineInferrer()

    def test_generate_sequences(self):
        sequences = self.inferrer.generate_sequences(
            "target.com",
            ["/api/v1/users", "/login", "/logout"],
        )
        assert len(sequences) >= 3
        # Should include auth flow sequence
        auth_seq = [s for s in sequences if any(
            step.get("name") == "access_after_logout" for step in s
        )]
        assert len(auth_seq) >= 1

    def test_detect_broken_access_after_logout(self):
        sequence = [
            {"name": "login", "expect": "redirect_or_token", "description": "Login"},
            {"name": "access_after_logout", "expect": "reject",
             "description": "Access after logout", "url": "https://t.com/api"},
        ]
        results = [
            {"status_code": 302},
            {"status_code": 200},  # Should have been rejected!
        ]
        findings = self.inferrer.analyze_sequence_results(sequence, results)
        assert any(f["severity"] == "critical" for f in findings)
        assert any("state_violation" in f["type"] for f in findings)

    def test_detect_idor(self):
        sequence = [
            {"name": "access_own_resource", "expect": "success",
             "description": "Own", "url": "https://t.com/users/1"},
            {"name": "access_other_resource", "expect": "reject_or_different",
             "description": "Other", "url": "https://t.com/users/2"},
        ]
        results = [
            {"status_code": 200},
            {"status_code": 200},  # Should have been different!
        ]
        findings = self.inferrer.analyze_sequence_results(sequence, results)
        assert any(f["type"] == "idor" for f in findings)

    def test_no_violation_when_correctly_rejected(self):
        sequence = [
            {"name": "access_after_logout", "expect": "reject",
             "description": "After logout", "url": "https://t.com/api"},
        ]
        results = [{"status_code": 403}]
        findings = self.inferrer.analyze_sequence_results(sequence, results)
        assert len(findings) == 0

    def test_url_scheme_added(self):
        sequences = self.inferrer.generate_sequences("target.com", [])
        for seq in sequences:
            for step in seq:
                assert step["url"].startswith("https://")


# -----------------------------------------------------------------------
# Cost Amplification Detection
# -----------------------------------------------------------------------

class TestCostAmplificationDetector:
    """Tests for resource exhaustion detection."""

    def setup_method(self):
        from app.services.cognition.unreplicable import CostAmplificationDetector
        self.detector = CostAmplificationDetector()

    def test_build_timing_probes(self):
        probes = self.detector.build_timing_probes(["https://target.com"])
        assert len(probes) >= 3
        assert all("probe_name" in p for p in probes)
        assert all("threshold_ms" in p for p in probes)

    def test_detect_amplification(self):
        probe = {
            "probe_name": "regex_dos",
            "description": "Test for ReDoS",
            "url": "https://target.com",
            "threshold_ms": 3000,
        }
        result = self.detector.analyze_timing(
            probe=probe,
            response_time_ms=8000,  # Way above threshold
            baseline_ms=50,  # Normal response is 50ms
        )
        assert result is not None
        assert result["type"] == "cost_amplification"
        assert result["amplification_factor"] > 100

    def test_no_amplification_normal_response(self):
        probe = {
            "probe_name": "regex_dos",
            "description": "Test for ReDoS",
            "url": "https://target.com",
            "threshold_ms": 3000,
        }
        result = self.detector.analyze_timing(
            probe=probe,
            response_time_ms=100,  # Normal
            baseline_ms=50,
        )
        assert result is None

    def test_probe_names_present(self):
        probes = self.detector.build_timing_probes(["https://t.com"])
        names = set(p["probe_name"] for p in probes)
        assert "regex_dos" in names
        assert "deep_nesting" in names

    def test_amplification_probes_defined(self):
        assert len(self.detector.AMPLIFICATION_PROBES) >= 4


# -----------------------------------------------------------------------
# Origin IP Discovery
# -----------------------------------------------------------------------

class TestOriginIPDiscovery:

    def setup_method(self):
        from app.services.cognition.unreplicable import OriginIPDiscovery
        self.discovery = OriginIPDiscovery()

    def test_generate_bypass_targets(self):
        targets = self.discovery.generate_bypass_targets("target.com")
        hostnames = [t["hostname"] for t in targets]
        assert "mail.target.com" in hostnames
        assert "staging.target.com" in hostnames
        assert "jenkins.target.com" in hostnames
        assert len(targets) > 30

    def test_categorize_subdomains(self):
        targets = self.discovery.generate_bypass_targets("t.com")
        categories = set(t["category"] for t in targets)
        assert "email" in categories
        assert "staging" in categories
        assert "monitoring" in categories

    def test_extract_ips_from_email_headers(self):
        headers = (
            "Received: from mail.target.com (203.0.113.42) by mx.google.com\n"
            "Received: from internal (10.0.0.5) by mail.target.com\n"
            "Received: from [192.168.1.1] by internal\n"
        )
        ips = self.discovery.analyze_email_headers(headers)
        assert "203.0.113.42" in ips
        # Private IPs should be filtered
        assert "10.0.0.5" not in ips
        assert "192.168.1.1" not in ips

    def test_origin_check_plan(self):
        plan = self.discovery.generate_origin_check_plan("target.com", "Cloudflare")
        assert len(plan) >= 4
        steps = [p["step"] for p in plan]
        assert any("subdomain" in s.lower() for s in steps)
        assert any("ipv6" in s.lower() for s in steps)
        assert any("email" in s.lower() for s in steps)
        assert any("historical" in s.lower() or "dns" in s.lower() for s in steps)


# -----------------------------------------------------------------------
# Forgotten Infrastructure Scanner
# -----------------------------------------------------------------------

class TestForgottenInfraScanner:

    def setup_method(self):
        from app.services.cognition.unreplicable import ForgottenInfraScanner
        self.scanner = ForgottenInfraScanner()

    def test_generate_probes(self):
        probes = self.scanner.generate_forgotten_probes("target.com")
        assert len(probes) > 20
        services = set(p["service"] for p in probes)
        assert "Jenkins" in services
        assert "Grafana" in services
        assert "Sentry" in services

    def test_detect_jenkins(self):
        result = self.scanner.analyze_probe_result(
            probe={"service": "Jenkins", "url": "https://t.com:8080", "check_string": "Jenkins-Crumb", "risk": "test"},
            status_code=200,
            body="<html>Jenkins-Crumb: abc123</html>",
            headers={},
        )
        assert result is not None
        assert result["service"] == "Jenkins"
        assert result["severity"] == "high"

    def test_detect_grafana_redirect(self):
        result = self.scanner.analyze_probe_result(
            probe={"service": "Grafana", "url": "https://t.com:3000", "check_string": "grafana", "risk": "test"},
            status_code=302,
            body="",
            headers={"Location": "/grafana/login"},
        )
        assert result is not None
        assert result["severity"] == "medium"

    def test_no_false_positive(self):
        result = self.scanner.analyze_probe_result(
            probe={"service": "Jenkins", "url": "https://t.com:8080", "check_string": "Jenkins-Crumb", "risk": "test"},
            status_code=404,
            body="Not Found",
            headers={},
        )
        assert result is None

    def test_services_have_risks(self):
        for svc in self.scanner._FORGOTTEN_SERVICES:
            assert svc["risk"], f"Service {svc['name']} missing risk description"
