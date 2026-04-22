"""Provider dispatcher for Company Mode outbound sends.

Each supported channel has a send_* function that accepts a Draft
and returns a ``SendOutcome``. The dispatcher routes by channel and
returns a typed outcome so the REST layer can store status + detail
without caring about the underlying provider.

Safety posture (deliberate):

* **Email**: we write an RFC-822 message to ``var/outbox/<draft_id>.eml``
  instead of hitting SMTP. This is the founder-approval-safe stub:
  nothing leaves the machine, but the founder can inspect exactly what
  would have been sent. Swapping to a real provider (Resend, Postmark,
  SMTP relay) is a single-function change.
* **LinkedIn**: automated send is a hard NO. It violates LinkedIn ToS
  and risks account suspension for the founder. This module returns
  ``status="blocked"`` with a ToS warning; no config flag can flip this
  on. Founder copies the draft into LinkedIn manually.
* **Other channels** (twitter_dm, sms, phone, web_form): return
  ``status="failed"`` with a clear "no provider yet" message. They
  surface in the UI so the founder knows why a draft did not ship.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict

from app.core.logging import get_logger
from app.services.company_mode import Draft, MissionChannel

logger = get_logger(__name__)


# Outbox lives under backend/var/outbox. ``var/`` is already gitignored
# at the repo root so the .eml artifacts never land in source control.
_OUTBOX_DIR = Path(__file__).resolve().parents[3] / "var" / "outbox"


class SendOutcome(TypedDict):
    """What a send_* function reports back to the dispatcher."""

    status: Literal["sent", "blocked", "failed"]
    provider: str
    sent_at: str | None
    detail: str | None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _outbox_path(draft_id: str) -> Path:
    """Resolve the outbox file path for a draft id (pure helper, testable)."""
    return _OUTBOX_DIR / f"{draft_id}.eml"


async def send_email(draft: Draft) -> SendOutcome:
    """Write the draft to ``var/outbox/<draft_id>.eml`` as an RFC-822 message.

    This is deliberately a filesystem stub, not SMTP. It gives the
    founder a single reviewable artifact per send and keeps the Company
    Mode pipeline testable without network side effects. Replace the
    body with an async SMTP / Resend call to enable real send.
    """
    try:
        _OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        subject = draft.subject or "(no subject)"
        headers = [
            f"To: {draft.recipient}",
            f"Subject: {subject}",
            f"X-Daena-Draft-Id: {draft.draft_id}",
            f"X-Daena-Mission-Id: {draft.mission_id}",
            f"X-Daena-Channel: {draft.channel}",
        ]
        message = "\r\n".join(headers) + "\r\n\r\n" + (draft.body or "")
        path = _outbox_path(draft.draft_id)
        path.write_text(message, encoding="utf-8")
        sent_at = _now_iso()
        logger.info(
            "company_mode.email_sent",
            draft_id=draft.draft_id,
            recipient=draft.recipient,
            outbox=str(path),
        )
        return SendOutcome(
            status="sent",
            provider="outbox-stub",
            sent_at=sent_at,
            detail=f"Written to {path.name}",
        )
    except Exception as exc:
        logger.warning("company_mode.email_send_failed", error=str(exc))
        return SendOutcome(
            status="failed",
            provider="outbox-stub",
            sent_at=None,
            detail=f"outbox_write_failed: {exc}",
        )


async def send_linkedin(draft: Draft) -> SendOutcome:
    """LinkedIn automated send is permanently disabled.

    Automating LinkedIn DM / InMail send violates LinkedIn's User
    Agreement (Section 8.2) and can result in account restriction or
    permanent ban. Daena never ships this provider. Founder copies the
    draft body into LinkedIn manually.
    """
    _ = draft  # argument retained for the uniform provider signature
    return SendOutcome(
        status="blocked",
        provider="linkedin-manual",
        sent_at=None,
        detail=(
            "LinkedIn automated sending is disabled. Copy draft into "
            "LinkedIn and send manually to stay compliant with "
            "LinkedIn ToS."
        ),
    )


async def dispatch_send(draft: Draft) -> SendOutcome:
    """Route a draft to the right send provider by channel.

    Unknown or unsupported channels (twitter_dm, sms, phone, web_form)
    get a failed outcome with a clear reason so the founder UI can
    show "no provider yet" instead of a silent no-op.
    """
    channel = (draft.channel or "").lower()
    if channel == MissionChannel.EMAIL.value:
        return await send_email(draft)
    if channel == MissionChannel.LINKEDIN.value:
        return await send_linkedin(draft)
    return SendOutcome(
        status="failed",
        provider="none",
        sent_at=None,
        detail=f"Channel {channel or 'unknown'} has no send provider yet",
    )
