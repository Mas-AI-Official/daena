"""3-pass refinement pipeline for Department Souls.

Mirrors the SkillRefinery pattern (gap finder / improver / critic) but
operates on soul markdown files instead of skill JSON. Key differences:

- **Soul files are character blueprints**, not task procedures. The gap
  finder asks "what's missing from this persona," not "what step is
  missing." The improver proposes additions/revisions grounded in
  domain evidence (web-research pass + existing soul text). The critic
  guards against persona drift -- core identity (name, mission) must
  stay stable; refinements update tone / expertise framing / tools.

- **Founder approval is required** before any refined soul overwrites
  the live file. The store module persists proposals as pending diffs;
  ``approve_proposal`` is the one-way gate to production.

- **Circuit breaker shared with SkillRefinery** -- same semaphore,
  emergency stop, daily token budget. Soul refinements count against
  the same budget as skill refinements to keep spend bounded.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.skill_refinery.refinement_service import (
    MAX_TOKENS_PER_PASS,
    REFINEMENT_TIMEOUT,
    _emergency_stop,
    _refinement_semaphore,
    _track_cost,
)
from app.services.soul_engine import SoulEngine, _load_department_soul, _normalize_department
from app.services.soul_maker.research import fetch_domain_best_practices

logger = get_logger(__name__)


@dataclass
class SoulRefinementResult:
    """Output of a full 3-pass refinement run.

    The ``proposed_body`` is the new soul content (without frontmatter).
    ``verdict`` tells the caller whether to auto-persist as a proposal
    (APPROVE / NEEDS_WORK) or discard (REJECT / ABORT).
    """

    department_slug: str
    original_body: str
    proposed_body: str
    gap_report: dict[str, Any] = field(default_factory=dict)
    improvement_notes: list[str] = field(default_factory=list)
    critic_report: dict[str, Any] = field(default_factory=dict)
    evidence_sources: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    verdict: str = "ABORT"  # APPROVE | NEEDS_WORK | REJECT | ABORT
    error: str | None = None


# ── Prompt templates ───────────────────────────────────────────────

_GAP_FINDER_PROMPT = """\
You are an AI persona quality auditor for the Daena platform.

Analyze the Department Soul below and identify what's missing, stale,
or vague. A Department Soul is a CHARACTER BLUEPRINT for an AI Mind
that operates as a specialist in the named domain. It shapes tone,
expertise framing, tool preferences, and reasoning patterns.

Focus your audit on:
- Missing expertise frames that a practitioner in this domain would expect.
- Stale tool or runtime preferences given the current landscape ({evidence_date_hint}).
- Vague or generic language that could apply to any domain.
- Missing handoff signals to other Minds.
- Missing anti-patterns (things this Mind should explicitly never do).

DEPARTMENT SOUL TO AUDIT:
<<<
{soul_body}
>>>

DOMAIN EVIDENCE (recent best practices, may be empty):
<<<
{evidence_block}
>>>

Respond with ONLY a JSON object:
{{
  "missing_expertise_frames": ["frame that should exist but doesn't"],
  "stale_items": ["anything referencing old tools or dated practices"],
  "vague_items": ["instructions too generic to be this Mind's specialty"],
  "missing_handoffs": ["handoff signals to other Minds that should exist"],
  "missing_anti_patterns": ["dangerous defaults this Mind should refuse"],
  "overall_quality": "LOW" | "MEDIUM" | "HIGH"
}}

No prose. JSON only."""


_IMPROVER_PROMPT = """\
You are an AI persona refinement specialist for the Daena platform.

Given the original Department Soul, a gap report, and current domain
evidence, produce a refined version of the soul. Your refinement rules:

HARD RULES (never break):
- Preserve the Mind's name, department, and core identity unchanged.
- Preserve the file frontmatter format (YAML between --- markers).
- Do not add content that conflicts with Daena's core soul (loyalty,
  shield, relentless reasoning) -- those live above this file.
- Keep the structure: Identity, Voice and Tone, Expertise Framing,
  Reasoning Pattern, Tool Preferences, Opening Phrases, Anti-Patterns,
  Handoff Signals. You may add subsections but not remove these.

SOFT GOALS:
- Address every item in the gap report.
- Ground new expertise frames in the domain evidence provided.
- Keep the total length within 20% of the original.
- Prefer specific names of frameworks, people, tools over generic terms.

ORIGINAL SOUL BODY:
<<<
{soul_body}
>>>

GAP REPORT:
{gap_report}

DOMAIN EVIDENCE:
<<<
{evidence_block}
>>>

