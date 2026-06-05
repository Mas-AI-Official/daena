"""Governance policy gate.

Classifies each agent action into a governance tier and an outcome,
mirroring Daena's tier model (0-1 logged, 2 notified, 3+ approval
required) and its three governance modes (UNLEASHED / BALANCED /
GOVERNED). The gate is the accountability layer: capability is not
enough -- every action must clear policy before it executes, and the
decision is recorded to the audit trail regardless of outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

# action_type -> (governance_tier, risk_level)
# The exploit-generation step is deliberately Tier 4 / CRITICAL: it is
# the high-stakes action a governed system must gate even though the
# model is perfectly capable of producing it.
_POLICY: dict[str, tuple[int, str]] = {
    "ANALYZE_CONTRACT": (1, "LOW"),
    "RANK_SEVERITY": (1, "LOW"),
    "PROPOSE_REMEDIATION": (2, "MEDIUM"),
    "GENERATE_EXPLOIT_POC": (4, "CRITICAL"),
    "SYNTHESIZE_VERDICT": (1, "LOW"),
}

_DEFAULT = (3, "HIGH")

_VALID_MODES = ("UNLEASHED", "BALANCED", "GOVERNED")


@dataclass(frozen=True)
class GateDecision:
    """Outcome of evaluating one action against governance policy."""

    action_type: str
    governance_tier: int
    risk_level: str
    result: str  # ALLOWED | APPROVAL_REQUIRED
    executed: bool
    rationale: str


def evaluate(
    action_type: str,
    *,
    mode: str = "GOVERNED",
    autonomous: bool = True,
) -> GateDecision:
    """Evaluate an action against the active governance mode.

    Args:
        action_type: One of the known action types (``_POLICY``).
        mode: Governance mode (UNLEASHED / BALANCED / GOVERNED).
        autonomous: When True (an unattended demo run), an
            APPROVAL_REQUIRED action is recorded but NOT executed --
            it waits for a human. When False, a caller is assumed to be
            present to approve, so the action still does not auto-run
            here; ``executed`` only ever flips True for ALLOWED.

    The asymmetry to notice: a Tier 4 asset/exploit action is gated even
    in UNLEASHED mode. UNLEASHED removes the governance pipeline, but the
    shield (asset protection) is always on -- exactly as in Daena.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"unknown governance mode: {mode!r}")

    tier, risk = _POLICY.get(action_type, _DEFAULT)

    if mode == "UNLEASHED":
        if tier >= 4:
            result = "APPROVAL_REQUIRED"
            rationale = "Tier 4 asset action gated even in UNLEASHED (shield always on)."
        else:
            result = "ALLOWED"
            rationale = "UNLEASHED: auto-proceed (shield-only)."
    elif mode == "BALANCED":
        if tier >= 4:
            result = "APPROVAL_REQUIRED"
            rationale = "BALANCED: approval required for Tier 4 only."
        else:
            result = "ALLOWED"
            rationale = "BALANCED: light governance, auto-proceed."
    else:  # GOVERNED
        if tier >= 3:
            result = "APPROVAL_REQUIRED"
            rationale = f"GOVERNED: Tier {tier} requires explicit human approval."
        else:
            result = "ALLOWED"
            rationale = (
                "GOVERNED: Tier 2 allowed, user notified."
                if tier == 2
                else "GOVERNED: Tier 0-1 logged."
            )

    executed = result == "ALLOWED"
    return GateDecision(
        action_type=action_type,
        governance_tier=tier,
        risk_level=risk,
        result=result,
        executed=executed,
        rationale=rationale,
    )
