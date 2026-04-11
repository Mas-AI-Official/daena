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

    # Configure sovereign-tier models for Quintessence debate.
    # Pick the BEST (largest/strongest) model from each provider.
    # Judge: Claude Opus 4.6
    # Debaters: Gemini Pro, Perplexity Pro, Codex
    #
    # Model selection logic:
    # - Prefer "pro", "opus", "max" in model name
    # - Prefer larger context window
    # - Exclude "flash", "mini", "instant" (cheap/fast variants)
    # - NO Ollama, NO Groq -- sovereign subscription/API only

    from app.core.constants import ModelProvider

    _SOVEREIGN_PROVIDERS = [
        ModelProvider.ANTHROPIC, ModelProvider.GEMINI,
        ModelProvider.PERPLEXITY, ModelProvider.OPENAI,
    ]

    # Score models: higher = better
    def _model_score(model_id: str, info) -> float:
        mid = model_id.lower()
        score = 0.0
        # CLI subscription models = highest tier (they use Pro/Max plans)
        if mid.endswith("-cli"):
            score += 200  # CLI subscription = sovereign tier
        # Strong positive signals
        if "opus" in mid or "pro" in mid or "max" in mid:
            score += 100
        if "4.6" in mid or "4-6" in mid or "3.1" in mid:
            score += 50
        if "sonar-pro" in mid:
            score += 100
        if "codex" in mid:
            score += 80
        # Negative signals (cheap models -- never pick these for Quintessence)
        if "flash" in mid or "mini" in mid or "instant" in mid or "nano" in mid:
            score -= 200
        if "8b" in mid or "3b" in mid or "7b" in mid:
            score -= 100
        if "preview" in mid and "pro" not in mid:
            score -= 50  # preview without pro = experimental
        # Context window bonus
        score += info.context_window / 100_000
        return score

    quintessence_models = []
    for provider in _SOVEREIGN_PROVIDERS:
        # Get ALL models from this provider, pick the best
        candidates = [
            (model_id, info)
            for model_id, info in registry._model_cache.items()
            if info.provider == provider
        ]
        if not candidates:
            print(f"  WARNING: No models from {provider.value}")
            continue

        # Sort by score (best first)
        candidates.sort(key=lambda x: _model_score(x[0], x[1]), reverse=True)
        best_id, best_info = candidates[0]
        quintessence_models.append(best_id)
        print(f"  {provider.value:12s} -> {best_id} (score={_model_score(best_id, best_info):.0f}, ctx={best_info.context_window})")

    if not quintessence_models:
        print("ERROR: No sovereign-tier models available. Check API keys.")
        return

    print()
    judge = quintessence_models[0]  # Claude as judge (highest priority)
    print(f"Judge (Primary Mind): {judge}")
    print(f"Debaters: {quintessence_models[1:]}")
    print()

    # Create runner
    runner = RealBenchmarkRunner(registry=registry)

    # Run benchmarks
    benchmarks = [
        (BenchmarkType.TRUTHFULQA, "TruthfulQA (20 questions)"),
        (BenchmarkType.GSM_SYMBOLIC, "GSM-Symbolic (20 questions)"),
        (BenchmarkType.AIME, "AIME 2025 (20 questions)"),
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
