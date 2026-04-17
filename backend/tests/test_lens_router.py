"""Tests for the Stage 6.7 Cognitive Lens router.

The router's job is to pick zero-to-three chat-appropriate lenses based on
query properties and fire them in parallel with a strict latency budget.
These tests pin the selection rules and the output shape; the individual
lens modules have their own tests.
"""

from __future__ import annotations

import pytest

from app.services.cognition.lens_router import (
    LensResult,
    apply_lenses,
    format_cognitive_notes,
    select_lenses,
)


# ── Selection rules ───────────────────────────────────────────────────

def test_simple_chat_fires_no_lenses() -> None:
    """Conversational turns must skip the router entirely."""
    assert select_lenses("hi there", "SIMPLE", "SIMPLE", "NONE") == []
    assert select_lenses("thanks", "CONVERSATIONAL", "SIMPLE", "NONE") == []


def test_complex_question_fires_first_principles_and_inversion() -> None:
    lenses = select_lenses(
        query="How should I architect multi-tenant billing with usage-based pricing?",
        intent="ANALYSIS",
        complexity="COMPLEX",
        risk="MEDIUM",
    )
    assert "first_principles" in lenses
    assert "inversion" in lenses


def test_high_risk_triggers_lenses_even_when_simple() -> None:
    lenses = select_lenses(
        query="Quick question about production data",
        intent="SEARCH",
        complexity="SIMPLE",
        risk="HIGH",
    )
    assert "first_principles" in lenses
    assert "inversion" in lenses


def test_dangerous_intent_adds_consequence_chain() -> None:
    lenses = select_lenses(
        query="wipe the staging database",
        intent="DANGEROUS",
        complexity="SIMPLE",
        risk="CRITICAL",
    )
    assert "consequence_chain" in lenses
    # risk=CRITICAL also brings in first_principles + inversion.
    assert "first_principles" in lenses


def test_action_keyword_triggers_consequence_chain() -> None:
    """Action verbs in the prompt alone are enough, independent of intent."""
    lenses = select_lenses(
        query="deploy the latest image to cloud run",
        intent="TOOL_USE",
        complexity="MEDIUM",
        risk="MEDIUM",
    )
    assert "consequence_chain" in lenses


def test_ambiguous_adds_first_principles_only_once() -> None:
    lenses = select_lenses(
        query="help me figure this out",
        intent="AMBIGUOUS",
        complexity="MEDIUM",
        risk="MEDIUM",
    )
    # No duplicate first_principles even if already added elsewhere.
    assert lenses.count("first_principles") == 1


def test_cap_at_three_lenses() -> None:
    """Router never fires more than 3 lenses per turn (prompt-lean invariant)."""
    lenses = select_lenses(
        query="deploy, migrate, and delete staging now",
        intent="DANGEROUS",
        complexity="VERY_COMPLEX",
        risk="CRITICAL",
    )
    assert len(lenses) <= 3


# ── Fragment formatting ──────────────────────────────────────────────

def test_format_cognitive_notes_empty_is_empty_string() -> None:
    """Empty lens list must produce an empty string (guard-free callers)."""
    assert format_cognitive_notes([]) == ""


def test_format_cognitive_notes_includes_header_and_body() -> None:
    results = [
        LensResult(
            name="first_principles",
            fragment="First-principles lens:\n  - Assumptions: X",
            duration_ms=12,
        ),
    ]
    out = format_cognitive_notes(results)
    assert "Cognitive Notes" in out
    assert "First-principles lens:" in out
    # Treat-as-hints framing so the LLM doesn't blindly follow bad lenses.
    assert "hints" in out.lower()


# ── End-to-end: lenses fire and produce non-empty fragments ──────────

@pytest.mark.asyncio
async def test_apply_lenses_on_complex_query_returns_fragments() -> None:
    results = await apply_lenses(
        query="How do I migrate the primary database to a new region with zero downtime?",
        intent="ANALYSIS",
        complexity="COMPLEX",
        risk="HIGH",
    )
    # At least one lens should produce output for this complex/high-risk query.
    assert len(results) >= 1
    names = {r.name for r in results}
    assert names.issubset({"first_principles", "inversion", "consequence_chain"})
    # Duration budget: each individual lens < 250ms (the router timeout).
    for r in results:
        assert r.duration_ms < 250


@pytest.mark.asyncio
async def test_apply_lenses_on_simple_chat_is_noop() -> None:
    results = await apply_lenses(
        query="hello",
        intent="CONVERSATIONAL",
        complexity="SIMPLE",
        risk="NONE",
    )
    assert results == []
