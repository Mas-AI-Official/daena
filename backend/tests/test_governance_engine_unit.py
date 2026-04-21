"""Unit tests for GovernanceEngine static/pure methods.

Complements the API-level tests in ``test_governance.py`` by
covering the static helpers in isolation (no DB, no HTTP, no
async). Ensures refactors to the inheritance chain, risk
classification, and skill-tier mapping do not silently change
behavior.

Covers:
    * get_effective_preset: role + team + org inheritance chain
    * get_allowed_range: role-bounded legal range
    * _to_mode: legacy vs canonical string coercion
    * _assess_risk: action_type to RiskLevel mapping
    * assess_skill_trust_tier: maturity to governance tier

These run in milliseconds and should never require I/O.
"""

from __future__ import annotations

import pytest

from app.core.constants import GovernanceMode, RiskLevel, UserRole
from app.services.governance import (
    ROLE_DEFAULT_PRESETS,
    ROLE_MODE_CONSTRAINTS,
    GovernanceEngine,
)


# ----------------------------------------------------------------------
# _to_mode (string coercion)
# ----------------------------------------------------------------------


def test_to_mode_accepts_canonical_values():
    assert GovernanceEngine._to_mode("UNLEASHED") == GovernanceMode.UNLEASHED
    assert GovernanceEngine._to_mode("BALANCED") == GovernanceMode.BALANCED
    assert GovernanceEngine._to_mode("GOVERNED") == GovernanceMode.GOVERNED


def test_to_mode_raises_on_nonsense():
    with pytest.raises(ValueError):
        GovernanceEngine._to_mode("not_a_real_mode")


# ----------------------------------------------------------------------
# get_effective_preset: role inheritance
# ----------------------------------------------------------------------


def test_effective_preset_defaults_to_role_default_when_no_override():
    for role, default in ROLE_DEFAULT_PRESETS.items():
        result = GovernanceEngine.get_effective_preset(user_role=role.value)
        assert result == default, f"Role {role.value} should default to {default}"


def test_effective_preset_clamps_to_role_max():
    # VIEWER is locked at GOVERNED (min == max); requesting UNLEASHED
    # must clamp back to GOVERNED.
    result = GovernanceEngine.get_effective_preset(
        user_role="VIEWER",
        requested_preset="UNLEASHED",
    )
    assert result == GovernanceMode.GOVERNED


def test_effective_preset_clamps_to_role_min():
    # ADMIN min is BALANCED; requesting UNLEASHED clamps to BALANCED.
    result = GovernanceEngine.get_effective_preset(
        user_role="ADMIN",
        requested_preset="UNLEASHED",
    )
    assert result == GovernanceMode.BALANCED


def test_effective_preset_team_minimum_raises_floor():
    # FOUNDER min is UNLEASHED; team_minimum=GOVERNED must raise floor.
    result = GovernanceEngine.get_effective_preset(
        user_role="FOUNDER",
        requested_preset="UNLEASHED",
        team_minimum="GOVERNED",
    )
    assert result == GovernanceMode.GOVERNED


def test_effective_preset_org_minimum_raises_floor():
    result = GovernanceEngine.get_effective_preset(
        user_role="FOUNDER",
        requested_preset="UNLEASHED",
        org_minimum="BALANCED",
    )
    assert result == GovernanceMode.BALANCED


def test_effective_preset_takes_max_of_all_minimums():
    # role_min=UNLEASHED (FOUNDER), team_min=BALANCED, org_min=GOVERNED
    # effective floor should be GOVERNED (the highest).
    result = GovernanceEngine.get_effective_preset(
        user_role="FOUNDER",
        requested_preset="UNLEASHED",
        team_minimum="BALANCED",
        org_minimum="GOVERNED",
    )
    assert result == GovernanceMode.GOVERNED


# ----------------------------------------------------------------------
# get_allowed_range
# ----------------------------------------------------------------------


def test_allowed_range_founder_full_span():
    lo, hi = GovernanceEngine.get_allowed_range(user_role="FOUNDER")
    assert lo == GovernanceMode.UNLEASHED
    assert hi == GovernanceMode.GOVERNED


