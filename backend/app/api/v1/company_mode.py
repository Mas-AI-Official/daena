"""Company Mode API -- activate Daena as an AI marketing+sales agency.

Endpoints:

* ``POST /company-mode/activate`` -- kick off Sales + Marketing missions.
  Drafts land in the approval queue by default; sending is never
  unattended unless the founder explicitly opts in via ``auto_send=True``
  (discouraged on LinkedIn).
* ``GET /company-mode/activations`` -- recent activations (ring buffer).
* ``GET /company-mode/seed-brief`` -- load the canonical founder brief
  from disk so the UI can pre-fill the form.
* ``POST /company-mode/seed-brief`` -- save a brief to disk. Founder IP,
  gitignored.
* ``GET /company-mode/missions/{mission_id}/drafts`` -- list drafts for a
  mission (from the module-level store).
* ``POST /company-mode/missions/{mission_id}/drafts/{draft_id}/send`` --
  dispatch one draft through the provider routing layer.
* ``POST /company-mode/replies/process`` -- classify a prospect reply,
  suggest booking slots, queue a confirmation draft on positive intent.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
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
    get_draft,
    list_drafts_for_mission,
    register_draft,
)
from app.services.company_mode_providers import dispatch_send
from app.services.company_mode_replies import classify_reply, suggest_booking_slots

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


# ── Seed brief persistence (TICKET-COMPANY-MODE-SEED) ─────────────


def _seed_path() -> Path:
    """Resolve the on-disk path for the canonical seed brief.

    Lives under ``backend/app/soul/`` which the repo root .gitignore
    excludes in full. This file is founder IP (CLAUDE.md rule 15) --
    never commit.
    """
    here = Path(__file__).resolve()
    # backend/app/api/v1/company_mode.py -> backend/app/soul/company_seed.md
    return here.parents[3] / "soul" / "company_seed.md"


def _load_seed() -> tuple[ActivateRequest | None, datetime | None]:
    """Parse the seed file into (ActivateRequest, mtime) if it exists."""
    path = _seed_path()
    if not path.exists():
        return None, None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("company_mode.seed_read_failed", error=str(exc))
        return None, None

    # Expect ``---\n<yaml>\n---\n# Seed brief\n``
    if not raw.startswith("---"):
        logger.warning("company_mode.seed_invalid_format", path=str(path))
        return None, None
    parts = raw.split("---", 2)
    if len(parts) < 3:
        logger.warning("company_mode.seed_invalid_format", path=str(path))
        return None, None
    frontmatter = parts[1].strip()
    try:
        data = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        logger.warning("company_mode.seed_yaml_failed", error=str(exc))
        return None, None
    if not isinstance(data, dict):
        logger.warning("company_mode.seed_not_mapping", path=str(path))
        return None, None

    try:
        brief = ActivateRequest(**data)
    except Exception as exc:
        logger.warning("company_mode.seed_validation_failed", error=str(exc))
        return None, None

    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return brief, updated_at


def _save_seed(brief: ActivateRequest) -> datetime:
    """Write the brief to disk as YAML frontmatter + header. Returns mtime."""
    path = _seed_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = brief.model_dump(mode="json")
    yaml_block = yaml.safe_dump(
        payload,
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    content = f"---\n{yaml_block}\n---\n# Seed brief\n"
    path.write_text(content, encoding="utf-8")
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


@router.get("/seed-brief")
async def get_seed_brief(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Return the persisted seed brief (or exists=false if absent).

    Founder-only. The frontend uses this to pre-fill the activation
    form when the founder clicks "Seed".
    """
    _ = user
    brief, updated_at = _load_seed()
    return {
        "brief": brief.model_dump(mode="json") if brief else None,
        "exists": brief is not None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


@router.post("/seed-brief")
async def save_seed_brief(
    body: ActivateRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Persist the brief to the gitignored soul directory."""
    _ = user
    try:
        updated_at = _save_seed(body)
    except OSError as exc:
        logger.error("company_mode.seed_write_failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"seed_write_failed: {exc}",
        ) from exc
    logger.info(
        "company_mode.seed_saved",
        company=body.company_name,
    )
    return {"exists": True, "updated_at": updated_at.isoformat()}


# ── Draft store access + send dispatch (TICKET-COMPANY-MODE-03) ───


class SendResponse(BaseModel):
    """Envelope returned by POST .../drafts/{id}/send."""

    outcome: dict[str, Any]
    draft: dict[str, Any]


@router.get("/missions/{mission_id}/drafts")
async def list_mission_drafts(
    mission_id: str,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> list[dict[str, Any]]:
    """List every draft belonging to a mission."""
    _ = user
    drafts = list_drafts_for_mission(mission_id)
    return [d.to_dict() for d in drafts]


@router.post("/missions/{mission_id}/drafts/{draft_id}/send")
async def send_draft(
    mission_id: str,
    draft_id: str,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> SendResponse:
    """Dispatch a single draft via the provider router."""
    _ = user
    draft = get_draft(draft_id)
    if draft is None or draft.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="draft_not_found")

    draft.status = "sending"
    outcome = await dispatch_send(draft)
    draft.status = outcome["status"]
    if outcome["status"] == "sent" and outcome["sent_at"]:
        try:
            draft.sent_at = datetime.fromisoformat(outcome["sent_at"])
        except ValueError:
            draft.sent_at = datetime.now(UTC)
        draft.error = None
    elif outcome["status"] in ("failed", "blocked"):
        draft.error = outcome["detail"]

    logger.info(
        "company_mode.draft_send",
        draft_id=draft_id,
        mission_id=mission_id,
        status=outcome["status"],
        provider=outcome["provider"],
    )
    return SendResponse(outcome=dict(outcome), draft=draft.to_dict())


# ── Reply-driven auto-booking (TICKET-COMPANY-MODE-02) ────────────


class ProcessReplyRequest(BaseModel):
    """Founder payload describing a prospect reply to process."""

    mission_id: str = Field(..., min_length=1, max_length=120)
    draft_id: str = Field(..., min_length=1, max_length=120)
    reply_text: str = Field(..., min_length=1, max_length=8000)
    reply_from: str = Field(..., min_length=1, max_length=320)


@router.post("/replies/process")
async def process_reply(
    body: ProcessReplyRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Classify a reply; on positive+meet, queue a confirmation draft.

    The original draft is looked up in the store; its channel is
    reused so the follow-up goes out on the same surface the prospect
    replied on. Negative / neutral replies return no slots and no new
    draft.
    """
    _ = user
    original = get_draft(body.draft_id)
    classification = classify_reply(body.reply_text)
    result: dict[str, Any] = {
        "classification": {
            "sentiment": classification.sentiment,
            "intent": classification.intent,
            "keywords_matched": classification.keywords_matched,
        },
        "suggested_slots": [],
        "confirmation_draft_id": None,
    }

    if classification.sentiment != "positive" or classification.intent != "meet":
        return result

    slots = suggest_booking_slots(datetime.now(UTC), count=3)
    result["suggested_slots"] = [s.isoformat() for s in slots]

    handle = body.reply_from.split("@")[0] if "@" in body.reply_from else body.reply_from
    slot_strs = ", ".join(s.strftime("%a %Y-%m-%d %H:%M UTC") for s in slots)
    body_text = (
        f"Hi {handle},\n\n"
        f"Great to hear from you. I have these slots open: {slot_strs}. "
        f"Reply with the one that works and I'll send an invite.\n\n"
        "-- Daena"
    )
    channel = original.channel if original else MissionChannel.EMAIL.value
    subject = "Re: Booking a time" if channel == MissionChannel.EMAIL.value else None

    confirmation = register_draft(
        mission_id=body.mission_id,
        channel=channel,
        recipient=body.reply_from,
        body=body_text,
        subject=subject,
    )
    result["confirmation_draft_id"] = confirmation.draft_id
    logger.info(
        "company_mode.confirmation_queued",
        mission_id=body.mission_id,
        draft_id=confirmation.draft_id,
        channel=channel,
    )
    return result