Respond with ONLY a JSON object:
{{
  "proposed_body": "the full refined soul body text, markdown, no frontmatter",
  "improvements": ["list of what you changed and why, one line each"]
}}

No prose outside the JSON. JSON only."""


_CRITIC_PROMPT = """\
You are an AI persona validation critic for the Daena platform.

Compare the proposed refined soul against the original. Your job is to
protect against PERSONA DRIFT -- core identity must stay stable; only
tone, expertise framing, and tooling updates are acceptable.

HARD FAILURES (verdict = REJECT):
- Mind's name, department, or core mission changed.
- New content conflicts with Daena's core soul (loyalty, shield).
- Required sections (Identity, Voice, Expertise Framing, Reasoning,
  Tools, Opening Phrases, Anti-Patterns, Handoffs) removed.
- Fabricated citations or tool names that don't exist.

SOFT FAILURES (verdict = NEEDS_WORK):
- Gaps from the gap report not actually addressed.
- New language is still vague or generic.
- Length increased or decreased by more than 30%.

PASS (verdict = APPROVE):
- All hard rules satisfied.
- Majority of gap items addressed with concrete content.
- Tone and framing feel consistent with original persona.

ORIGINAL BODY:
<<<
{original_body}
>>>

PROPOSED BODY:
<<<
{proposed_body}
>>>

GAP REPORT (what the improver was supposed to address):
{gap_report}

Respond with ONLY a JSON object:
{{
  "verdict": "APPROVE" | "NEEDS_WORK" | "REJECT",
  "persona_drift_detected": true | false,
  "hallucinations": ["fabricated items, empty list if none"],
  "conflicts_with_core_soul": ["anything that contradicts loyalty/shield"],
  "unaddressed_gaps": ["gap items the improver missed"],
  "confidence": 0.0,
  "notes": "one short paragraph"
}}

JSON only."""


async def _call_llm(prompt: str) -> str:
    """Call the configured refinement LLM (same as SkillRefinery).

    Shares circuit breaker + token budget with SkillRefinery so total
    refinement spend is bounded across both subsystems.
    """
    if _emergency_stop.is_set():
        logger.warning("soul_maker.emergency_stop_active")
        return ""

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            coro = client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": MAX_TOKENS_PER_PASS,
                    },
                },
            )
            resp = await asyncio.wait_for(coro, timeout=REFINEMENT_TIMEOUT)
            resp.raise_for_status()
            result = resp.json().get("message", {}).get("content", "")
            _track_cost(len(result) // 4)
            return result
    except TimeoutError:
        logger.error("soul_maker.llm_timeout", timeout=REFINEMENT_TIMEOUT)
        return ""
    except Exception as exc:
        logger.error("soul_maker.llm_call_failed", error=str(exc))
        return ""


def _parse_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a (possibly fenced) LLM reply."""
    if not text:
        return {}
    # Strip markdown fences
    t = text.strip()
    if t.startswith("```"):
        # drop leading fence line + trailing fence
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # Try to find the first {...} block
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(t[start : end + 1])
            except json.JSONDecodeError:
                pass
    logger.warning("soul_maker.json_parse_failed", preview=text[:300])
    return {}


def _format_evidence(snippets: list[dict[str, Any]]) -> str:
    """Serialize evidence snippets into a compact prompt block."""
    if not snippets:
        return "(no external evidence available)"
    lines: list[str] = []
    for i, snip in enumerate(snippets, 1):
        src = snip.get("source", "unknown")
        date = snip.get("date", "")
        title = snip.get("title", "")[:140]
        text = snip.get("text", "")[:400]
        header = f"[{i}] {src}" + (f" · {date}" if date else "") + (f" · {title}" if title else "")
        lines.append(header + "\n    " + text)
    return "\n\n".join(lines)