def test_allowed_range_viewer_locked():
    lo, hi = GovernanceEngine.get_allowed_range(user_role="VIEWER")
    assert lo == GovernanceMode.GOVERNED
    assert hi == GovernanceMode.GOVERNED


def test_allowed_range_respects_team_minimum():
    lo, _ = GovernanceEngine.get_allowed_range(
        user_role="FOUNDER", team_minimum="BALANCED",
    )
    assert lo == GovernanceMode.BALANCED


def test_allowed_range_respects_org_minimum():
    lo, _ = GovernanceEngine.get_allowed_range(
        user_role="FOUNDER", org_minimum="GOVERNED",
    )
    assert lo == GovernanceMode.GOVERNED


# ----------------------------------------------------------------------
# _assess_risk: action_type to RiskLevel
# ----------------------------------------------------------------------


def test_assess_risk_destructive_always_critical():
    for action in ("DELETE", "DROP", "TRUNCATE", "PURGE"):
        assert GovernanceEngine._assess_risk(action, {}) == RiskLevel.CRITICAL.value
        # Case-insensitive
        assert GovernanceEngine._assess_risk(action.lower(), {}) == RiskLevel.CRITICAL.value


def test_assess_risk_high_risk_actions():
    for action in ("DEPLOY", "SEND_EMAIL", "GRANT_ACCESS", "REVOKE_ACCESS"):
        assert GovernanceEngine._assess_risk(action, {}) == RiskLevel.HIGH.value


def test_assess_risk_medium_risk_actions():
    for action in ("EXECUTE", "WRITE_FILE", "MODIFY_CONFIG", "API_CALL_EXTERNAL"):
        assert GovernanceEngine._assess_risk(action, {}) == RiskLevel.MEDIUM.value


def test_assess_risk_readonly_actions_are_none():
    for action in ("READ", "QUERY", "LIST", "GET", "SEARCH"):
        assert GovernanceEngine._assess_risk(action, {}) == RiskLevel.NONE.value


def test_assess_risk_unknown_defaults_to_low():
    assert GovernanceEngine._assess_risk("DISCOVER_PLANET", {}) == RiskLevel.LOW.value
    assert GovernanceEngine._assess_risk("UNDOCUMENTED", {}) == RiskLevel.LOW.value


# ----------------------------------------------------------------------
# assess_skill_trust_tier
# ----------------------------------------------------------------------


def test_skill_trust_tier_raw_and_draft_are_notified():
    # T0_RAW and T1_DRAFT: untrusted external content -> tier 2
    assert GovernanceEngine.assess_skill_trust_tier(0) == 2
    assert GovernanceEngine.assess_skill_trust_tier(1) == 2


def test_skill_trust_tier_refined_and_above_are_log_only():
    # T2_REFINED, T3_PRODUCTION, T4_COMPOUND: validated -> tier 1
    assert GovernanceEngine.assess_skill_trust_tier(2) == 1
    assert GovernanceEngine.assess_skill_trust_tier(3) == 1
    assert GovernanceEngine.assess_skill_trust_tier(4) == 1


# ----------------------------------------------------------------------
# Role constraints sanity check (guardrails never regress)
# ----------------------------------------------------------------------


def test_every_role_has_constraint():
    for role in UserRole:
        assert role in ROLE_MODE_CONSTRAINTS, (
            f"Role {role.value} missing from ROLE_MODE_CONSTRAINTS"
        )


def test_every_role_has_default_preset():
    for role in UserRole:
        assert role in ROLE_DEFAULT_PRESETS, (
            f"Role {role.value} missing from ROLE_DEFAULT_PRESETS"
        )


def test_default_preset_is_within_role_allowed_range():
    """Regression: default preset must always be legal for the role."""
    for role, default in ROLE_DEFAULT_PRESETS.items():
        lo, hi = GovernanceEngine.get_allowed_range(user_role=role.value)
        # Verify default is within [lo, hi] by asking get_effective_preset
        # with the default as the requested value -- it should pass through.
        effective = GovernanceEngine.get_effective_preset(
            user_role=role.value, requested_preset=default.value,
        )
        assert effective == default, (
            f"Role {role.value} default {default.value} got clamped to {effective.value}"
        )
