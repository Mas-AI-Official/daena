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


# Pattern table -- order matters. Sprint-20 PR-7 adds three explicit-id
# commands BEFORE the vague-text Sprint-19 commands so a precise input
# routes to the implementation, not to the implemented=False stub.
_UUID_RE = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_EMAIL_RE = (
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

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
    # Sprint-20 PR-7: explicit-id commands (must come BEFORE the
    # corresponding vague-text Sprint-19 stubs).
    (
        "create_workstream_from_opp_by_id",
        re.compile(
            r"\bcreate\s+workstream\s+(?:from|for)\s+opp(?:ortunity)?\s+("
            + _UUID_RE + r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        "draft_outreach_for_opp_to",
        re.compile(
            r"\bdraft\s+outreach\s+for\s+opp(?:ortunity)?\s+("
            + _UUID_RE + r")\s+to\s+(" + _EMAIL_RE + r")\b",
            re.IGNORECASE,
        ),
    ),
    (
        "send_approved_draft_by_id",
        re.compile(
            r"\bsend\s+(?:approved\s+)?draft\s+(" + _UUID_RE + r")\b",
            re.IGNORECASE,
        ),
    ),
    # Sprint-19 vague-text stubs: still match, still refuse.
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
            "draft outreach for top N is not auto-runnable from chat. "
            "Use 'draft outreach for opp <uuid> to <email>' with an "
            "explicit opportunity id and recipient email."
        ),
    }


def _send_not_implemented() -> dict[str, Any]:
    return {
        "implemented": False,
        "reason": (
            "send-the-approved-draft is not auto-runnable from chat "
            "without an id. Use 'send draft <outreach_draft_uuid>' "
            "with an explicit draft id, or approve the existing "
            "gmail.send_existing_draft GoaRequest in the Approvals page."
        ),
    }


# Sprint-20 PR-7: ID-explicit runners.


async def _create_workstream_from_opp_by_id(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    opp_id_str: str,
) -> dict[str, Any]:
    """Promote an explicit opportunity-id to a workstream. ID-explicit
    only -- never fuzzy-matches by title."""
    from app.services.business_pipeline.workstream_bridge import (
        DepartmentNotFound, DuplicateWorkstream, OpportunityNotFound,
        UnknownOpportunityType, ValidationRequired,
        create_workstream_for_opportunity,
    )
    try:
        opp_id = uuid.UUID(opp_id_str)
    except ValueError:
        return {
            "ok": False,
            "code": "invalid_uuid",
            "reason": f"{opp_id_str!r} is not a valid UUID.",
        }
    try:
        result = await create_workstream_for_opportunity(
            db, tenant_id=tenant_id, user_id=user_id,
            opportunity_id=opp_id,
        )
    except OpportunityNotFound:
        return {"ok": False, "code": "opportunity_not_found"}
    except UnknownOpportunityType as exc:
        return {
            "ok": False, "code": "unknown_opportunity_type",
            "type": str(exc),
        }
    except DepartmentNotFound as exc:
        return {
            "ok": False, "code": "department_not_found",
            "department": str(exc),
        }
    except DuplicateWorkstream as exc:
        return {
            "ok": False, "code": "duplicate_workstream",
            "existing_workstream_id": str(exc.existing_workstream_id),
        }
    except ValidationRequired:
        return {"ok": False, "code": "validation_required"}

    return {
        "ok": True,
        "workstream_id": str(result.workstream_id),
        "department_name": result.department_name,
        "collaborators": result.collaborators,
    }


async def _draft_outreach_for_opp_to(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    opp_id_str: str, recipient_email: str,
) -> dict[str, Any]:
    """Create a local outreach draft for an explicit opportunity +
    recipient. Local-only -- NEVER queues a Gmail draft. Operator
    approves create_draft via the Approvals page."""
    from app.services.outreach.draft_factory import (
        create_outreach_draft_for_opportunity,
    )
    try:
        opp_id = uuid.UUID(opp_id_str)
    except ValueError:
        return {
            "ok": False, "code": "invalid_uuid",
            "reason": f"{opp_id_str!r} is not a valid UUID.",
        }

    opp = (await db.execute(
        select(Opportunity).where(
            Opportunity.id == opp_id,
            Opportunity.tenant_id == tenant_id,
        ),
    )).scalar_one_or_none()
    if opp is None:
        return {"ok": False, "code": "opportunity_not_found"}

    result = await create_outreach_draft_for_opportunity(
        db, opportunity=opp, user_id=user_id,
        recipient_email=recipient_email,
    )
    return {
        "ok": result.status == "drafted",
        "draft_id": result.draft_id,
        "status": result.status,
        "blocked_reason": result.blocked_reason,
    }


