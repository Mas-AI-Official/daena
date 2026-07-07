"""Tests for stop-slop anti-AI-writing-pattern rules.

Validates phrase scanning, content scoring, stripping, and system prompt injection.
"""

import pytest

from app.config.stop_slop import (
    BANNED_PHRASES,
    MINIMUM_SCORE,
    STOP_SLOP_SYSTEM_INSTRUCTION,
    SlopMatch,
    SlopScore,
    scan_slop,
    score_content,
    strip_slop,
)


# ── scan_slop ──


class TestScanSlop:
    """Verify slop pattern detection."""

    def test_clean_text_no_matches(self):
        matches = scan_slop("The function returns a list of integers sorted by value.")
        assert len(matches) == 0

    def test_banned_phrase_detected(self):
        matches = scan_slop("Let's dive in to the architecture.")
        assert len(matches) >= 1
        assert any(m.category == "banned_phrase" for m in matches)

    def test_multiple_banned_phrases(self):
        text = "This is a game-changer. Let's dive in. It's truly groundbreaking."
        matches = scan_slop(text)
        banned = [m for m in matches if m.category == "banned_phrase"]
        assert len(banned) >= 3

    def test_case_insensitive_matching(self):
        matches = scan_slop("this is CUTTING-EDGE technology")
        assert any(m.category == "banned_phrase" for m in matches)

    def test_rhetorical_qa_detected(self):
        text = "What if I told you there's a better way? Well, here it is."
        matches = scan_slop(text)
        assert any(m.category == "rhetorical_question_then_answer" for m in matches)

    def test_binary_contrast_detected(self):
        text = "It's not just a tool, it's a platform."
        matches = scan_slop(text)
        assert any(m.category == "binary_contrast" for m in matches)

    def test_throat_clearing_detected(self):
        text = "Here's the thing about microservices."
        matches = scan_slop(text)
        assert any(m.category == "throat_clearing_opener" for m in matches)

    def test_false_buildup_detected(self):
        text = "The results might surprise you."
        matches = scan_slop(text)
        assert any(m.category == "false_buildup" for m in matches)

    def test_dramatic_fragmentation_detected(self):
        # Three consecutive single-word sentences trip _DRAMATIC_FRAGMENT.
        # Every other structural pattern has a detection test; this one was
        # the lone gap. RED if _DRAMATIC_FRAGMENT is pruned from scan_slop.
        text = "Fast. Simple. Reliable."
        matches = scan_slop(text)
        assert any(m.category == "dramatic_fragmentation" for m in matches)

    def test_empty_string(self):
        matches = scan_slop("")
        assert len(matches) == 0

    def test_match_has_position(self):
        matches = scan_slop("Hello. Let's dive in.")
        assert len(matches) >= 1
        assert matches[0].position > 0


# ── strip_slop ──


class TestStripSlop:
    """Verify slop phrase removal."""

    def test_removes_banned_phrase(self):
        result = strip_slop("Let's dive in to the code.")
        assert "dive in" not in result.lower()

    def test_preserves_clean_text(self):
        text = "The function returns sorted integers."
        assert strip_slop(text) == text

    def test_collapses_whitespace(self):
        result = strip_slop("This is a game-changer in the industry.")
        assert "  " not in result

    def test_handles_multiple_removals(self):
        text = "Let's dive in. This is groundbreaking. It's truly innovative."
        result = strip_slop(text)
        assert "dive in" not in result.lower()
        assert "groundbreaking" not in result.lower()

    def test_collapses_blank_lines(self):
        # The \n{3,} -> \n\n branch (distinct from the double-space collapse).
        # Stripping must not leave 3+ consecutive newlines. RED if removed.
        result = strip_slop("Alpha line.\n\n\n\nBeta line.")
        assert "\n\n\n" not in result
        assert result == "Alpha line.\n\nBeta line."

    def test_empty_string(self):
        assert strip_slop("") == ""


# ── score_content ──


class TestScoreContent:
    """Verify content quality scoring."""

    def test_clean_content_scores_high(self):
        text = (
            "The API processes requests in three stages. "
            "First, it validates the input against a JSON schema. "
            "Then it routes to the appropriate handler. "
            "The handler queries the database and returns results. "
            "Error responses use standard HTTP status codes."
        )
        score = score_content(text)
        assert score.total >= 30
        assert score.directness >= 5

    def test_sloppy_content_scores_lower(self):
        text = (
            "Let's dive in to this groundbreaking paradigm shift. "
            "It's not just innovative, it's transformative. "
            "Here's the thing: this game-changer will revolutionize "
            "how you think about cutting-edge technology. "
            "The results might surprise you."
        )
        score = score_content(text)
        clean_text = (
            "The API processes requests in three stages. "
            "First, it validates the input. "
            "Then it routes to the handler. "
            "Results come back as JSON."
        )
        clean_score = score_content(clean_text)
        assert score.total < clean_score.total

    def test_score_dimensions_bounded(self):
        score = score_content("Hello world.")
        assert 1 <= score.directness <= 10
        assert 1 <= score.rhythm <= 10
        assert 1 <= score.trust <= 10
        assert 1 <= score.authenticity <= 10
        assert 1 <= score.density <= 10

    def test_score_to_dict(self):
        score = score_content("Test content.")
        d = score.to_dict()
        assert "directness" in d
        assert "total" in d
        assert "passes" in d
        assert isinstance(d["total"], int)
        assert isinstance(d["passes"], bool)

    def test_empty_content(self):
        score = score_content("")
        assert score.total >= 5  # empty gets neutral scores

    def test_passes_threshold(self):
        score = SlopScore(directness=8, rhythm=7, trust=8, authenticity=7, density=7)
        assert score.total == 37
        assert score.passes is True

    def test_fails_threshold(self):
        score = SlopScore(directness=3, rhythm=3, trust=3, authenticity=3, density=3)
        assert score.total == 15
        assert score.passes is False


# ── System instruction ──


class TestSystemInstruction:
    """Verify the system prompt injection string."""

    def test_instruction_is_string(self):
        assert isinstance(STOP_SLOP_SYSTEM_INSTRUCTION, str)

    def test_instruction_not_empty(self):
        assert len(STOP_SLOP_SYSTEM_INSTRUCTION) > 50

    def test_instruction_mentions_key_rules(self):
        assert "filler" in STOP_SLOP_SYSTEM_INSTRUCTION.lower()
        assert "direct" in STOP_SLOP_SYSTEM_INSTRUCTION.lower()
        assert "em dash" in STOP_SLOP_SYSTEM_INSTRUCTION.lower()

    def test_banned_phrases_list_not_empty(self):
        assert len(BANNED_PHRASES) > 20

    def test_minimum_score_value(self):
        assert MINIMUM_SCORE == 35
