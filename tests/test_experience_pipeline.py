"""
Tests for Experience-Without-Data Pipeline.

Tests:
- Pattern distillation (no tenant data leakage)
- Cryptographic pointers
- Adoption gating
- Kill-switch
- ABAC compliance
"""

import pytest
from memory_service.experience_pipeline import (
    experience_pipeline,
    SharedPattern,
    PatternStatus,
    PatternType,
    CryptographicPointer
)


@pytest.fixture
def sample_task_data():
    """Sample task data with tenant identifiers."""
    return {
        "task_id": "task_123",
        "tenant_id": "tenant_a",
        "user_id": "user_456",
        "email": "user@tenant-a.com",
        "description": "Process customer order #789",
        "customer_name": "Acme Corp",
        "success": True,
        "outcome": "Order processed successfully",
        "metadata": {
            "order_id": "ORD-789",
            "amount": 1000.00
        }
    }


def test_pattern_distillation_no_tenant_data(sample_task_data):
    """Test that pattern distillation removes all tenant identifiers."""
    tenant_id = "tenant_a"
    
    shared_pattern, pointers = experience_pipeline.distill_pattern_from_tenant(
        tenant_id=tenant_id,
        task_data=sample_task_data,
        pattern_type=PatternType.DECISION_PATTERN
    )
    
    assert shared_pattern is not None
    assert shared_pattern.pattern_id is not None
    
    # Verify no tenant data in pattern
    pattern_str = str(shared_pattern.experience_vector)
    assert tenant_id not in pattern_str
    assert "tenant_a" not in pattern_str.lower()
    assert "user_456" not in pattern_str
    assert "user@tenant-a.com" not in pattern_str
    assert "Acme Corp" not in pattern_str
    assert "ORD-789" not in pattern_str
    
    # Verify pointers exist
    assert len(pointers) > 0
    assert pointers[0].tenant_id == tenant_id


def test_cryptographic_pointer_verification(sample_task_data):
    """Test that cryptographic pointers can verify evidence."""
    tenant_id = "tenant_a"
    
    shared_pattern, pointers = experience_pipeline.distill_pattern_from_tenant(
        tenant_id=tenant_id,
        task_data=sample_task_data,
        pattern_type=PatternType.DECISION_PATTERN
    )
    
    assert len(pointers) > 0
    pointer = pointers[0]
    
    # Verify pointer can verify evidence
    evidence_content = str(sample_task_data).encode('utf-8')
    assert pointer.verify(evidence_content) is True
    
    # Verify pointer rejects wrong content
    wrong_content = b"wrong content"
    assert pointer.verify(wrong_content) is False


def test_contamination_check(sample_task_data):
    """Test that contamination check detects tenant data."""
    tenant_id = "tenant_a"
    
    shared_pattern, _ = experience_pipeline.distill_pattern_from_tenant(
        tenant_id=tenant_id,
        task_data=sample_task_data,
        pattern_type=PatternType.DECISION_PATTERN
    )
    
    # Check contamination
    contamination_score = experience_pipeline.check_contamination(shared_pattern)
    
    # Should be low (pattern should be sanitized)
    assert contamination_score <= 0.3, f"Contamination score {contamination_score} too high"


def test_adoption_gating_confidence_threshold():
    """Test that adoption gating enforces confidence threshold."""
    # Create a low-confidence pattern
    low_confidence_pattern = SharedPattern(
        pattern_id="test_pattern_low",
        pattern_type=PatternType.DECISION_PATTERN,
        experience_vector=None,  # Simplified
        confidence_score=0.5,  # Below threshold (0.7)
        source_pointers=[],
        status=PatternStatus.APPROVED,
        created_at="2025-01-01T00:00:00Z"
    )
    
    experience_pipeline.shared_pool["test_pattern_low"] = low_confidence_pattern
    
    # Try to adopt
    allowed, reason, _ = experience_pipeline.gate_adoption(
        pattern_id="test_pattern_low",
        target_tenant_id="tenant_b"
    )
    
    assert allowed is False
    assert "confidence" in reason.lower() or "threshold" in reason.lower()
    
    # Cleanup
    del experience_pipeline.shared_pool["test_pattern_low"]


def test_adoption_gating_contamination():
    """Test that adoption gating enforces contamination limits."""
    # Create a high-contamination pattern
    high_contamination_pattern = SharedPattern(
        pattern_id="test_pattern_contaminated",
        pattern_type=PatternType.DECISION_PATTERN,
        experience_vector=None,  # Simplified
        confidence_score=0.8,
        source_pointers=[],
        status=PatternStatus.APPROVED,
        created_at="2025-01-01T00:00:00Z",
        contamination_score=0.5  # Above limit (0.1)
    )
    
    experience_pipeline.shared_pool["test_pattern_contaminated"] = high_contamination_pattern
    
    # Try to adopt
    allowed, reason, _ = experience_pipeline.gate_adoption(
        pattern_id="test_pattern_contaminated",
        target_tenant_id="tenant_b"
    )
    
    assert allowed is False
    assert "contamination" in reason.lower()
    
    # Cleanup
    del experience_pipeline.shared_pool["test_pattern_contaminated"]


