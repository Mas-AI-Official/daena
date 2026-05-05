"""ResearchFlow -- chains scrape -> persist into a local ResearchDraft.

PR-CAREEROPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-3, 2026-05-05).
PR-CONTENTOPS-READONLY-RESEARCH-FLOW (Sprint-10 PR-4, 2026-05-05).

The flow is deliberately small and read-only:

  1. Validate inputs (kind, url, goal).
  2. Call ``scrape_service.extract_from_url`` -- which itself enforces
     URL safety + caps output + audits.
  3. Persist a ``ResearchDraft`` row in the operator's tenant.
  4. Return the draft id + summary.

NEVER:
  * sends the draft anywhere (no email, no LinkedIn / Indeed
    automation, no DMs, no posting)
  * triggers a second LLM round-trip to "improve" the draft
  * reads / writes any external system beyond the URL the operator
    specified
  * stores the operator's OAuth token / API key / any credential

The summary the LLM produced inside the scrape worker is the draft's
summary -- ScrapeGraphAI's SmartScraperGraph is already a "scrape
under this goal" call that returns goal-tailored text. A future PR
can add a separate post-process LLM step (e.g. extract structured
fields) without changing this service's contract.
"""

from __future__ import annotations

import uuid
from typing import Literal
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.research import ResearchDraft
from app.services.scrape import (
    ExtractResult,
    ScrapeError,
    extract_from_url,
)


logger = get_logger(__name__)


ResearchKind = Literal["career", "content"]
ALLOWED_KINDS: tuple[ResearchKind, ...] = ("career", "content")


class ResearchFlowError(Exception):
    """Operator-safe error -- the message is fine for an API response."""


def _safe_host(url: str) -> str:
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        port = f":{parts.port}" if parts.port else ""
        return f"{(parts.scheme or 'http').lower()}://{host}{port}"
    except Exception:
        return "?"


async def create_research_draft(
    db: AsyncSession,
    *,
    kind: ResearchKind,
    url: str,
    goal: str,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    max_chars: int = 8000,
) -> ResearchDraft:
    """Run the read-only research flow and persist a draft.

    Raises:
      ResearchFlowError on validation / scrape failure. The message
      carries a stable prefix (``url_safety:``, ``goal_required``,
      ``scrape_failed``, ``unknown_kind``) the API + UI can match.
    """
    if kind not in ALLOWED_KINDS:
        raise ResearchFlowError(
            f"unknown_kind: {kind!r} not in {ALLOWED_KINDS}"
        )
    if not isinstance(url, str) or not url.strip():
        raise ResearchFlowError("url_safety:url_invalid")
    if not isinstance(goal, str) or not goal.strip():
        raise ResearchFlowError("goal_required")

    # Delegate to scrape_service. It re-validates URL safety + caps
    # + audits the call. We never bypass that audit row here -- it is
    # the source of truth for "what URL did Daena fetch on this
    # research call". The DRAFT row separately captures "what the
    # operator chose to keep".
    try:
        outcome: ExtractResult = await extract_from_url(
            url, goal, max_chars=max_chars,
        )
    except ScrapeError as exc:
        # Surface the same prefix so the API + UI can match without
        # a second wrapper layer.
        raise ResearchFlowError(str(exc)) from exc

    if not outcome.success:
        raise ResearchFlowError(
            f"scrape_failed:{outcome.error or 'unknown'}"
        )

    draft = ResearchDraft(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        source_url=url.strip(),
        source_host=_safe_host(url),
        goal=goal.strip(),
        summary=outcome.result,
        raw_extract=outcome.result,  # same blob for V1; future PR can
                                      # split if a second LLM stage lands
        status="DRAFT",
        audit_event_id=None,  # set by API layer post-write
    )
    db.add(draft)
    await db.flush()

    logger.info(
        "research_flow.draft_created",
        draft_id=str(draft.id),
        kind=kind,
        source_host=_safe_host(url),
        # NEVER log the source_url, goal, or summary text.
    )

    return draft
