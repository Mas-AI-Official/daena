"""Tests for Cost Benchmark System -- proves Daena's value proposition.

Verifies that Daena's orchestrated approach consistently saves tokens
and cost vs the regular "send everything to one expensive model" approach.
"""

from __future__ import annotations

import pytest

from app.services.benchmarks.cost_benchmark import (
    BenchmarkComparison,
    BenchmarkReport,
    CostBenchmark,
    DaenaCostResult,
    MODEL_COSTS,
    QueryScenario,
    RegularCostResult,
)


@pytest.fixture
def bench() -> CostBenchmark:
    return CostBenchmark()


# ── Routing Intelligence Tests ────────────────────────────────

class TestRoutingIntelligence:
    def test_simple_query_routes_to_free_model(self, bench: CostBenchmark):
        scenario = QueryScenario(query="Hi", intent="simple", complexity=0.05)
        result = bench.benchmark_single(scenario)
        # Daena should use a free or very cheap model
        assert result.daena.cost_usd == 0.0 or result.daena.cost_usd < result.regular.cost_usd

    def test_coding_query_routes_to_code_model(self, bench: CostBenchmark):
        scenario = QueryScenario(
            query="Write a sort function", intent="coding", complexity=0.4,
            requires_tools=["terminal"],
        )
        result = bench.benchmark_single(scenario)
        # Should use a coding-optimized model
        assert "coder" in result.daena.model_used or "claude" in result.daena.model_used

    def test_complex_coding_uses_premium_model(self, bench: CostBenchmark):
        scenario = QueryScenario(
            query="Complex refactor", intent="coding", complexity=0.8,
            requires_tools=["terminal", "file_system"],
        )
        result = bench.benchmark_single(scenario)
        # High complexity should use a capable model
        assert result.daena.model_used in ("claude-3.5-sonnet", "gpt-4o", "claude-4-sonnet")

    def test_dangerous_query_uses_safe_model(self, bench: CostBenchmark):
        scenario = QueryScenario(
            query="Delete everything", intent="dangerous", complexity=0.5,
            requires_tools=["terminal"],
        )
        result = bench.benchmark_single(scenario)
        assert "claude" in result.daena.model_used  # needs best judgment


# ── Token Savings Tests ───────────────────────────────────────

class TestTokenSavings:
    def test_tlm_saves_tool_tokens(self, bench: CostBenchmark):
        """TLM only loads active tool schemas, not all 20+."""
        scenario = QueryScenario(
            query="Read a file", intent="simple", complexity=0.2,
            requires_tools=["file_system"],
            expected_input_tokens=100, expected_output_tokens=200,
        )
        result = bench.benchmark_single(scenario)
        # Regular loads ALL tools (4200 tokens), Daena loads 1 (210 tokens)
        assert result.regular.tool_schema_tokens == 4200
        assert result.daena.tool_schema_tokens == 210
        assert result.token_savings > 3000

    def test_no_tools_saves_all_schema_tokens(self, bench: CostBenchmark):
        """Query with no tools saves all schema token overhead."""
        scenario = QueryScenario(
            query="What is 2+2?", intent="simple", complexity=0.05,
            requires_tools=[],
        )
        result = bench.benchmark_single(scenario)
        assert result.daena.tool_schema_tokens == 0
        assert result.token_savings >= 4200

    def test_savings_always_non_negative(self, bench: CostBenchmark):
        """Daena should never cost MORE tokens than regular approach."""
        report = bench.run_standard_benchmark()
        for c in report.comparisons:
            assert c.token_savings >= 0, \
                f"Negative token savings for '{c.scenario.query}': {c.token_savings}"


# ── Cost Savings Tests ────────────────────────────────────────

