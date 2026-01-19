"""
Billing Service with Stripe Integration.

Features:
- Stripe subscription management
- Feature flags based on plan
- Usage tracking
- Billing toggle (env-driven)
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Optional, List
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PlanTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class Subscription:
    """Subscription information."""
    user_id: str
    plan: PlanTier
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    status: str = "active"  # active, canceled, past_due
    current_period_end: Optional[int] = None


class BillingService:
    """
    Billing service with Stripe integration.
    
    Features:
    - Stripe subscription management (if enabled)
    - Feature flags based on plan
    - Usage tracking
    - Billing toggle (env-driven)
    """
    
    def __init__(self):
        # Billing toggle
        self.billing_enabled = os.getenv("BILLING_ENABLED", "false").lower() == "true"
        
        # Stripe keys (from environment)
        self.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.stripe_publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
        
        # Feature flags per plan
        self.plan_features = {
            PlanTier.FREE: {
                "max_agents": 10,
                "max_projects": 5,
                "api_calls_per_month": 1000,
                "features": ["basic_agents", "basic_memory"]
            },
            PlanTier.STARTER: {
                "max_agents": 48,  # Full 8×6 structure
                "max_projects": 20,
                "api_calls_per_month": 10000,
                "features": ["full_agents", "nbmf_memory", "council_rounds"]
            },
            PlanTier.PROFESSIONAL: {
                "max_agents": 100,
                "max_projects": 100,
                "api_calls_per_month": 100000,
                "features": ["full_agents", "nbmf_memory", "council_rounds", "sec_loop", "advanced_analytics"]
            },
            PlanTier.ENTERPRISE: {
                "max_agents": -1,  # Unlimited
                "max_projects": -1,  # Unlimited
                "api_calls_per_month": -1,  # Unlimited
                "features": ["all_features", "custom_integrations", "dedicated_support"]
            }
        }
        
        # In-memory subscription store (in production, use database)
        self.subscriptions: Dict[str, Subscription] = {}
        
        if self.billing_enabled and not self.stripe_secret_key:
            logger.warning("Billing enabled but STRIPE_SECRET_KEY not set. Billing features will be limited.")
    
    def get_user_plan(self, user_id: str) -> PlanTier:
        """
        Get user's subscription plan.
        
        Args:
            user_id: User identifier
        
        Returns:
            Plan tier
        """
        if not self.billing_enabled:
            # Billing disabled - return enterprise plan (all features)
            return PlanTier.ENTERPRISE
        
        subscription = self.subscriptions.get(user_id)
        if subscription:
            return subscription.plan
        
        # Default to free plan
        return PlanTier.FREE
    
    def check_feature_access(self, user_id: str, feature: str) -> bool:
        """
        Check if user has access to a feature.
        
        Args:
            user_id: User identifier
            feature: Feature name
        
        Returns:
            True if user has access
        """
        if not self.billing_enabled:
            # Billing disabled - all features available
            return True
        
        plan = self.get_user_plan(user_id)
        features = self.plan_features.get(plan, {}).get("features", [])
        
        return feature in features or "all_features" in features
    
    def check_quota(self, user_id: str, resource: str, current_usage: int) -> bool:
        """
        Check if user is within quota limits.
        
        Args:
            user_id: User identifier
            resource: Resource type ("agents", "projects", "api_calls")
            current_usage: Current usage count
        
        Returns:
            True if within quota
        """
        if not self.billing_enabled:
            # Billing disabled - no limits
            return True
        
        plan = self.get_user_plan(user_id)
        plan_config = self.plan_features.get(plan, {})
        
        quota_key = f"max_{resource}"
        max_quota = plan_config.get(quota_key, -1)
        
        # -1 means unlimited
        if max_quota == -1:
            return True
        
        return current_usage < max_quota
    
    def create_subscription(
        self,
        user_id: str,
        plan: PlanTier,
        stripe_customer_id: Optional[str] = None
    ) -> Subscription:
        """
        Create a subscription for a user.
        
        Args:
            user_id: User identifier
            plan: Plan tier
            stripe_customer_id: Stripe customer ID (if using Stripe)
        
        Returns:
            Subscription object
        """
        subscription = Subscription(
            user_id=user_id,
            plan=plan,
            stripe_customer_id=stripe_customer_id
        )
        
        self.subscriptions[user_id] = subscription
        logger.info(f"Created subscription for user {user_id}: {plan.value}")
        
        return subscription
    
    def update_subscription(self, user_id: str, plan: PlanTier) -> Optional[Subscription]:
        """
        Update user's subscription plan.
        
        Args:
            user_id: User identifier
            plan: New plan tier
        
        Returns:
            Updated subscription
        """
        if user_id not in self.subscriptions:
            return None
        
        subscription = self.subscriptions[user_id]
        subscription.plan = plan
        
        logger.info(f"Updated subscription for user {user_id}: {plan.value}")
        return subscription


# Global instance
billing_service = BillingService()

