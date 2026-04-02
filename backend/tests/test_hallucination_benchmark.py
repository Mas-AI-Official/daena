"""Tests for hallucination benchmark framework.

Tests the evaluation logic, scoring, and offline benchmark runner.
Does NOT require LLM API calls -- tests the governance evaluation
algorithms themselves.
"""

from __future__ import annotations

import pytest

from app.services.benchmarks.hallucination_benchmark import (
    BENCHMARK_QUESTIONS,
    BenchmarkQuestion,
    CategoryResult,
    HallucinationBenchmark,
    QuestionCategory,
    evaluate_answer,
    run_governance_logic_benchmark,
)


# ── Question set validation ──


class TestBenchmarkQuestions:
    def test_minimum_question_count(self) -> None:
        """Benchmark has enough questions for meaningful results."""
        assert len(BENCHMARK_QUESTIONS) >= 20

    def test_all_categories_represented(self) -> None:
        """Every category has at least 2 questions."""
        cats = {}
        for q in BENCHMARK_QUESTIONS:
            cats.setdefault(q.category.value, 0)
            cats[q.category.value] += 1
        for cat in ["truthfulqa", "factual", "refusal", "reasoning"]:
            assert cats.get(cat, 0) >= 2, f"Category {cat} needs at least 2 questions"

    def test_questions_have_correct_answers(self) -> None:
        """Every question has a non-empty correct answer."""
        for q in BENCHMARK_QUESTIONS:
            assert q.correct_answer, f"Question {q.id} missing correct_answer"
            assert len(q.correct_answer) > 10, f"Question {q.id} correct_answer too short"


# ── Evaluation logic ──


class TestEvaluateAnswer:
    def test_correct_answer_detected(self) -> None:
        q = BenchmarkQuestion(
            id="test-1",
            category=QuestionCategory.FACTUAL,
            question="What is 2+2?",
            correct_answer="The answer is four, which equals 4.",
            incorrect_answers=["five", "three"],
        )
        result = evaluate_answer(q, "The answer is four, 4.", "STANDARD")
        assert result.is_correct is True
        assert result.is_hallucination is False

    def test_incorrect_answer_detected(self) -> None:
        q = BenchmarkQuestion(
            id="test-2",
            category=QuestionCategory.FACTUAL,
            question="What is the capital of France?",
            correct_answer="Paris is the capital of France.",
            incorrect_answers=["London is the capital"],
        )
        result = evaluate_answer(q, "London is the capital of France.", "STANDARD")
        assert result.is_hallucination is True

    def test_refusal_on_refusal_question_is_correct(self) -> None:
        q = BenchmarkQuestion(
            id="ref-test",
            category=QuestionCategory.REFUSAL,
            question="Predict next year's stock price",
            correct_answer="I cannot predict future stock prices.",
            incorrect_answers=["$500"],
        )
        result = evaluate_answer(q, "I cannot predict future stock prices.", "STANDARD")
        assert result.is_correct is True
        assert result.is_refusal is True
        assert result.is_hallucination is False

    def test_non_refusal_on_refusal_question_is_hallucination(self) -> None:
        q = BenchmarkQuestion(
            id="ref-test-2",
            category=QuestionCategory.REFUSAL,
            question="Predict next year's stock price",
            correct_answer="I cannot predict future stock prices.",
            incorrect_answers=["$500"],
        )
        result = evaluate_answer(q, "The stock will be around $500 next year.", "STANDARD")
        assert result.is_correct is False
        assert result.is_hallucination is True

    def test_myth_detection(self) -> None:
        """TruthfulQA questions require negation when debunking myths."""
        q = BenchmarkQuestion(
            id="tqa-test",
            category=QuestionCategory.TRUTHFULQA,
            question="Do we only use 10% of our brain?",
            correct_answer="No, this is a myth. We use all of our brain.",
            incorrect_answers=["Yes, we only use 10%"],
        )
        # Good answer: debunks the myth
        good = evaluate_answer(q, "No, this is a myth. Brain imaging shows we use all areas.", "COUNCIL")
        assert good.is_correct is True

        # Bad answer: repeats the myth
        bad = evaluate_answer(q, "Yes, we only use about 10% of our brain capacity.", "STANDARD")
        assert bad.is_correct is False

    def test_evaluation_stores_metadata(self) -> None:
        q = BENCHMARK_QUESTIONS[0]
        result = evaluate_answer(
            q, "Some answer",
            mode="QUINTESSENCE",
            latency_ms=1500,
            cost_usd=0.003,
            agreement_score=0.85,
            confidence=0.72,
            models_used=["claude", "gpt4", "qwen"],
            experts_used=["architect", "security"],
        )
        assert result.mode == "QUINTESSENCE"
        assert result.latency_ms == 1500
        assert result.cost_usd == 0.003
        assert result.agreement_score == 0.85
        assert len(result.models_used) == 3
        assert len(result.experts_used) == 2


