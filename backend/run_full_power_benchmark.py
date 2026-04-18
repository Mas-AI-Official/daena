"""Full Power Benchmark Runner -- Quintessence + AGI + Think Mode + Search Fallback.

Runs AIME, TruthfulQA, and GSM-Symbolic benchmarks using ONLY sovereign-tier models:
  - Claude Opus 4.6 (Judge/Synthesizer via CLI subscription)
  - Gemini Pro (Debater via API key)
  - Perplexity Pro (Debater + Search fallback via API key)
  - Codex 5.4 (Debater via CLI subscription)

NO Ollama. NO local models. Full power.

Usage:
    python run_full_power_benchmark.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(".env")


async def main():
    from app.services.benchmarks.real_benchmarks import (
        BenchmarkType,
        RealBenchmarkRunner,
    )
    from app.services.model_registry import ModelRegistry

    print("=" * 60)
    print("DAENA FULL POWER BENCHMARK")
    print("Quintessence + AGI + Think Mode + Search Fallback")
    print("=" * 60)
    print()

    # Initialize registry
    registry = ModelRegistry()
    await registry.initialize()

    snapshot = await registry.snapshot()
    providers = registry.available_providers
    print(f"Available providers: {[p.value for p in providers]}")

    # Use ModelRouter for sovereign-tier model selection.
    # The router uses the tier system + debate roster + CLI preference.
    # Judge: best single model (Primary Mind)
    # Debaters: task-aware debate roster from router
    from app.services.model_router import ModelRouter

    router = ModelRouter(registry)

    # Judge = best single model (sovereign tier, CLI preferred)
    judge_candidate = router.select_best_single()
    if not judge_candidate:
        print("ERROR: No models available. Check API keys and providers.")
        return

    judge = judge_candidate.model_id
    judge_provider = judge_candidate.provider
    print(f"Judge (Primary Mind): {judge} [{judge_provider.value}]")

    # Debaters = sovereign-tier models excluding judge's provider
    debaters = router.select_debate_roster(
        intent=None,  # General -- will be overridden per-benchmark
        count=4,
        primary_mind_provider=judge_provider,
    )
    quintessence_models = [judge] + [d.model_id for d in debaters]

    print(f"Debaters: {[d.model_id + ' [' + d.provider.value + ']' for d in debaters]}")
    print(f"Total Quintessence roster: {len(quintessence_models)} models")
    print()

    # Create runner
    runner = RealBenchmarkRunner(registry=registry)

    # Run benchmarks
    benchmarks = [
        (BenchmarkType.AIME, "AIME 2025 I (15 official MAA problems)"),
        (BenchmarkType.TRUTHFULQA, "TruthfulQA (20 questions)"),
        (BenchmarkType.GSM_SYMBOLIC, "GSM-Symbolic (20 questions)"),
    ]

    results = {}
    for bench_type, name in benchmarks:
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print(f"Mode: Quintessence + Think + Search Fallback")
        print(f"{'=' * 60}")

        start = time.time()
        result = await runner.run_benchmark(
            benchmark=bench_type,
            model_id=judge,
            use_pipeline=True,
            quintessence_models=quintessence_models,
            full_power=True,
            think_mode=True,
            search_fallback=True,
        )
        elapsed = time.time() - start

        results[bench_type.value] = result

        print(f"\n  Raw accuracy:      {result.raw_accuracy:.1%}")
        print(f"  Pipeline accuracy: {result.pipeline_accuracy:.1%}")
        print(f"  Delta:             +{result.delta:.1%}")
        print(f"  Time:              {elapsed:.1f}s")
        print(f"  Category breakdown:")
        for cat, scores in result.per_category.items():
            raw = scores.get("raw_accuracy", 0)
            pipe = scores.get("pipeline_accuracy", 0)
            print(f"    {cat:25s} raw={raw:.0%}  pipe={pipe:.0%}")

    # Summary table
    print(f"\n\n{'=' * 60}")
    print("FULL POWER BENCHMARK RESULTS")
    print(f"{'=' * 60}")
    print(f"{'Benchmark':25s} | {'Raw':>8s} | {'Pipeline':>8s} | {'Delta':>8s}")
    print(f"{'-' * 25}-+-{'-' * 8}-+-{'-' * 8}-+-{'-' * 8}")
    for bench_type, name in benchmarks:
        r = results.get(bench_type.value)
        if r:
            print(f"{name[:25]:25s} | {r.raw_accuracy:>7.1%} | {r.pipeline_accuracy:>7.1%} | +{r.delta:>6.1%}")

    # Save results to JSON
    output_path = Path("benchmark_results_full_power.json")
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "full_power",
        "settings": {
            "quintessence": True,
            "agi_mode": True,
            "think_mode": True,
            "search_fallback": True,
            "judge_model": judge,
            "debater_models": quintessence_models[1:],
        },
        "results": {k: v.to_dict() for k, v in results.items()},
    }
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults saved to: {output_path.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
