"""Tests for Subscription Service (Sprint 5, Phase 10).

Covers RuntimeSubscription properties, SubscriptionService CRUD,
rate limiting, usage tracking, and alternative suggestions.
"""

from __future__ import annotations

from app.services.subscription_service import (
    AuthMethod,
    RuntimeSubscription,
    SubscriptionService,
    SubscriptionTier,
)

# ── RuntimeSubscription tests ──


class TestRuntimeSubscription:
    def test_default_fields(self):
        sub = RuntimeSubscription()
        assert sub.runtime_id == ""
        assert sub.auth_method == AuthMethod.NONE
        assert sub.is_authenticated is False
        assert sub.subscription_tier == SubscriptionTier.UNKNOWN
        assert sub.rate_limited is False

    def test_is_available_when_authenticated(self):
        sub = RuntimeSubscription(is_authenticated=True)
        assert sub.is_available is True

    def test_not_available_when_unauthenticated(self):
        sub = RuntimeSubscription(is_authenticated=False)
        assert sub.is_available is False

    def test_not_available_when_rate_limited(self):
        sub = RuntimeSubscription(is_authenticated=True, rate_limited=True)
        assert sub.is_available is False

    def test_not_available_when_daily_limit_exceeded(self):
        sub = RuntimeSubscription(
            is_authenticated=True,
            daily_limit=100,
            daily_used=100,
        )
        assert sub.is_available is False

    def test_available_when_under_daily_limit(self):
        sub = RuntimeSubscription(
            is_authenticated=True,
            daily_limit=100,
            daily_used=50,
        )
        assert sub.is_available is True

    def test_not_available_when_monthly_limit_exceeded(self):
        sub = RuntimeSubscription(
            is_authenticated=True,
            monthly_limit=1000,
            monthly_used=1000,
        )
        assert sub.is_available is False

    def test_status_message_not_authenticated(self):
        sub = RuntimeSubscription(is_authenticated=False)
        assert sub.status_message == "Not authenticated"

    def test_status_message_rate_limited(self):
        sub = RuntimeSubscription(
            is_authenticated=True,
            rate_limited=True,
            rate_limit_resets_at="2026-03-21T15:00:00",
        )
        assert "Rate limited" in sub.status_message
        assert "2026-03-21T15:00:00" in sub.status_message

    def test_status_message_daily_remaining(self):
        sub = RuntimeSubscription(
            is_authenticated=True,
            daily_limit=100,
            daily_used=60,
        )
        assert "40 requests remaining" in sub.status_message

    def test_status_message_available(self):
        sub = RuntimeSubscription(is_authenticated=True)
        assert sub.status_message == "Available"

    def test_to_dict(self):
        sub = RuntimeSubscription(
            runtime_id="claude_code",
            auth_method=AuthMethod.CLI_LOGIN,
            is_authenticated=True,
            subscription_tier=SubscriptionTier.PRO,
        )
        d = sub.to_dict()
        assert d["runtime_id"] == "claude_code"
        assert d["auth_method"] == "cli_login"
        assert d["is_available"] is True
        assert d["subscription_tier"] == "pro"
        assert d["status_message"] == "Available"


# ── SubscriptionService tests ──


class TestSubscriptionService:
    def test_initialize_defaults(self):
        service = SubscriptionService()
        service.initialize_defaults()
        all_subs = service.get_all()
        assert len(all_subs) == 7  # 7 default runtimes (added perplexity, vllm)

    def test_get_existing(self):
        service = SubscriptionService()
        service.initialize_defaults()
        sub = service.get("claude_code")
        assert sub is not None
        assert sub.runtime_id == "claude_code"
        assert sub.auth_method == AuthMethod.CLI_LOGIN

    def test_get_nonexistent(self):
        service = SubscriptionService()
        assert service.get("no_such_runtime") is None

    def test_ollama_available_by_default(self):
        service = SubscriptionService()
        service.initialize_defaults()
        sub = service.get("ollama")
        assert sub is not None
        assert sub.is_authenticated is True
        assert sub.is_available is True
        assert sub.subscription_tier == SubscriptionTier.FREE

    def test_get_available(self):
        service = SubscriptionService()
        service.initialize_defaults()
        available = service.get_available()
        # ollama and vllm are authenticated by default (local, no auth needed)
        assert len(available) == 2
        runtime_ids = {s.runtime_id for s in available}
        assert "ollama" in runtime_ids
        assert "vllm" in runtime_ids

    def test_set_authenticated(self):
        service = SubscriptionService()
        service.initialize_defaults()
        sub = service.set_authenticated(
            "claude_code",
            authenticated=True,
            tier=SubscriptionTier.MAX,
        )
        assert sub is not None
        assert sub.is_authenticated is True
        assert sub.subscription_tier == SubscriptionTier.MAX
        assert sub.is_available is True

    def test_set_authenticated_nonexistent(self):
        service = SubscriptionService()
        result = service.set_authenticated("nope", True)
        assert result is None

    def test_set_rate_limited(self):
        service = SubscriptionService()
        service.initialize_defaults()
        service.set_authenticated("claude_code", True)

        sub = service.set_rate_limited(
            "claude_code",
            limited=True,
            resets_at="2026-03-21T15:00:00",
        )
        assert sub is not None
        assert sub.rate_limited is True
        assert sub.rate_limit_resets_at == "2026-03-21T15:00:00"
        assert sub.is_available is False

    def test_clear_rate_limit(self):
        service = SubscriptionService()
        service.initialize_defaults()
        service.set_authenticated("claude_code", True)
        service.set_rate_limited("claude_code", limited=True)

        sub = service.set_rate_limited("claude_code", limited=False)
        assert sub is not None
        assert sub.rate_limited is False
        assert sub.rate_limit_resets_at is None
        assert sub.is_available is True

    def test_record_usage(self):
        service = SubscriptionService()
        service.initialize_defaults()
        sub = service.record_usage("ollama", count=5)
        assert sub is not None
        assert sub.daily_used == 5
        assert sub.monthly_used == 5

    def test_record_usage_accumulates(self):
        service = SubscriptionService()
        service.initialize_defaults()
        service.record_usage("ollama", count=3)
        sub = service.record_usage("ollama", count=7)
        assert sub is not None
        assert sub.daily_used == 10
        assert sub.monthly_used == 10

    def test_record_usage_nonexistent(self):
        service = SubscriptionService()
        result = service.record_usage("nope")
        assert result is None

    def test_suggest_alternative(self):
        service = SubscriptionService()
        service.initialize_defaults()
        # Only ollama is authenticated by default
        alt = service.suggest_alternative("claude_code")
        assert alt == "ollama"

    def test_suggest_alternative_none_available(self):
        service = SubscriptionService()
        service.initialize_defaults()
        # Ollama and vllm are both available (free local). Requesting alt to ollama returns vllm.
        alt = service.suggest_alternative("ollama")
        assert alt == "vllm"

    def test_suggest_alternative_prefers_free(self):
        service = SubscriptionService()
        service.initialize_defaults()
        service.set_authenticated("claude_code", True)
        service.set_authenticated("codex", True)
        # Should prefer ollama (free) over claude_code/codex (paid)
        alt = service.suggest_alternative("codex")
        assert alt == "ollama"

    def test_get_summary(self):
        service = SubscriptionService()
        service.initialize_defaults()
        summary = service.get_summary()
        assert summary["total"] == 7
        assert summary["authenticated"] == 2  # ollama + vllm
        assert summary["available"] == 2
        assert summary["rate_limited"] == 0
        assert len(summary["runtimes"]) == 7
