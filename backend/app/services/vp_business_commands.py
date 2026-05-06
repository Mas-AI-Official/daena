"""VP business execution chat commands -- Sprint-19 PR-7 (2026-05-06).

Eight deterministic chat commands. NO LLM in the path. Each
command matches a regex pattern; runners read authoritative
backend state and produce a structured response. The frontend
renders that as a fixed table.

Commands:

  1. "find ways to make money today"      -> run discovery loop
  2. "find grants for mas-ai"             -> list grant opps
  3. "find hackathons (we can join)"      -> list hackathon opps
  4. "find customer leads"                -> list customer_lead opps
  5. "draft outreach for top 3"           -> NOT implemented in v1
                                              -- requires recipient
                                              addresses per opp,
                                              which Sprint-19 does
                                              not auto-discover
  6. "what needs my approval"             -> list pending GoaRequests
  7. "send the approved draft"            -> NOT implemented in v1
                                              -- requires explicit
                                              outreach_draft_id;
                                              chat command can't
                                              guess intent safely
  8. "what did you do today"              -> recent audit/log
                                              activity summary
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Opportunity
from app.models.governance import GoaRequest


@dataclass
class BusinessChatResult:
    matched: bool
    command: str | None = None
    summary: str = ""
    structured: dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Pattern table -- order-sensitive, longest/most-specific first.
# ────────────────────────────────────────────────────────────────────


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "find_ways_to_make_money",
        re.compile(
            r"\bfind\s+(?:a\s+|some\s+)?ways?\s+to\s+make\s+money\b",
            re.IGNORECASE,
        ),
    ),
    (
        "find_grants",
        re.compile(r"\bfind\s+grants?\b", re.IGNORECASE),
    ),
    (
        "find_hackathons",
        re.compile(r"\bfind\s+hackathons?\b", re.IGNORECASE),
    ),
    (
        "find_customer_leads",
        re.compile(
            r"\bfind\s+(?:customer\s+)?leads?\b", re.IGNORECASE,
        ),
    ),
    (
        "draft_outreach_for_top",
        re.compile(
            r"\bdraft\s+outreach\s+for\s+top\s+\d+\b",
            re.IGNORECASE,
        ),
    ),
    (
        "what_needs_approval",
        re.compile(
            r"\bwhat\s+(?:still\s+)?needs?\s+(?:my\s+)?approval\b",
            re.IGNORECASE,
        ),
    ),
    (
        "send_approved_draft",
        re.compile(
            r"\bsend\s+the\s+approved\s+draft\b", re.IGNORECASE,
        ),
    ),
    (
        "what_did_you_do_today",
        re.compile(
            r"\bwhat\s+did\s+you\s+do\s+today\b", re.IGNORECASE,
        ),
    ),
]


# ────────────────────────────────────────────────────────────────────
# Runners
# ────────────────────────────────────────────────────────────────────


async def _list_opps_by_type(
    db: AsyncSession, *, tenant_id: uuid.UUID, type_: str | None,
    limit: int = 20,
) -> list[Opportunity]:
    stmt = select(Opportunity).where(Opportunity.tenant_id == tenant_id)
    if type_ is not None:
        stmt = stmt.where(Opportunity.type == type_)
    stmt = stmt.order_by(Opportunity.score.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


def _opps_to_rows(opps: list[Opportunity]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(o.id),
            "type": o.type,
            "title": o.title,
            "score": o.score,
            "deadline_at": (
                o.deadline_at.isoformat() if o.deadline_at else None
            ),
            "estimated_value_usd": o.estimated_value_usd,
            "status": o.status,
        }
        for o in opps
    ]


async def _find_ways_to_make_money(
    db: AsyncSession, *, tenant_id: uuid.UUID,
) -> dict[str, Any]:
    """Return top-10 highest-scoring discovered opportunities of
    ANY type. Does NOT trigger a fresh discovery -- chat commands
    are read-only. Operator triggers discovery via the inbox or
    the routine."""
    opps = await _list_opps_by_type(db, tenant_id=tenant_id, type_=None, limit=10)
    return {
        "found_count": len(opps),
        "rows": _opps_to_rows(opps),
        "note": (
            "These are existing opportunities, ranked by score. "
            "To run fresh discovery, use the 'Run discovery' button "
            "on the Opportunities page."
        ),
    }


async def _find_typed(
    db: AsyncSession, *, tenant_id: uuid.UUID, type_: str,
) -> dict[str, Any]:
    opps = await _list_opps_by_type(db, tenant_id=tenant_id, type_=type_, limit=20)
    return {
        "type": type_,
        "found_count": len(opps),
        "rows": _opps_to_rows(opps),
    }


def _draft_outreach_not_implemented() -> dict[str, Any]:
    return {
        "implemented": False,
        "reason": (
            "draft outreach for top N is not auto-runnable from chat "
            "in v1: each opportunity needs a target recipient email "
            "the discovery layer does not always supply. Use the "
            "Opportunities page to pick an opportunity and trigger "
            "draft creation explicitly."
        ),
    }


def _send_not_implemented() -> dict[str, Any]:
    return {
        "implemented": False,
        "reason": (
            "send-the-approved-draft is not auto-runnable from chat "
            "in v1: chat cannot safely guess which approval row + "
            "which Gmail draft. Use the Approvals page to approve "
            "the gmail.send_existing_draft GoaRequest, then the "
            "controlled execution dispatcher fires it."
        ),
    }


async def _what_needs_approval(
    db: AsyncSession, *, tenant_id: uuid.UUID,
) -> dict[str, Any]:
    write_tools = {
        "gmail.create_draft",
        "gmail.send_existing_draft",
        "calendar.create_tentative_event_without_invites",
        "local.file_change_proposal",
        "local.file_change_proposal.apply",
        "local.git_commit_approved_patch",
    }
    stmt = (
        select(GoaRequest)
        .where(GoaRequest.tenant_id == tenant_id)
        .where(GoaRequest.status == "PENDING")
        .order_by(GoaRequest.created_at.desc())
        .limit(50)
    )
    pending = list((await db.execute(stmt)).scalars().all())
    rows = [
        {
            "id": str(r.id),
            "action_type": r.action_type,
            "risk_level": r.risk_level,
            "tier": r.governance_tier,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "controlled": r.action_type in write_tools,
        }
        for r in pending
    ]
    return {
        "pending_count": len(rows),
        "controlled_count": sum(1 for r in rows if r["controlled"]),
        "rows": rows,
    }


async def _what_did_you_do_today(
    db: AsyncSession, *, tenant_id: uuid.UUID,
) -> dict[str, Any]:
    """Lightweight activity summary based on GoaRequest decisions
    in the last 24h (approved + rejected)."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    stmt = (
        select(GoaRequest)
        .where(GoaRequest.tenant_id == tenant_id)
        .where(GoaRequest.decided_at != None)  # noqa: E711
        .where(GoaRequest.decided_at >= cutoff)
        .order_by(GoaRequest.decided_at.desc())
        .limit(100)
    )
    decided = list((await db.execute(stmt)).scalars().all())

    counts: dict[str, int] = {}
    for r in decided:
        key = f"{r.action_type}:{(r.status or '').lower()}"
        counts[key] = counts.get(key, 0) + 1

    return {
        "since_utc": cutoff.isoformat(),
        "decided_count": len(decided),
        "counts": counts,
    }


