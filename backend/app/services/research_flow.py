"""ResearchFlow -- chains scrape -> structure -> persist into ResearchDraft.

Sprint-10 PR-3 / PR-4: read-only career + content research flows.
Sprint-11 PR-2:        post-process scrape output into a structured
                       payload (opportunity-shaped for kind=career,
                       brief-shaped for kind=content) stored in
                       ``ResearchDraft.structured_payload`` JSONB.

The flow is deliberately small and read-only:

  1. Validate inputs (kind, url, goal).
  2. Call ``scrape_service.extract_from_url`` -- which itself enforces
     URL safety + caps output + audits.
  3. Build a kind-specific structured payload via deterministic
     extraction (host -> company candidate, URLs in extract -> sources,
     bulleted lines -> outline / requirements). LLM enrichment is
     deferred to a follow-up PR; fields the heuristic cannot fill carry
     ``_llm_pending=true`` so the UI can render an honest
     "needs LLM enrichment" badge.
  4. Persist a ``ResearchDraft`` row in the operator's tenant.
  5. Return the draft id + summary.

NEVER:
  * sends the draft anywhere (no email, no LinkedIn / Indeed
    automation, no DMs, no posting)
  * triggers an LLM round-trip in this PR (deterministic shape only)
  * reads / writes any external system beyond the URL the operator
    specified
  * stores the operator's OAuth token / API key / any credential

CLAUDE.md Rule 2 is upheld: ``structured_payload`` is JSONB on the
single canonical ``ResearchDraft`` table. NO parallel
``OpportunityDraft`` / ``ContentBrief`` tables exist or will be added.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal
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


ResearchKind = Literal["career", "content", "business_opportunity"]
ALLOWED_KINDS: tuple[ResearchKind, ...] = ("career", "content", "business_opportunity")

# Sprint-13 PR-2 (2026-05-06): the closed set of opportunity types
# Daena scouts for. The set is closed so the workstream generator
# (PR-3) can map type -> default department deterministically. Adding
# a new type requires touching this tuple AND the department map in
# PR-3 -- they must move in lockstep.
OpportunityType = Literal[
    "grant",
    "accelerator",
    "hackathon",
    "freelance",
    "customer",
    "partnership",
    "security_bounty",
    "rfp",
    "content",
    "startup_program",
]
ALLOWED_OPPORTUNITY_TYPES: tuple[OpportunityType, ...] = (
    "grant",
    "accelerator",
    "hackathon",
    "freelance",
    "customer",
    "partnership",
    "security_bounty",
    "rfp",
    "content",
    "startup_program",
)


# Schema version for structured_payload. Bumped if the shape changes
# in a backwards-incompatible way; consumers should ignore unknown
# fields rather than pin to a specific version.
STRUCTURED_PAYLOAD_VERSION = "2026-05-05.v1"


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


# ── Structured-payload extraction ─────────────────────────────────────


_BULLET_RE = re.compile(r"^\s*(?:[-*•·●]|\d+[\.)])\s+(.+?)\s*$", re.MULTILINE)
_URL_RE = re.compile(r"https?://[^\s)>\"']+", re.IGNORECASE)


def _bullets(text: str, *, limit: int = 12) -> list[str]:
    """Return de-duplicated bulleted lines from a text blob."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _BULLET_RE.finditer(text or ""):
        line = m.group(1).strip()
        if not line or line.lower() in seen:
            continue
        seen.add(line.lower())
        out.append(line[:300])
        if len(out) >= limit:
            break
    return out


def _urls(text: str, *, limit: int = 12) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        url = m.group(0).rstrip(".,;)")
        if url in seen:
            continue
        seen.add(url)
        out.append(url[:2048])
        if len(out) >= limit:
            break
    return out


def _company_candidate_from_host(source_host: str) -> str | None:
    """Best-effort company name from the source host.

    ``https://greenhouse.io/...`` -> ``greenhouse``. The LLM enrichment
    step will replace this with the real company name when it lands.
    """
    try:
        host = source_host.split("://", 1)[-1].split("/", 1)[0]
        host = host.split(":", 1)[0]
        parts = host.split(".")
        # Drop common ATS subdomains so jobs.acme.com -> acme
        if parts and parts[0] in {"jobs", "careers", "boards", "apply"}:
            parts = parts[1:]
        if len(parts) >= 2:
            return parts[0]
        return host or None
    except Exception:
        return None


