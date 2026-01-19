"""
Tests for Billing Service.

Tests:
- Billing toggle (enabled/disabled)
- Payment processing
- Paid endpoint guarding
- Feature flags per plan
"""

import pytest
import os
from backend.services.billing_service import billing_service, BillingService


def test_billing_disabled_by_default():
    """Test that billing is disabled by default."""
    # Create new instance without env var
    original_value = os.environ.get("BILLING_ENABLED")
    if "BILLING_ENABLED" in os.environ:
        del os.environ["BILLING_ENABLED"]
    
    service = BillingService()
    assert service.is_billing_enabled() is False
    
    # Restore original value
    if original_value:
        os.environ["BILLING_ENABLED"] = original_value


def test_billing_enabled_with_env_var():
    """Test that billing can be enabled via environment variable."""
    original_value = os.environ.get("BILLING_ENABLED")
    
    try:
        os.environ["BILLING_ENABLED"] = "true"
        service = BillingService()
        assert service.is_billing_enabled() is True
    finally:
        # Restore original value
        if original_value:
            os.environ["BILLING_ENABLED"] = original_value
        elif "BILLING_ENABLED" in os.environ:
            del os.environ["BILLING_ENABLED"]


def test_payment_processing_disabled():
    """Test that payment processing fails when billing is disabled."""
    original_value = os.environ.get("BILLING_ENABLED")
    if "BILLING_ENABLED" in os.environ:
        del os.environ["BILLING_ENABLED"]
    
    service = BillingService()
    result = service.process_payment("user_123", 100.0, "usd")
    
    assert result["success"] is False
    assert "disabled" in result["message"].lower()
    
    # Restore original value
    if original_value:
        os.environ["BILLING_ENABLED"] = original_value


def test_payment_processing_enabled():
    """Test that payment processing works when billing is enabled."""
    original_value = os.environ.get("BILLING_ENABLED")
    original_stripe = os.environ.get("STRIPE_API_KEY")
    
    try:
        os.environ["BILLING_ENABLED"] = "true"
        os.environ["STRIPE_API_KEY"] = "test_key_123"
        
        service = BillingService()
        result = service.process_payment("user_123", 100.0, "usd")
        
        # Should succeed (or fail with specific Stripe error, not "disabled")
        assert result["success"] is True or "stripe" in result.get("message", "").lower()
    finally:
        # Restore original values
        if original_value:
            os.environ["BILLING_ENABLED"] = original_value
        elif "BILLING_ENABLED" in os.environ:
            del os.environ["BILLING_ENABLED"]
        
        if original_stripe:
            os.environ["STRIPE_API_KEY"] = original_stripe
        elif "STRIPE_API_KEY" in os.environ:
            del os.environ["STRIPE_API_KEY"]


def test_guard_paid_endpoint_disabled():
    """Test that paid endpoint guard does nothing when billing is disabled."""
    original_value = os.environ.get("BILLING_ENABLED")
    if "BILLING_ENABLED" in os.environ:
        del os.environ["BILLING_ENABLED"]
    
    service = BillingService()
    
    # Should not raise exception
    service.guard_paid_endpoint("user_123")
    
    # Restore original value
    if original_value:
        os.environ["BILLING_ENABLED"] = original_value


def test_guard_paid_endpoint_enabled():
    """Test that paid endpoint guard works when billing is enabled."""
    original_value = os.environ.get("BILLING_ENABLED")
    original_stripe = os.environ.get("STRIPE_API_KEY")
    
    try:
        os.environ["BILLING_ENABLED"] = "true"
        os.environ["STRIPE_API_KEY"] = "test_key_123"
        
        service = BillingService()
        
        # Should not raise exception (assuming user is paid)
        # In real implementation, would check user's subscription status
        service.guard_paid_endpoint("user_123")
    finally:
        # Restore original values
        if original_value:
            os.environ["BILLING_ENABLED"] = original_value
        elif "BILLING_ENABLED" in os.environ:
            del os.environ["BILLING_ENABLED"]
        
        if original_stripe:
            os.environ["STRIPE_API_KEY"] = original_stripe
        elif "STRIPE_API_KEY" in os.environ:
            del os.environ["STRIPE_API_KEY"]


def test_feature_flags_per_plan():
    """Test that feature flags are checked per plan."""
    from backend.services.billing_service import billing_service, PlanTier
    
    # Test FREE plan
    has_feature_free = billing_service.check_feature_access("user_free", "basic_agents")
    assert has_feature_free is True  # Should have basic features
    
    # Test ENTERPRISE plan
    has_feature_enterprise = billing_service.check_feature_access("user_enterprise", "all_features")
    assert has_feature_enterprise is True  # Should have all features
    
    # Test quota checking
    within_quota_free = billing_service.check_quota("user_free", "agents", 5)
    assert within_quota_free is True  # 5 < 10 (max for free)
    
    over_quota_free = billing_service.check_quota("user_free", "agents", 15)
    assert over_quota_free is False  # 15 > 10 (max for free)
    
    # Enterprise should have unlimited quota
    within_quota_enterprise = billing_service.check_quota("user_enterprise", "agents", 1000)
    assert within_quota_enterprise is True  # Enterprise has unlimited

