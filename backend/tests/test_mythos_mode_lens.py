"""Tests for the Mythos Mode lens and its lens_router integration.

Covers: mode classification table, no-fire on trivial text, directive
payload shape, selection-rule integration (prepended on non-trivial
turns, absent on simple chat, existing lens selection unchanged), and
the runner's rendered fragment.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.cognition.lens_router import _run_mythos_mode, select_lenses
from app.services.cognition.mythos_mode import MythosMode, classify


# ── classify ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fix the auth bug in login.py", "DEBUG"),
        ("the login page is broken again", "DEBUG"),
        ("investigate why indexing crashes at 2am", "DEBUG"),
        ("should we use postgres or sqlite for the queue", "DECIDE"),
        ("compare langchain vs raw sdk", "DECIDE"),
        ("security review of the upload endpoint", "AUDIT"),
        ("audit the billing pipeline", "AUDIT"),
        ("build a stripe webhook handler", "BUILD"),
        ("design a multi-tenant billing system", "BUILD"),
        ("refactor the retriever to reuse stored vectors", "BUILD"),
    ],
)
def test_classify_modes(text: str, expected: str) -> None:
    assert classify(text) == expected


@pytest.mark.parametrize("text", ["hello there", "what time is it", "", "   "])
def test_classify_no_mode_on_trivial(text: str) -> None:
    assert classify(text) == ""


def test_audit_beats_debug_on_specificity() -> None:
    # "review ... fix" contains both; AUDIT is checked first by design.
    assert classify("review the fix for the upload endpoint") == "AUDIT"


# ── MythosMode.analyze ───────────────────────────────────────────────

def test_analyze_returns_mode_and_directive() -> None:
    result = asyncio.run(MythosMode().analyze(task="debug the flaky scheduler"))
    assert result["mode"] == "DEBUG"
    assert "Reproduce first" in result["directive"]


def test_analyze_empty_on_no_match() -> None:
    result = asyncio.run(MythosMode().analyze(task="good morning"))
    assert result == {"mode": "", "directive": ""}


# ── select_lenses integration ────────────────────────────────────────

def test_select_prepends_mythos_on_complex_turn() -> None:
    lenses = select_lenses(
        query="fix the race condition in session persistence",
        intent="CODING",
        complexity="COMPLEX",
        risk="LOW",
    )
    assert lenses[0] == "mythos_mode"
    # Existing complex-turn selection is preserved after the frame lens.
    assert "first_principles" in lenses
    assert "inversion" in lenses


def test_select_no_mythos_on_simple_chat() -> None:
    lenses = select_lenses(
        query="thanks, that worked",
        intent="SIMPLE",
        complexity="SIMPLE",
        risk="LOW",
    )
    assert "mythos_mode" not in lenses


def test_select_no_mythos_when_mode_hits_but_turn_trivial() -> None:
    # Mode keyword present but the turn is simple and no other lens fired:
    # the frame lens stays out to keep cheap turns cheap.
    lenses = select_lenses(
        query="fix a typo",
        intent="SIMPLE",
        complexity="SIMPLE",
        risk="LOW",
    )
    assert "mythos_mode" not in lenses


def test_select_existing_behavior_unchanged_without_mode_hit() -> None:
    # High complexity, no mode keyword: classic selection, no frame lens.
    lenses = select_lenses(
        query="summarize the council notes from yesterday's session",
        intent="ANALYSIS",
        complexity="COMPLEX",
        risk="LOW",
    )
    assert "mythos_mode" not in lenses
    assert lenses[0] == "first_principles"


# ── runner fragment ──────────────────────────────────────────────────

def test_runner_renders_fragment() -> None:
    fragment = asyncio.run(_run_mythos_mode("debug the SSE stream cutoff"))
    assert fragment.startswith("Mythos mode [DEBUG]")
    assert "root cause" in fragment


def test_runner_empty_on_no_match() -> None:
    assert asyncio.run(_run_mythos_mode("hello")) == ""