def build_structured_payload(
    *,
    kind: ResearchKind,
    goal: str,
    raw_extract: str,
    source_url: str,
    source_host: str,
) -> dict[str, Any]:
    """Produce a kind-specific structured payload.

    Deterministic only -- no LLM call. Fields the heuristic cannot
    fill confidently are set to ``None`` (or empty list/string) and the
    payload's ``_llm_pending`` flag stays True so the UI can render an
    honest pending badge. A follow-up PR will run an LLM enrichment
    pass that flips ``_llm_pending`` to False and fills the gaps.

    The shape is stable across LLM-enrichment passes -- the same keys,
    just better values.
    """
    extract = raw_extract or ""

    if kind == "career":
        # Opportunity shape per Sprint-11 brief.
        return {
            "_schema_version": STRUCTURED_PAYLOAD_VERSION,
            "_kind": "opportunity",
            "_llm_pending": True,
            "company": _company_candidate_from_host(source_host),
            "role": None,             # LLM enrichment fills
            "team": None,
            "location": None,
            "compensation": None,
            "requirements": _bullets(extract, limit=12),
            "responsibilities": [],   # LLM enrichment fills
            "fit_score": None,        # 0-100, LLM enrichment fills
            "fit_rationale": None,
            "missing_skills": [],     # LLM enrichment fills
            "suggested_answers": [],  # list[{question, answer, confidence}]
            "outreach_draft_local": None,
            "next_tasks": [],         # list[str]; first pass: empty
            "sources": [source_url, *_urls(extract, limit=8)],
            "goal_echo": goal,
        }

    if kind == "content":
        # Content brief shape per Sprint-11 brief.
        bullets = _bullets(extract, limit=12)
        return {
            "_schema_version": STRUCTURED_PAYLOAD_VERSION,
            "_kind": "brief",
            "_llm_pending": True,
            "audience": None,
            "key_points": bullets[:8],
            "angle": None,
            "outline": bullets,
            "captions": [],           # LLM enrichment fills
            "hooks": [],
            "sources": [source_url, *_urls(extract, limit=10)],
            "risks_to_verify": [],
            "claims_to_verify": [],
            "goal_echo": goal,
        }

    if kind == "business_opportunity":
        # Sprint-13 PR-2 -- business opportunity shape. The workstream
        # generator (PR-3) reads ``opportunity_type`` to pick a
        # default department; the draft action factory (PR-4) reads
        # ``next_action`` and ``deadline`` to schedule local drafts.
        bullets = _bullets(extract, limit=12)
        return {
            "_schema_version": STRUCTURED_PAYLOAD_VERSION,
            "_kind": "business_opportunity",
            "_llm_pending": True,
            "title": None,                  # LLM enrichment fills
            "opportunity_type": None,       # set by API caller (closed set)
            "deadline": None,               # ISO date or null; LLM fills
            "fit_score": None,              # 0-100; LLM fills
            "revenue_potential": None,      # USD estimate or text
            "effort_estimate": None,        # hours/days; LLM fills
            "risk_level": None,             # low/medium/high; LLM fills
            "next_action": None,            # one-line; LLM fills
            "suggested_department": None,   # PR-3 maps from opportunity_type
            "evidence": [source_url],
            "source_notes": bullets,
            "confidence": None,             # 0-100; LLM fills
            "sources": [source_url, *_urls(extract, limit=8)],
            "goal_echo": goal,
        }

    raise ResearchFlowError(f"unknown_kind: {kind!r}")


