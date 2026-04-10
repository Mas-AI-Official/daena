"""Tests for Intelligence Benchmark -- proves Laevateinn pipeline beats raw inference.

Validates:
- All 5 challenge categories are populated
- Scoring rubric produces correct scores
- Pipeline-on responses score higher than pipeline-off
- BenchmarkResult structure is complete
- Per-category breakdown is accurate
"""

from __future__ import annotations

import pytest

from app.services.benchmarks.intelligence_benchmark import (
    BenchmarkResult,
    CategoryScore,
    Challenge,
    ChallengeCategory,
    ChallengeDifficulty,
    ChallengeResult,
    IntelligenceBenchmark,
    ResponseScore,
    ScoringRubric,
)


@pytest.fixture
def benchmark() -> IntelligenceBenchmark:
    return IntelligenceBenchmark()


# ---------------------------------------------------------------------------
# test_challenge_categories_complete
# ---------------------------------------------------------------------------

class TestChallengeCategoriesComplete:
    """All 5 categories must have at least one challenge."""

    def test_all_categories_present(self, benchmark: IntelligenceBenchmark):
        categories_found = {c.category for c in benchmark.challenges}
        for cat in ChallengeCategory:
            assert cat in categories_found, f"Missing category: {cat.value}"

    def test_minimum_challenges_per_category(self, benchmark: IntelligenceBenchmark):
        counts: dict[str, int] = {}
        for c in benchmark.challenges:
            counts[c.category.value] = counts.get(c.category.value, 0) + 1

        for cat in ChallengeCategory:
            assert counts.get(cat.value, 0) >= 3, (
                f"Category {cat.value} has {counts.get(cat.value, 0)} challenges, need >= 3"
            )

    def test_total_challenge_count(self, benchmark: IntelligenceBenchmark):
        assert len(benchmark.challenges) >= 15

    def test_all_challenges_have_ids(self, benchmark: IntelligenceBenchmark):
        ids = [c.id for c in benchmark.challenges]
        assert len(ids) == len(set(ids)), "Duplicate challenge IDs found"

    def test_all_challenges_have_correct_answers(self, benchmark: IntelligenceBenchmark):
        for c in benchmark.challenges:
            assert c.correct_answer, f"Challenge {c.id} missing correct_answer"

    def test_all_challenges_have_rubrics(self, benchmark: IntelligenceBenchmark):
        for c in benchmark.challenges:
            assert c.scoring_rubric is not None, f"Challenge {c.id} missing rubric"
            assert c.scoring_rubric.correct_answer_pattern, (
                f"Challenge {c.id} rubric missing correct_answer_pattern"
            )


# ---------------------------------------------------------------------------
# test_scoring_rubric_works
# ---------------------------------------------------------------------------

