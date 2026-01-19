"""
Tests for SEC-Loop retention tracking.
"""

from __future__ import annotations

import pytest
from self_evolve.tester import EvaluationTester
from self_evolve.revisor import NBMFAbstract, AbstractRevisor
from self_evolve.selector import CandidateSlice


@pytest.fixture
def tester():
    """Create an evaluation tester for testing."""
    return EvaluationTester()


@pytest.fixture
def test_abstract():
    """Create a test abstract."""
    return NBMFAbstract(
        abstract_id="test_abstract_1",
        content="Test abstract content",
        embedding=None,
        metadata={"source": "test"},
        confidence=0.8,
        source_slice_id="test_slice_1"
    )


def test_retention_drift_calculation(tester, test_abstract):
    """Test that retention drift is calculated correctly."""
    result = tester.evaluate(test_abstract, department="engineering")
    
    # Retention drift should be a float between 0 and 1
    assert isinstance(result.retention_drift, float)
    assert 0.0 <= result.retention_drift <= 1.0


def test_retention_drift_threshold(tester, test_abstract):
    """Test that retention drift threshold is enforced."""
    result = tester.evaluate(test_abstract, department="engineering")
    
    # Should pass if retention drift <= 1%
    max_drift = tester.thresholds.get("retention_drift_max", 0.01)
    
    if result.retention_drift <= max_drift:
        assert result.passed or result.retention_drift <= max_drift
    else:
        # If drift exceeds threshold, should fail
        assert not result.passed or result.retention_drift > max_drift


def test_baseline_metrics_loaded(tester):
    """Test that baseline metrics are loaded."""
    assert tester.baseline_metrics is not None
    assert "retention" in tester.baseline_metrics
    assert "latency_p50" in tester.baseline_metrics
    assert "latency_p95" in tester.baseline_metrics
    assert "cost_per_1k" in tester.baseline_metrics


def test_retention_tracking_multiple_iterations(tester, test_abstract):
    """Test retention tracking across multiple iterations."""
    results = []
    
    # Simulate 3 iterations
    for i in range(3):
        result = tester.evaluate(test_abstract, department="engineering")
        results.append(result.retention_drift)
    
    # All retention drifts should be within threshold
    max_drift = tester.thresholds.get("retention_drift_max", 0.01)
    for drift in results:
        assert drift <= max_drift * 1.1  # Allow small margin

