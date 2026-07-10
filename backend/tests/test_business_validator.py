"""Phase 4 (Venture Studio) -- deterministic startup-idea validator contract.

Pins:
  1. Fully-specified opportunity scores 100 -> verdict "go".
  2. Empty opportunity scores near-zero -> verdict "no_go".
  3. Validation is deterministic: same input -> same score, NO LLM.
  4. Check weights sum to exactly 100.
  5. Verdict bands: >=70 go, <40 no_go, otherwise review.
  6. window_open honours an injected `now` (future open, past closed, none open).
  7. has_persisted_validation is the governance floor the bridge consumes:
     True iff a numeric score sits under raw_metadata["validation"].
  8. Booleans are never counted as ints (market_sized / effort_scoped / score).
  9. Module surface imports no LLM / network client.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.business_pipeline.discoverer import DiscoveredOpportunity
from app.services.business_pipeline.validator import (
    GO_THRESHOLD,
    REVIEW_FLOOR,
    VALIDATION_METADATA_KEY,
    VALIDATION_VERSION,
    VERDICT_GO,
    VERDICT_NO_GO,
    VERDICT_REVIEW,
    has_persisted_validation,
    validate_opportunity,
)


# Fixed reference instant so window_open tests never depend on wall clock.
_NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=UTC)


def _opp(**overrides) -> DiscoveredOpportunity:
    """A fully-specified startup_idea; override fields to weaken it."""
    base = dict(
        type="startup_idea",
        title="Governed agent audit trails for regulated SMBs",
        source_name="manual_seed",
        description=(
            "SMBs in regulated industries cannot adopt AI agents because they "
            "lack an auditable approval trail. Daena already produces one."
        ),
        source_url="https://news.ycombinator.com/item?id=1",
        deadline_at=None,
        estimated_value_usd=250_000,
        effort_hours=40,
        risk_label="medium",
        next_action="Interview 5 compliance leads to size willingness to pay.",
        raw_metadata={},
    )
    base.update(overrides)
    return DiscoveredOpportunity(**base)


class TestValidateOpportunity:
    def test_fully_specified_scores_100_and_go(self):
        result = validate_opportunity(_opp(), now=_NOW)
        assert result.score == 100
        assert result.verdict == VERDICT_GO
        assert all(c.passed for c in result.checks)

    def test_empty_opportunity_scores_low_and_no_go(self):
        # Only window_open passes (no deadline), everything else absent.
        bare = _opp(
            description="",
            source_url="",
            estimated_value_usd=None,
            effort_hours=None,
            risk_label="",
            next_action="",
        )
        result = validate_opportunity(bare, now=_NOW)
        assert result.score == 5  # window_open weight only
        assert result.verdict == VERDICT_NO_GO

    def test_deterministic_same_input_same_score(self):
        op = _opp()
        first = validate_opportunity(op, now=_NOW)
        second = validate_opportunity(op, now=_NOW)
        assert first.score == second.score
        assert first.verdict == second.verdict

    def test_check_weights_sum_to_100(self):
        result = validate_opportunity(_opp(), now=_NOW)
        assert sum(c.weight for c in result.checks) == 100

    def test_check_keys_are_the_seven_locked_checks(self):
        result = validate_opportunity(_opp(), now=_NOW)
        assert [c.key for c in result.checks] == [
            "problem_described",
            "market_sized",
            "evidence_linked",
            "effort_scoped",
            "next_action_defined",
            "risk_assessed",
            "window_open",
        ]

    def test_review_band(self):
        # 20 (problem) + 20 (market) + 5 (window) = 45 -> review.
        op = _opp(
            source_url="",
            effort_hours=None,
            risk_label="",
            next_action="",
        )
        result = validate_opportunity(op, now=_NOW)
        assert REVIEW_FLOOR <= result.score < GO_THRESHOLD
        assert result.verdict == VERDICT_REVIEW

    def test_short_description_fails_problem_check(self):
        op = _opp(description="too short")
        result = validate_opportunity(op, now=_NOW)
        problem = next(c for c in result.checks if c.key == "problem_described")
        assert problem.passed is False

    def test_future_deadline_keeps_window_open(self):
        op = _opp(deadline_at=_NOW + timedelta(days=3))
        result = validate_opportunity(op, now=_NOW)
        window = next(c for c in result.checks if c.key == "window_open")
        assert window.passed is True

    def test_past_deadline_closes_window(self):
        op = _opp(deadline_at=_NOW - timedelta(days=1))
        result = validate_opportunity(op, now=_NOW)
        window = next(c for c in result.checks if c.key == "window_open")
        assert window.passed is False
        assert result.score == 95  # everything but window_open (weight 5)

    def test_naive_deadline_treated_as_utc(self):
        # A naive datetime (SQLite round-trip) must not raise on comparison.
        op = _opp(deadline_at=(_NOW + timedelta(days=1)).replace(tzinfo=None))
        result = validate_opportunity(op, now=_NOW)
        window = next(c for c in result.checks if c.key == "window_open")
        assert window.passed is True

    def test_bool_value_not_counted_as_market_size(self):
        # bool is a subclass of int; True must NOT satisfy market_sized.
        op = _opp(estimated_value_usd=True)
        result = validate_opportunity(op, now=_NOW)
        market = next(c for c in result.checks if c.key == "market_sized")
        assert market.passed is False

    def test_zero_value_and_zero_effort_fail(self):
        op = _opp(estimated_value_usd=0, effort_hours=0)
        result = validate_opportunity(op, now=_NOW)
        market = next(c for c in result.checks if c.key == "market_sized")
        effort = next(c for c in result.checks if c.key == "effort_scoped")
        assert market.passed is False
        assert effort.passed is False


class TestToMetadata:
    def test_metadata_shape(self):
        result = validate_opportunity(_opp(), now=_NOW)
        meta = result.to_metadata()
        assert meta["score"] == 100
        assert meta["verdict"] == VERDICT_GO
        assert meta["version"] == VALIDATION_VERSION
        assert len(meta["checks"]) == 7
        assert "validated_at" not in meta  # pure by default

    def test_metadata_stamps_validated_at_when_given(self):
        result = validate_opportunity(_opp(), now=_NOW)
        meta = result.to_metadata(validated_at=_NOW.isoformat())
        assert meta["validated_at"] == _NOW.isoformat()


class TestHasPersistedValidation:
    def test_none_is_false(self):
        assert has_persisted_validation(None) is False

    def test_non_dict_is_false(self):
        assert has_persisted_validation("nope") is False  # type: ignore[arg-type]

    def test_missing_key_is_false(self):
        assert has_persisted_validation({"other": 1}) is False

    def test_validation_without_score_is_false(self):
        assert has_persisted_validation({VALIDATION_METADATA_KEY: {"verdict": "go"}}) is False

    def test_validation_with_non_int_score_is_false(self):
        assert has_persisted_validation({VALIDATION_METADATA_KEY: {"score": "80"}}) is False

    def test_bool_score_is_false(self):
        assert has_persisted_validation({VALIDATION_METADATA_KEY: {"score": True}}) is False

    def test_validation_with_int_score_is_true(self):
        assert has_persisted_validation({VALIDATION_METADATA_KEY: {"score": 0}}) is True

    def test_roundtrip_from_validate(self):
        result = validate_opportunity(_opp(), now=_NOW)
        raw_metadata = {VALIDATION_METADATA_KEY: result.to_metadata()}
        assert has_persisted_validation(raw_metadata) is True


class TestNoLLMImport:
    def test_no_llm_or_network_import_in_validator(self):
        # Match import statements, not prose -- the docstring legitimately
        # says "NOT an LLM judgment", so a bare "llm" substring would false-fire.
        from app.services.business_pipeline import validator

        src = open(validator.__file__, encoding="utf-8").read().lower()
        for forbidden in (
            "import openai",
            "import anthropic",
            "from anthropic",
            "import httpx",
            "import requests",
            "import aiohttp",
            "import litellm",
            "import vllm",
        ):
            assert forbidden not in src, f"validator must not import {forbidden!r}"
