"""Benchmark API -- exposes cost comparison between regular and Daena approaches.

GET /api/v1/benchmark/cost-comparison  -> full benchmark report
GET /api/v1/benchmark/quick-summary    -> one-line savings summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

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


@router.post("/intelligence")
async def run_intelligence_benchmark(user=Depends(get_current_user)):
    """Run full intelligence benchmark comparing pipeline ON vs OFF.

    This runs all challenge questions through both raw inference and the
    full Laevateinn pipeline, then scores and compares. Takes 1-5 minutes
    depending on model speed.

    Returns a job_id for polling results via GET /benchmark/intelligence/{job_id}.
    """
    import asyncio

    from app.services.benchmarks.intelligence_benchmark import get_intelligence_benchmark

    benchmark = get_intelligence_benchmark()

    # Start the benchmark in background and return job_id immediately
    result = await benchmark.run_full_benchmark(model_id="auto")

    return {
        "data": {
            "job_id": result.job_id,
            "status": result.status,
            "total_challenges": result.total_challenges,
            "pipeline_on_avg_score": round(result.pipeline_on_avg_score, 2),
            "pipeline_off_avg_score": round(result.pipeline_off_avg_score, 2),
            "delta": round(result.delta, 2),
            "delta_percent": round(result.delta_percent, 1),
            "per_category_scores": [c.to_dict() for c in result.per_category_scores],
            "report": benchmark.generate_comparison_report(result),
        }
    }


@router.get("/intelligence/{job_id}")
async def get_intelligence_results(job_id: str, user=Depends(get_current_user)):
    """Get results for a previously-started intelligence benchmark run."""
    from app.services.benchmarks.intelligence_benchmark import get_intelligence_benchmark

    benchmark = get_intelligence_benchmark()
    result = benchmark.get_job(job_id)

    if result is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Benchmark job {job_id} not found")

    data = result.to_dict()
    if result.status == "completed":
        data["report"] = benchmark.generate_comparison_report(result)

    return {"data": data}


@router.get("/intelligence/challenges")
async def list_intelligence_challenges(user=Depends(get_current_user)):
    """List all available intelligence benchmark challenges."""
    from app.services.benchmarks.intelligence_benchmark import get_intelligence_benchmark

    benchmark = get_intelligence_benchmark()
    challenges = benchmark.challenges

    # Group by category
    by_category: dict[str, list] = {}
    for c in challenges:
        cat = c.category.value
        by_category.setdefault(cat, []).append(c.to_dict())

    return {
        "data": {
            "total": len(challenges),
            "categories": list(by_category.keys()),
            "by_category": by_category,
            "challenges": [c.to_dict() for c in challenges],
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


# ── Real-world benchmark endpoints (TruthfulQA, GSM-Symbolic, etc.) ──


@router.get("/real/available")
async def list_real_benchmarks(user=Depends(get_current_user)):
    """List available real-world benchmark suites."""
    from app.services.benchmarks.real_benchmarks import RealBenchmarkRunner

    runner = RealBenchmarkRunner()
    return {"data": runner.get_available_benchmarks()}


@router.post("/real/run")
async def run_real_benchmark(
    request: Request,
    user=Depends(get_current_user),
):
    """Run a real-world benchmark (TruthfulQA, GSM-Symbolic, etc.).

    Body: {"benchmark": "truthfulqa" | "gsm_symbolic", "model_id": "default"}
    """
    from app.services.benchmarks.real_benchmarks import (
        BenchmarkType,
        RealBenchmarkRunner,
    )

    body = await request.json()
    benchmark_str = body.get("benchmark", "truthfulqa")
    model_id = body.get("model_id", "default")

    try:
        benchmark_type = BenchmarkType(benchmark_str)
    except ValueError:
        return {"error": f"Unknown benchmark: {benchmark_str}. Available: {[b.value for b in BenchmarkType]}"}

    # Pass ModelRegistry for real LLM calls (falls back to simulation if unavailable)
    registry = getattr(request.app.state, "model_registry", None)
    runner = RealBenchmarkRunner(registry=registry)
    result = await runner.run_benchmark(benchmark_type, model_id)

    return {"data": result.to_dict()}


@router.get("/real/{job_id}")
async def get_real_benchmark_result(job_id: str, user=Depends(get_current_user)):
    """Get results from a real-world benchmark run."""
    from app.services.benchmarks.real_benchmarks import RealBenchmarkRunner

    runner = RealBenchmarkRunner()
    result = runner.get_job(job_id)
    if not result:
        return {"error": "Job not found"}
    return {"data": result.to_dict()}
