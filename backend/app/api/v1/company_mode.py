"""Company Mode API -- activate Daena as an AI marketing+sales agency.

One endpoint (POST /company-mode/activate) takes a founder brief and
kicks off Sales + Marketing missions. Drafts land in the approval
queue by default; sending is never unattended unless the founder
explicitly opts in via ``auto_send=True`` (discouraged on LinkedIn).

Founder can pull activation history via GET /company-mode/activations
(returns the last N activations from the in-process registry).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.company_mode import (
    ActivationBrief,
    ActivationResult,
    MissionChannel,
    activate,
)

logger = get_logger(__name__)

router = APIRouter()


# ── Request / response schemas ─────────────────────────────────────


class ActivateRequest(BaseModel):
    """What the founder sends to activate Daena as a company.

    Mirrors the ``ActivationBrief`` dataclass but stays a Pydantic
    surface so FastAPI validates the channel enum + bounds on limits
    before anything heavy runs.
    """

    company_name: str = Field(..., min_length=1, max_length=120)
    company_one_liner: str = Field(..., min_length=3, max_length=300)
    target_customer: str = Field(..., min_length=3, max_length=600)
    customer_pain: str = Field(..., min_length=3, max_length=600)
    our_promise: str = Field(..., min_length=3, max_length=600)
    proof_points: list[str] = Field(default_factory=list, max_length=10)
    channels: list[str] = Field(
        default_factory=lambda: ["linkedin", "email"],
        description="One or more of: linkedin, email, twitter_dm, sms, web_form, phone",
    )
    prospect_limit_per_mission: int = Field(default=10, ge=1, le=50)
    tone: str = Field(default="warm-direct", max_length=60)
    auto_send: bool = False
    require_founder_approval: bool = True
    notes: str | None = Field(default=None, max_length=2000)


# Tiny ring buffer so /activations returns the last N without a DB
# model. Production could persist these; for now they live in memory
# and are enough for the founder UI to render a timeline.
_ACTIVATION_HISTORY: deque[dict[str, Any]] = deque(maxlen=50)


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/activate")
async def activate_company(
    body: ActivateRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Activate Daena to run autonomous GTM for the company described.

    Founder-only. Produces prospect list + first-touch drafts +
    missions. Outbound send is gated behind the approval queue unless
    ``auto_send=True`` (which triggers a governance warning for
    LinkedIn because unattended LI automation breaks their ToS).
    """
    try:
        channels = [MissionChannel(c.lower()) for c in body.channels] or [MissionChannel.EMAIL]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid channel: {exc}") from exc

    # Safety: loud warning when auto-send is enabled on LinkedIn.
    warning: str | None = None
    if body.auto_send and MissionChannel.LINKEDIN in channels:
        warning = (
            "auto_send=true with linkedin channel violates LinkedIn ToS and "
            "risks account suspension. Prefer draft+click-to-send; override "
            "only if you accept the account-risk."
        )
        logger.warning(
            "company_mode.linkedin_autosend_warn",
            founder=getattr(user, "email", None),
        )

    brief = ActivationBrief(
        company_name=body.company_name,
        company_one_liner=body.company_one_liner,
        target_customer=body.target_customer,
        customer_pain=body.customer_pain,
        our_promise=body.our_promise,
        proof_points=body.proof_points,
        channels=channels,
        prospect_limit_per_mission=body.prospect_limit_per_mission,
        tone=body.tone,
        auto_send=body.auto_send,
        require_founder_approval=body.require_founder_approval,
        notes=body.notes,
    )

    try:
        result: ActivationResult = await activate(
            db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            brief=brief,
        )
    except Exception as exc:
        logger.error("company_mode.activation_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"activation_failed: {exc}") from exc

    payload = result.to_dict()
    if warning:
        payload["governance_warning"] = warning
    _ACTIVATION_HISTORY.appendleft({
        "activation_id": payload["activation_id"],
        "created_at": payload["created_at"],
        "company_name": brief.company_name,
        "prospects": payload["prospects_count"],
        "drafts": sum(m["drafts_generated"] for m in payload["missions"]),
        "summary": payload["summary"],
    })
    return payload


@router.get("/activations")
async def list_activations(
    user: CurrentUser = Depends(require_role("FOUNDER")),
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Recent activations (in-memory ring buffer)."""
    _ = user
    return list(_ACTIVATION_HISTORY)[: max(1, min(limit, 50))]
