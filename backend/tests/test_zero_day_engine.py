"""Tests for Zero-Day Discovery Engine."""

import pytest

from app.services.security.zero_day_engine import (
    SpecGapAnalyzer,
    LogicFlowAnalyzer,
    SupplyChainAttackPlanner,
    SupplyChainRisk,
    ZeroDayCandidate,
)


class TestSpecGapAnalyzer:

    def test_http_gaps_found(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(["nginx"], headers={})
        http_candidates = [c for c in candidates if "HTTP" in c.title]
        assert len(http_candidates) >= 1

    def test_jwt_gaps_when_detected(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(["jwt", "express"])
        jwt_candidates = [c for c in candidates if "JWT" in c.title]
        assert len(jwt_candidates) >= 1
        assert any(c.severity == "critical" for c in jwt_candidates)

    def test_oauth_gaps_when_detected(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(["oauth", "auth0"])
        oauth_candidates = [c for c in candidates if "OAUTH" in c.title]
        assert len(oauth_candidates) >= 1

    def test_cors_from_headers(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(
            ["express"],
            headers={"access-control-allow-origin": "*"},
        )
        cors_candidates = [c for c in candidates if "CORS" in c.title]
        assert len(cors_candidates) >= 1
        assert any(c.confidence >= 0.7 for c in cors_candidates)

    def test_graphql_gaps(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(
            ["graphql"],
            endpoints=["/graphql"],
        )
        gql_candidates = [c for c in candidates if "GRAPHQL" in c.title]
        assert len(gql_candidates) >= 1

    def test_api_design_always_checked(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(["unknown-tech"])
        api_candidates = [c for c in candidates if "API_DESIGN" in c.title]
        assert len(api_candidates) >= 1

    def test_candidate_has_reasoning_chain(self):
        analyzer = SpecGapAnalyzer()
        candidates = analyzer.analyze_target(["nginx"])
        for c in candidates:
            assert len(c.reasoning_chain) >= 2
            assert c.cwe  # Should have CWE reference

    def test_all_protocols_covered(self):
        analyzer = SpecGapAnalyzer()
        assert "http" in analyzer._SPEC_GAPS
        assert "oauth" in analyzer._SPEC_GAPS
        assert "jwt" in analyzer._SPEC_GAPS
        assert "cors" in analyzer._SPEC_GAPS
        assert "graphql" in analyzer._SPEC_GAPS
        assert "api_design" in analyzer._SPEC_GAPS


class TestLogicFlowAnalyzer:

    def test_finds_idor(self):
        analyzer = LogicFlowAnalyzer()
        candidates = analyzer.analyze_endpoints([
            {"path": "/api/users/{user_id}/profile", "params": "user_id"},
        ])
        assert len(candidates) >= 1
        assert any("IDOR" in c.title or "object reference" in c.title.lower() for c in candidates)

    def test_finds_race_condition(self):
        analyzer = LogicFlowAnalyzer()
        candidates = analyzer.analyze_endpoints([
            {"path": "/api/transfer", "params": "amount,balance"},
        ])
        race_candidates = [c for c in candidates if "race" in c.title.lower() or "Race" in c.title]
        assert len(race_candidates) >= 1

    def test_finds_price_manipulation(self):
        analyzer = LogicFlowAnalyzer()
        candidates = analyzer.analyze_endpoints([
            {"path": "/api/checkout", "params": "price,quantity,total"},
        ])
        price_candidates = [c for c in candidates if "price" in c.title.lower() or "Price" in c.title]
        assert len(price_candidates) >= 1
        assert any(c.severity == "critical" for c in price_candidates)

    def test_finds_admin_access(self):
        analyzer = LogicFlowAnalyzer()
        candidates = analyzer.analyze_endpoints([
            {"path": "/admin/users/delete", "params": "id"},
        ])
        admin_candidates = [c for c in candidates if "access control" in c.title.lower() or "admin" in c.description.lower()]
        assert len(admin_candidates) >= 1

    def test_empty_endpoints(self):
        analyzer = LogicFlowAnalyzer()
        candidates = analyzer.analyze_endpoints([])
        assert candidates == []

    def test_confidence_increases_with_matches(self):
        analyzer = LogicFlowAnalyzer()
        single = analyzer.analyze_endpoints([
            {"path": "/api/order", "params": "id"},
        ])
        multi = analyzer.analyze_endpoints([
            {"path": "/api/order/checkout", "params": "price,quantity,total,amount"},
        ])
        # More matching indicators should give higher confidence
        if single and multi:
            max_single = max(c.confidence for c in single)
            max_multi = max(c.confidence for c in multi)
            assert max_multi >= max_single


class TestSupplyChainAttackPlanner:

    def test_dependency_confusion_detected(self):
        planner = SupplyChainAttackPlanner()
        risks = planner.analyze_dependencies([
            {"name": "internal-auth-lib", "version": "1.0.0"},
        ])
        confusion_risks = [r for r in risks if r.attack_type == "dependency_confusion"]
        assert len(confusion_risks) >= 1
        assert confusion_risks[0].severity == "critical"

    def test_typosquatting_detected(self):
        planner = SupplyChainAttackPlanner()
        risks = planner.analyze_dependencies([
            {"name": "lodahs", "version": "4.17.0"},  # Typo of lodash
        ])
        typo_risks = [r for r in risks if r.attack_type == "typosquatting"]
        assert len(typo_risks) >= 1
        assert "lodash" in typo_risks[0].description

    def test_no_false_positive_on_exact_name(self):
        planner = SupplyChainAttackPlanner()
        risks = planner.analyze_dependencies([
            {"name": "lodash", "version": "4.17.21"},
        ])
        typo_risks = [r for r in risks if r.attack_type == "typosquatting"]
        assert len(typo_risks) == 0

    def test_build_pipeline_always_included(self):
        planner = SupplyChainAttackPlanner()
        risks = planner.analyze_dependencies([
            {"name": "react", "version": "18.0.0"},
        ])
        pipeline_risks = [r for r in risks if r.attack_type == "build_pipeline_injection"]
        assert len(pipeline_risks) >= 1

    def test_campaign_plan_structure(self):
        planner = SupplyChainAttackPlanner()
        campaign = planner.plan_campaign(
            target_org="TechCorp",
            technologies=["react", "node", "docker"],
        )
        assert campaign["target"] == "TechCorp"
        assert len(campaign["stages"]) >= 5
        assert "recommended_defenses" in campaign
        # Verify stages are in order
        for i, stage in enumerate(campaign["stages"]):
            assert stage["stage"] == i + 1
            assert "name" in stage
            assert "actions" in stage
            assert "opsec" in stage

    def test_edit_distance(self):
        assert SupplyChainAttackPlanner._edit_distance("lodash", "lodash") == 0
        assert SupplyChainAttackPlanner._edit_distance("lodash", "lodahs") == 2
        assert SupplyChainAttackPlanner._edit_distance("lodash", "lodashs") == 1
        assert SupplyChainAttackPlanner._edit_distance("react", "raect") == 2

    def test_pypi_ecosystem(self):
        planner = SupplyChainAttackPlanner()
        risks = planner.analyze_dependencies([
            {"name": "reqeusts", "version": "2.28.0"},  # Typo of requests
        ], ecosystem="pypi")
        typo_risks = [r for r in risks if r.attack_type == "typosquatting"]
        assert len(typo_risks) >= 1
        assert typo_risks[0].ecosystem == "pypi"

    def test_scoped_package_detected_as_internal(self):
        planner = SupplyChainAttackPlanner()
        risks = planner.analyze_dependencies([
            {"name": "@company/auth-utils", "version": "3.0.0"},
        ])
        confusion_risks = [r for r in risks if r.attack_type == "dependency_confusion"]
        assert len(confusion_risks) >= 1

    def test_supply_chain_risk_dataclass(self):
        risk = SupplyChainRisk(
            attack_type="dependency_confusion",
            target_package="internal-lib",
            ecosystem="npm",
            description="Test risk",
            exploitation_steps=["step1", "step2"],
        )
        assert risk.severity == "high"
        assert risk.real_world_examples == []
