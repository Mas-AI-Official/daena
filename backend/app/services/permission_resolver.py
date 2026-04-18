"""Unify per-tool Allow/Ask/Block with the governance mode pipeline.

Background
----------
Daena has two permission layers that evolved separately:

1. ``GovernanceMode`` (UNLEASHED / BALANCED / GOVERNED) with its tier
   map at ``constants.GOVERNANCE_TIER_MAP``. Decides approval behavior
   for every action Daena takes based on assessed risk level.
2. Per-tool ``Allow/Ask/Block`` permissions on MCP extensions and
   connector tools. Added earlier to let users configure individual
   tools.

These layers can disagree. UNLEASHED governance says "auto-approve
everything except CRITICAL" but a per-tool "Ask" pill on a low-risk
tool would still prompt the user. That is the confusion operators
have reported.

This resolver makes governance mode the source of truth and treats
per-tool Allow/Ask/Block as a constrained override:

* UNLEASHED: per-tool defaults force to ALLOW. BLOCK is still honored
  because user explicitly opted out of that specific tool.
* BALANCED: per-tool overrides are respected for high-risk tools,
  auto-promoted to ALLOW for read-only / low-risk tools if the user
  left the default.
* GOVERNED: per-tool overrides are strictly enforced, identical to
  the pre-resolver behavior. This is the enterprise mode.

Autopilot amplifies the effect:

* UNLEASHED + Autopilot ON -> Daena does not prompt at all. Matches
  the "AGI Mode Active" UX.
* GOVERNED + Autopilot ON -> tier 3+ still blocks and asks; tier 0-1
  auto-proceeds. Autopilot cannot defeat GOVERNED approval gates.
"""

from __future__ import annotations

from enum import Enum

from app.core.constants import GovernanceMode, RiskLevel
from app.core.constants import GOVERNANCE_TIER_MAP


class ToolPermission(str, Enum):
    """The three values stored per-tool in User.settings JSONB."""

    ALLOW = "ALLOW"
    ASK_EACH_TIME = "ASK_EACH_TIME"
    BLOCK = "BLOCK"


class EffectivePermission(str, Enum):
    """What the runtime actually does at tool-dispatch time.

    AUTO_PROCEED:  Run without prompting. Log + audit still happen.
    REQUEST_INPUT: Pause the flow and ask the user to confirm.
    REFUSE:        Do not run. Log a refusal.
    """

    AUTO_PROCEED = "AUTO_PROCEED"
    REQUEST_INPUT = "REQUEST_INPUT"
    REFUSE = "REFUSE"


def resolve_permission(
    *,
    governance_mode: GovernanceMode,
    autopilot_active: bool,
    tool_risk: RiskLevel,
    user_pref: ToolPermission | None,
) -> EffectivePermission:
    """Compute the effective permission for a single tool invocation.

    Args:
        governance_mode: UNLEASHED / BALANCED / GOVERNED.
        autopilot_active: whether AGI/continuation mode is on.
        tool_risk: the tool's inherent risk classification.
        user_pref: per-tool override the operator set, if any.

    Returns:
        EffectivePermission telling the tool dispatcher what to do.
    """
    # Always respect an explicit BLOCK, no matter the mode. Operators
    # who turned a specific tool off mean it. We never override that.
    if user_pref == ToolPermission.BLOCK:
        return EffectivePermission.REFUSE

    tier_map = GOVERNANCE_TIER_MAP.get(
        governance_mode,
        GOVERNANCE_TIER_MAP[GovernanceMode.BALANCED],
    )
    tier = tier_map.get(tool_risk, 0)

    # Tier semantics (see constants.py::GOVERNANCE_TIER_MAP):
    #   0 = logged, silent
    #   1 = logged
    #   2 = notified (post-hoc)
    #   3 = approval required
    #   4 = strict approval required

    if governance_mode == GovernanceMode.UNLEASHED:
        # UNLEASHED + autopilot = full autonomy. We only pause on tier 4,
        # which is only reached for CRITICAL tool_risk (data exfiltration,
        # destructive ops). Per-tool ALLOW/ASK are overridden to ALLOW
        # because UNLEASHED is the whole point of the mode.
        if tier >= 3:
            return EffectivePermission.REQUEST_INPUT
        return EffectivePermission.AUTO_PROCEED

    if governance_mode == GovernanceMode.BALANCED:
        # Honor ASK_EACH_TIME only when the tier is >= 2. Low/no risk
        # tools auto-proceed even if the user default is ASK, matching
        # the "auto-proceed for most actions" description in BALANCED.
        if user_pref == ToolPermission.ASK_EACH_TIME and tier >= 2:
            return EffectivePermission.REQUEST_INPUT
        if tier >= 3:
            return EffectivePermission.REQUEST_INPUT
        if autopilot_active and tier <= 2:
            return EffectivePermission.AUTO_PROCEED
        return EffectivePermission.AUTO_PROCEED

    # GOVERNED: strict enforcement. ASK_EACH_TIME means ASK no matter
    # what tier. Autopilot does not override approval gates here; it
    # only affects tier 0-1 "logged" actions.
    if user_pref == ToolPermission.ASK_EACH_TIME:
        return EffectivePermission.REQUEST_INPUT
    if tier >= 3:
        return EffectivePermission.REQUEST_INPUT
    if tier >= 2 and not autopilot_active:
        return EffectivePermission.REQUEST_INPUT
    return EffectivePermission.AUTO_PROCEED


def explain_permission_ui_state(
    governance_mode: GovernanceMode,
    autopilot_active: bool,
) -> dict[str, str]:
    """Return UI hints so the Connections page can explain the state.

    The frontend uses this to dim the per-tool pills when governance
    overrides them, and to show a banner explaining why.
    """
    if governance_mode == GovernanceMode.UNLEASHED:
        return {
            "per_tool_override_active": "true",
            "banner_headline": "UNLEASHED: governance is at the agent level, not per-tool",
            "banner_body": (
                "Per-tool Allow/Ask settings below are shown for reference. "
                "In UNLEASHED mode Daena proceeds without asking, except for "
                "CRITICAL actions (data exfiltration, destructive ops). "
                "Tools you set to BLOCK are always honored."
            ),
        }
    if governance_mode == GovernanceMode.BALANCED:
        return {
            "per_tool_override_active": "false",
            "banner_headline": "BALANCED: per-tool Ask only applies to medium/high-risk tools",
            "banner_body": (
                "Read-only and low-risk tools auto-proceed. Write operations "
                "and higher-risk tools respect your Ask/Block settings."
            ),
        }
    # GOVERNED
    return {
        "per_tool_override_active": "false",
        "banner_headline": "GOVERNED: per-tool settings are strictly enforced",
        "banner_body": (
            "Daena prompts for confirmation on every Ask tool and refuses "
            "every Block tool. Autopilot only auto-proceeds on "
            "tier 0-1 logged actions."
        ),
    }
