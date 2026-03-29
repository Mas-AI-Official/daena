"""Tests for subscription authentication model.

Covers SubscriptionAuth dataclass, priority scoring, serialization,
and AuthMethod/SubscriptionStatus enums.
"""

import pytest

from app.services.runtimes.subscription_auth import (
    AuthMethod,
    SubscriptionAuth,
    SubscriptionStatus,
)


class TestAuthMethod:
    """Verify AuthMethod enum values."""

    def test_all_methods_exist(self):
        assert AuthMethod.SUBSCRIPTION.value == "subscription"
        assert AuthMethod.API_KEY.value == "api_key"
        assert AuthMethod.OAUTH.value == "oauth"
        assert AuthMethod.LOCAL.value == "local"
        assert AuthMethod.MCP.value == "mcp"

    def test_enum_count(self):
        assert len(AuthMethod) == 5


class TestSubscriptionStatus:
    """Verify SubscriptionStatus enum values."""

    def test_all_statuses_exist(self):
        assert SubscriptionStatus.AUTHENTICATED.value == "authenticated"
        assert SubscriptionStatus.NOT_AUTHENTICATED.value == "not_authenticated"
        assert SubscriptionStatus.EXPIRED.value == "expired"
        assert SubscriptionStatus.UNKNOWN.value == "unknown"


class TestSubscriptionAuth:
    """Test SubscriptionAuth dataclass properties and methods."""

    def test_authenticated_subscription(self):
        auth = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.AUTHENTICATED,
            user_display="max@mas-ai.co",
            plan_name="Claude Max",
        )
        assert auth.is_authenticated is True
        assert auth.priority_score == 100

    def test_not_authenticated_subscription(self):
        auth = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.NOT_AUTHENTICATED,
            setup_command="claude login",
        )
        assert auth.is_authenticated is False
        assert auth.priority_score == 0

    def test_expired_subscription(self):
        auth = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.EXPIRED,
        )
        assert auth.is_authenticated is False
        assert auth.priority_score == 0

    def test_local_always_available(self):
        """LOCAL method gets priority 80 even when not 'authenticated'."""
        auth = SubscriptionAuth(
            method=AuthMethod.LOCAL,
            status=SubscriptionStatus.NOT_AUTHENTICATED,
        )
        assert auth.priority_score == 80

    def test_local_authenticated(self):
        auth = SubscriptionAuth(
            method=AuthMethod.LOCAL,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        assert auth.priority_score == 80

    def test_mcp_authenticated(self):
        auth = SubscriptionAuth(
            method=AuthMethod.MCP,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        assert auth.priority_score == 70

    def test_oauth_authenticated(self):
        auth = SubscriptionAuth(
            method=AuthMethod.OAUTH,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        assert auth.priority_score == 60

    def test_api_key_authenticated(self):
        auth = SubscriptionAuth(
            method=AuthMethod.API_KEY,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        assert auth.priority_score == 20

    def test_api_key_not_authenticated(self):
        auth = SubscriptionAuth(
            method=AuthMethod.API_KEY,
            status=SubscriptionStatus.NOT_AUTHENTICATED,
        )
        assert auth.priority_score == 0

    def test_to_dict_complete(self):
        auth = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.AUTHENTICATED,
            user_display="max@mas-ai.co",
            plan_name="Claude Max",
            setup_command="claude login",
            login_url="https://claude.ai/login",
        )
        d = auth.to_dict()
        assert d["method"] == "subscription"
        assert d["status"] == "authenticated"
        assert d["user_display"] == "max@mas-ai.co"
        assert d["plan_name"] == "Claude Max"
        assert d["setup_command"] == "claude login"
        assert d["login_url"] == "https://claude.ai/login"
        assert d["is_authenticated"] is True
        assert d["priority_score"] == 100

    def test_to_dict_minimal(self):
        auth = SubscriptionAuth(
            method=AuthMethod.LOCAL,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        d = auth.to_dict()
        assert d["method"] == "local"
        assert d["user_display"] is None
        assert d["plan_name"] is None

    def test_requires_api_key_fallback_default(self):
        auth = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        assert auth.requires_api_key_fallback is False

    def test_requires_api_key_fallback_set(self):
        auth = SubscriptionAuth(
            method=AuthMethod.API_KEY,
            status=SubscriptionStatus.NOT_AUTHENTICATED,
            requires_api_key_fallback=True,
        )
        assert auth.requires_api_key_fallback is True

    def test_priority_ordering(self):
        """Verify the priority hierarchy: Subscription > Local > MCP > OAuth > API key."""
        subscription = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        local = SubscriptionAuth(
            method=AuthMethod.LOCAL,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        mcp = SubscriptionAuth(
            method=AuthMethod.MCP,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        oauth = SubscriptionAuth(
            method=AuthMethod.OAUTH,
            status=SubscriptionStatus.AUTHENTICATED,
        )
        api_key = SubscriptionAuth(
            method=AuthMethod.API_KEY,
            status=SubscriptionStatus.AUTHENTICATED,
        )

        scores = [
            subscription.priority_score,
            local.priority_score,
            mcp.priority_score,
            oauth.priority_score,
            api_key.priority_score,
        ]
        assert scores == sorted(scores, reverse=True)

    def test_unknown_status(self):
        auth = SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.UNKNOWN,
        )
        assert auth.is_authenticated is False
        assert auth.priority_score == 0
