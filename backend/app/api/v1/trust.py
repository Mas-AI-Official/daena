"""Trust Ladder API -- Sprint-18 PR-2 (2026-05-06).

REST surface over ``trust_policy`` + ``trust_ladder``.

Endpoints:

  * GET  /trust/policies                      -- list all policy + ladder rows
  * GET  /trust/eligible-tools                -- static eligibility lists
  * POST /trust/policies/tier-set             -- founder-only tier mutation
  * POST /trust/policies/preview-decision     -- dry-run "would this graduate?"

Security:

  * GET endpoints: any authenticated user (read-only state).
  * Tier-set: ``require_role("FOUNDER")`` -- enforced at FastAPI layer
    BEFORE the trust_policy module is touched. Daena's tool dispatches
    NEVER hit this endpoint -- they go through the controlled
    execution dispatcher, which has no path to ``set_max_auto_tier``.

The tier-set body MUST include the exact ``confirmation_phrase``
expected by ``trust_policy.expected_confirmation_phrase`` for the
target (tool_id, tier) pair. The frontend computes + displays this
phrase to the founder and the trust_policy module verifies it
again server-side. Prompt injection cannot bypass because the
expected phrase is a static template.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.logging import get_logger
from app.services import trust_ladder, trust_policy
from app.services.trust_policy import (
    DispatchInitiator,
    TrustTier,
    TRUST_ELIGIBLE_TOOLS,
    TRUST_FORBIDDEN_TOOLS,
    expected_confirmation_phrase,
    set_max_auto_tier,
    should_auto_approve,
)

logger = get_logger(__name__)
router = APIRouter()


# ────────────────────────────────────────────────────────────────────
# Read endpoints
# ────────────────────────────────────────────────────────────────────


class PolicyRow(BaseModel):
    tool_id: str
    template_class: str
    max_auto_tier: str
    locked_reason: str | None
    approvals_count: int
    rejection_count: int
    last_approved_at: str | None
    last_rejected_at: str | None
    eligible: bool
    forbidden: bool


@router.get("/policies", response_model=list[PolicyRow])
async def list_policies(
    user: CurrentUser = Depends(get_current_user),
) -> list[PolicyRow]:
    """List every policy row joined with ladder counters.

    Both stores are keyed by (tool_id, template_class). We union
    keys from both so a row with ladder activity but no explicit
    policy still shows (default tier NONE)."""
    policies = {p.key: p for p in trust_policy.list_policies()}
    ladder = {e.key: e for e in trust_ladder.list_entries()}
    keys = set(policies.keys()) | set(ladder.keys())

    rows: list[PolicyRow] = []
    for key in sorted(keys):
        tool_id, _, template_class = key.partition("::")
        policy = policies.get(key) or trust_policy.get_policy(
            tool_id=tool_id, template_class=template_class,
        )
        l = ladder.get(key)
        rows.append(PolicyRow(
            tool_id=tool_id,
            template_class=template_class,
            max_auto_tier=policy.max_auto_tier.value,
            locked_reason=policy.locked_reason,
            approvals_count=l.approvals_count if l else 0,
            rejection_count=l.rejection_count if l else 0,
            last_approved_at=l.last_approved_at if l else None,
            last_rejected_at=l.last_rejected_at if l else None,
            eligible=tool_id in TRUST_ELIGIBLE_TOOLS,
            forbidden=tool_id in TRUST_FORBIDDEN_TOOLS,
        ))
    return rows


class EligibilityResponse(BaseModel):
    eligible_tools: list[str]
    forbidden_tools: list[str]
    available_tiers: list[str]
    min_approvals_to_graduate: int


@router.get("/eligible-tools", response_model=EligibilityResponse)
async def get_eligibility(
    user: CurrentUser = Depends(get_current_user),
) -> EligibilityResponse:
    """Static lists for the UI to render lock-reasons + dropdowns."""
    return EligibilityResponse(
        eligible_tools=sorted(TRUST_ELIGIBLE_TOOLS),
        forbidden_tools=sorted(TRUST_FORBIDDEN_TOOLS),
        available_tiers=[
            TrustTier.NONE.value,
            TrustTier.SUGGEST_ONLY.value,
            TrustTier.AUTO_APPROVE_LOW_RISK.value,
        ],
        min_approvals_to_graduate=trust_policy.MIN_APPROVALS_TO_GRADUATE,
    )


# ────────────────────────────────────────────────────────────────────
# Tier-set (founder only)
# ────────────────────────────────────────────────────────────────────


class TierSetRequest(BaseModel):
    tool_id: str
    template_class: str
    tier: str
    confirmation_phrase: str = Field(min_length=1, max_length=300)


class TierSetResponse(BaseModel):
    tool_id: str
    template_class: str
    max_auto_tier: str
    expected_confirmation_phrase: str | None = None
    success: bool
    error_code: str | None = None


@router.post("/policies/tier-set", response_model=TierSetResponse)
async def tier_set(
    body: TierSetRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> TierSetResponse:
    """Founder-only tier mutation.

    Returns 200 with ``success=False`` and ``error_code`` instead of
    raising HTTPException for expected refusals (forbidden tool,
    confirmation phrase mismatch, rejections force NONE) so the UI
    can render a clear inline error. Returns 4xx only for bad
    enum / unauthorized.
    """
    try:
        tier_enum = TrustTier(body.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_tier")

    try:
        entry = set_max_auto_tier(
            tool_id=body.tool_id,
            template_class=body.template_class,
            tier=tier_enum,
            requested_by_user_id=str(user.id),
            is_founder=True,  # require_role guarantees this
            confirmation_phrase=body.confirmation_phrase,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        return TierSetResponse(
            tool_id=body.tool_id,
            template_class=body.template_class,
            max_auto_tier="none",
            expected_confirmation_phrase=expected_confirmation_phrase(
                body.tool_id, tier_enum,
            ),
            success=False,
            error_code=str(exc),
        )

    logger.info(
        "trust.tier_set.success",
        tool_id=body.tool_id,
        template_class=body.template_class,
        tier=tier_enum.value,
        by=str(user.id),
    )
    return TierSetResponse(
        tool_id=entry.tool_id,
        template_class=entry.template_class,
        max_auto_tier=entry.max_auto_tier.value,
        success=True,
    )


# ────────────────────────────────────────────────────────────────────
# Preview decision (dry run)
# ────────────────────────────────────────────────────────────────────


class PreviewRequest(BaseModel):
    tool_id: str
    payload: dict[str, Any]
    initiator: str = "operator"


class PreviewResponse(BaseModel):
    auto_approve: bool
    reason: str
    template_class: str | None
    approvals_count: int
    rejection_count: int
    max_auto_tier: str


@router.post("/policies/preview-decision", response_model=PreviewResponse)
async def preview_decision(
    body: PreviewRequest,
    user: CurrentUser = Depends(get_current_user),
) -> PreviewResponse:
    """Dry-run: would this request auto-approve right now?"""
    try:
        initiator_enum = DispatchInitiator(body.initiator)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_initiator")

    decision = should_auto_approve(
        tool_id=body.tool_id,
        payload=body.payload,
        initiator=initiator_enum,
    )
    return PreviewResponse(
        auto_approve=decision.auto_approve,
        reason=decision.reason,
        template_class=decision.template_class,
        approvals_count=decision.approvals_count,
        rejection_count=decision.rejection_count,
        max_auto_tier=decision.max_auto_tier.value,
    )
