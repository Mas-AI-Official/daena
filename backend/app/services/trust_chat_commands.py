"""Trust-aware VP chat commands -- Sprint-18 PR-5 (2026-05-06).

Five deterministic chat commands. No LLM in the path. Each command
matches a regex pattern, and the response is built from authoritative
backend state (trust_policy + routine_autonomy). The frontend renders
it as a fixed table; no free-form generation, no hallucinated
permissions.

Commands:

  1. "what can you do without asking me"      -> auto-approved table
  2. "what still needs approval"              -> always-gated table
  3. "show trusted routines"                  -> registered routines
  4. "pause autonomy"                         -> mutates global pause
  5. "resume research-only autonomy"          -> resumes global, but
                                                  does not unlock writes
  6. "why did you not execute this"           -> last-blocked reason

Order matters: more specific regex patterns first so "pause" doesn't
swallow "pause autonomy". Returns ``None`` if nothing matches; the
caller can fall through to the LLM-driven /vp-commands path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services import routine_autonomy, trust_policy
from app.services.trust_policy import (
    TRUST_ELIGIBLE_TOOLS,
    TRUST_FORBIDDEN_TOOLS,
    TrustTier,
)


@dataclass
class ChatCommandResult:
    matched: bool
    command: str | None = None
    summary: str = ""
    structured: dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Pattern table (order-sensitive)
# ────────────────────────────────────────────────────────────────────


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "pause_autonomy",
        re.compile(r"\bpause\s+(?:all\s+)?autonomy\b", re.IGNORECASE),
    ),
    (
        "resume_research_only_autonomy",
        re.compile(
            r"\bresume\s+(?:research[-\s]?only\s+)?autonomy\b",
            re.IGNORECASE,
        ),
    ),
    (
        "what_without_approval",
        re.compile(
            r"\bwhat\s+can\s+you\s+do\s+without\s+asking\b", re.IGNORECASE,
        ),
    ),
    (
        "what_needs_approval",
        re.compile(r"\bwhat\s+still\s+needs\s+approval\b", re.IGNORECASE),
    ),
    (
        "show_trusted_routines",
        re.compile(r"\bshow\s+(?:trusted\s+)?routines\b", re.IGNORECASE),
    ),
    (
        "why_not_executed",
        re.compile(
            r"\bwhy\s+did(?:n['’]t\s+you|\s+you\s+not)"
            r"\s+(?:execute|run|fire)\b",
            re.IGNORECASE,
        ),
    ),
]


# ────────────────────────────────────────────────────────────────────
# Command runners
# ────────────────────────────────────────────────────────────────────


def _what_without_approval() -> dict[str, Any]:
    """Inspect trust_policy + ladder; return rows that WOULD
    auto-approve right now for an OPERATOR-initiated dispatch
    (using a synthetic empty payload to compute a default
    template_class)."""
    rows = []
    for entry in trust_policy.list_policies():
        if entry.max_auto_tier != TrustTier.AUTO_APPROVE_LOW_RISK:
            continue
        if entry.tool_id in TRUST_FORBIDDEN_TOOLS:
            # Impossible (set_max_auto_tier refuses) but defensive.
            continue
        rows.append({
            "tool_id": entry.tool_id,
            "template_class": entry.template_class,
            "tier": entry.max_auto_tier.value,
        })
    return {
        "auto_approved": rows,
        "note": (
            "Only operator-initiated dispatches with verified counters "
            "will actually fire. Scheduler / self-healing dispatches "
            "always require manual approval."
        ),
    }


def _what_needs_approval() -> dict[str, Any]:
    return {
        "always_gated": sorted(TRUST_FORBIDDEN_TOOLS),
        "reason": (
            "send / file apply / git commit cannot graduate. They "
            "ALWAYS require manual approval, regardless of trust history."
        ),
        "eligible_but_not_yet": [
            t for t in sorted(TRUST_ELIGIBLE_TOOLS)
            if not any(
                e.tool_id == t and e.max_auto_tier == TrustTier.AUTO_APPROVE_LOW_RISK
                for e in trust_policy.list_policies()
            )
        ],
    }


def _show_trusted_routines() -> dict[str, Any]:
    return {
        "routines": [
            {
                "id": r.id,
                "kind": r.kind,
                "name": r.name,
                "paused": r.paused,
                "last_run_at": r.last_run_at,
                "last_outcome": r.last_outcome,
            }
            for r in routine_autonomy.list_routines()
        ],
        "global_paused": routine_autonomy.is_global_paused(),
    }


def _pause_autonomy() -> dict[str, Any]:
    routine_autonomy.pause_all()
    return {
        "global_paused": True,
        "effect": (
            "All routines paused. Operator-initiated work is unaffected."
        ),
    }


def _resume_research_only_autonomy() -> dict[str, Any]:
    """Resume routines, but the trust ladder still gates anything
    a routine could try to escalate. So 'research-only' is an
    accurate label given that scheduler-initiated work cannot
    auto-approve."""
    routine_autonomy.resume_all()
    return {
        "global_paused": False,
        "effect": (
            "Routines resumed. Scheduler-initiated work cannot "
            "auto-approve send / file apply / git commit -- those "
            "always need you. Daena will draft and propose; you "
            "approve."
        ),
    }


def _why_not_executed() -> dict[str, Any]:
    """Surface the most recent blocked-routine outcome."""
    last: dict[str, Any] | None = None
    for r in routine_autonomy.list_routines():
        if r.last_outcome and r.last_outcome != "ok":
            last = {
                "routine_id": r.id,
                "kind": r.kind,
                "name": r.name,
                "last_run_at": r.last_run_at,
                "last_outcome": r.last_outcome,
            }
    if last is None:
        return {
            "found": False,
            "note": "No recent blocked routine runs in scheduler state.",
        }
    return {"found": True, "last_blocked": last}


_RUNNERS = {
    "what_without_approval": _what_without_approval,
    "what_needs_approval": _what_needs_approval,
    "show_trusted_routines": _show_trusted_routines,
    "pause_autonomy": _pause_autonomy,
    "resume_research_only_autonomy": _resume_research_only_autonomy,
    "why_not_executed": _why_not_executed,
}


def parse_and_run(text: str) -> ChatCommandResult:
    """Match ``text`` against the locked pattern table; if matched,
    invoke the corresponding runner. Returns matched=False so the
    caller can fall through to LLM-driven flow if nothing matched.
    """
    if not isinstance(text, str) or not text.strip():
        return ChatCommandResult(matched=False)

    for name, pattern in _PATTERNS:
        if pattern.search(text):
            runner = _RUNNERS.get(name)
            if runner is None:  # defensive
                return ChatCommandResult(matched=False)
            structured = runner()
            summary = _summary_for(name, structured)
            return ChatCommandResult(
                matched=True,
                command=name,
                summary=summary,
                structured=structured,
            )

    return ChatCommandResult(matched=False)


def _summary_for(command: str, structured: dict[str, Any]) -> str:
    """One-line deterministic summary per command. Frontend can
    render structured for the table; summary is the audit-log line."""
    if command == "what_without_approval":
        n = len(structured.get("auto_approved", []))
        return f"{n} (tool, template_class) pairs are auto-approved for operator-initiated dispatches."
    if command == "what_needs_approval":
        gated = structured.get("always_gated", [])
        return f"{len(gated)} tools always require manual approval (forbidden from graduation)."
    if command == "show_trusted_routines":
        rs = structured.get("routines", [])
        return f"{len(rs)} routines registered. global_paused={structured.get('global_paused')}."
    if command == "pause_autonomy":
        return "All routines paused. Manual work unaffected."
    if command == "resume_research_only_autonomy":
        return "Routines resumed. Scheduler-initiated dispatches still cannot auto-approve."
    if command == "why_not_executed":
        if structured.get("found"):
            return f"Last blocked routine: {structured['last_blocked']['name']} ({structured['last_blocked']['last_outcome']})."
        return "No recent blocked routine runs."
    return ""
