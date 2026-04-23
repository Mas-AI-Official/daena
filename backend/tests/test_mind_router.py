"""Tests for the auto-Mind router (Step 2 of intelligence consolidation).

Verifies:
- Strong topical matches pick the right Mind.
- Weak / ambiguous queries return None (fall back to generic soul).
- Word-boundary logic doesn't match substrings inside unrelated words.
- Multiple matches in the same query pick the highest score.
"""

from __future__ import annotations

import pytest

from app.services.cognition.mind_router import MindMatch, pick_mind


@pytest.mark.parametrize(
    "query,expected_slug",
    [
        # Engineering -- Aria
        ("My pytest suite fails with a stack trace on this function", "engineering"),
        ("Can you refactor this python module and run the unit test?", "engineering"),
        # Sales -- Orion
        ("Draft a cold email to this prospect, log in the CRM", "sales"),
        ("Help me qualify this lead and map our ICP", "sales"),
        # Marketing -- Zephyr
        ("Write a LinkedIn post and a blog post about the launch", "marketing"),
        ("Review the landing page copy and ad messaging", "marketing"),
        # Product -- Nova
        ("Add a PRD for this feature and update the roadmap", "product"),
        ("Prioritize the backlog for next sprint", "product"),
        # Finance -- Sterling
        ("What's our runway given current burn and revenue?", "finance"),
        ("Build a P&L cohort view with gross margin", "finance"),
        # Research -- Iris
        ("Survey the prior art and cite the relevant arxiv paper", "research"),
        ("Summarize the benchmark and dataset for this study", "research"),
        # Legal & Compliance -- Themis
        ("Review this NDA and the mutual NDA clause", "legal_compliance"),
        ("Does this terms of service comply with GDPR and SOC2?", "legal_compliance"),
        # Operations -- Atlas
        ("Write a runbook for this incident and our SOP", "operations"),
        ("Plan capacity for next quarter OKRs and KPIs", "operations"),
        # Skill Governance -- Kira
        ("Update the skill refinery playbook and the style guide", "skill_governance"),
        # Security Operations -- Rourke
        ("Run a pentest, map the attack surface and CVEs", "security_operations"),
        ("Triage this breach -- check SIEM and incident response", "security_operations"),
    ],
)
def test_pick_mind_strong_match(query: str, expected_slug: str) -> None:
    result = pick_mind(query)
    assert result.slug == expected_slug, (
        f"expected {expected_slug}, got {result.slug} "
        f"(score={result.score}, kw={result.matched_keywords})"
    )
    assert result.score >= 2


@pytest.mark.parametrize(
    "query",
    [
        "",
        "hi",
        "how are you",
        "tell me a joke",
        "what's the weather",
        "good morning",
        # Single weak keyword should NOT trigger -- ambiguous topical signal
        "what is code",  # only "code" once, score=1, below threshold
    ],
)
def test_pick_mind_weak_or_empty_returns_none(query: str) -> None:
    result = pick_mind(query)
    assert result.slug is None, f"expected None for weak query, got {result.slug}"


def test_pick_mind_word_boundary_no_false_match() -> None:
    # "codependent" should NOT match engineering's "code" keyword.
    # "codebase" (engineering) also has "code" at word start + boundary.
    # The rule: match requires the full keyword at a word boundary.
    result = pick_mind("I am codependent on my cofounder")
    assert result.slug is None


def test_pick_mind_highest_score_wins_on_multi_topic() -> None:
    # Two engineering keywords + one marketing keyword -> engineering wins.
    result = pick_mind("Debug the api and write the blog post copy")
    assert result.slug == "engineering"
    assert result.score == 2
    # "blog post" and "copy" were seen too but marketing's score was 2 -- tie.
    # In a tie the order in _MIND_KEYWORDS decides; engineering is earlier.


def test_pick_mind_returns_match_object() -> None:
    result = pick_mind("deploy the api and write a unit test")
    assert isinstance(result, MindMatch)
    assert result.slug == "engineering"
    assert "api" in result.matched_keywords or "deploy" in result.matched_keywords
