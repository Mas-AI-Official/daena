"""Tests for the system-wide Asset Shield primitives.

Covers vault_adapter + egress_filter + consent_token + operator_initiation.
"""

from __future__ import annotations

import time

import pytest

from app.services.security.asset_shield import consent_token as ct_mod
from app.services.security.asset_shield import operator_initiation as oi_mod
from app.services.security.asset_shield import vault_adapter as va_mod
from app.services.security.asset_shield import (
    ConsentTokenExpired,
    ConsentTokenRevoked,
    EgressFilter,
    VaultAdapter,
    clear_tokens,
    is_operator_initiated,
    mark_operator_initiated,
    mint_token,
    register_fingerprint,
    use_token,
)
from app.services.security.asset_shield.operator_initiation import (
    collapse_tier_for_operator_initiated,
)


@pytest.fixture(autouse=True)
def _reset_state():
    va_mod.clear_registry()
    clear_tokens()
    oi_mod.clear_markers()
    yield
    va_mod.clear_registry()
    clear_tokens()
    oi_mod.clear_markers()


# ----------------------------------------------------------------------
# Vault adapter
# ----------------------------------------------------------------------


def test_register_fingerprint_happy_path():
    reg = register_fingerprint(
        asset_id="anth-key-1",
        raw_value="sk-ant-TEST-12345",
        asset_class="api_keys",
    )
    assert reg.fingerprint_prefix == reg.fingerprint_prefix  # non-empty
    assert len(reg.fingerprint_prefix) == 16
    assert VaultAdapter().list_registered() == [reg]


def test_register_fingerprint_rejects_unknown_class():
    with pytest.raises(ValueError):
        register_fingerprint("id", "secret", "made_up_class")


def test_register_fingerprint_rejects_empty_secret():
    with pytest.raises(ValueError):
        register_fingerprint("id", "", "api_keys")


def test_hash_reference_is_stable():
    va = VaultAdapter()
    a = va.hash_reference("supersecret")
    b = va.hash_reference("supersecret")
    assert a == b
    assert a != va.hash_reference("different")


# ----------------------------------------------------------------------
# Egress filter
# ----------------------------------------------------------------------


def test_egress_filter_redacts_registered_secret():
    register_fingerprint("gh-pat-1", "ghp_ABC123XYZ", "api_keys")
    ef = EgressFilter()
    result = ef.scan_and_redact("my token is ghp_ABC123XYZ please hide it")
    assert "ghp_ABC123XYZ" not in result.redacted_text
    assert "[REDACTED:api_keys:" in result.redacted_text
    assert result.hit_count == 1


def test_egress_filter_ignores_unregistered_text():
    register_fingerprint("gh-pat-1", "ghp_ONLYME", "api_keys")
    ef = EgressFilter()
    result = ef.scan_and_redact("this is benign text with no secrets")
    assert result.redacted_text == "this is benign text with no secrets"
    assert result.hit_count == 0


def test_egress_filter_handles_multiple_secrets():
    register_fingerprint("a", "secret-A", "api_keys")
    register_fingerprint("b", "secret-B", "finance")
    ef = EgressFilter()
    result = ef.scan_and_redact("the keys are secret-A and secret-B")
    assert "secret-A" not in result.redacted_text
    assert "secret-B" not in result.redacted_text
    assert result.hit_count == 2


def test_egress_filter_scan_only_returns_true_for_hit():
    register_fingerprint("a", "secret-xyz", "api_keys")
    ef = EgressFilter()
    assert ef.scan_only("echo secret-xyz from shell") is True
    assert ef.scan_only("echo no-such-value") is False


def test_egress_filter_empty_registry_passthrough():
    ef = EgressFilter()
    result = ef.scan_and_redact("anything goes here")
    assert result.redacted_text == "anything goes here"
    assert result.hit_count == 0


# ----------------------------------------------------------------------
# Consent token
# ----------------------------------------------------------------------


def test_mint_and_use_token_once():
    register_fingerprint("gh-pat-1", "ghp_ONESHOT", "api_keys")
    token = mint_token(
        asset_id="gh-pat-1",
        destination="https://api.github.com",
        op_type="repo_clone",
    )
    secret = use_token(
        token.token_id, for_destination="https://api.github.com",
    )
    assert secret == "ghp_ONESHOT"


def test_second_use_raises_revoked():
    register_fingerprint("a", "sec", "api_keys")
    token = mint_token("a", "x", "op")
    use_token(token.token_id)
    with pytest.raises(ConsentTokenRevoked):
        use_token(token.token_id)


def test_expired_token_raises():
    register_fingerprint("a", "sec", "api_keys")
    token = mint_token("a", "x", "op", expiry_seconds=1)
    token.expires_at = time.time() - 1  # force expiry
    with pytest.raises(ConsentTokenExpired):
        use_token(token.token_id)


def test_scope_mismatch_raises():
    from app.services.security.asset_shield.consent_token import (
        ConsentTokenScopeMismatch,
    )

    register_fingerprint("a", "sec", "api_keys")
    token = mint_token("a", "https://intended.example", "op")
    with pytest.raises(ConsentTokenScopeMismatch):
        use_token(token.token_id, for_destination="https://other.example")


def test_unknown_token_raises_keyerror():
    with pytest.raises(KeyError):
        use_token("no-such-token")


def test_mint_requires_asset_id():
    with pytest.raises(ValueError):
        mint_token("", "dest", "op")


# ----------------------------------------------------------------------
# Operator initiation
# ----------------------------------------------------------------------


def test_operator_initiated_founder_within_window():
    mark_operator_initiated("sess-1", "u", "FOUNDER")
    assert is_operator_initiated("sess-1") is True


def test_not_operator_initiated_for_unknown_session():
    assert is_operator_initiated("no-such") is False
    assert is_operator_initiated(None) is False


def test_operator_initiated_role_gate():
    mark_operator_initiated("sess-2", "u", "USER")
    assert is_operator_initiated("sess-2") is False


def test_operator_initiated_expires():
    mark_operator_initiated("sess-3", "u", "FOUNDER")
    marker = oi_mod.get_marker("sess-3")
    assert marker is not None
    marker.marked_at = time.time() - 1000  # blow past TTL
    assert is_operator_initiated("sess-3") is False


# ----------------------------------------------------------------------
# Initiator-aware tier collapse
# ----------------------------------------------------------------------


def test_tier_collapse_operator_initiated_non_asset():
    assert collapse_tier_for_operator_initiated(3, True, False) == 1
    assert collapse_tier_for_operator_initiated(4, True, False) == 1


def test_tier_collapse_preserves_asset_crossing():
    assert collapse_tier_for_operator_initiated(3, True, True) == 3


def test_tier_collapse_noop_for_background_ops():
    assert collapse_tier_for_operator_initiated(3, False, False) == 3
    assert collapse_tier_for_operator_initiated(4, False, True) == 4
