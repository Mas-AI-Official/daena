"""Plan entitlements: the single source of truth for what each subscription tier unlocks.

This module is the feature-gating spine that the monetization surface needs. It answers
two questions the rest of the app keeps asking:

  1. "Is plan A at least as high as plan B?"            -> rank comparison (require_tier)
  2. "Does plan A include feature F?"                   -> feature lookup (require_feature)

PLAN RESOLUTION mirrors the budget-side rule in app/services/cost_guard.py exactly, so
"what plan is this tenant on" has ONE answer across the codebase: a FOUNDER user always
resolves to the FOUNDER tier; everyone else resolves to their tenant's ACTIVE
Subscription.plan, defaulting to FREE. (The duplication of this resolver with cost_guard
is deliberate for now -- folding both onto a shared helper is flagged future cleanup, not
done here, to keep this change surgical.)

The FastAPI dependencies that ENFORCE these answers (require_tier / require_feature) live
next to require_role in app/api/deps.py, to keep the api layer importing from core and not
the other way around.

FEATURE_MIN_PLAN below is a product/pricing decision surface: the mechanism (ranking,
gating) is fixed, but the exact feature-to-plan assignments are a founder business call,
expressed here as a tunable default in ONE place. Each feature maps to a capability that
already exists in code; no feature here is aspirational.
"""

from __future__ import annotations

import enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import Subscription


# ---------------------------------------------------------------------------
# Plan ranking
# ---------------------------------------------------------------------------
# Ordinal rank for the four customer tiers in app.core.constants.PlanType, plus the
# internal FOUNDER owner tier (which is a UserRole, not a PlanType, but resolves to the
# highest effective plan -- mirroring cost_guard, where FOUNDER short-circuits to its own
# unrestricted budget). Higher number == more access.
PLAN_RANK: dict[str, int] = {
    "FREE": 0,
    "PRO": 10,
    "MAX": 20,
    "ENTERPRISE": 30,
    "FOUNDER": 100,
}

# The canonical default when an unknown / missing plan string is seen anywhere below.
_DEFAULT_PLAN = "FREE"


class Feature(str, enum.Enum):
    """Gateable product capabilities.

    Every member maps to a real, already-shipped lever -- not a promise. Keeping this
    enum tight (versus inventing tiers of imaginary perks) is what keeps the gate honest:
    a 402 from require_feature always points at something the higher tier can actually do.
    """

    # RoutingMode.COUNCIL: parallel multi-model synthesis (see constants.RoutingMode).
    COUNCIL_ROUTING = "council_routing"
    # RoutingMode.QUINTESSENCE: Council + DCP expert-lens injection.
    QUINTESSENCE_ROUTING = "quintessence_routing"
    # /org team administration: member list, role assignment, seat management.
    ORG_MANAGEMENT = "org_management"


# Minimum plan required for each feature. This is the founder-tunable packaging table.
# Defaults are conservative and derived from how the capabilities are positioned today:
# Council is the entry paid differentiator, Quintessence is the premium tier, and team /
# org administration is the Enterprise surface.
FEATURE_MIN_PLAN: dict[Feature, str] = {
    Feature.COUNCIL_ROUTING: "PRO",
    Feature.QUINTESSENCE_ROUTING: "MAX",
    Feature.ORG_MANAGEMENT: "ENTERPRISE",
}


def plan_rank(plan: str | None) -> int:
    """Return the ordinal rank of a plan string, defaulting to FREE for unknown input."""
    if not plan:
        return PLAN_RANK[_DEFAULT_PLAN]
    return PLAN_RANK.get(plan.upper(), PLAN_RANK[_DEFAULT_PLAN])


def plan_satisfies(current: str | None, required: str | None) -> bool:
    """True if `current` plan ranks at or above `required` plan."""
    return plan_rank(current) >= plan_rank(required)


def min_plan_for_feature(feature: Feature) -> str:
    """Return the minimum plan name that unlocks `feature`."""
    return FEATURE_MIN_PLAN[feature]


def plan_has_feature(plan: str | None, feature: Feature) -> bool:
    """True if `plan` is high enough to unlock `feature`."""
    return plan_satisfies(plan, min_plan_for_feature(feature))


def plan_entitlements(plan: str | None) -> list[Feature]:
    """List every feature that `plan` unlocks. Useful for the upgrade UI to render
    'what you get' without the frontend re-encoding the packaging table."""
    return [feature for feature in Feature if plan_has_feature(plan, feature)]


async def resolve_effective_plan(db: AsyncSession, *, role: str | None, tenant_id) -> str:
    """Resolve the effective plan for a user.

    Mirrors cost_guard's resolution EXACTLY so plan identity has one answer:
      - FOUNDER role  -> "FOUNDER" (short-circuits; no DB read needed)
      - otherwise     -> the tenant's ACTIVE Subscription.plan, or "FREE"

    Returned plan is always upper-cased and present in PLAN_RANK (falls back to FREE).
    """
    if (role or "").upper() == "FOUNDER":
        return "FOUNDER"

    stmt = select(Subscription.plan).where(
        Subscription.tenant_id == tenant_id,
        Subscription.status == "ACTIVE",
    )
    result = await db.execute(stmt)
    plan = result.scalar_one_or_none() or _DEFAULT_PLAN
    plan = plan.upper()
    return plan if plan in PLAN_RANK else _DEFAULT_PLAN
