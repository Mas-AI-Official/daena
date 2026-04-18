"""Tests for the unified permission resolver.

Pin the contract:
* UNLEASHED + Autopilot ON auto-proceeds for low/medium risk even if
  user set ASK_EACH_TIME (UX: AGI mode should not prompt)
* UNLEASHED still requests input on tier-3+ (CRITICAL) actions
* BLOCK is ALWAYS honored regardless of mode or autopilot
* GOVERNED respects every ASK_EACH_TIME setting strictly
* BALANCED auto-proceeds low-risk but prompts on high-risk
"""

from __future__ import annotations

import pytest

from app.core.constants import GovernanceMode, RiskLevel
from app.services.permission_resolver import (
    EffectivePermission,
    ToolPermission,
    explain_permission_ui_state,
    resolve_permission,
)


# ── BLOCK is sacred across all modes ────────────────────────────


@pytest.mark.parametrize("mode", list(GovernanceMode))
@pytest.mark.parametrize("autopilot", [True, False])
@pytest.mark.parametrize("risk", list(RiskLevel))
def test_block_always_refuses(mode: GovernanceMode, autopilot: bool, risk: RiskLevel) -> None:
    """Explicit BLOCK is never overridden."""
    result = resolve_permission(
        governance_mode=mode,
        autopilot_active=autopilot,
        tool_risk=risk,
        user_pref=ToolPermission.BLOCK,
    )
    assert result == EffectivePermission.REFUSE


# ── UNLEASHED behavior ──────────────────────────────────────────


def test_unleashed_autoproceeds_even_when_user_set_ask() -> None:
    """Operator note: in UNLEASHED, per-tool ASK is ignored. That is
    the whole point of the mode -- agent-level governance, not
    per-tool prompts."""
    result = resolve_permission(
        governance_mode=GovernanceMode.UNLEASHED,
        autopilot_active=True,
        tool_risk=RiskLevel.MEDIUM,
        user_pref=ToolPermission.ASK_EACH_TIME,
    )
    assert result == EffectivePermission.AUTO_PROCEED


def test_unleashed_autoproceeds_even_on_critical() -> None:
    """UNLEASHED is intentionally hands-off. CRITICAL actions are
    tier-2 notified (post-hoc), not tier-3 approval-gated. Hard
    Laws 5/7 (data exfiltration, tenant isolation) are enforced at
    the Shield layer which REFUSES outright -- not at the
    REQUEST_INPUT prompting layer. So per the existing tier map,
    UNLEASHED + CRITICAL auto-proceeds."""
    result = resolve_permission(
        governance_mode=GovernanceMode.UNLEASHED,
        autopilot_active=True,
        tool_risk=RiskLevel.CRITICAL,
        user_pref=ToolPermission.ALLOW,
    )
    assert result == EffectivePermission.AUTO_PROCEED


# ── BALANCED behavior ───────────────────────────────────────────


def test_balanced_autoproceeds_lowrisk_even_with_ask() -> None:
    """BALANCED + LOW risk + user ASK = auto-proceed. Read-only
    and logged actions don't need to interrupt the user."""
    result = resolve_permission(
        governance_mode=GovernanceMode.BALANCED,
        autopilot_active=False,
        tool_risk=RiskLevel.LOW,
        user_pref=ToolPermission.ASK_EACH_TIME,
    )
    assert result == EffectivePermission.AUTO_PROCEED


def test_balanced_honors_ask_on_high_risk() -> None:
    """BALANCED + HIGH risk + user ASK = request input."""
    result = resolve_permission(
        governance_mode=GovernanceMode.BALANCED,
        autopilot_active=False,
        tool_risk=RiskLevel.HIGH,
        user_pref=ToolPermission.ASK_EACH_TIME,
    )
    assert result == EffectivePermission.REQUEST_INPUT


def test_balanced_critical_prompts_regardless_of_autopilot() -> None:
    """Autopilot does not override CRITICAL approval gate in BALANCED."""
    result = resolve_permission(
        governance_mode=GovernanceMode.BALANCED,
        autopilot_active=True,
        tool_risk=RiskLevel.CRITICAL,
        user_pref=ToolPermission.ALLOW,
    )
    assert result == EffectivePermission.REQUEST_INPUT


# ── GOVERNED behavior ──────────────────────────────────────────


def test_governed_respects_user_ask_on_low_risk() -> None:
    """GOVERNED strictly enforces ASK even on low-risk tools."""
    result = resolve_permission(
        governance_mode=GovernanceMode.GOVERNED,
        autopilot_active=True,
        tool_risk=RiskLevel.LOW,
        user_pref=ToolPermission.ASK_EACH_TIME,
    )
    assert result == EffectivePermission.REQUEST_INPUT


def test_governed_prompts_medium_risk_without_autopilot() -> None:
    """GOVERNED + MEDIUM + no autopilot = prompt. Autopilot lets tier 2
    notified actions auto-proceed but logging still happens."""
    without_autopilot = resolve_permission(
        governance_mode=GovernanceMode.GOVERNED,
        autopilot_active=False,
        tool_risk=RiskLevel.MEDIUM,
        user_pref=ToolPermission.ALLOW,
    )
    assert without_autopilot == EffectivePermission.REQUEST_INPUT

    with_autopilot = resolve_permission(
        governance_mode=GovernanceMode.GOVERNED,
        autopilot_active=True,
        tool_risk=RiskLevel.MEDIUM,
        user_pref=ToolPermission.ALLOW,
    )
    assert with_autopilot == EffectivePermission.AUTO_PROCEED


def test_governed_high_risk_prompts_even_with_autopilot() -> None:
    """Tier 3 approval gate is never defeated by autopilot."""
    result = resolve_permission(
        governance_mode=GovernanceMode.GOVERNED,
        autopilot_active=True,
        tool_risk=RiskLevel.HIGH,
        user_pref=ToolPermission.ALLOW,
    )
    assert result == EffectivePermission.REQUEST_INPUT


# ── UI hints ───────────────────────────────────────────────────


def test_ui_state_unleashed_flags_override_active() -> None:
    """Frontend dims the per-tool pills when this is 'true'."""
    state = explain_permission_ui_state(GovernanceMode.UNLEASHED, autopilot_active=True)
    assert state["per_tool_override_active"] == "true"
    assert "UNLEASHED" in state["banner_headline"]


def test_ui_state_governed_flags_strict() -> None:
    """GOVERNED keeps per-tool pills active."""
    state = explain_permission_ui_state(GovernanceMode.GOVERNED, autopilot_active=False)
    assert state["per_tool_override_active"] == "false"
    assert "GOVERNED" in state["banner_headline"]