class TestCostSavings:
    def test_simple_query_massive_savings(self, bench: CostBenchmark):
        """Simple queries routed to free Ollama = 100% cost savings."""
        scenario = QueryScenario(
            query="Hello", intent="simple", complexity=0.05,
            expected_input_tokens=20, expected_output_tokens=40,
        )
        result = bench.benchmark_single(scenario)
        assert result.cost_savings_percent > 90, \
            f"Expected >90% savings for simple query, got {result.cost_savings_percent}%"

    def test_standard_benchmark_shows_savings(self, bench: CostBenchmark):
        """Full benchmark across 10 scenarios should show overall savings."""
        report = bench.run_standard_benchmark()
        assert report.total_savings_percent > 0, \
            f"Expected positive savings, got {report.total_savings_percent}%"
        assert report.total_savings_usd > 0

    def test_benchmark_report_complete(self, bench: CostBenchmark):
        report = bench.run_standard_benchmark()
        assert report.scenarios_count == 10
        assert len(report.comparisons) == 10
        assert report.total_regular_cost > 0
        assert report.total_daena_cost >= 0
        assert report.generated_at > 0


# ── Model Cost Database Tests ─────────────────────────────────

class TestModelCosts:
    def test_local_models_free(self):
        for model in ["llama3.1:8b", "mistral:7b", "qwen2.5-coder:14b"]:
            assert MODEL_COSTS[model]["input"] == 0.0
            assert MODEL_COSTS[model]["output"] == 0.0

    def test_cloud_models_have_cost(self):
        for model in ["gpt-4o", "claude-3.5-sonnet", "gemini-1.5-pro"]:
            assert MODEL_COSTS[model]["input"] > 0

    def test_all_models_have_label(self):
        for model, costs in MODEL_COSTS.items():
            assert "label" in costs, f"Model {model} missing label"


# ── Comparison Structure Tests ────────────────────────────────

class TestComparisonStructure:
    def test_comparison_has_all_fields(self, bench: CostBenchmark):
        scenario = QueryScenario(query="test", intent="simple", complexity=0.1)
        c = bench.benchmark_single(scenario)
        assert isinstance(c, BenchmarkComparison)
        assert isinstance(c.regular, RegularCostResult)
        assert isinstance(c.daena, DaenaCostResult)
        assert c.regular.label == "Regular (No Daena)"
        assert c.daena.label == "Daena Orchestrated"

    def test_daena_result_has_routing_reason(self, bench: CostBenchmark):
        scenario = QueryScenario(query="test", intent="coding", complexity=0.5)
        c = bench.benchmark_single(scenario)
        assert c.daena.routing_reason != ""

    def test_report_summary_math_correct(self, bench: CostBenchmark):
        report = bench.run_standard_benchmark()
        expected_savings = report.total_regular_cost - report.total_daena_cost
        assert abs(report.total_savings_usd - expected_savings) < 0.000001


# ── Real-World Scenario Tests ─────────────────────────────────

class TestRealWorldScenarios:
    def test_10_message_session_savings(self, bench: CostBenchmark):
        """Simulate a 10-message session and calculate cumulative savings."""
        report = bench.run_standard_benchmark()
        # 10 scenarios, but in a real session, tool savings compound per turn
        assert report.total_token_savings > 10000, \
            f"Expected >10K token savings across 10 messages, got {report.total_token_savings}"

    def test_monthly_cost_projection(self, bench: CostBenchmark):
        """Project monthly savings for 100 messages/day."""
        report = bench.run_standard_benchmark()
        daily_savings = report.total_savings_usd * 10  # 10 scenarios = ~100 msgs
        monthly_savings = daily_savings * 30
        assert monthly_savings > 0, "Monthly savings should be positive"

    def test_enterprise_scenario(self):
        """Enterprise with expensive default model saves even more."""
        bench = CostBenchmark(regular_model="gpt-4-turbo")  # $10/1M input
        report = bench.run_standard_benchmark()
        assert report.total_savings_percent > 50, \
            f"Enterprise should save >50%, got {report.total_savings_percent}%"