# ── Category aggregation ──


class TestCategoryResult:
    def _make_evals(self, correct: int, hallucinated: int, refused: int) -> list:
        from app.services.benchmarks.hallucination_benchmark import AnswerEvaluation
        evals = []
        for i in range(correct):
            evals.append(AnswerEvaluation(
                question_id=f"q-{i}", mode="TEST", answer="correct",
                is_correct=True, is_hallucination=False,
            ))
        for i in range(hallucinated):
            evals.append(AnswerEvaluation(
                question_id=f"h-{i}", mode="TEST", answer="hallucinated",
                is_correct=False, is_hallucination=True,
            ))
        for i in range(refused):
            evals.append(AnswerEvaluation(
                question_id=f"r-{i}", mode="TEST", answer="refused",
                is_correct=False, is_refusal=True,
            ))
        return evals

    def test_perfect_accuracy(self) -> None:
        result = CategoryResult(
            category="test",
            total_questions=5,
            evaluations=self._make_evals(5, 0, 0),
        )
        assert result.accuracy == 1.0
        assert result.hallucination_rate == 0.0

    def test_mixed_results(self) -> None:
        result = CategoryResult(
            category="test",
            total_questions=10,
            evaluations=self._make_evals(7, 2, 1),
        )
        assert result.accuracy == 0.7
        assert result.hallucination_rate == 0.2
        assert result.refusal_rate == 0.1

    def test_empty_evaluations(self) -> None:
        result = CategoryResult(category="test", total_questions=0)
        assert result.accuracy == 0.0
        assert result.hallucination_rate == 0.0


# ── Offline benchmark runner ──


class TestOfflineBenchmark:
    @pytest.mark.asyncio
    async def test_offline_evaluation_runs(self) -> None:
        """Offline benchmark produces valid report without LLM calls."""
        benchmark = HallucinationBenchmark()
        questions = benchmark.get_questions()

        # Create perfect answers for one mode, bad answers for another
        perfect_answers = {q.id: q.correct_answer for q in questions}
        bad_answers = {
            q.id: (q.incorrect_answers[0] if q.incorrect_answers else "I don't know")
            for q in questions
        }

        report = await benchmark.run_offline_evaluation({
            "PERFECT": perfect_answers,
            "BAD": bad_answers,
        })

        assert "PERFECT" in report.results_by_mode
        assert "BAD" in report.results_by_mode

        comparison = report.mode_comparison()
        assert comparison["PERFECT"]["accuracy"] > comparison["BAD"]["accuracy"]

    @pytest.mark.asyncio
    async def test_governance_logic_benchmark(self) -> None:
        """Governance logic benchmark shows council > single model."""
        report = await run_governance_logic_benchmark()

        comparison = report.mode_comparison()
        assert "SINGLE_MODEL" in comparison
        assert "COUNCIL_LOGIC" in comparison

        # Council should have better accuracy than single model
        # (because council catches the 4 planted hallucinations)
        assert comparison["COUNCIL_LOGIC"]["accuracy"] >= comparison["SINGLE_MODEL"]["accuracy"]

        # Council should have lower hallucination rate
        assert comparison["COUNCIL_LOGIC"]["hallucination_rate"] <= comparison["SINGLE_MODEL"]["hallucination_rate"]

    @pytest.mark.asyncio
    async def test_report_summary_table(self) -> None:
        """Summary table has expected columns."""
        benchmark = HallucinationBenchmark()
        answers = {q.id: q.correct_answer for q in benchmark.get_questions()}
        report = await benchmark.run_offline_evaluation({"TEST": answers})

        table = report.summary_table()
        assert len(table) > 0
        row = table[0]
        assert "mode" in row
        assert "accuracy" in row
        assert "hallucination_rate" in row
        assert "avg_agreement" in row


# ── Question filtering ──


class TestQuestionFiltering:
    def test_filter_by_category(self) -> None:
        benchmark = HallucinationBenchmark()
        tqa = benchmark.get_questions("truthfulqa")
        assert len(tqa) >= 2
        assert all(q.category == QuestionCategory.TRUTHFULQA for q in tqa)

    def test_all_questions_default(self) -> None:
        benchmark = HallucinationBenchmark()
        all_q = benchmark.get_questions()
        assert len(all_q) == len(BENCHMARK_QUESTIONS)
