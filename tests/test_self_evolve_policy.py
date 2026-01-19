"""
Tests for SEC-Loop policy enforcement.
"""

from __future__ import annotations

import pytest
from self_evolve.policy import CouncilPolicy, DecisionStatus
from self_evolve.tester import EvaluationResult, EvaluationTester


@pytest.fixture
def policy():
    """Create a policy manager for testing."""
    return CouncilPolicy()


@pytest.fixture
def passed_evaluation():
    """Create a passed evaluation result."""
    return EvaluationResult(
        abstract_id="test_abstract_1",
        knowledge_incorporation=0.05,  # 5% improvement
        retention_drift=0.005,  # 0.5% drift
        latency_p50=0.1,
        latency_p95=0.2,
        latency_change_p50=0.02,  # 2% increase
        latency_change_p95=0.03,  # 3% increase
        cost_per_1k=0.7,  # 30% reduction
        cost_reduction=0.30,
        abac_compliant=True,
        passed=True,
        metrics={}
    )


@pytest.fixture
def failed_evaluation():
    """Create a failed evaluation result."""
    return EvaluationResult(
        abstract_id="test_abstract_2",
        knowledge_incorporation=0.01,  # 1% improvement (below threshold)
        retention_drift=0.02,  # 2% drift (above threshold)
        latency_p50=0.1,
        latency_p95=0.2,
        latency_change_p50=0.02,
        latency_change_p95=0.10,  # 10% increase (above threshold)
        cost_per_1k=0.9,  # 10% reduction (below threshold)
        cost_reduction=0.10,
        abac_compliant=True,
        passed=False,
        metrics={}
    )


def test_policy_approves_passed_evaluation(policy, passed_evaluation):
    """Test that policy approves passed evaluations."""
    decision = policy.make_decision(
        passed_evaluation,
        department="engineering",
        tenant_id="test_tenant"
    )
    
    # Should be PROMOTE or HOLD (depending on quorum)
    assert decision.status in [DecisionStatus.PROMOTE, DecisionStatus.HOLD]
    assert decision.abstract_id == passed_evaluation.abstract_id
    assert decision.department == "engineering"


def test_policy_rejects_failed_evaluation(policy, failed_evaluation):
    """Test that policy rejects failed evaluations."""
    decision = policy.make_decision(
        failed_evaluation,
        department="engineering",
        tenant_id="test_tenant"
    )
    
    # Should be REJECT
    assert decision.status == DecisionStatus.REJECT
    assert decision.abstract_id == failed_evaluation.abstract_id
    assert "Evaluation failed" in decision.reasoning


def test_policy_quorum_requirement(policy, passed_evaluation):
    """Test that policy requires quorum for promotion."""
    decision = policy.make_decision(
        passed_evaluation,
        department="engineering",
        tenant_id="test_tenant",
        cell_id="D1"  # Engineering department
    )
    
    # Decision should have quorum information
    assert decision.quorum_reached is not None
    assert isinstance(decision.votes, dict)


def test_policy_tenant_isolation(policy, passed_evaluation):
    """Test that policy enforces tenant isolation."""
    decision1 = policy.make_decision(
        passed_evaluation,
        department="engineering",
        tenant_id="tenant_1"
    )
    
    decision2 = policy.make_decision(
        passed_evaluation,
        department="engineering",
        tenant_id="tenant_2"
    )
    
    # Decisions should be separate
    assert decision1.decision_id != decision2.decision_id
    assert decision1.tenant_id == "tenant_1"
    assert decision2.tenant_id == "tenant_2"

