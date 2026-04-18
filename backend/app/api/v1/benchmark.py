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


# ── CLI Benchmark (live multi-runtime) ──


@router.get("/cli/available")
async def list_available_clis(user=Depends(get_current_user)):
    """List which CLI runtimes are installed and available for benchmark."""
    from app.services.benchmarks.cli_benchmark import CLIBenchmarkService

    bench = CLIBenchmarkService()
    available = await bench.discover_available_clis()
    return {
        "data": {
            "available": available,
            "count": len(available),
            "ready": len(available) >= 2,
        }
    }


@router.post("/cli/run")
async def run_cli_benchmark(
    request: Request,
    user=Depends(get_current_user),
):
    """Run a live CLI benchmark: send a prompt to all CLIs, score responses.

    Body: {"prompt": "Your challenge prompt here", "timeout": 120}

    This runs real CLI subprocesses (Claude Code, Codex, Gemini) in
    parallel and returns scored benchmark results. Each CLI uses its
    own authentication and subscription.
    """
    from app.services.benchmarks.cli_benchmark import CLIBenchmarkService

    body = await request.json()
    prompt = body.get("prompt", "")
    timeout = body.get("timeout", 120.0)

    if not prompt:
        return {"error": "prompt is required"}

    bench = CLIBenchmarkService()
    result = await bench.run(prompt, timeout=timeout)

    return {"data": result.to_dict()}


@router.post("/cli/suite")
async def run_cli_benchmark_suite(
    request: Request,
    user=Depends(get_current_user),
):
    """Run the full CLI benchmark suite: all challenges through all CLIs.

    Body: {"timeout": 120} (optional)

    Runs 12 curated challenges across 6 categories (math, reasoning,
    security, adversarial, system design) through all available CLIs.
    Each challenge is scored and checked for correctness.
    Returns a full scorecard with per-runtime accuracy and rankings.
    """
    from app.services.benchmarks.cli_benchmark import (
        BENCHMARK_SUITE,
        CLIBenchmarkService,
        _check_correct,
    )

    body = await request.json() if request.headers.get("content-type") else {}
    timeout = body.get("timeout", 120.0)

    bench = CLIBenchmarkService()
    available = await bench.discover_available_clis()

    if len(available) < 2:
        return {"error": f"Need 2+ CLIs for benchmark, found {len(available)}"}

    # Run all challenges
    results_per_challenge = []
    composite_totals: dict[str, float] = {}
    correct_counts: dict[str, int] = {}
    total_counts: dict[str, int] = {}

    for challenge in BENCHMARK_SUITE:
        result = await bench.run(challenge.prompt, timeout=timeout)

        challenge_data = {
            "id": challenge.id,
            "category": challenge.category,
            "difficulty": challenge.difficulty,
            "correct_answer": challenge.correct_answer,
            "runtimes": {},
        }

        for resp in result.responses:
            is_correct = False
            if resp.content and not resp.error:
                is_correct = _check_correct(resp.content, challenge)
                correct_counts[resp.runtime_id] = (
                    correct_counts.get(resp.runtime_id, 0) + (1 if is_correct else 0)
                )
                total_counts[resp.runtime_id] = total_counts.get(resp.runtime_id, 0) + 1

            challenge_data["runtimes"][resp.runtime_id] = {
                "correct": is_correct,
                "latency_ms": resp.latency_ms,
                "error": resp.error,
                "word_count": len(resp.content.split()) if resp.content else 0,
            }

        for sc in result.scores:
            composite_totals[sc.runtime_id] = (
                composite_totals.get(sc.runtime_id, 0.0) + sc.composite
            )

        results_per_challenge.append(challenge_data)

    # Compute averages
    avg_scores = {
        rid: composite_totals.get(rid, 0.0) / max(len(BENCHMARK_SUITE), 1)
        for rid in available
    }
    winner = max(avg_scores, key=avg_scores.get) if avg_scores else ""

    return {
        "data": {
            "total_challenges": len(BENCHMARK_SUITE),
            "runtimes": available,
            "avg_scores": {rid: round(s, 1) for rid, s in avg_scores.items()},
            "accuracy": {
                rid: {
                    "correct": correct_counts.get(rid, 0),
                    "total": total_counts.get(rid, 0),
                    "percent": round(
                        correct_counts.get(rid, 0) * 100
                        / max(total_counts.get(rid, 0), 1),
                    ),
                }
                for rid in available
            },
            "winner": winner,
            "per_challenge": results_per_challenge,
        }
    }


