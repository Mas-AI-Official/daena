"""Workstream Redirect Parser — natural-language to RedirectAction list.

Per the Council R3 lock + Council R5 (2026-04-26) NL pivot, a
workstream's defining user action is REDIRECT:

    "pause file edits, ask Council, only produce a migration plan"

This parser turns that one sentence into a structured list of
``RedirectAction`` operations. Per the founder's directive 2026-04-26:
**no catalog mode**. The founder talks to Daena the way he talks to
Claude — typos, multi-task chaining, Persian-influenced phrasing — and
Daena is expected to understand. If something is genuinely unclear,
**Daena asks** rather than failing silently or partial-applying.

Architecture (Council R5 synthesized — Claude + Perplexity + GPT-5.5):

  1. **Pure LLM parse** with the Founder Voice Profile reference doc
     (``backend/app/soul/founder_voice_profile.md``) injected into the
     system prompt so Daena recognizes Masoud's natural style.
  2. **Strict JSON schema** validation on the LLM output. Anything
     that doesn't match the schema is treated as a parse failure.
  3. **Action-conflict detection** — e.g. PAUSE_AUTOPILOT +
     RESUME_AUTOPILOT in the same redirect is invalid; Daena asks.
  4. **Risk gating** — CANCEL always requires explicit confirmation
     regardless of LLM confidence (it's terminal + irreversible).
  5. **Audit record** — every parse attempt logs the original text,
     parsed actions, validation outcome, confidence, and the
     clarification (when asked) for the workstream timeline.

The legacy regex catalog (``REDIRECT_VERBS``) was DROPPED in this
revision because the founder explicitly rejected catalog mode. There
is no fast-path; every redirect goes through the LLM. The Voice
Profile makes that affordable + reliable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.core.universal_cognitive_gateway import (
    attach_gateway_review,
    build_gateway_request,
)

logger = get_logger(__name__)


class RedirectActionKind(str, Enum):
    """The operations a redirect can apply to a workstream.

    Add a kind here ONLY when there's also a corresponding handler in
    ``WorkstreamService``. The LLM parser is given this exact list in
    the system prompt; new kinds = new prompt entries.
    """

    PAUSE_AUTOPILOT = "PAUSE_AUTOPILOT"
    RESUME_AUTOPILOT = "RESUME_AUTOPILOT"
    NARROW_SCOPE = "NARROW_SCOPE"
    BROADEN_SCOPE = "BROADEN_SCOPE"
    REPLACE_GOAL = "REPLACE_GOAL"
    ESCALATE_COUNCIL = "ESCALATE_COUNCIL"
    ESCALATE_QUINTESSENCE = "ESCALATE_QUINTESSENCE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    REASSIGN_DEPARTMENT = "REASSIGN_DEPARTMENT"
    CANCEL = "CANCEL"


# Risk-gated kinds: even at high LLM confidence, these require an
# explicit confirmation step. CANCEL is the only terminal action; we
# never apply a CANCEL on the strength of LLM extraction alone.
_RISK_GATED_KINDS: set[RedirectActionKind] = {
    RedirectActionKind.CANCEL,
}

# Conflicting kind pairs — if both appear in one parse, Daena asks
# which one wins. ESCALATE_* are mutually exclusive; PAUSE/RESUME
# are mutually exclusive.
_CONFLICTING_PAIRS: list[tuple[RedirectActionKind, RedirectActionKind]] = [
    (RedirectActionKind.PAUSE_AUTOPILOT, RedirectActionKind.RESUME_AUTOPILOT),
    (RedirectActionKind.ESCALATE_COUNCIL, RedirectActionKind.ESCALATE_QUINTESSENCE),
    (RedirectActionKind.ESCALATE_COUNCIL, RedirectActionKind.ESCALATE_HUMAN),
    (RedirectActionKind.ESCALATE_QUINTESSENCE, RedirectActionKind.ESCALATE_HUMAN),
    (RedirectActionKind.CANCEL, RedirectActionKind.RESUME_AUTOPILOT),
    (RedirectActionKind.CANCEL, RedirectActionKind.REPLACE_GOAL),
]


@dataclass(slots=True, frozen=True)
class RedirectAction:
    """One parsed operation extracted from a redirect instruction."""

    kind: RedirectActionKind
    payload: dict[str, str] = field(default_factory=dict)
    matched_phrase: str = ""


@dataclass(slots=True)
class ParseResult:
    """Output of ``parse_redirect``."""

    actions: list[RedirectAction]
    unmatched_segments: list[str]
    raw_instruction: str
    confidence: float = 0.0
    reasoning: str = ""
    clarifying_question: str | None = None
    validation_errors: list[str] = field(default_factory=list)

    @property
    def fully_understood(self) -> bool:
        """True if every meaningful segment got matched and validation passed."""
        return (
            not self.unmatched_segments
            and not self.validation_errors
            and self.clarifying_question is None
        )

    @property
    def needs_user_clarification(self) -> bool:
        """True if Daena should surface a clarification question."""
        return self.clarifying_question is not None or bool(self.validation_errors)

    def to_audit_dict(self) -> dict[str, Any]:
        """Serialize for ``WorkstreamEvent.payload``."""
        return {
            "raw_instruction": self.raw_instruction,
            "actions": [
                {"kind": a.kind.value, "payload": a.payload, "matched": a.matched_phrase}
                for a in self.actions
            ],
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning[:280],
            "clarifying_question": self.clarifying_question,
            "validation_errors": self.validation_errors,
            "unmatched_segments": self.unmatched_segments,
        }


# ── Voice Profile loader (process-cached) ─────────────────────────────

_VOICE_PROFILE_PATH = (
    Path(__file__).resolve().parent.parent / "soul" / "founder_voice_profile.md"
)
_VOICE_PROFILE_CACHE: str | None = None


def _load_voice_profile() -> str:
    """Read and cache the Founder Voice Profile reference doc.

    The doc lives in the soul vault (``backend/app/soul/``) so it ships
    with the codebase + Docker images. If missing, the parser still
    works but loses founder-specific pattern recognition.
    """
    global _VOICE_PROFILE_CACHE
    if _VOICE_PROFILE_CACHE is not None:
        return _VOICE_PROFILE_CACHE
    try:
        if _VOICE_PROFILE_PATH.exists():
            text = _VOICE_PROFILE_PATH.read_text(encoding="utf-8")
            # Strip YAML front-matter the same way SoulEngine does.
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    text = parts[2].strip()
            _VOICE_PROFILE_CACHE = text
        else:
            logger.warning(
                "redirect_parser.voice_profile_missing",
                path=str(_VOICE_PROFILE_PATH),
            )
            _VOICE_PROFILE_CACHE = ""
    except Exception as exc:
        logger.warning("redirect_parser.voice_profile_read_failed", error=str(exc))
        _VOICE_PROFILE_CACHE = ""
    return _VOICE_PROFILE_CACHE


# ── LLM parse prompt ──────────────────────────────────────────────────

_SCHEMA_DESCRIPTION = """\
Output STRICTLY this JSON shape (no prose, no markdown fences):

