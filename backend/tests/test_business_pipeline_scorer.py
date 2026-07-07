"""Unit coverage for ``app.services.business_pipeline.scorer``.

The opportunity scorer is the deterministic ranking brain of the business
pipeline: the discoverer surfaces raw opportunities (grants, customer leads,
accelerators, bounties) and ``score_opportunity`` assigns each a 0-100 priority
that the orchestrator uses to decide what the company chases first. A silent
regression here is expensive in a way no exception would flag -- it does not
crash, it just quietly mis-ranks, so the founder spends the company's attention
on a low-value lead while a closing-tomorrow grant scores below it. That makes
every threshold worth pinning.

The module is pure integer arithmetic over four independent components
(deadline proximity, dollar value on a log scale, inverse effort, and a static
type weight). No DB, no network, no async, no LLM -- ``score_opportunity``
reads four attributes off a plain ``DiscoveredOpportunity`` dataclass and adds
four lookups. The only time dependency is ``datetime.now(UTC)`` inside
``_deadline_proximity``; the tests below feed deadlines computed *relative* to
the current instant (never a hard-coded calendar date) and stay safely
mid-bucket, so they are robust to the microseconds of clock drift between the
test building a deadline and the scorer reading the clock.

Every expected value here was pinned against the live function, not derived by
re-implementing its formula, so a change to the scoring curve fails these
tests instead of shipping a quietly re-weighted pipeline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, UTC

import pytest

from app.services.business_pipeline.discoverer import DiscoveredOpportunity
from app.services.business_pipeline.scorer import (
    _deadline_proximity,
    _effort_inverse,
    _type_weight,
    _value_score,
    score_components,
    score_opportunity,
)


def _op(**overrides) -> DiscoveredOpportunity:
    """A valid DiscoveredOpportunity with the three required fields filled.

    Only ``type``/``deadline_at``/``estimated_value_usd``/``effort_hours``
    affect the score; ``title``/``source_name`` are required by the dataclass
    but irrelevant to ranking, so they get fixed throwaway values.
    """
    base = dict(type="customer_lead", title="t", source_name="src")
    base.update(overrides)
    return DiscoveredOpportunity(**base)


def _in_days(days: float) -> datetime:
    """An aware UTC deadline ``days`` from now (negative => already past)."""
    return datetime.now(UTC) + timedelta(days=days)


# ---------------------------------------------------------------------------
# _deadline_proximity -- the closing-soon urgency curve (0..25)
# ---------------------------------------------------------------------------
# Offsets are chosen mid-bucket so each consecutive pair straddles exactly one
# threshold (0.5<1, 2 in (1,3], 5 in (3,7], ...). Together they pin every
# bucket boundary without depending on sub-second clock alignment.

@pytest.mark.parametrize(
    "days,expected",
    [
        (-5, 0),    # already past due -> dead last
        (0.5, 25),  # <= 1 day  -> max urgency
        (2, 22),    # (1, 3]
        (5, 18),    # (3, 7]
        (10, 13),   # (7, 14]
        (20, 9),    # (14, 30]
        (60, 5),    # (30, 90]
        (120, 2),   # > 90 days -> barely urgent
    ],
)
def test_deadline_proximity_buckets(days, expected):
    assert _deadline_proximity(_in_days(days)) == expected


def test_deadline_proximity_none_is_mid_value():
    # No deadline is not treated as "urgent" nor "ignored" -- it sits at 5,
    # the same as a 30-90 day horizon.
    assert _deadline_proximity(None) == 5


def test_deadline_proximity_accepts_naive_datetime():
    # A naive deadline is coerced to UTC rather than raising on the
    # aware/naive subtraction. 60 days of margin makes this robust to any
    # local/UTC offset on the host running the test.
    naive = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=60)
    assert _deadline_proximity(naive) == 5


# ---------------------------------------------------------------------------
# _value_score -- log10 dollar value, raw (log_v - 2) * 6 clamped to 0..25
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        (1, 0),            # log10(1)=0 -> raw -12 -> clamped up to 0
        (100, 0),          # log10(100)=2 -> raw 0
        (1_000, 6),        # an order of magnitude above the $100 floor
        (10_000, 12),
        (50_000, 16),
        (100_000, 18),
        (500_000, 22),
        (1_000_000, 24),
        (10_000_000, 25),  # past the curve -> clamped down to the 25 ceiling
    ],
)
def test_value_score_log_curve(value, expected):
    assert _value_score(value) == expected


@pytest.mark.parametrize("value", [None, 0, -100])
def test_value_score_missing_or_nonpositive_is_baseline(value):
    # Unknown or absurd dollar values fall back to a neutral 5 rather than
    # scoring 0 (which would bury every value-less opportunity).
    assert _value_score(value) == 5


def test_value_score_is_monotonic_non_decreasing():
    # A bigger opportunity never scores lower than a smaller one across the
    # curve -- the core ranking invariant for the value component.
    ladder = [1_000, 10_000, 100_000, 1_000_000, 10_000_000]
    scores = [_value_score(v) for v in ladder]
    assert scores == sorted(scores)


# ---------------------------------------------------------------------------
# _effort_inverse -- cheaper-to-pursue scores higher (0..25)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "hours,expected",
    [
        (1, 25),   # <= 1h  -> trivial, max reward
        (2, 22),   # (1, 4]
        (4, 22),   # boundary stays in the (1, 4] bucket
        (5, 18),   # (4, 8]
        (8, 18),
        (9, 13),   # (8, 24]
        (24, 13),
        (25, 8),   # (24, 80]
        (80, 8),
        (81, 3),   # > 80h -> expensive, near-floor
        (200, 3),
    ],
)
def test_effort_inverse_buckets(hours, expected):
    assert _effort_inverse(hours) == expected


@pytest.mark.parametrize("hours", [None, 0, -5])
def test_effort_inverse_missing_or_nonpositive_is_baseline(hours):
    # Unknown effort gets a neutral 10, not the trivial-effort max of 25.
    assert _effort_inverse(hours) == 10


# ---------------------------------------------------------------------------
# _type_weight -- static per-type priority, unknown -> 10
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "opportunity_type,expected",
    [
        ("grant", 25),
        ("customer_lead", 22),
        ("accelerator", 20),
        ("partnership", 18),
        ("freelance_project", 18),
        ("bug_bounty_program", 15),
        ("hackathon", 12),
        ("content_opportunity", 8),
    ],
)
def test_type_weight_known_types(opportunity_type, expected):
    # Config-drift tripwire: re-weighting a business priority should fail a
    # test, not silently re-order the whole pipeline.
    assert _type_weight(opportunity_type) == expected


@pytest.mark.parametrize("unknown", ["unknown_xyz", "", "GRANT"])
def test_type_weight_unknown_type_defaults(unknown):
    # Unrecognized (or wrong-case) types get the neutral 10 rather than 0,
    # and the lookup is case-sensitive ("GRANT" is not "grant").
    assert _type_weight(unknown) == 10


# ---------------------------------------------------------------------------
# score_opportunity / score_components -- the composed 0..100 total
# ---------------------------------------------------------------------------

def test_score_components_keys_and_values():
    op = _op(
        type="grant",
        deadline_at=_in_days(2),       # 22
        estimated_value_usd=1_000_000,  # 24
        effort_hours=1,                 # 25
    )
    assert score_components(op) == {
        "deadline_proximity": 22,
        "value_score": 24,
        "effort_inverse": 25,
        "type_weight": 25,
    }


def test_score_opportunity_equals_sum_of_components():
    # The headline score is exactly the sum of its parts -- no hidden
    # re-weighting between score_components and score_opportunity.
    op = _op(
        type="accelerator",
        deadline_at=_in_days(10),
        estimated_value_usd=50_000,
        effort_hours=9,
    )
    assert score_opportunity(op) == sum(score_components(op).values())


def test_score_opportunity_hits_the_natural_ceiling():
    # Best-case opportunity: grant (25) + closing tomorrow (25) + huge value
    # (25) + trivial effort (25) = the natural 100 ceiling.
    op = _op(
        type="grant",
        deadline_at=_in_days(0.5),
        estimated_value_usd=10_000_000,
        effort_hours=1,
    )
    assert score_opportunity(op) == 100


def test_score_opportunity_with_no_signals_is_a_low_baseline():
    # An unknown-type, deadline-less, value-less, effort-less opportunity
    # still scores its component baselines (10 type + 5 deadline + 5 value +
    # 10 effort = 30), never a negative or out-of-range number.
    op = _op(type="mystery", deadline_at=None,
             estimated_value_usd=None, effort_hours=None)
    assert score_opportunity(op) == 30


@pytest.mark.parametrize(
    "op",
    [
        _op(),
        _op(type="grant", deadline_at=_in_days(0.5),
            estimated_value_usd=10_000_000, effort_hours=1),
        _op(type="content_opportunity", deadline_at=_in_days(200),
            estimated_value_usd=1, effort_hours=500),
    ],
)
def test_score_opportunity_always_within_0_100(op):
    assert 0 <= score_opportunity(op) <= 100