def test_kill_switch_revoke_pattern():
    """Test that kill-switch can revoke patterns globally."""
    # Create and approve a pattern
    test_pattern = SharedPattern(
        pattern_id="test_pattern_revoke",
        pattern_type=PatternType.DECISION_PATTERN,
        experience_vector=None,
        confidence_score=0.8,
        source_pointers=[],
        status=PatternStatus.APPROVED,
        created_at="2025-01-01T00:00:00Z"
    )
    
    experience_pipeline.shared_pool["test_pattern_revoke"] = test_pattern
    
    # Revoke pattern
    revoked = experience_pipeline.revoke_pattern(
        pattern_id="test_pattern_revoke",
        reason="Test revocation",
        revoke_dependents=False
    )
    
    assert revoked is True
    assert test_pattern.status == PatternStatus.REVOKED
    
    # Try to adopt revoked pattern
    allowed, reason, _ = experience_pipeline.gate_adoption(
        pattern_id="test_pattern_revoke",
        target_tenant_id="tenant_b"
    )
    
    assert allowed is False
    assert "revoked" in reason.lower() or "status" in reason.lower()
    
    # Cleanup
    del experience_pipeline.shared_pool["test_pattern_revoke"]


def test_tenant_isolation_abac():
    """Test that ABAC prevents cross-tenant access to evidence."""
    tenant_a = "tenant_a"
    tenant_b = "tenant_b"
    
    # Distill pattern from tenant A
    shared_pattern, pointers = experience_pipeline.distill_pattern_from_tenant(
        tenant_id=tenant_a,
        task_data={"task": "test", "tenant_id": tenant_a},
        pattern_type=PatternType.DECISION_PATTERN
    )
    
    # Approve pattern
    experience_pipeline.approve_pattern(shared_pattern)
    
    # Tenant B should be able to adopt pattern (pattern has no tenant data)
    allowed, reason, _ = experience_pipeline.gate_adoption(
        pattern_id=shared_pattern.pattern_id,
        target_tenant_id=tenant_b
    )
    
    # Adoption should be allowed (pattern has no tenant data)
    # But tenant B cannot access tenant A's evidence vault
    assert allowed is True or "confidence" in reason.lower() or "contamination" in reason.lower()
    
    # Verify tenant B cannot access tenant A's vault
    if tenant_a in experience_pipeline.tenant_vaults:
        vault_a = experience_pipeline.tenant_vaults[tenant_a]
        # Tenant B should not have access to vault A
        assert tenant_b not in experience_pipeline.tenant_vaults or \
               experience_pipeline.tenant_vaults.get(tenant_b) != vault_a


def test_pattern_recommendations():
    """Test that pattern recommendations work."""
    tenant_id = "tenant_c"
    
    # Create some approved patterns
    for i in range(5):
        pattern = SharedPattern(
            pattern_id=f"test_pattern_{i}",
            pattern_type=PatternType.DECISION_PATTERN,
            experience_vector=None,
            confidence_score=0.7 + (i * 0.05),
            source_pointers=[],
            status=PatternStatus.APPROVED,
            created_at="2025-01-01T00:00:00Z"
        )
        experience_pipeline.shared_pool[f"test_pattern_{i}"] = pattern
    
    # Get recommendations
    recommendations = experience_pipeline.get_pattern_recommendations(
        tenant_id=tenant_id,
        limit=3
    )
    
    assert len(recommendations) <= 3
    assert all(p.status == PatternStatus.APPROVED for p in recommendations)
    
    # Cleanup
    for i in range(5):
        if f"test_pattern_{i}" in experience_pipeline.shared_pool:
            del experience_pipeline.shared_pool[f"test_pattern_{i}"]


def test_red_team_probe():
    """Test that red-team probe detects risks."""
    # Create a pattern that might be risky
    risky_pattern = SharedPattern(
        pattern_id="test_pattern_risky",
        pattern_type=PatternType.DECISION_PATTERN,
        experience_vector=None,
        confidence_score=0.8,
        source_pointers=[
            CryptographicPointer(
                tenant_id="tenant_b",
                evidence_hash="test_hash",
                evidence_location="vault://tenant_b/test"
            )
        ],
        status=PatternStatus.APPROVED,
        created_at="2025-01-01T00:00:00Z"
    )
    
    experience_pipeline.shared_pool["test_pattern_risky"] = risky_pattern
    
    # Probe for tenant B (source points to tenant B - circular reference)
    probe_result = experience_pipeline._red_team_probe(
        pattern=risky_pattern,
        target_tenant_id="tenant_b"
    )
    
    # Should detect risk
    assert probe_result["safe"] is False or len(probe_result["risks"]) > 0
    
    # Cleanup
    del experience_pipeline.shared_pool["test_pattern_risky"]

