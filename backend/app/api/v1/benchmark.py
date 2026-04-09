"""Benchmark API -- exposes cost comparison between regular and Daena approaches.

GET /api/v1/benchmark/cost-comparison  -> full benchmark report
GET /api/v1/benchmark/quick-summary    -> one-line savings summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("/cost-comparison")
async def cost_comparison(user=Depends(get_current_user)):
    """Run the standard 10-scenario benchmark and return full comparison."""
    from app.services.benchmarks.cost_benchmark import CostBenchmark

    bench = CostBenchmark()
    report = bench.run_standard_benchmark()

    return {
        "data": {
            "scenarios_count": report.scenarios_count,
            "total_regular_cost_usd": report.total_regular_cost,
            "total_daena_cost_usd": report.total_daena_cost,
            "total_savings_usd": report.total_savings_usd,
            "total_savings_percent": report.total_savings_percent,
            "total_token_savings": report.total_token_savings,
            "comparisons": [
                {
                    "query": c.scenario.query,
                    "intent": c.scenario.intent,
                    "complexity": c.scenario.complexity,
                    "regular": {
                        "model": c.regular.model_used,
                        "tokens": c.regular.total_tokens,
                        "cost_usd": c.regular.cost_usd,
                    },
                    "daena": {
                        "model": c.daena.model_used,
                        "tokens": c.daena.total_tokens,
                        "cost_usd": c.daena.cost_usd,
                        "routing_reason": c.daena.routing_reason,
                        "tools_activated": c.daena.tools_activated,
                    },
                    "token_savings": c.token_savings,
                    "cost_savings_percent": c.cost_savings_percent,
                }
                for c in report.comparisons
            ],
        }
    }


@router.get("/full")
async def full_benchmark(user=Depends(get_current_user)):
    """Run all Daena benchmarks (governance overhead, memory, code quality, security).

    Returns full suite results including competitor comparisons.
    This endpoint may take 30-60 seconds depending on test suite runtime.
    """
    from app.services.benchmarks.suite import DaenaBenchmarkSuite

    suite = DaenaBenchmarkSuite()
    results = await suite.run_all()

    return {
        "data": {
            "benchmark_count": len(results),
            "results": {name: r.to_dict() for name, r in results.items()},
        }
    }


@router.get("/quick-summary")
async def quick_summary(user=Depends(get_current_user)):
    """One-line savings summary for dashboard/mobile."""
    from app.services.benchmarks.cost_benchmark import CostBenchmark

    bench = CostBenchmark()
    report = bench.run_standard_benchmark()

    return {
        "data": {
            "savings_percent": report.total_savings_percent,
            "savings_usd": report.total_savings_usd,
            "token_savings": report.total_token_savings,
            "summary": (
                f"Daena saves {report.total_savings_percent:.0f}% vs regular prompting "
                f"({report.total_token_savings:,} tokens saved across {report.scenarios_count} scenarios)"
            ),
        }
    }