# ────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────


def _summary_for(command: str, structured: dict[str, Any]) -> str:
    if command == "find_ways_to_make_money":
        return (
            f"{structured.get('found_count', 0)} existing opportunities "
            "ranked by score."
        )
    if command == "find_grants":
        return f"{structured.get('found_count', 0)} grants in inbox."
    if command == "find_hackathons":
        return f"{structured.get('found_count', 0)} hackathons in inbox."
    if command == "find_customer_leads":
        return (
            f"{structured.get('found_count', 0)} customer leads in inbox."
        )
    if command == "draft_outreach_for_top":
        return "Drafting from chat is not implemented in v1."
    if command == "what_needs_approval":
        return (
            f"{structured.get('pending_count', 0)} pending approvals "
            f"({structured.get('controlled_count', 0)} controlled-execution)."
        )
    if command == "send_approved_draft":
        return "Send from chat is not implemented in v1."
    if command == "what_did_you_do_today":
        return f"{structured.get('decided_count', 0)} decisions in the last 24h."
    return ""


async def parse_and_run(
    text: str, *, db: AsyncSession, tenant_id: uuid.UUID,
) -> BusinessChatResult:
    """Match text against pattern table; run the corresponding
    runner. Returns matched=False if nothing matches."""
    if not isinstance(text, str) or not text.strip():
        return BusinessChatResult(matched=False)

    matched_command: str | None = None
    for name, pattern in _PATTERNS:
        if pattern.search(text):
            matched_command = name
            break

    if matched_command is None:
        return BusinessChatResult(matched=False)

    if matched_command == "find_ways_to_make_money":
        structured = await _find_ways_to_make_money(db, tenant_id=tenant_id)
    elif matched_command == "find_grants":
        structured = await _find_typed(db, tenant_id=tenant_id, type_="grant")
    elif matched_command == "find_hackathons":
        structured = await _find_typed(db, tenant_id=tenant_id, type_="hackathon")
    elif matched_command == "find_customer_leads":
        structured = await _find_typed(
            db, tenant_id=tenant_id, type_="customer_lead",
        )
    elif matched_command == "draft_outreach_for_top":
        structured = _draft_outreach_not_implemented()
    elif matched_command == "what_needs_approval":
        structured = await _what_needs_approval(db, tenant_id=tenant_id)
    elif matched_command == "send_approved_draft":
        structured = _send_not_implemented()
    elif matched_command == "what_did_you_do_today":
        structured = await _what_did_you_do_today(db, tenant_id=tenant_id)
    else:  # defensive
        return BusinessChatResult(matched=False)

    return BusinessChatResult(
        matched=True,
        command=matched_command,
        summary=_summary_for(matched_command, structured),
        structured=structured,
    )
