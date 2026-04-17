"""Cognitive Lens Router -- Stage 6.7 of the chat pipeline.

Purpose
-------
The general chat path used to fire only ``knowledge_graph`` (Stage 6.2) and
``ooda_engine`` (Stage 7.5, EXE only) from the 20-module cognition arsenal.
The rest of the arsenal -- Inversion, FirstPrinciples, ConsequenceChain,
FiveWhys, ConstraintAnalyzer, PreMortem, apex_cognition, unreplicable,
beyond_mythos -- fires only in the offensive security scan path. That is
the Mythos gap: we built the capability, we just never wired it into the
default pipeline (see ARCHITECTURE.md Section 11).

This router closes the gap. Per turn it picks 0-3 chat-appropriate lenses
using complexity-adaptive keyword heuristics (zero LLM, target <=150ms),
fires them in parallel via ``asyncio.gather``, and returns a system-prompt
fragment the downstream LLM (and every Council debater, and every
Quintessence expert) sees as "Cognitive Notes".

Not a new cognitive capability -- a router over capabilities that already
exist. By design this is the thinnest possible glue.

Non-goals
---------
* Full OODA orchestration (that is Stage 7.5, EXE only, and is heavier).
* LLM-driven lens generation (lenses here are deterministic).
* The offensive-only lenses (``apex_cognition``, ``unreplicable``,
  ``beyond_mythos``). Those stay gated behind the scan path.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Action keywords that surface a consequence-chain lens ────────────
_ACTION_KEYWORDS: tuple[str, ...] = (
    "deploy", "release", "push",
    "delete", "remove", "drop", "rm ",
    "write", "modify", "edit file", "update file",
    "install", "pip install", "npm install", "apt ",
    "migrate", "migration",
    "restart", "kill", "shutdown",
    "revoke", "disable",
)


@dataclass(slots=True)
class LensResult:
    """One lens's contribution to the Cognitive Notes fragment."""
    name: str
    fragment: str
    duration_ms: int


# ── Selection rule ────────────────────────────────────────────────────

def select_lenses(
    query: str,
    intent: str,
    complexity: str,
    risk: str,
) -> list[str]:
    """Pick which lenses to fire based on query properties.

    Returns an ordered list of lens names. May be empty for simple chat.
    Selection rules match ARCHITECTURE.md Section 11.5 table.

    Zero-cost: pure string/dict logic. No I/O.
    """
    lenses: list[str] = []
    query_lower = query.lower()
    complexity_upper = (complexity or "").upper()
    risk_upper = (risk or "").upper()
    intent_upper = (intent or "").upper()

    # Complex or high-risk: reason from first principles + invert for
    # failure modes. This is the default "smart mode" for real questions.
    if (
        complexity_upper in ("COMPLEX", "VERY_COMPLEX", "HIGH")
        or risk_upper in ("HIGH", "CRITICAL")
    ):
        lenses.append("first_principles")
        lenses.append("inversion")

    # Ambiguous intent: first principles alone is enough to surface the
    # hidden assumption. Avoid firing inversion too (doubles up with
    # first_principles on assumption questioning).
    if intent_upper == "AMBIGUOUS" and "first_principles" not in lenses:
        lenses.append("first_principles")

    # Actions (tool-use, dangerous intents, or literal action verbs):
    # consequence chain catches 2nd/3rd-order effects.
    if (
        intent_upper in ("DANGEROUS", "TOOL_USE")
        or any(kw in query_lower for kw in _ACTION_KEYWORDS)
    ):
        if "consequence_chain" not in lenses:
            lenses.append("consequence_chain")

    # Cap at 3 lenses per turn to keep the prompt lean.
    return lenses[:3]


# ── Individual lens runners ───────────────────────────────────────────

