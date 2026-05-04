"""Self-Diagnostic Advisor — Sprint-7 PR-2 (2026-05-04).

Lets Daena answer "are you OK?" / "what is broken?" / "why 0 callable?"
in chat WITHOUT calling an LLM. Reuses the diagnostic logic that
already lives in ``app.api.v1.system_self_diagnostic`` (Sprint-6 PR-7)
so chat and the dashboard card always agree on the state of the world.

Scope (intentionally narrow)
----------------------------

* DIAGNOSE ONLY. Never modifies OS / cloud / secrets / connector
  state / running processes. Every recommended action is advisory
  text the operator (or a future approval-gated automation) acts on.
* No external network. The diagnostic itself is loopback-only and
  this advisor adds no further calls.
* No Phase 3 writes -- we never call the executor or any side-effecting
  service.

Public surface
--------------

* ``is_self_diagnostic_question(message: str) -> bool``
* ``SAFETY_BOUNDARY``: the verbatim text the response always ends
  with. Surfaces in chat so the operator sees the boundary even if
  the page is plain markdown.
* ``compose_answer_text(payload: dict) -> str``: pure formatter
  (deterministic given the same payload).
* ``gather_and_compose(db, tenant_id) -> str``: does the full
  gather + compose with a graceful fallback if anything in the
  diagnostic stack throws.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger


logger = get_logger(__name__)


# Standing safety statement the response always ends with. Keep
# verbatim so the operator never has to wonder if Daena is in a mode
# where she might silently fix things.
SAFETY_BOUNDARY = (
    "I can diagnose; I need approval to modify."
)


# ──────────────────────────────────────────────────────────────────
# 1. Intent classifier (cheap regex; no LLM)
# ──────────────────────────────────────────────────────────────────


# Phrases the operator actually types when asking Daena about her own
# state. Patterns are matched against a normalized lower-cased message.
# Each pattern is anchored loosely (substring) -- false positives matter
# less here than missing a real ask, because the advisor's answer is
# always honest and deterministic.
_SELF_DIAGNOSTIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p) for p in (
        # Direct health questions.
        r"\bare you (ok|okay|alright|healthy|alive|working|up|broken)\b",
        r"\bis (everything|anything) (ok|okay|alright|broken|wrong|working)\b",
        # "What's wrong" / "what is broken" family. Tightened so
        # "what's wrong with this code?" / "what's wrong with this
        # config?" do NOT match -- those are asking about an external
        # subject, not about Daena's runtime. We only match when
        # the question is bare (ends with ?, ., !, end-of-string,
        # "right now", or self-reference: you / yourself / daena /
        # the system / the backend).
        r"\bwhat('s| is) (broken|wrong)\s*(\?|\.|!|$|right now|now\b)",
        r"\bwhat('s| is) (broken|wrong)\s+with\s+(you|yourself|daena|the\s+system|the\s+backend)\b",
        r"\banything (broken|wrong)\b",
        # Callability question (the dominant local-laptop confusion).
        r"\bwhy\s*0\s*(of\s*\d+\s*)?callable\b",
        r"\bwhy (no|none|nothing) (is\s*)?callable\b",
        r"\b0\s*(of\s*\d+\s*)?callable\b.*\bwhy\b",
        # Self-diagnostic verbs.
        r"\b(self[\s\-]?diagnostic|self[\s\-]?check|self[\s\-]?test)\b",
        r"\b(diagnose|diagnostic) (yourself|daena|the system)\b",
        r"\b(check|verify|test) (yourself|your (health|status|state))\b",
        # System status family.
        r"\b(system|backend|runtime) (health|status|state)\b",
        r"\b(your|daena's?) (health|status|state)\b",
        r"\bshow (me )?(your )?(diagnostics?|health|status)\b",
        # "Fix yourself" -- the advisor REFUSES to act, but should
        # still recognize the ask so the response can carry the
        # safety-boundary explanation.
        r"\bfix (yourself|the system|daena)\b",
        r"\brepair (yourself|the system|daena)\b",
    )
)


def is_self_diagnostic_question(message: str) -> bool:
    """Return True if the message reads as a self-diagnostic ask.

    Conservative-leaning: only matches when the operator is plainly
    asking about Daena's own state. Generic "what's wrong with this
    code?" or "diagnose this error trace" do NOT match (they lack
    the self-referential anchor)."""
    if not message:
        return False
    normalized = message.strip().lower()
    if not normalized:
        return False
    return any(p.search(normalized) for p in _SELF_DIAGNOSTIC_PATTERNS)


# ──────────────────────────────────────────────────────────────────
# 2. Pure formatter (deterministic given same payload)
# ──────────────────────────────────────────────────────────────────


_OVERALL_LABEL = {
    "healthy": "HEALTHY",
    "warning": "WARNING",
    "blocked": "BLOCKED",
}


def compose_answer_text(payload: dict[str, Any]) -> str:
    """Format a diagnostic payload as a markdown chat answer.

    The payload shape matches what
    ``system_self_diagnostic.system_self_diagnostic`` returns under
    its ``data`` key.

    The output ALWAYS ends with ``SAFETY_BOUNDARY``.
    """
    data = payload.get("data", payload)  # accept both shapes
    overall = data.get("overall_status", "healthy")
    overall_label = _OVERALL_LABEL.get(overall, overall.upper())
    checks: dict[str, dict[str, Any]] = data.get("checks", {}) or {}
    actions: list[str] = list(data.get("recommended_actions", []) or [])

    lines: list[str] = []
    lines.append("## Self-diagnostic")
    lines.append("")
    lines.append(f"**Overall:** {overall_label}")
    lines.append("")

    # Top blockers: every check whose status is warning or blocked.
    blockers: list[tuple[str, str, str]] = []
    for name, c in checks.items():
        status = (c or {}).get("status", "healthy")
        if status in ("warning", "blocked"):
            blockers.append((
                name,
                status,
                (c or {}).get("detail", "") or "",
            ))

    if blockers:
        lines.append("### Top blockers")
        for name, status, detail in blockers:
            label = _OVERALL_LABEL.get(status, status.upper())
            pretty_name = name.replace("_", " ")
            tail = f" -- {detail}" if detail else ""
            lines.append(f"- **{pretty_name}** ({label}){tail}")
        lines.append("")
    else:
        lines.append("All checks pass. Daena's local runtime is healthy.")
        lines.append("")

    if actions:
        lines.append("### Next 3 recommended actions")
        # Cap to top 3 -- the chat answer is for orientation, not a
        # full runbook.
        for idx, action in enumerate(actions[:3], start=1):
            lines.append(f"{idx}. {action}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(SAFETY_BOUNDARY)

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────
# 3. Gather + compose (with graceful fallback)
# ──────────────────────────────────────────────────────────────────


_FALLBACK_RESPONSE = (
    "## Self-diagnostic\n"
    "\n"
    "**Overall:** UNKNOWN\n"
    "\n"
    "I couldn't run the diagnostic right now. Open the Connections "
    "page or hit `/api/v1/system/self-diagnostic` directly to see the "
    "raw state.\n"
    "\n"
    "---\n"
    "\n"
    f"{SAFETY_BOUNDARY}"
)


async def gather_and_compose(db: AsyncSession, tenant_id: Any) -> str:
    """Run the full diagnostic and return a formatted markdown answer.

    On any failure (DB blip, marketplace stall, frontend probe
    blowing up), returns ``_FALLBACK_RESPONSE``. The advisor never
    raises into the chat orchestrator -- a self-diagnostic should
    not be the thing that breaks the chat.
    """
    try:
        # Imported lazily so the test suite can stub the module without
        # paying its import cost when the advisor itself is being
        # unit-tested in isolation.
        from app.api.v1.system_self_diagnostic import (
            _check_backend,
            _check_connector_callability,
            _check_database,
            _check_frontend_reachable,
            _check_local_models,
            _check_migration_head,
            _recommended_actions,
            _worst,
        )
        import asyncio as _asyncio

        backend, database, migration, frontend, local_models, callability = await _asyncio.gather(
            _check_backend(),
            _check_database(db),
            _check_migration_head(db),
            _check_frontend_reachable(),
            _check_local_models(),
            _check_connector_callability(db, tenant_id),
        )
        checks = {
            "backend": backend,
            "database": database,
            "migration_head": migration,
            "frontend": frontend,
            "local_models": local_models,
            "connector_callability": callability,
        }
        payload = {
            "data": {
                "overall_status": _worst(*[c["status"] for c in checks.values()]),
                "checks": checks,
                "recommended_actions": _recommended_actions(checks),
            },
        }
        return compose_answer_text(payload)
    except Exception as exc:  # noqa: BLE001 -- self-diag must never raise
        logger.warning(
            "self_diagnostic_advisor.gather_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return _FALLBACK_RESPONSE


__all__ = [
    "SAFETY_BOUNDARY",
    "compose_answer_text",
    "gather_and_compose",
    "is_self_diagnostic_question",
]