def _security_bounty_overlay(extract: str) -> dict[str, Any]:
    """Return the bounty-program-specific overlay for the structured payload.

    Heuristic only (deterministic); ``_llm_pending`` stays True at the
    draft level so a follow-up enrichment can replace heuristic
    guesses with LLM-extracted ground truth. The overlay carries:

      * ``program_name``        -- best-effort title from the extract
      * ``allowed_domains``     -- list of domains the program scope
                                   appears to allow
      * ``out_of_scope_rules``  -- list of out-of-scope hints
      * ``reward_range``        -- plain-text reward / payout hint
      * ``report_url``          -- the report intake URL if mentioned
      * ``identity_required``   -- true when the program clearly
                                   requires registration / KYC
      * ``safe_next_action``    -- LITERAL text the UI surfaces
                                   verbatim. NEVER asks Daena to
                                   scan; always asks the operator
                                   to register manually first.
      * ``scope_check_status``  -- "not_yet_in_scope" until the
                                   operator adds the program's
                                   allowed_domains to authorized_scope.
                                   Daena is never permitted to scan
                                   from this row.

    Note: NO ``scan`` / ``exploit`` / ``test_target`` key ever
    appears -- the scout's output is metadata only. Contract test
    enforces this.
    """
    text = extract or ""
    lowered = text.lower()

    # Out-of-scope token sniff (lots of programs use a literal
    # "Out of scope" header).
    out_of_scope: list[str] = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        if "out of scope" in l.lower() or "not in scope" in l.lower():
            # Take the next 3 lines as candidates.
            out_of_scope.append(l)

    # Identity hint: programs requiring HackerOne / Bugcrowd / a
    # named portal usually require an account.
    identity_required = any(
        token in lowered
        for token in (
            "hackerone", "bugcrowd", "intigriti", "yeswehack",
            "register", "create an account", "must be a member",
            "must be enrolled",
        )
    )

    # Reward range hint: pull a "$<n>" or "<n>k" mention if present.
    reward_range = None
    for token in ("$", "USD", "EUR", "rewards", "bounty", "payout"):
        idx = lowered.find(token.lower())
        if idx >= 0:
            reward_range = text[max(0, idx - 30): idx + 80].strip()[:160]
            break

    # Report URL: pull the first url that looks like an intake link.
    report_url = None
    for url in _urls(text, limit=20):
        u = url.lower()
        if any(t in u for t in ("/report", "/submit", "/disclos", "/policy")):
            report_url = url
            break

    return {
        "program_name": None,            # LLM enrichment fills
        "allowed_domains": [],           # LLM enrichment fills
        "out_of_scope_rules": out_of_scope[:8],
        "reward_range": reward_range,
        "report_url": report_url,
        "identity_required": identity_required,
        "safe_next_action": (
            "Register on the program's official portal manually before "
            "any test or scan. Add the allowed_domains to the operator's "
            "authorized_scope; Daena will refuse to scan a target that "
            "is not explicitly in scope."
        ),
        "scope_check_status": "not_yet_in_scope",
    }


async def create_research_draft(
    db: AsyncSession,
    *,
    kind: ResearchKind,
    url: str,
    goal: str,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    max_chars: int = 8000,
    opportunity_type: OpportunityType | None = None,
) -> ResearchDraft:
    """Run the read-only research flow and persist a draft.

    Raises:
      ResearchFlowError on validation / scrape failure. The message
      carries a stable prefix (``url_safety:``, ``goal_required``,
      ``scrape_failed``, ``unknown_kind``) the API + UI can match.

    ``opportunity_type`` is required when ``kind == "business_opportunity"``
    and forbidden for all other kinds. The closed set lives on
    ``ALLOWED_OPPORTUNITY_TYPES``.
    """
    if kind not in ALLOWED_KINDS:
        raise ResearchFlowError(
            f"unknown_kind: {kind!r} not in {ALLOWED_KINDS}"
        )
    if not isinstance(url, str) or not url.strip():
        raise ResearchFlowError("url_safety:url_invalid")
    if not isinstance(goal, str) or not goal.strip():
        raise ResearchFlowError("goal_required")
    if kind == "business_opportunity":
        if opportunity_type is None:
            raise ResearchFlowError("opportunity_type_required")
        if opportunity_type not in ALLOWED_OPPORTUNITY_TYPES:
            raise ResearchFlowError(
                f"opportunity_type_invalid: {opportunity_type!r} "
                f"not in {ALLOWED_OPPORTUNITY_TYPES}"
            )
    elif opportunity_type is not None:
        raise ResearchFlowError(
            "opportunity_type_only_with_business_opportunity_kind"
        )

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

    structured = build_structured_payload(
        kind=kind,
        goal=goal.strip(),
        raw_extract=outcome.result,
        source_url=url.strip(),
        source_host=_safe_host(url),
    )
    if kind == "business_opportunity" and opportunity_type is not None:
        # Stamp the closed-set type so the workstream generator (PR-3)
        # can deterministically pick the default department.
        structured["opportunity_type"] = opportunity_type
        # Sprint-13 PR-5: security bounty programs get extra
        # metadata fields the scout fills heuristically (program
        # name, allowed_domains hint, identity_required, etc.) and
        # a verbatim safe_next_action that explicitly forbids any
        # automated scan until the operator registers on the
        # program portal manually.
        if opportunity_type == "security_bounty":
            structured.update(_security_bounty_overlay(outcome.result))

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
        structured_payload=structured,
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
