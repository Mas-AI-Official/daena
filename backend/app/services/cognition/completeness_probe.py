"""Completeness Probe -- post-stream "shallow but successful" detector.

Step 4 of the Council R2 plan (2026-04-25).

The founder's argument (correct): when an LLM returns a SUCCESSFUL but
INCOMPLETE response, no failure flag fires, so failure-only diagnosis
never triggers. The shallow output ships. Mythos thinks from the
beginning AND verifies coverage at the end.

This module runs a cheap small-model eval (~$0.001-0.015) AFTER the
main stream completes, asking *"does the response cover all evidence
dimensions a senior reviewer would expect?"* If 2+ angles missed AND
confidence > 0.65 AND the gate conditions hold, the orchestrator can
re-stream with the missing frameworks added.

GPT-5.5 R2 mandatory guardrails (do NOT remove):

  1. **Max 1 rerun per turn.** The orchestrator tracks a
     ``_completeness_rerun_count`` flag; this module only runs the
     probe; gating + counter live at the call site (Stage 9.5).
  2. **Probe never probes its own rerun.** Stage 9.5 must not invoke
     this module again on the rerun output. Surface
     "possible missing angles" as a FOOTER if still judged incomplete.
  3. **Bounded additions only.** The rerun prompt extends with the
     specific missing dimensions returned here -- not "try harder" /
     "be more thorough" generic phrasing.
  4. **No meta-probe.** This is a quality gate, not a new reasoning
     sovereign. Recursion = trap.
  5. **Tier-3 + high-stakes only.** Gate at the call site; this module
     is task-agnostic.

Cost envelope (per probe):
  - Haiku / Mistral 7B: ~$0.001
  - Sonnet 4.6: ~$0.015 (only on architecture-lock / legal / governance)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# Per-intent "evidence dimensions a senior reviewer would expect."
# Picked deliberately tight (3-5 per intent) so the probe is bounded
# and doesn't hallucinate "missing angle inflation" -- a specific
# failure mode flagged by GPT-5.5 R2 (small judge models invent
# reasonable-sounding extra dimensions because their job is to critique).
EXPECTED_DIMENSIONS: dict[str, list[str]] = {
    "CODING": [
        "explicit edge cases",
        "error handling",
        "minimal viable test sketch",
    ],
    "ANALYSIS": [
        "data sources / assumptions",
        "counterargument or alternative explanation",
        "confidence + uncertainty notes",
    ],
    "MULTI_STEP": [
        "ordered steps with dependencies",
        "explicit failure-recovery branch",
        "verification check after each milestone",
    ],
    "DANGEROUS": [
        "explicit risk callout",
        "irreversibility check",
        "approval / abort path",
    ],
    "SEARCH": [
        "primary source citation",
        "freshness / date stamp on key claims",
        "single contradicting source if one exists",
    ],
    "CREATIVE": [
        "concrete grounding example",
        "constraint compliance check",
    ],
    "AMBIGUOUS": [
        "explicit clarifying question or assumption note",
    ],
    "SIMPLE": [],  # never probed; sentinel only
}


# Confidence threshold for triggering a rerun. Below this, the probe's
# verdict is treated as "low signal, ship the answer." Tuned conservative
# (0.65) so weak probes don't trigger spurious reruns.
RERUN_CONFIDENCE_THRESHOLD = 0.65

# Minimum missing dimensions to trigger a rerun. 1 missing isn't enough
# (probe might just be picky); 2+ is the signal of a genuinely shallow
# response.
MIN_MISSING_FOR_RERUN = 2


@dataclass(frozen=True, slots=True)
class CompletenessResult:
    """Output of one probe call.

    Attributes:
        complete: True if the response covers expected dimensions.
        missing_dimensions: Specific dimensions the response did NOT cover.
            Bounded to the expected list per intent; NEVER unbounded text.
        confidence: 0.0-1.0 self-rated confidence in the verdict.
        reasoning: One-line probe rationale for audit.
        should_rerun: Computed gate: complete=False AND
            len(missing) >= MIN_MISSING_FOR_RERUN AND
            confidence >= RERUN_CONFIDENCE_THRESHOLD.
        probe_tokens_used: Tokens consumed by the probe (audit).
        probe_cost_usd: Probe cost in USD (audit).
    """

    complete: bool
    missing_dimensions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    should_rerun: bool = False
    probe_tokens_used: int = 0
    probe_cost_usd: float = 0.0
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "missing_dimensions": self.missing_dimensions,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "should_rerun": self.should_rerun,
            "probe_tokens_used": self.probe_tokens_used,
            "probe_cost_usd": round(self.probe_cost_usd, 5),
        }


def _expected_for_intent(intent_value: str) -> list[str]:
    """Return the bounded list of expected dimensions for an intent."""
    return list(EXPECTED_DIMENSIONS.get(intent_value.upper(), []))


def build_probe_prompt(
    user_message: str,
    response_text: str,
    intent_value: str,
    frameworks_used: list[str] | None = None,
) -> str:
    """Construct the bounded probe prompt for a small judge model.

    The prompt is INTENTIONALLY constrained: we list the expected
    dimensions for this intent and ask the judge to mark each one
    covered/missing. This prevents "missing angle inflation" because
    the judge cannot invent new dimensions outside the given list.
    """
    expected = _expected_for_intent(intent_value)
    if not expected:
        # SIMPLE / unknown intents: caller should skip the probe entirely.
        # Returned as a sentinel; the caller checks before invoking the LLM.
        return ""

    expected_block = "\n".join(f"- {d}" for d in expected)
    frameworks_note = (
        f"\nFrameworks already applied during reasoning: {', '.join(frameworks_used or []) or 'none'}."
    )
    truncated_response = (
        response_text if len(response_text) <= 4000
        else response_text[:4000] + "\n[... truncated for probe ...]"
    )
    return (
        "You are a quality gate, not a reasoner. Your job is bounded.\n\n"
        "TASK: Decide whether the assistant's response covers each of the "
        "EXPECTED DIMENSIONS below. You MUST NOT invent additional dimensions.\n\n"
        f"USER QUERY:\n{user_message}\n\n"
        f"ASSISTANT RESPONSE:\n{truncated_response}\n\n"
        f"INTENT: {intent_value}\n"
        f"EXPECTED DIMENSIONS:\n{expected_block}\n"
        f"{frameworks_note}\n\n"
        "Output STRICTLY this JSON shape (no prose, no markdown fences):\n"
        '{"complete": true|false, '
        '"missing_dimensions": [<exact strings from EXPECTED DIMENSIONS only>], '
        '"confidence": <0.0-1.0>, '
        '"reasoning": "<one short sentence>"}'
    )


def parse_probe_output(raw: str, expected: list[str]) -> CompletenessResult:
    """Parse the judge's JSON; tolerant of extra prose/markdown.

    Defensive: if the judge wrapped output in code fences or added
    a preamble, we strip and re-attempt. If parsing fails entirely,
    we return ``complete=True`` (no rerun) -- a broken probe must
    never cause a rerun loop.
    """
    if not raw:
        return CompletenessResult(complete=True, raw_output=raw)

    text = raw.strip()
    # Strip markdown code fences if any
    fence_match = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    # Locate the JSON object span
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        logger.debug("completeness_probe.parse_no_json", raw_head=raw[:120])
        return CompletenessResult(complete=True, raw_output=raw, reasoning="probe_unparseable")

    try:
        payload = json.loads(text[start : end + 1])
    except Exception as exc:
        logger.debug("completeness_probe.parse_failed", error=str(exc), raw_head=raw[:120])
        return CompletenessResult(complete=True, raw_output=raw, reasoning="probe_unparseable")

    complete = bool(payload.get("complete", True))
    confidence = float(payload.get("confidence", 0.0) or 0.0)
    reasoning = str(payload.get("reasoning", "") or "")[:280]

    # Bound missing_dimensions to the expected set -- defends against the
    # "missing angle inflation" GPT-5.5 R2 flagged.
    raw_missing = payload.get("missing_dimensions") or []
    if not isinstance(raw_missing, list):
        raw_missing = []
    expected_lower = {d.lower(): d for d in expected}
    missing: list[str] = []
    for item in raw_missing:
        key = str(item).strip().lower()
        canonical = expected_lower.get(key)
        if canonical and canonical not in missing:
            missing.append(canonical)

    should_rerun = (
        not complete
        and len(missing) >= MIN_MISSING_FOR_RERUN
        and confidence >= RERUN_CONFIDENCE_THRESHOLD
    )
    return CompletenessResult(
        complete=complete,
        missing_dimensions=missing,
        confidence=confidence,
        reasoning=reasoning,
        should_rerun=should_rerun,
        raw_output=raw,
    )


def render_footer_for_incomplete(missing: list[str]) -> str:
    """Render an unobtrusive 'possible missing angles' footer.

    Used when (a) the gate decides to skip the rerun, OR (b) the rerun
    fired and the second answer was STILL judged incomplete (R2 rule:
    no third pass; surface as footer instead). Plain text; no
    Markdown fences so it composes cleanly into SSE chunks.
    """
    if not missing:
        return ""
    bullets = "\n".join(f"  - {d}" for d in missing)
    return (
        "\n\n---\n"
        "Possible missing angles a reviewer might still want covered:\n"
        f"{bullets}"
    )


def build_rerun_extension(missing: list[str]) -> str:
    """Build a BOUNDED extension to the system_prompt for the rerun.

    R2 rule: NOT a generic "try harder" -- only the specific dimensions
    the probe identified as missing. This keeps the rerun on-task and
    prevents recursive over-answering.
    """
    if not missing:
        return ""
    bullets = "\n".join(f"- {d}" for d in missing)
    return (
        "\n\n## Completeness pass\n"
        "Your previous answer covered the core but missed these dimensions. "
        "Address each one EXPLICITLY in this revised response. Do not "
        "broaden scope beyond these items:\n"
        f"{bullets}"
    )