async def _send_approved_draft_by_id(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    draft_id_str: str,
) -> dict[str, Any]:
    """Queue the second-wall send approval for an explicit
    BizOutreachDraft id. NEVER auto-approves. NEVER bypasses the
    rate limit. NEVER skips the dispatcher gates.
    """
    # Local imports keep the chat module decoupled from the send
    # surface unless this command is actually executed.
    from app.services.outreach.send_bridge import queue_gmail_send
    from app.services.trust_policy import DispatchInitiator
    from app.models.business import BizOutreachDraft

    try:
        draft_id = uuid.UUID(draft_id_str)
    except ValueError:
        return {
            "ok": False, "code": "invalid_uuid",
            "reason": f"{draft_id_str!r} is not a valid UUID.",
        }

    draft = (await db.execute(
        select(BizOutreachDraft).where(
            BizOutreachDraft.id == draft_id,
            BizOutreachDraft.tenant_id == tenant_id,
        ),
    )).scalar_one_or_none()
    if draft is None:
        return {"ok": False, "code": "draft_not_found"}

    # Chat-driven send is OPERATOR initiator -- the operator typed the
    # exact id. Trust auto-approval for send is FORBIDDEN regardless
    # (Sprint-18 wall #1: gmail.send_existing_draft is in
    # TRUST_FORBIDDEN_TOOLS). The send_bridge is defensive too.
    bridge = await queue_gmail_send(
        db, outreach_draft_id=draft.id,
        owner_email=(draft.recipient_email or "").split(",")[0].strip()
        or "unknown@unknown",
        tenant_id=tenant_id, user_id=user_id,
        initiator=DispatchInitiator.OPERATOR,
    )
    return {
        "ok": bridge.success,
        "approval_id": bridge.approval_id,
        "auto_approved": bridge.auto_approved,
        "refusal_code": bridge.refusal_code,
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
    if command == "create_workstream_from_opp_by_id":
        if structured.get("ok"):
            return (
                f"Workstream created in "
                f"{structured.get('department_name', '?')}."
            )
        return f"Workstream not created: {structured.get('code', '?')}."
    if command == "draft_outreach_for_opp_to":
        if structured.get("ok"):
            return "Local outreach draft created."
        return (
            f"Draft not created: "
            f"{structured.get('code') or structured.get('blocked_reason', '?')}."
        )
    if command == "send_approved_draft_by_id":
        if structured.get("ok"):
            return "Send queued for approval."
        return (
            f"Send not queued: {structured.get('refusal_code', '?')}."
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
    user_id: uuid.UUID | None = None,
) -> BusinessChatResult:
    """Match text against pattern table; run the corresponding
    runner. Returns matched=False if nothing matches.

    ``user_id`` is required for the ID-explicit commands added in
    Sprint-20 PR-7 (create-workstream / draft-outreach / send-by-id).
    Vague Sprint-19 commands run without it.
    """
    if not isinstance(text, str) or not text.strip():
        return BusinessChatResult(matched=False)

    matched_command: str | None = None
    matched_groups: tuple[str, ...] = ()
    for name, pattern in _PATTERNS:
        m = pattern.search(text)
        if m is not None:
            matched_command = name
            matched_groups = m.groups()
            break

    if matched_command is None:
        return BusinessChatResult(matched=False)

    # ID-explicit commands need user_id.
    _ID_EXPLICIT = {
        "create_workstream_from_opp_by_id",
        "draft_outreach_for_opp_to",
        "send_approved_draft_by_id",
    }
    if matched_command in _ID_EXPLICIT and user_id is None:
        return BusinessChatResult(
            matched=True, command=matched_command,
            summary="user_id required for explicit-id commands.",
            structured={
                "ok": False, "code": "user_id_required",
                "reason": (
                    "id-explicit chat commands require an authenticated "
                    "user context. Run via /api/v1/business/chat which "
                    "supplies it automatically."
                ),
            },
        )

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
    elif matched_command == "create_workstream_from_opp_by_id":
        structured = await _create_workstream_from_opp_by_id(
            db, tenant_id=tenant_id, user_id=user_id,
            opp_id_str=matched_groups[0],
        )
    elif matched_command == "draft_outreach_for_opp_to":
        structured = await _draft_outreach_for_opp_to(
            db, tenant_id=tenant_id, user_id=user_id,
            opp_id_str=matched_groups[0],
            recipient_email=matched_groups[1],
        )
    elif matched_command == "send_approved_draft_by_id":
        structured = await _send_approved_draft_by_id(
            db, tenant_id=tenant_id, user_id=user_id,
            draft_id_str=matched_groups[0],
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