{
  "actions": [
    {
      "kind": "<one of: PAUSE_AUTOPILOT, RESUME_AUTOPILOT, NARROW_SCOPE,
              BROADEN_SCOPE, REPLACE_GOAL, ESCALATE_COUNCIL,
              ESCALATE_QUINTESSENCE, ESCALATE_HUMAN, REASSIGN_DEPARTMENT,
              CANCEL>",
      "payload": {
        // For NARROW_SCOPE / BROADEN_SCOPE: {"constraint": "<text>"}
        // For REPLACE_GOAL: {"new_goal": "<text>"}
        // For REASSIGN_DEPARTMENT: {"department_slug": "<slug>"}
        // For PAUSE/RESUME/ESCALATE_*/CANCEL: {} (empty object)
      },
      "matched_phrase": "<the exact substring from the input that justified this action>"
    }
  ],
  "confidence": <float 0.0 to 1.0 — your overall confidence in this parse>,
  "reasoning": "<one short sentence explaining how you decoded the founder's intent>",
  "clarifying_question": null OR "<one specific question if the parse is ambiguous>"
}

If the input is too ambiguous to parse safely, set "actions" to []
and put a SPECIFIC clarifying question in "clarifying_question". Do
NOT generate menu-style questions; offer a sensible default the
founder can override.
"""


def _build_system_prompt() -> str:
    """Compose the LLM parser system prompt with Voice Profile."""
    voice = _load_voice_profile()
    return (
        "You are Daena's redirect parser. Your only job: turn the founder's "
        "free-form natural-language redirect instruction into a structured "
        "JSON list of RedirectAction operations.\n\n"
        "You MUST handle the founder's natural style — typos, multi-task "
        "messages, Persian-influenced word order, no formal punctuation. "
        "If the input is ambiguous, ask ONE specific clarifying question "
        "with a sensible default; never present a menu.\n\n"
        "=== FOUNDER VOICE PROFILE ===\n"
        f"{voice}\n"
        "=== END VOICE PROFILE ===\n\n"
        f"{_SCHEMA_DESCRIPTION}"
    )


# ── LLM call ──────────────────────────────────────────────────────────


async def _call_llm_parser(instruction: str) -> dict[str, Any] | None:
    """Call Daena's LLM router for redirect extraction.

    Picks the cheapest reliable judge model from the registry. Falls
    back to None on any failure so the caller can surface a clean
    "redirect parsing service unavailable" message instead of crashing.
    """
    try:
        # Lazy import to avoid circular deps with model_registry.
        from app.core.events import get_model_registry
        from app.core.constants import ModelProvider as _MP
        from app.services.providers.base import GenerateRequest, LLMMessage

        registry = get_model_registry()
        # Cheap, reliable JSON-emitter pick order:
        #   Gemini (Flash if available) > Perplexity (sonar) > Anthropic > OpenAI > Ollama
        provider = (
            registry.get_provider(_MP.GEMINI)
            or registry.get_provider(_MP.PERPLEXITY)
            or registry.get_provider(_MP.ANTHROPIC)
            or registry.get_provider(_MP.OPENAI)
            or registry.get_provider(_MP.OLLAMA)
        )
        if provider is None:
            logger.warning("redirect_parser.no_llm_available")
            return None

        request = GenerateRequest(
            messages=[
                LLMMessage(role="system", content=_build_system_prompt()),
                LLMMessage(role="user", content=instruction),
            ],
            model_id="auto",  # provider picks its default
            temperature=0.0,  # deterministic-as-possible for parsing
            max_tokens=600,
            metadata={"stage": "workstream_redirect_parse"},
        )
        request = build_gateway_request(
            request,
            model_id="auto",
            available_models=["gemini", "perplexity", "anthropic", "openai", "ollama"],
        )
        resp = await provider.generate(request)
        resp = attach_gateway_review(resp, request)
        if not resp or not resp.content:
            return None
        return _extract_json(resp.content)
    except Exception as exc:
        logger.warning("redirect_parser.llm_call_failed", error=str(exc))
        return None


def _extract_json(raw: str) -> dict[str, Any] | None:
    """Tolerant JSON extractor — strips fences, locates {...} body."""
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


# ── Validation layer (Council R5 — GPT-5.5's deterministic gate) ─────


def _validate_actions(actions: list[RedirectAction]) -> list[str]:
    """Run schema + conflict + risk-gating checks on parsed actions.

    Returns a list of validation-error strings. Empty list = OK.
    """
    errors: list[str] = []

    # Conflict detection — both members of any conflicting pair present.
    kinds = {a.kind for a in actions}
    for a, b in _CONFLICTING_PAIRS:
        if a in kinds and b in kinds:
            errors.append(
                f"conflict: {a.value} and {b.value} cannot apply in the same redirect",
            )

    # Risk gating — CANCEL must arrive solo with explicit confirmation.
    if RedirectActionKind.CANCEL in kinds and len(actions) > 1:
        errors.append(
            "risk: CANCEL is terminal; combining it with other actions requires explicit confirmation",
        )

    # Schema sanity — REASSIGN_DEPARTMENT must have a department_slug.
    for a in actions:
        if a.kind == RedirectActionKind.REASSIGN_DEPARTMENT:
            if not a.payload.get("department_slug"):
                errors.append(
                    "schema: REASSIGN_DEPARTMENT missing department_slug",
                )
        elif a.kind == RedirectActionKind.NARROW_SCOPE:
            if not a.payload.get("constraint"):
                errors.append("schema: NARROW_SCOPE missing constraint")
        elif a.kind == RedirectActionKind.BROADEN_SCOPE:
            if not a.payload.get("constraint"):
                errors.append("schema: BROADEN_SCOPE missing constraint")
        elif a.kind == RedirectActionKind.REPLACE_GOAL:
            if not a.payload.get("new_goal"):
                errors.append("schema: REPLACE_GOAL missing new_goal")

    return errors


def _build_clarification_for_errors(
    actions: list[RedirectAction], errors: list[str], raw: str,
) -> str:
    """Craft ONE specific clarification question per the founder's style.

    Per the Voice Profile: never numbered menus, never "what did you
    mean?" — always concrete, with a sensible default.
    """
    # Conflict cases get specific resolutions.
    if any("conflict:" in e for e in errors):
        kinds = [a.kind.value for a in actions]
        return (
            f"You said '{raw}' — that mixes {', '.join(kinds)}, which I can't apply "
            "together. Which one wins, or should I keep the current state and just "
            "do the rest? (Reply with the action name or 'rest')"
        )
    # Risk cases: always confirm CANCEL.
    if any("risk:" in e for e in errors):
        return (
            f"You said '{raw}' — CANCEL is terminal and irreversible. "
            "Confirm with 'yes cancel' to apply, or 'no' to keep the workstream alive."
        )
    # Schema cases: ask for the missing field.
    if any("schema:" in e for e in errors):
        # Find first schema error and ask about it.
        first = next((e for e in errors if "schema:" in e), "")
        if "REASSIGN_DEPARTMENT" in first:
            return (
                f"You said '{raw}' — which department? (e.g. engineering, marketing, sales)"
            )
        if "NARROW_SCOPE" in first or "BROADEN_SCOPE" in first:
            return (
                f"You said '{raw}' — what specifically should I narrow/broaden the scope to?"
            )
        if "REPLACE_GOAL" in first:
            return f"You said '{raw}' — what's the new goal in one line?"
    return (
        f"You said '{raw}' — I caught some of it but want to confirm before applying. "
        "Could you restate the part I missed?"
    )


# ── Public API (unchanged signature for back-compat) ─────────────────


async def parse_redirect(instruction: str) -> ParseResult:
    """Parse a free-form redirect instruction into a ParseResult.

    Algorithm (Council R5 synthesized):
      1. Empty instruction -> empty ParseResult.
      2. Call the LLM parser with the Voice Profile in system prompt.
      3. Validate schema + conflicts + risk-gating.
      4. If validation fails OR confidence < 0.6, return a
         ParseResult with a specific clarifying_question.
      5. Otherwise return actions ready to apply.

    Returns:
        ParseResult with actions and (optionally) a clarifying question.
        Never raises — failures degrade to clarification asks.
    """
    if not instruction or not instruction.strip():
        return ParseResult(actions=[], unmatched_segments=[], raw_instruction=instruction)

    raw = instruction.strip()
    payload = await _call_llm_parser(raw)

    if payload is None:
        # LLM unavailable — surface as clarification rather than crashing.
        logger.info("redirect_parser.llm_unavailable", instruction=raw[:200])
        return ParseResult(
            actions=[],
            unmatched_segments=[raw],
            raw_instruction=raw,
            clarifying_question=(
                "The redirect parser is offline right now — could you state "
                "the redirect as discrete actions (e.g. 'pause autopilot' / "
                "'switch to engineering')?"
            ),
        )

    # Decode actions from LLM payload.
    actions: list[RedirectAction] = []
    raw_actions = payload.get("actions") or []
    for entry in raw_actions:
        try:
            kind = RedirectActionKind(str(entry.get("kind", "")).strip().upper())
        except ValueError:
            continue  # unknown kind — silently drop
        action_payload = entry.get("payload") or {}
        if not isinstance(action_payload, dict):
            action_payload = {}
        # Normalize payload values to strings.
        clean_payload = {
            str(k): str(v).strip() for k, v in action_payload.items() if v is not None
        }
        matched = str(entry.get("matched_phrase", ""))[:200]
        actions.append(RedirectAction(kind=kind, payload=clean_payload, matched_phrase=matched))

    confidence = float(payload.get("confidence") or 0.0)
    reasoning = str(payload.get("reasoning") or "")[:500]
    llm_clarify = payload.get("clarifying_question")
    if llm_clarify is not None:
        llm_clarify = str(llm_clarify).strip() or None

    # Run deterministic validation (R5 Phase 5: GPT-5.5's gate).
    validation_errors = _validate_actions(actions)

    # Decide whether to ask for clarification.
    clarifying = None
    if llm_clarify and not actions:
        # LLM itself asked for clarification.
        clarifying = llm_clarify
    elif validation_errors:
        clarifying = _build_clarification_for_errors(actions, validation_errors, raw)
    elif confidence < 0.6 and actions:
        # Low confidence — confirm before applying.
        action_summary = ", ".join(a.kind.value for a in actions)
        clarifying = (
            f"You said '{raw}' — I'm reading this as: {action_summary}. "
            "Apply that, or did you mean something else?"
        )

    result = ParseResult(
        actions=actions if not clarifying else [],
        unmatched_segments=[] if (actions and not clarifying) else [raw],
        raw_instruction=raw,
        confidence=confidence,
        reasoning=reasoning,
        clarifying_question=clarifying,
        validation_errors=validation_errors,
    )
    logger.info(
        "redirect_parser.parsed",
        instruction=raw[:200],
        action_count=len(result.actions),
        confidence=round(confidence, 3),
        validation_errors=validation_errors,
        needs_clarification=result.needs_user_clarification,
        kinds=[a.kind.value for a in result.actions],
    )
    return result


def render_clarification_hint(result: ParseResult) -> str:
    """Return the clarification text if any. Empty string when fully understood.

    Kept for backward compatibility with the existing API endpoint.
    Prefer ``result.clarifying_question`` directly when writing new code.
    """
    return result.clarifying_question or ""
