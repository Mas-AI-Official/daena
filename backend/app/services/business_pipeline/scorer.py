"""Deterministic opportunity scorer -- Sprint-19 PR-1.

Score is an integer 0..100 computed from structured fields. Pure
Python; no LLM. Same inputs always produce the same score, so
operator decisions are auditable + reproducible.

Components (each clamped 0..25):

  deadline_proximity   -- nearer deadline = higher (max 25)
  estimated_value      -- log-scaled USD value (max 25)
  effort_inverse       -- shorter effort = higher (max 25)
  type_weight          -- per opportunity_type baseline (max 25)

Total = sum, clamped 0..100. Source credibility is intentionally
NOT in the score -- credibility belongs in the source allowlist
(if it's allowlisted, it's credible). Otherwise an attacker with
seed file write access could dial credibility up to 11.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from app.services.business_pipeline.discoverer import DiscoveredOpportunity


# Per-type baseline (capped at 25). Tunable via founder policy
# in a future sprint; locked for Sprint-19.
_TYPE_WEIGHT: dict[str, int] = {
    "customer_lead": 22,
    "grant": 25,
    "accelerator": 20,
    "hackathon": 12,
    "freelance_project": 18,
    "partnership": 18,
    "bug_bounty_program": 15,
    "content_opportunity": 8,
}


def _deadline_proximity(deadline: datetime | None) -> int:
    if deadline is None:
        return 5  # baseline -- no deadline known
    now = datetime.now(UTC)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    delta = deadline - now
    days = delta.total_seconds() / 86400.0
    if days < 0:
        return 0  # already past due
    if days <= 1:
        return 25
    if days <= 3:
        return 22
    if days <= 7:
        return 18
    if days <= 14:
        return 13
    if days <= 30:
        return 9
    if days <= 90:
        return 5
    return 2


def _value_score(estimated_value_usd: int | None) -> int:
    if estimated_value_usd is None or estimated_value_usd <= 0:
        return 5  # baseline
    # log10($1000) = 3, log10($1M) = 6. Map 3..6 -> 8..25
    log_v = math.log10(max(estimated_value_usd, 1))
    raw = (log_v - 2.0) * 6.0  # 2->0, 3->6, 6->24
    return max(0, min(25, int(raw)))


def _effort_inverse(effort_hours: int | None) -> int:
    if effort_hours is None or effort_hours <= 0:
        return 10  # baseline -- effort unknown
    if effort_hours <= 1:
        return 25
    if effort_hours <= 4:
        return 22
    if effort_hours <= 8:
        return 18
    if effort_hours <= 24:
        return 13
    if effort_hours <= 80:
        return 8
    return 3


def _type_weight(opportunity_type: str) -> int:
    return _TYPE_WEIGHT.get(opportunity_type, 10)


def score_opportunity(op: DiscoveredOpportunity) -> int:
    """Deterministic 0..100 score for one opportunity.

    Components:
      deadline_proximity (0..25)
      estimated_value    (0..25)
      effort_inverse     (0..25)
      type_weight        (0..25)
    """
    total = (
        _deadline_proximity(op.deadline_at)
        + _value_score(op.estimated_value_usd)
        + _effort_inverse(op.effort_hours)
        + _type_weight(op.type)
    )
    return max(0, min(100, total))


def score_components(op: DiscoveredOpportunity) -> dict[str, int]:
    """Return individual components for audit / debug."""
    return {
        "deadline_proximity": _deadline_proximity(op.deadline_at),
        "value_score": _value_score(op.estimated_value_usd),
        "effort_inverse": _effort_inverse(op.effort_hours),
        "type_weight": _type_weight(op.type),
    }