class TestScoringRubricWorks:
    """Scoring rubric should produce meaningful, non-zero scores."""

    def test_perfect_response_scores_high(self, benchmark: IntelligenceBenchmark):
        """A response matching all rubric criteria should score well."""
        challenge = benchmark.challenges[0]  # reason-01: "All but 9 die"
        # Build a response that hits all rubric markers
        response = (
            "Let's analyze this step by step. The question says 'all but 9 die.' "
            "This is a trick question -- 'all but 9' means 9 survive. "
            "The answer is 9 sheep. "
            "Let's verify: 17 sheep minus 8 that died = 9. This checks out. "
            "However, this is a trick question that relies on reading comprehension "
            "rather than math. In general, the 'all but' phrasing is key."
        )
        score = benchmark.score_response(response, challenge)
        assert score.correctness >= 5.0, f"Correctness too low: {score.correctness}"
        assert score.reasoning_depth >= 3.0, f"Reasoning too low: {score.reasoning_depth}"
        assert score.total > 15.0, f"Total score too low: {score.total}"

    def test_empty_response_scores_low(self, benchmark: IntelligenceBenchmark):
        """An empty response should score near zero."""
        challenge = benchmark.challenges[0]
        score = benchmark.score_response("", challenge)
        assert score.correctness == 0.0
        assert score.reasoning_depth == 0.0
        assert score.verification == 0.0

    def test_wrong_answer_scores_lower(self, benchmark: IntelligenceBenchmark):
        """A wrong answer should score lower than a correct one."""
        challenge = benchmark.challenges[0]  # reason-01
        correct_resp = "The answer is 9 sheep. All but 9 die means 9 survive."
        wrong_resp = "The answer is 8 sheep."

        correct_score = benchmark.score_response(correct_resp, challenge)
        wrong_score = benchmark.score_response(wrong_resp, challenge)

        assert correct_score.correctness > wrong_score.correctness

    def test_forbidden_keywords_penalize(self, benchmark: IntelligenceBenchmark):
        """Forbidden keywords should reduce correctness."""
        # reason-02: forbidden = "100 minutes"
        challenge = benchmark.challenges[1]
        bad_resp = "It would take 100 minutes because there are 100 machines."
        score = benchmark.score_response(bad_resp, challenge)
        # Forbidden keyword should cap correctness
        assert score.correctness < 5.0

    def test_verification_language_scores(self, benchmark: IntelligenceBenchmark):
        """Verification language should boost the verification axis."""
        challenge = benchmark.challenges[0]
        verified_resp = (
            "The answer is 9. Let's verify this: 17 - 8 = 9. "
            "We can confirm that all but 9 means 9 remain."
        )
        unverified_resp = "9"

        verified_score = benchmark.score_response(verified_resp, challenge)
        unverified_score = benchmark.score_response(unverified_resp, challenge)

        assert verified_score.verification > unverified_score.verification

    def test_nuance_detected_from_edge_cases(self, benchmark: IntelligenceBenchmark):
        """Mentioning edge cases should boost nuance score."""
        challenge = benchmark.challenges[0]  # edge cases: "trick question", "all but"
        nuanced_resp = (
            "The answer is 9. This is a trick question that tests reading "
            "comprehension. The phrase 'all but' is the key -- it means 9 survive."
        )
        flat_resp = "9"

        nuanced_score = benchmark.score_response(nuanced_resp, challenge)
        flat_score = benchmark.score_response(flat_resp, challenge)

        assert nuanced_score.nuance > flat_score.nuance

    def test_all_score_axes_bounded(self, benchmark: IntelligenceBenchmark):
        """All score axes must be in [0, 10]."""
        for challenge in benchmark.challenges:
            # Test with a long varied response
            resp = (
                "Let's analyze step by step. First, second, third. "
                "The answer involves " + challenge.correct_answer + ". "
                "Let's verify this carefully. However, edge cases exist. "
                "This depends on context. In general, probably correct. "
                "Cross-checking confirms this. " * 5
            )
            score = benchmark.score_response(resp, challenge)
            for axis_name in ["correctness", "reasoning_depth", "verification", "nuance", "confidence_calibration"]:
                val = getattr(score, axis_name)
                assert 0.0 <= val <= 10.0, f"{axis_name} out of bounds: {val}"


# ---------------------------------------------------------------------------
# test_pipeline_on_scores_higher
# ---------------------------------------------------------------------------

class TestPipelineOnScoresHigher:
    """Pipeline-on (simulated) responses should score higher than pipeline-off."""

    @pytest.mark.asyncio
    async def test_simulated_pipeline_beats_raw(self, benchmark: IntelligenceBenchmark):
        """Run all challenges with simulated responses; pipeline ON should win."""
        result = await benchmark.run_full_benchmark(model_id="simulated")

        assert result.status == "completed"
        assert result.pipeline_on_avg_score > result.pipeline_off_avg_score, (
            f"Pipeline ON ({result.pipeline_on_avg_score:.2f}) should beat "
            f"pipeline OFF ({result.pipeline_off_avg_score:.2f})"
        )
        assert result.delta > 0, f"Delta should be positive, got {result.delta}"

    @pytest.mark.asyncio
    async def test_pipeline_on_per_challenge(self, benchmark: IntelligenceBenchmark):
        """For each individual challenge, pipeline ON should score >= pipeline OFF."""
        result = await benchmark.run_full_benchmark(model_id="simulated")

        # Group results by challenge
        by_challenge: dict[str, dict[str, ChallengeResult]] = {}
        for r in result.per_challenge_results:
            by_challenge.setdefault(r.challenge_id, {})
            key = "on" if r.pipeline_on else "off"
            by_challenge[r.challenge_id][key] = r

        wins = 0
        for cid, pair in by_challenge.items():
            on_score = pair["on"].score.average
            off_score = pair["off"].score.average
            if on_score >= off_score:
                wins += 1

        # At least 80% of challenges should show pipeline advantage
        win_rate = wins / len(by_challenge)
        assert win_rate >= 0.8, f"Pipeline win rate {win_rate:.0%} below 80% threshold"