@router.get("/cli/suite/challenges")
async def list_suite_challenges(user=Depends(get_current_user)):
    """List all challenges in the benchmark suite."""
    from app.services.benchmarks.cli_benchmark import BENCHMARK_SUITE

    return {
        "data": {
            "total": len(BENCHMARK_SUITE),
            "categories": list({c.category for c in BENCHMARK_SUITE}),
            "challenges": [
                {
                    "id": c.id,
                    "category": c.category,
                    "difficulty": c.difficulty,
                    "prompt_preview": c.prompt[:100],
                    "correct_answer": c.correct_answer,
                }
                for c in BENCHMARK_SUITE
            ],
        }
    }


# ── Intelligence Benchmark (Pipeline ON vs OFF) ──


@router.post("/intelligence/run-background")
async def run_intelligence_benchmark_background(
    request: Request,
    user=Depends(get_current_user),
):
    """Launch the intelligence benchmark as a background task.

    Runs ALL benchmark suites (AIME, TruthfulQA, GSM-Symbolic,
    GPQA-Diamond, HaluEval, MMLU-Pro) through raw model inference
    AND the full Daena Laevateinn 19-stage pipeline. Compares
    accuracy to prove the pipeline makes models smarter.

    Results save to intelligence_benchmark_results.json.
    This endpoint returns immediately -- the benchmark runs in background.

    Body (optional): {"suites": ["aime", "truthfulqa"], "think_mode": true}
    """
    import asyncio
    import json as _json
    from pathlib import Path

    from app.services.benchmarks.cli_benchmark import (
        run_intelligence_benchmark_streaming,
    )
    from app.services.model_registry import ModelRegistry

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    suites = body.get("suites")  # None = all suites
    think_mode = body.get("think_mode", True)
    full_power = body.get("full_power", True)

    registry = ModelRegistry()
    await registry.initialize()

    results_file = Path("D:/Ideas/Daena/backend/intelligence_benchmark_results.json")

    async def _run_bg():
        report = ""
        event_count = 0
        try:
            async for event in run_intelligence_benchmark_streaming(
                registry,
                benchmarks=suites,
                think_mode=think_mode,
                full_power=full_power,
            ):
                event_count += 1
                if event.get("type") == "chunk":
                    report += event.get("content", "")
                if event_count % 10 == 0:
                    logger.info(
                        "benchmark.bg_progress",
                        events=event_count,
                        chars=len(report),
                    )
        except Exception as exc:
            logger.error("benchmark.bg_failed", error=str(exc))
            report += f"\n\nBENCHMARK ERROR: {exc}"
        finally:
            results_file.write_text(
                _json.dumps({
                    "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                    "status": "complete" if report and "ERROR" not in report else "failed",
                    "events": event_count,
                    "report": report,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("benchmark.bg_saved", file=str(results_file), events=event_count)

    asyncio.create_task(_run_bg())

    return {
        "data": {
            "status": "launched",
            "message": "Intelligence benchmark running in background",
            "results_file": str(results_file),
            "suites": suites or ["aime", "truthfulqa", "gsm_symbolic", "gpqa_diamond", "halueval", "mmlu_pro"],
            "think_mode": think_mode,
            "full_power": full_power,
        }
    }


@router.get("/intelligence/results")
async def get_intelligence_results(user=Depends(get_current_user)):
    """Get the latest intelligence benchmark results."""
    import json as _json
    from pathlib import Path

    results_file = Path("D:/Ideas/Daena/backend/intelligence_benchmark_results.json")
    if not results_file.exists():
        return {"data": {"status": "not_started", "message": "No benchmark results found. Run POST /benchmark/intelligence/run-background first."}}

    data = _json.loads(results_file.read_text(encoding="utf-8"))
    return {"data": data}
