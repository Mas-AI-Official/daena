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

import uuid
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.crm import OutreachDraft
from app.services.company_context import (
    CompanyContext,
    company_context_store,
)
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
    # Phase 10 commit-1: refuse the contradictory combination at the
    # REST boundary. Previously the UI form let the founder set
    # ``auto_send=true`` AND ``require_founder_approval=false``
    # simultaneously, which would dispatch outbound traffic without
    # any approval gate. Defense-in-depth — the UI also disables
    # auto_send when approval is off (CompanyModePage.tsx).
    if body.auto_send and not body.require_founder_approval:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "auto_send_requires_founder_approval",
                "message": (
                    "auto_send=true requires require_founder_approval=true. "
                    "Outbound traffic must be founder-approved."
                ),
            },
        )

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
        # EH-01: keep the operational label, drop the raw exc from the body
        # (full detail is in the log line above).
        raise HTTPException(status_code=500, detail="activation_failed") from exc

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

    # Phase 1 F4 (2026-04-24): publish the brief into the runtime
    # CompanyContext store so soul_engine.get_soul_prompt() picks it up
    # on every subsequent chat without requiring a server restart or a
    # disk re-read. The on-disk file remains the durable source -- this
    # is the runtime cache for fast reads.
    try:
        runtime_ctx = CompanyContext(
            company_name=brief.company_name,
            one_liner=brief.company_one_liner,
            target_customer=brief.target_customer,
            pain=brief.customer_pain,
            promise=brief.our_promise,
            proof_points=list(brief.proof_points or []),
            channels=[c.value for c in brief.channels],
            tone=brief.tone or "professional",
        )
        tenant_key = str(getattr(user, "tenant_id", "") or "founder")
        company_context_store.set(tenant_key, runtime_ctx)
        # Mirror to the bootstrap key so chat handlers that haven't
        # plumbed tenant_id yet still find the brief.
        company_context_store.set("founder", runtime_ctx)
    except Exception as exc:
        logger.warning("company_mode.context_publish_failed", error=str(exc))

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
    # Parent chain: v1 (0) -> api (1) -> app (2) -> backend (3).
    # We want backend/app/soul/, so parents[2] is the correct index.
    # parents[3] was a P0 bug: it resolved to backend/soul/ which is NOT
    # covered by .gitignore line 15 (`backend/app/soul/`), so a real
    # founder brief saved from the UI would leak to public git on the
    # next `git add -A`.
    return here.parents[2] / "soul" / "company_seed.md"


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


@router.delete("/seed-brief")
async def delete_seed_brief(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Soft-archive the persisted seed brief.

    Phase 10b: the founder UI already exposed a Delete button at
    ``CompanyModePage.tsx:235`` but the backend route did not exist
    (Phase 9D ghost G1 — 405 Method Not Allowed). Per the audit's
    "prefer soft-delete/archive semantics if persistent" rule, we
    rename the file to ``company_seed.archived-<UTC-timestamp>.md``
    instead of unlinking. The founder can manually purge from disk
    if they want; this preserves the IP for recovery.

    Returns 200 with ``exists: false`` either way so the UI optimistic
    update succeeds.
    """
    _ = user
    path = _seed_path()
    if not path.exists():
        return {"exists": False, "archived_to": None}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archived = path.with_name(f"{path.stem}.archived-{stamp}{path.suffix}")
    try:
        path.rename(archived)
    except OSError as exc:
        logger.error("company_mode.seed_archive_failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail="seed_archive_failed",  # EH-01: no raw exc
        ) from exc

    # Best-effort: also clear the runtime context for this tenant so
    # the next chat doesn't keep responding as the (now-archived) VP.
    try:
        tenant_key = str(getattr(user, "tenant_id", "") or "founder")
        company_context_store.clear(tenant_key)
        company_context_store.clear("founder")
    except Exception as exc:  # noqa: BLE001
        logger.warning("company_mode.context_clear_failed", error=str(exc))

    logger.info(
        "company_mode.seed_archived",
        archived_to=str(archived.name),
    )
    return {"exists": False, "archived_to": archived.name}


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
            status_code=500, detail="seed_write_failed",  # EH-01: no raw exc
        ) from exc

    # Phase 1 F4: a save-without-activate still updates the runtime
    # store so the next chat sees the freshest brief. The activate path
    # already does this; saving alone used to leave the cache stale.
    try:
        runtime_ctx = CompanyContext(
            company_name=body.company_name,
            one_liner=body.company_one_liner,
            target_customer=body.target_customer,
            pain=body.customer_pain,
            promise=body.our_promise,
            proof_points=list(body.proof_points or []),
            channels=[c for c in body.channels],
            tone=body.tone or "professional",
        )
        tenant_key = str(getattr(user, "tenant_id", "") or "founder")
        company_context_store.set(tenant_key, runtime_ctx)
        company_context_store.set("founder", runtime_ctx)
    except Exception as exc:
        logger.warning("company_mode.context_publish_failed", error=str(exc))

    logger.info(
        "company_mode.seed_saved",
        company=body.company_name,
    )
    return {"exists": True, "updated_at": updated_at.isoformat()}


# ── Runtime context: chat orchestrator + dashboards read this ─────


@router.get("/context")
async def get_runtime_context(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Return the active CompanyContext from the runtime store.

    Frontend uses this to render the "VP of <Company>" badge in the
    chat header + on department cards, and to attach a chip to chat
    messages so the orchestrator can see which company brief is in
    effect for this turn. 404 when no Company Mode has been activated
    yet -- the UI handles that with a "Activate Company Mode" CTA.
    """
    tenant_key = str(getattr(user, "tenant_id", "") or "founder")
    ctx = company_context_store.get(tenant_key) or company_context_store.get("founder")
    if ctx is None:
        raise HTTPException(status_code=404, detail="company_context_not_set")
    return ctx.model_dump(mode="json")


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


async def _mark_crm_draft_sent(
    db: AsyncSession,
    draft_id: str,
    *,
    tenant_id: Any,
) -> None:
    """Mirror a successful send onto the persisted OutreachDraft row.

    Marketing-mission drafts share their id with a crm_outreach_drafts
    row (register_draft reuses the id author_outreach persisted), so
    the Pipeline page must see SENT instead of a stale DRAFT. Drafts
    with no CRM row (reply-confirmation follow-ups) are a silent no-op.
    Fail-open: the provider outcome already landed on the in-memory
    draft; a mirror failure is logged, never breaks the send response.
    """
    try:
        row_id = uuid.UUID(draft_id)
    except ValueError:
        return
    try:
        stmt = select(OutreachDraft).where(
            OutreachDraft.id == row_id,
            OutreachDraft.tenant_id == tenant_id,
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return
        row.status = "SENT"
        await db.commit()
    except Exception as exc:
        logger.warning(
            "company_mode.crm_send_mirror_failed",
            draft_id=draft_id,
            error=str(exc),
        )


@router.post("/missions/{mission_id}/drafts/{draft_id}/send")
async def send_draft(
    mission_id: str,
    draft_id: str,
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> SendResponse:
    """Dispatch a single draft via the provider router."""
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
        await _mark_crm_draft_sent(db, draft_id, tenant_id=user.tenant_id)
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