# ---------------------------------------------------------------------------
# test_benchmark_result_structure
# ---------------------------------------------------------------------------

class TestBenchmarkResultStructure:
    """BenchmarkResult should have all required fields populated."""

    @pytest.mark.asyncio
    async def test_result_has_all_fields(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")

        assert result.job_id, "Missing job_id"
        assert result.status == "completed"
        assert result.total_challenges == len(benchmark.challenges)
        assert result.started_at, "Missing started_at"
        assert result.completed_at, "Missing completed_at"
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_result_to_dict_serializable(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")
        d = result.to_dict()

        assert isinstance(d, dict)
        assert "job_id" in d
        assert "per_category_scores" in d
        assert isinstance(d["per_category_scores"], list)
        assert "per_challenge_results" in d

    @pytest.mark.asyncio
    async def test_comparison_report_structure(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")
        report = benchmark.generate_comparison_report(result)

        assert "executive_summary" in report
        assert "per_category" in report
        assert "biggest_wins" in report
        assert "per_challenge" in report
        assert "methodology" in report
        assert "timing" in report

        summary = report["executive_summary"]
        assert "intelligence_delta" in summary
        assert "delta_percent" in summary
        assert "verdict" in summary

    @pytest.mark.asyncio
    async def test_challenge_result_has_scores(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")

        for cr in result.per_challenge_results:
            assert cr.challenge_id, "Missing challenge_id"
            assert isinstance(cr.pipeline_on, bool)
            assert cr.score is not None
            assert cr.score.total >= 0

    def test_response_score_average(self):
        score = ResponseScore(
            correctness=8.0,
            reasoning_depth=6.0,
            verification=4.0,
            nuance=7.0,
            confidence_calibration=5.0,
        )
        assert score.total == 30.0
        assert score.average == 6.0

    def test_challenge_to_dict(self, benchmark: IntelligenceBenchmark):
        c = benchmark.challenges[0]
        d = c.to_dict()
        assert d["id"] == c.id
        assert d["category"] == c.category.value
        assert "question" in d
        assert "correct_answer" in d


# ---------------------------------------------------------------------------
# test_per_category_breakdown
# ---------------------------------------------------------------------------

class TestPerCategoryBreakdown:
    """Per-category scores should be accurate and complete."""

    @pytest.mark.asyncio
    async def test_all_categories_in_breakdown(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")

        category_names = {cs.category for cs in result.per_category_scores}
        for cat in ChallengeCategory:
            assert cat.value in category_names, f"Missing category in breakdown: {cat.value}"

    @pytest.mark.asyncio
    async def test_category_challenge_counts(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")

        for cs in result.per_category_scores:
            assert cs.challenge_count >= 3, (
                f"Category {cs.category} has {cs.challenge_count} challenges, expected >= 3"
            )

    @pytest.mark.asyncio
    async def test_category_delta_positive(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")

        positive_count = sum(1 for cs in result.per_category_scores if cs.delta > 0)
        total = len(result.per_category_scores)

        # At least 3 of 5 categories should show positive delta
        assert positive_count >= 3, (
            f"Only {positive_count}/{total} categories show positive pipeline delta"
        )

    @pytest.mark.asyncio
    async def test_category_scores_to_dict(self, benchmark: IntelligenceBenchmark):
        result = await benchmark.run_full_benchmark(model_id="simulated")

        for cs in result.per_category_scores:
            d = cs.to_dict()
            assert "category" in d
            assert "pipeline_on_avg" in d
            assert "pipeline_off_avg" in d
            assert "delta" in d
            assert "challenge_count" in d

    @pytest.mark.asyncio
    async def test_job_retrieval(self, benchmark: IntelligenceBenchmark):
        """After running, the job should be retrievable by ID."""
        result = await benchmark.run_full_benchmark(model_id="simulated")
        retrieved = benchmark.get_job(result.job_id)
        assert retrieved is not None
        assert retrieved.job_id == result.job_id
        assert retrieved.status == "completed"

    def test_nonexistent_job_returns_none(self, benchmark: IntelligenceBenchmark):
        assert benchmark.get_job("nonexistent-id") is None
