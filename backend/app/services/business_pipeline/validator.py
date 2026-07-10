"""Deterministic startup-idea validation checklist -- Phase 4 (Venture Studio).

A Polsia-style idea-to-business pipeline needs a GATE between "an idea was
discovered" and "a department spends real effort on it". In Daena that gate is
a DETERMINISTIC, pure-Python validation checklist -- deliberately NOT an LLM
judgment.

Why deterministic and not an LLM:
  * Reproducible: the same opportunity yields the same score on every run, so
    the score can back a CI invariant (see workstream_bridge promotion guard).
    An LLM would drift and could not be trusted as a governance floor.
  * Auditable: every point is tied to a named, inspectable check the operator
    can see and contest. No black box between discovery and spend.
  * Cheap + local: zero tokens, zero network, zero DB. Fits the routine
    autonomy loop without tripping a spend gate.

What the checklist measures: STRUCTURED completeness + freshness of an
opportunity -- "is this idea worked-out enough to promote?" -- NOT "is this a
good idea?". Whether the idea is worth pursuing is the human's GO / NO-GO call
(master.md human gate 1); this module only enforces that the minimum an owner
needs (a described problem, a sized market, linked evidence, a scoped effort, a
defined next action, an assessed risk, an open window) is actually present.

The verdict here is ADVISORY. The promotion guard requires only that a score
was persisted, never that the verdict was "go" -- the human keeps the judgment.

NO LLM. NO network. NO DB. Pure function of the opportunity's own fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

# Key under Opportunity.raw_metadata where the validation payload is persisted.
VALIDATION_METADATA_KEY = "validation"

# Bump when the checklist / scoring changes so persisted rows are traceable to
# the scoring version that produced them.
VALIDATION_VERSION = 1

# Verdict bands over the 0..100 score. Lowercase to match the opportunity
# status idiom ("discovered", "queued", ...). These are ADVISORY inputs to the
# human GO / NO-GO gate, not hard code-level blocks.
GO_THRESHOLD = 70   # score >= 70 -> recommend GO
REVIEW_FLOOR = 40   # score <  40 -> recommend NO-GO; between -> REVIEW

VERDICT_GO = "go"
VERDICT_REVIEW = "review"
VERDICT_NO_GO = "no_go"


@dataclass(frozen=True)
class ValidationCheck:
    """One inspectable checklist item. ``weight`` is the points it contributes
    to the 0..100 score when ``passed`` is True."""

    key: str
    label: str
    passed: bool
    weight: int
    detail: str


@dataclass(frozen=True)
class ValidationResult:
    score: int              # 0..100 (sum of passed-check weights)
    verdict: str            # VERDICT_GO | VERDICT_REVIEW | VERDICT_NO_GO
    checks: list[ValidationCheck] = field(default_factory=list)
    version: int = VALIDATION_VERSION

    def to_metadata(self, *, validated_at: str | None = None) -> dict:
        """Serialize for persistence under raw_metadata[VALIDATION_METADATA_KEY].

        ``validated_at`` is optional so the pure result stays reproducible for
        tests; the persistence site (routine handler / API) stamps the wall
        clock when it writes.
        """
        payload: dict = {
            "score": self.score,
            "verdict": self.verdict,
            "version": self.version,
            "checks": [
                {
                    "key": c.key,
                    "label": c.label,
                    "passed": c.passed,
                    "weight": c.weight,
                    "detail": c.detail,
                }
                for c in self.checks
            ],
        }
        if validated_at is not None:
            payload["validated_at"] = validated_at
        return payload


def _as_aware(dt: datetime) -> datetime:
    """Treat a naive datetime (e.g. from SQLite) as UTC so deadline
    comparisons never raise on tz mismatch."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _verdict_for(score: int) -> str:
    if score >= GO_THRESHOLD:
        return VERDICT_GO
    if score < REVIEW_FLOOR:
        return VERDICT_NO_GO
    return VERDICT_REVIEW


def validate_opportunity(op: object, *, now: datetime | None = None) -> ValidationResult:
    """Score an opportunity's readiness to promote.

    Works on any object exposing the DiscoveredOpportunity / Opportunity
    fields (duck-typed via getattr) so both the pre-DB dataclass and the ORM
    row can be validated with one code path. NEVER raises.
    """
    now = now or datetime.now(UTC)
    checks: list[ValidationCheck] = []

    description = (getattr(op, "description", None) or "").strip()
    checks.append(ValidationCheck(
        key="problem_described",
        label="Problem described",
        passed=len(description) >= 40,
        weight=20,
        detail=f"{len(description)} chars of description (need >= 40).",
    ))

    value = getattr(op, "estimated_value_usd", None)
    checks.append(ValidationCheck(
        key="market_sized",
        label="Market / value sized",
        passed=isinstance(value, int) and not isinstance(value, bool) and value > 0,
        weight=20,
        detail=f"estimated_value_usd={value!r}.",
    ))

    source_url = (getattr(op, "source_url", None) or "").strip()
    checks.append(ValidationCheck(
        key="evidence_linked",
        label="Evidence linked",
        passed=bool(source_url),
        weight=15,
        detail="source_url present." if source_url else "no source_url.",
    ))

    effort = getattr(op, "effort_hours", None)
    checks.append(ValidationCheck(
        key="effort_scoped",
        label="Effort scoped",
        passed=isinstance(effort, int) and not isinstance(effort, bool) and effort > 0,
        weight=15,
        detail=f"effort_hours={effort!r}.",
    ))

    next_action = (getattr(op, "next_action", None) or "").strip()
    checks.append(ValidationCheck(
        key="next_action_defined",
        label="Next action defined",
        passed=bool(next_action),
        weight=15,
        detail="next_action present." if next_action else "no next_action.",
    ))

    risk_label = (getattr(op, "risk_label", None) or "").strip()
    checks.append(ValidationCheck(
        key="risk_assessed",
        label="Risk assessed",
        passed=bool(risk_label),
        weight=10,
        detail=f"risk_label={risk_label!r}." if risk_label else "no risk_label.",
    ))

    deadline = getattr(op, "deadline_at", None)
    window_open = deadline is None or _as_aware(deadline) >= now
    checks.append(ValidationCheck(
        key="window_open",
        label="Window open",
        passed=window_open,
        weight=5,
        detail="no deadline set." if deadline is None
        else f"deadline_at={_as_aware(deadline).isoformat()}.",
    ))

    score = sum(c.weight for c in checks if c.passed)
    return ValidationResult(score=score, verdict=_verdict_for(score), checks=checks)


def has_persisted_validation(raw_metadata: dict | None) -> bool:
    """True iff a validation score has been persisted onto the opportunity.

    This is the CI-enforced governance FLOOR consumed by the workstream bridge:
    a startup_idea cannot be promoted to a workstream until validation has run
    and been recorded. Presence of a numeric score is sufficient; the verdict
    is advisory and never checked here (the human owns GO / NO-GO).
    """
    if not isinstance(raw_metadata, dict):
        return False
    validation = raw_metadata.get(VALIDATION_METADATA_KEY)
    if not isinstance(validation, dict):
        return False
    score = validation.get("score")
    return isinstance(score, int) and not isinstance(score, bool)
