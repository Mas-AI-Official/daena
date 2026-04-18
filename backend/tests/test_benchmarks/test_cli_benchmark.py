"""Tests for CLI Benchmark scoring and synthesis logic.

Tests the heuristic scoring engine, agreement matrix, and synthesis
without actually calling CLI subprocesses (those are tested via
integration tests with the real CLIs).
"""

import pytest

from app.services.benchmarks.cli_benchmark import (
    BenchmarkScore,
    CLIBenchmarkResult,
    CLIBenchmarkService,
    CLIResponse,
    _compute_agreement,
    _extract_meaningful_words,
    _score_actionability,
    _score_clarity,
    _score_depth,
    _score_relevance,
    _score_speed,
    _score_structure,
)


# ── Word extraction ──────────────────────────────────────────


class TestExtractMeaningfulWords:
    def test_filters_stopwords(self):
        words = _extract_meaningful_words("the quick brown fox is very fast")
        assert "the" not in words
        assert "is" not in words
        assert "very" not in words
        assert "quick" in words
        assert "brown" in words
        assert "fast" in words

    def test_filters_short_words(self):
        words = _extract_meaningful_words("I am ok but not good at it")
        assert "am" not in words
        assert "ok" not in words
        assert "good" in words

    def test_empty_string(self):
        assert _extract_meaningful_words("") == set()


# ── Relevance scoring ────────────────────────────────────────


class TestScoreRelevance:
    def test_high_relevance(self):
        prompt = "explain quantum computing entanglement"
        response = "quantum computing uses entanglement to achieve superposition"
        score = _score_relevance(prompt, response)
        assert score >= 7.0

    def test_low_relevance(self):
        prompt = "explain quantum computing"
        response = "the weather today is sunny and warm outside"
        score = _score_relevance(prompt, response)
        assert score < 7.0

    def test_empty_prompt(self):
        score = _score_relevance("", "some response text here")
        assert score == 5.0


# ── Depth scoring ────────────────────────────────────────────


class TestScoreDepth:
    def test_short_response_low_depth(self):
        score = _score_depth("yes it works")
        assert score < 4.0

    def test_long_response_high_depth(self):
        long_text = " ".join(["word"] * 400)
        score = _score_depth(long_text)
        assert score >= 7.0

    def test_technical_indicators_boost(self):
        text = (
            "However, the trade-off between performance and accuracy "
            "must be carefully considered. Therefore, we should analyze "
            "the constraint that limits throughput."
        )
        score = _score_depth(text)
        # Should get technical bonus even though it's short
        assert score >= 3.0


# ── Clarity scoring ──────────────────────────────────────────


class TestScoreClarity:
    def test_empty_response(self):
        score = _score_clarity("")
        assert score == 3.0

    def test_well_structured_response(self):
        text = (
            "The solution involves three main steps.\n\n"
            "First, configure the database connection properly.\n\n"
            "Second, run the migration script to update the schema.\n\n"
            "Third, verify the data integrity after migration."
        )
        score = _score_clarity(text)
        assert score >= 6.0  # Well-structured text with paragraph breaks


# ── Actionability scoring ────────────────────────────────────


class TestScoreActionability:
    def test_actionable_response(self):
        text = (
            "Step 1: Install the package with pip install requests. "
            "You should configure the API key first. "
            "Example: ```python\nimport requests\n```"
        )
        score = _score_actionability(text)
        assert score >= 5.0

    def test_passive_response(self):
        score = _score_actionability(
            "Quantum mechanics describes physical phenomena at nanoscopic scales."
        )
        assert score < 5.0


# ── Structure scoring ────────────────────────────────────────


class TestScoreStructure:
    def test_well_formatted(self):
        text = (
            "## Overview\n\n"
            "The system has these components:\n\n"
            "- Database layer\n"
            "- API endpoints\n\n"
            "```python\nclass Handler:\n    pass\n```\n\n"
            "**Important:** always validate input."
        )
        score = _score_structure(text)
        assert score >= 8.0

    def test_plain_text(self):
        score = _score_structure("just some plain text with no formatting")
        assert score == 5.0


# ── Speed scoring ────────────────────────────────────────────


class TestScoreSpeed:
    def test_fastest_gets_highest_score(self):
        latencies = [1000, 3000, 5000]
        score = _score_speed(1000, latencies)
        assert score == 10.0

    def test_slowest_gets_lowest_score(self):
        latencies = [1000, 3000, 5000]
        score = _score_speed(5000, latencies)
        assert score == 4.0

    def test_all_same_speed(self):
        latencies = [2000, 2000, 2000]
        score = _score_speed(2000, latencies)
        assert score == 8.0


# ── Agreement matrix ─────────────────────────────────────────


class TestComputeAgreement:
    def test_identical_responses(self):
        responses = [
            CLIResponse(
                runtime_id="a", display_name="A",
                content="quantum computing uses qubits for computation",
                latency_ms=100, cost_usd=0.0, model_used="m",
            ),
            CLIResponse(
                runtime_id="b", display_name="B",
                content="quantum computing uses qubits for computation",
                latency_ms=100, cost_usd=0.0, model_used="m",
            ),
        ]
        matrix = _compute_agreement(responses)
        assert matrix["a"]["b"] == 1.0
        assert matrix["b"]["a"] == 1.0

    def test_different_responses(self):
        responses = [
            CLIResponse(
                runtime_id="a", display_name="A",
                content="quantum computing uses qubits for computation",
                latency_ms=100, cost_usd=0.0, model_used="m",
            ),
            CLIResponse(
                runtime_id="b", display_name="B",
                content="cooking pasta requires boiling water and seasoning",
                latency_ms=100, cost_usd=0.0, model_used="m",
            ),
        ]
        matrix = _compute_agreement(responses)
        assert matrix["a"]["b"] < 0.3

    def test_skips_error_responses(self):
        responses = [
            CLIResponse(
                runtime_id="a", display_name="A",
                content="valid response here",
                latency_ms=100, cost_usd=0.0, model_used="m",
            ),
            CLIResponse(
                runtime_id="b", display_name="B",
                content="",
                latency_ms=100, cost_usd=0.0, model_used="m",
                error="timeout",
            ),
        ]
        matrix = _compute_agreement(responses)
        assert "b" not in matrix


# ── Synthesis ────────────────────────────────────────────────


class TestSynthesis:
    def test_synthesis_contains_winner(self):
        service = CLIBenchmarkService()
        responses = [
            CLIResponse(
                runtime_id="claude_code", display_name="Claude Code",
                content="Detailed analysis of the problem with code examples.",
                latency_ms=2000, cost_usd=0.01, model_used="claude-opus-4-6",
            ),
            CLIResponse(
                runtime_id="codex", display_name="Codex (OpenAI)",
                content="Short answer.",
                latency_ms=1000, cost_usd=0.0, model_used="o4-mini",
            ),
        ]
        scores = [
            BenchmarkScore(
                runtime_id="claude_code", display_name="Claude Code",
                composite=8.5,
            ),
            BenchmarkScore(
                runtime_id="codex", display_name="Codex (OpenAI)",
                composite=5.0,
            ),
        ]
        result = service._synthesize_responses("test prompt", responses, scores)
        assert "Claude Code" in result
        assert "Benchmark Results" in result

    def test_synthesis_with_no_responses(self):
        service = CLIBenchmarkService()
        result = service._synthesize_responses("test", [], [])
        assert "No successful" in result


# ── Composite score calculation ──────────────────────────────


class TestCompositeScore:
    def test_weights_sum_to_one(self):
        total = sum(CLIBenchmarkService._WEIGHTS.values())
        assert abs(total - 1.0) < 0.001
