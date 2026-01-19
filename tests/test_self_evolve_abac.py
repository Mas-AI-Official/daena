"""
Tests for SEC-Loop ABAC compliance.
"""

from __future__ import annotations

import pytest
from self_evolve.tester import EvaluationTester
from self_evolve.revisor import NBMFAbstract
from self_evolve.selector import DataSelector, CandidateSlice


@pytest.fixture
def tester():
    """Create an evaluation tester for testing."""
    return EvaluationTester()


@pytest.fixture
def selector():
    """Create a data selector for testing."""
    return DataSelector()


@pytest.fixture
def tenant_abstract():
    """Create an abstract with tenant ID."""
    return NBMFAbstract(
        abstract_id="test_abstract_tenant_1",
        content="Test content",
        embedding=None,
        metadata={"source": "test"},
        confidence=0.8,
        tenant_id="tenant_1",
        project_id="project_1"
    )


@pytest.fixture
def cross_tenant_abstract():
    """Create an abstract with different tenant ID."""
    return NBMFAbstract(
        abstract_id="test_abstract_tenant_2",
        content="Test content",
        embedding=None,
        metadata={"source": "test"},
        confidence=0.8,
        tenant_id="tenant_2",  # Different tenant
        project_id="project_2"
    )


def test_abac_compliance_check(tester, tenant_abstract):
    """Test that ABAC compliance is checked."""
    result = tester.evaluate(tenant_abstract, department="engineering", tenant_id="tenant_1")
    
    # Should check ABAC compliance
    assert hasattr(result, "abac_compliant")
    assert isinstance(result.abac_compliant, bool)


def test_abac_tenant_isolation(tester, tenant_abstract, cross_tenant_abstract):
    """Test that tenant isolation is enforced."""
    # Evaluate with matching tenant
    result1 = tester.evaluate(tenant_abstract, department="engineering", tenant_id="tenant_1")
    
    # Evaluate with mismatched tenant
    result2 = tester.evaluate(cross_tenant_abstract, department="engineering", tenant_id="tenant_1")
    
    # Result 1 should be compliant (matching tenant)
    # Result 2 should be non-compliant (mismatched tenant)
    assert result1.abac_compliant is True
    assert result2.abac_compliant is False


def test_abac_required_for_promotion(tester, tenant_abstract):
    """Test that ABAC compliance is required for promotion."""
    result = tester.evaluate(tenant_abstract, department="engineering", tenant_id="tenant_1")
    
    # If ABAC fails, overall should fail
    if not result.abac_compliant:
        assert not result.passed


def test_selector_tenant_safety(selector):
    """Test that selector enforces tenant safety."""
    candidate = CandidateSlice(
        slice_id="test_slice_1",
        content="Test content",
        source="benchmark",
        confidence=0.8,
        metadata={},
        tenant_id="tenant_1"
    )
    
    # Should validate tenant safety
    is_safe = selector.validate_tenant_safety(candidate, tenant_id="tenant_1")
    assert is_safe is True
    
    # Should reject mismatched tenant
    is_safe_mismatch = selector.validate_tenant_safety(candidate, tenant_id="tenant_2")
    assert is_safe_mismatch is False


def test_selector_tenant_safety_disabled(selector):
    """Test that tenant safety can be disabled."""
    # Temporarily disable tenant safety
    original_tenant_safe = selector.tenant_safe
    selector.tenant_safe = False
    
    candidate = CandidateSlice(
        slice_id="test_slice_1",
        content="Test content",
        source="benchmark",
        confidence=0.8,
        metadata={},
        tenant_id="tenant_1"
    )
    
    # Should pass when tenant safety disabled
    is_safe = selector.validate_tenant_safety(candidate, tenant_id="tenant_2")
    assert is_safe is True
    
    # Restore original setting
    selector.tenant_safe = original_tenant_safe