async def _run_first_principles(query: str) -> str:
    from app.services.cognition.first_principles import FirstPrinciples
    analysis = await FirstPrinciples().decompose(task=query)
    assumptions = analysis.get("assumptions") or []
    truths = analysis.get("truths") or []
    if not assumptions and not truths:
        return ""
    parts: list[str] = ["First-principles lens:"]
    if assumptions:
        top = "; ".join(a for a in assumptions[:3])
        parts.append(f"  - Assumptions worth questioning: {top}")
    if truths:
        top = "; ".join(t for t in truths[:3])
        parts.append(f"  - Provable constraints: {top}")
    return "\n".join(parts)


async def _run_inversion(query: str) -> str:
    from app.services.cognition.inversion import Inversion
    result = await Inversion().analyze(task=query)
    failure_modes = result.get("failure_modes") or []
    preventions = result.get("preventions") or []
    if not failure_modes:
        return ""
    top_failures = "; ".join(fm for fm in failure_modes[:3])
    parts: list[str] = [
        "Inversion lens (what would make this fail?):",
        f"  - Failure modes: {top_failures}",
    ]
    if preventions:
        parts.append(f"  - Prevent by: {'; '.join(p for p in preventions[:3])}")
    return "\n".join(parts)


async def _run_consequence_chain(query: str) -> str:
    from app.services.cognition.consequence_chain import ConsequenceChain
    consequences = await ConsequenceChain().analyze(action=query)
    if not consequences:
        return ""
    # Surface the highest-severity consequences first.
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(
        consequences,
        key=lambda c: sev_rank.get(str(getattr(c, "severity", "low")).lower(), 3),
    )
    parts: list[str] = ["Consequence-chain lens (2-3 order effects):"]
    for c in ranked[:3]:
        order = getattr(c, "order", "?")
        desc = getattr(c, "description", str(c))
        sev = getattr(c, "severity", "?")
        parts.append(f"  - Order {order} [{sev}]: {desc}")
    return "\n".join(parts)


_RUNNERS: dict[str, Any] = {
    "first_principles": _run_first_principles,
    "inversion": _run_inversion,
    "consequence_chain": _run_consequence_chain,
}


# ── Public API ────────────────────────────────────────────────────────

async def apply_lenses(
    query: str,
    intent: str,
    complexity: str,
    risk: str,
    timeout_s: float = 0.25,
) -> list[LensResult]:
    """Fire the selected lenses in parallel. Zero LLM cost.

    Returns a (possibly empty) list of LensResult, one per successful
    lens. Failed lenses are logged and omitted -- never raise.

    The caller should wrap the resulting fragments with
    ``format_cognitive_notes`` for injection into the system prompt.
    """
    import time

    lenses = select_lenses(query, intent, complexity, risk)
    if not lenses:
        return []

    async def _fire(name: str) -> LensResult | None:
        runner = _RUNNERS.get(name)
        if runner is None:
            return None
        start = time.monotonic()
        try:
            fragment = await asyncio.wait_for(runner(query), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning("lens_router.timeout", lens=name)
            return None
        except Exception:
            logger.exception("lens_router.failed", lens=name)
            return None
        if not fragment:
            return None
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return LensResult(name=name, fragment=fragment, duration_ms=elapsed_ms)

    raw = await asyncio.gather(*[_fire(n) for n in lenses], return_exceptions=False)
    results = [r for r in raw if r is not None]
    logger.info(
        "lens_router.applied",
        lenses=[r.name for r in results],
        total_ms=sum(r.duration_ms for r in results),
        skipped=[l for l in lenses if l not in {r.name for r in results}],
    )
    return results


def format_cognitive_notes(results: list[LensResult]) -> str:
    """Render LensResult list as a system-prompt addendum.

    Returns the empty string when ``results`` is empty so the caller can
    unconditionally append without a guard.
    """
    if not results:
        return ""
    header = (
        "\n\n---\n"
        "## Cognitive Notes\n"
        "The following lenses fired automatically. Treat them as hints, "
        "not hard facts. If a lens is irrelevant to the user's actual "
        "question, ignore it. If a lens surfaces a real risk or "
        "hidden assumption, address it directly in your answer.\n"
    )
    body = "\n\n".join(r.fragment for r in results)
    return f"{header}\n{body}\n"