async def refine_department_soul(
    department: str,
    *,
    use_research: bool = True,
    persist_proposal: bool = True,
) -> SoulRefinementResult:
    """Run a full 3-pass refinement for one Department Soul.

    Args:
        department: Name, slug, or Mind name (resolved via SoulEngine).
        use_research: If True, fetch current domain best practices via
            intel_fanout before refinement. Disable in tests or when the
            refinement target is the research itself.
        persist_proposal: If True and the critic verdict is APPROVE or
            NEEDS_WORK, save the proposal to the store for founder
            review. REJECT / ABORT results are never persisted.

    Returns:
        SoulRefinementResult with verdict, confidence, and the proposed
        new body. Never overwrites the live soul file -- only a founder
        can approve via ``store.approve_proposal``.
    """
    slug = _normalize_department(department)
    if not slug:
        return SoulRefinementResult(
            department_slug=str(department),
            original_body="",
            proposed_body="",
            verdict="ABORT",
            error=f"unknown_department: {department!r}",
        )

    meta, original_body = _load_department_soul(slug)
    if not original_body:
        return SoulRefinementResult(
            department_slug=slug,
            original_body="",
            proposed_body="",
            verdict="ABORT",
            error="soul_file_missing_or_empty",
        )

    # ── Research pass (optional) ──
    evidence: list[dict[str, Any]] = []
    if use_research:
        try:
            evidence = await fetch_domain_best_practices(slug)
        except Exception as exc:
            logger.warning("soul_maker.research_failed", slug=slug, error=str(exc))
    evidence_block = _format_evidence(evidence)
    evidence_date_hint = "2026-Q2 and later"

    # ── Pass 1: Gap Finder ──
    async with _refinement_semaphore:
        gap_raw = await _call_llm(
            _GAP_FINDER_PROMPT.format(
                soul_body=original_body,
                evidence_block=evidence_block,
                evidence_date_hint=evidence_date_hint,
            ),
        )
        gap_report = _parse_json(gap_raw)
        if not gap_report:
            return SoulRefinementResult(
                department_slug=slug,
                original_body=original_body,
                proposed_body="",
                evidence_sources=evidence,
                verdict="ABORT",
                error="gap_finder_returned_no_json",
            )

        # ── Pass 2: Improver ──
        improv_raw = await _call_llm(
            _IMPROVER_PROMPT.format(
                soul_body=original_body,
                gap_report=json.dumps(gap_report, indent=2),
                evidence_block=evidence_block,
            ),
        )
        improv = _parse_json(improv_raw)
        proposed_body = (improv.get("proposed_body") or "").strip()
        if not proposed_body:
            return SoulRefinementResult(
                department_slug=slug,
                original_body=original_body,
                proposed_body="",
                gap_report=gap_report,
                evidence_sources=evidence,
                verdict="ABORT",
                error="improver_returned_empty_body",
            )

        # ── Pass 3: Critic ──
        critic_raw = await _call_llm(
            _CRITIC_PROMPT.format(
                original_body=original_body,
                proposed_body=proposed_body,
                gap_report=json.dumps(gap_report, indent=2),
            ),
        )
        critic = _parse_json(critic_raw)
        if not critic:
            critic = {"verdict": "NEEDS_WORK", "confidence": 0.0, "notes": "critic_no_json"}

    verdict = str(critic.get("verdict") or "NEEDS_WORK").upper()
    if verdict not in {"APPROVE", "NEEDS_WORK", "REJECT"}:
        verdict = "NEEDS_WORK"
    try:
        confidence = float(critic.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    result = SoulRefinementResult(
        department_slug=slug,
        original_body=original_body,
        proposed_body=proposed_body,
        gap_report=gap_report,
        improvement_notes=list(improv.get("improvements") or []),
        critic_report=critic,
        evidence_sources=evidence,
        confidence=confidence,
        verdict=verdict,
    )

    # Persist as a pending proposal for founder review. REJECT is never
    # persisted -- that's junk. ABORT never reaches here.
    if persist_proposal and verdict in {"APPROVE", "NEEDS_WORK"}:
        try:
            from app.services.soul_maker.store import save_proposal

            save_proposal(
                slug=slug,
                mind_name=str(meta.get("name") or slug),
                original_body=original_body,
                proposed_body=proposed_body,
                gap_report=gap_report,
                improvement_notes=result.improvement_notes,
                critic_report=critic,
                evidence_sources=evidence,
                confidence=confidence,
                verdict=verdict,
            )
        except Exception as exc:
            logger.warning("soul_maker.persist_failed", slug=slug, error=str(exc))

    logger.info(
        "soul_maker.refined",
        slug=slug,
        verdict=verdict,
        confidence=confidence,
        gaps=len((gap_report.get("missing_expertise_frames") or [])),
        evidence_sources=len(evidence),
    )
    return result


async def refine_all_departments(*, use_research: bool = True) -> list[SoulRefinementResult]:
    """Refine every known department soul in parallel.

    Used by the weekly heartbeat job. Respects the shared SkillRefinery
    semaphore so concurrent runs don't exceed MAX_CONCURRENT_REFINEMENTS.
    """
    departments = SoulEngine.list_departments()
    tasks = [
        refine_department_soul(d["slug"], use_research=use_research)
        for d in departments
    ]
    return await asyncio.gather(*tasks, return_exceptions=False)
