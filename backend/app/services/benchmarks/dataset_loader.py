"""Benchmark Dataset Loader -- reads real benchmark questions from files.

Loads datasets from backend/data/benchmarks/ directory:
- GPQA-Diamond: 198 PhD-level science questions (CSV from GitHub)
- MMLU-Pro STEM: 5878 graduate-level STEM questions (JSON from HuggingFace)
- AIME 2025 I: 15 competition math questions (built-in, verified by MAA)
- TruthfulQA: 20 hallucination-resistance questions (built-in subset)
- GSM-Symbolic: 20 adversarial math questions (built-in, Apple-style)
- HaluEval: 10 hallucination detection questions (built-in)

No hardcoded questions for GPQA and MMLU-Pro. All loaded from real
dataset files downloaded from their official sources.

Usage::

    loader = DatasetLoader()
    questions = loader.load("gpqa_diamond")
    # Returns list of BenchmarkQuestion
    # Full 198 questions, or sample N for faster runs
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.benchmarks.real_benchmarks import (
    BenchmarkQuestion,
    BenchmarkType,
)

logger = get_logger(__name__)

# Path to benchmark dataset files
_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "benchmarks"


def _load_gpqa_diamond(
    *,
    sample: int | None = None,
    seed: int = 42,
) -> list[BenchmarkQuestion]:
    """Load GPQA-Diamond from CSV file.

    198 PhD-level multiple-choice questions across physics,
    chemistry, and biology. Each has 4 answer choices with
    1 correct answer. Downloaded from github.com/idavidrein/gpqa.

    Args:
        sample: If set, randomly sample N questions (for faster runs).
        seed: Random seed for reproducible sampling.
    """
    csv_path = _DATA_DIR / "gpqa_diamond.csv"
    if not csv_path.exists():
        logger.warning("gpqa_diamond.csv not found", path=str(csv_path))
        return []

    questions = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            q_text = row.get("Question", "").strip()
            correct = row.get("Correct Answer", "").strip()
            wrong1 = row.get("Incorrect Answer 1", "").strip()
            wrong2 = row.get("Incorrect Answer 2", "").strip()
            wrong3 = row.get("Incorrect Answer 3", "").strip()
            domain = row.get("High-level domain", "").strip()
            subdomain = row.get("Subdomain", "").strip()

            if not q_text or not correct:
                continue

            # Build multiple-choice format with shuffled answers
            choices = [correct, wrong1, wrong2, wrong3]
            choices = [c for c in choices if c]  # remove empty
            rng = random.Random(seed + i)
            rng.shuffle(choices)
            correct_letter = chr(65 + choices.index(correct))  # A, B, C, D

            mc_text = q_text + "\n"
            for j, choice in enumerate(choices):
                mc_text += f"\n{chr(65 + j)}) {choice}"

            questions.append(BenchmarkQuestion(
                id=f"gpqa-{i + 1:03d}",
                benchmark=BenchmarkType.GPQA_DIAMOND,
                question=mc_text,
                correct_answer=correct_letter,
                category=subdomain or domain or "science",
                difficulty="graduate",
                metadata={
                    "domain": domain,
                    "subdomain": subdomain,
                    "correct_text": correct,
                },
            ))

    if sample and sample < len(questions):
        rng = random.Random(seed)
        questions = rng.sample(questions, sample)

    logger.info(
        "dataset.loaded",
        dataset="gpqa_diamond",
        total=len(questions),
        sample=sample,
    )
    return questions


def _load_mmlu_pro_stem(
    *,
    sample: int | None = None,
    seed: int = 42,
    categories: list[str] | None = None,
) -> list[BenchmarkQuestion]:
    """Load MMLU-Pro STEM questions from JSON file.

    5878 graduate-level STEM questions across physics, chemistry,
    biology, math, computer science, engineering. Each has 10
    answer choices (A-J). Downloaded from TIGER-Lab/MMLU-Pro on
    HuggingFace.

    Args:
        sample: If set, randomly sample N questions.
        seed: Random seed for reproducible sampling.
        categories: Filter to specific categories (e.g. ["physics", "math"]).
    """
    json_path = _DATA_DIR / "mmlu_pro_stem.json"
    if not json_path.exists():
        logger.warning("mmlu_pro_stem.json not found", path=str(json_path))
        return []

    with open(json_path, encoding="utf-8") as f:
        raw = json.load(f)

    questions = []
    for row in raw:
        cat = row.get("category", "")
        if categories and cat not in categories:
            continue

        q_text = row.get("question", "")
        options = row.get("options", [])
        answer = row.get("answer", "")  # Letter like "A", "B", etc.

        if not q_text or not answer:
            continue

        # Build multiple-choice format
        mc_text = q_text
        if options:
            mc_text += "\n"
            for j, opt in enumerate(options):
                mc_text += f"\n{chr(65 + j)}) {opt}"

        questions.append(BenchmarkQuestion(
            id=row.get("id", f"mmlu-{len(questions)}"),
            benchmark=BenchmarkType.MMLU_PRO,
            question=mc_text,
            correct_answer=answer,
            category=cat,
            difficulty="graduate",
        ))

    if sample and sample < len(questions):
        # Stratified sampling: equal from each category
        if categories is None:
            cats = list({q.category for q in questions})
        else:
            cats = categories
        per_cat = max(sample // len(cats), 1)
        sampled = []
        rng = random.Random(seed)
        for cat in cats:
            cat_qs = [q for q in questions if q.category == cat]
            sampled.extend(rng.sample(cat_qs, min(per_cat, len(cat_qs))))
        questions = sampled[:sample]

    logger.info(
        "dataset.loaded",
        dataset="mmlu_pro_stem",
        total=len(questions),
        sample=sample,
        categories=categories,
    )
    return questions


class DatasetLoader:
    """Central loader for all benchmark datasets.

    Reads from files (no hardcoded questions for GPQA/MMLU-Pro).
    Built-in datasets (AIME, TruthfulQA, GSM) still use the
    existing curated lists in real_benchmarks.py.
    """

    def load(
        self,
        benchmark: str | BenchmarkType,
        *,
        sample: int | None = None,
        seed: int = 42,
    ) -> list[BenchmarkQuestion]:
        """Load questions for a benchmark.

        Args:
            benchmark: Benchmark ID or BenchmarkType enum.
            sample: Random sample size (None = all questions).
            seed: Random seed for reproducible sampling.

        Returns:
            List of BenchmarkQuestion objects.
        """
        if isinstance(benchmark, str):
            benchmark = BenchmarkType(benchmark)

        if benchmark == BenchmarkType.GPQA_DIAMOND:
            return _load_gpqa_diamond(sample=sample, seed=seed)

        elif benchmark == BenchmarkType.MMLU_PRO:
            return _load_mmlu_pro_stem(sample=sample, seed=seed)

        else:
            # Built-in datasets (AIME, TruthfulQA, GSM, HaluEval)
            from app.services.benchmarks.real_benchmarks import RealBenchmarkRunner
            runner = RealBenchmarkRunner()
            return runner.load_questions(benchmark)

    def available(self) -> list[dict[str, Any]]:
        """List all available benchmarks with metadata."""
        return [
            {
                "id": "gpqa_diamond",
                "name": "GPQA-Diamond",
                "description": "198 PhD-level science questions. Experts score 81%, non-experts 22%.",
                "total": 198,
                "source": "github.com/idavidrein/gpqa",
                "file": "gpqa_diamond.csv",
                "available": (_DATA_DIR / "gpqa_diamond.csv").exists(),
            },
            {
                "id": "mmlu_pro",
                "name": "MMLU-Pro STEM",
                "description": "5878 graduate STEM questions across 6 categories.",
                "total": 5878,
                "source": "huggingface.co/datasets/TIGER-Lab/MMLU-Pro",
                "file": "mmlu_pro_stem.json",
                "available": (_DATA_DIR / "mmlu_pro_stem.json").exists(),
            },
            {
                "id": "aime",
                "name": "AIME 2025 I",
                "description": "15 competition math questions from MAA.",
                "total": 15,
                "source": "artofproblemsolving.com",
                "available": True,
            },
            {
                "id": "truthfulqa",
                "name": "TruthfulQA",
                "description": "20 hallucination-resistance questions.",
                "total": 20,
                "source": "github.com/sylinrl/TruthfulQA",
                "available": True,
            },
            {
                "id": "gsm_symbolic",
                "name": "GSM-Symbolic (Apple)",
                "description": "20 adversarial math with distractors.",
                "total": 20,
                "source": "github.com/apple/ml-gsm-symbolic",
                "available": True,
            },
            {
                "id": "halueval",
                "name": "HaluEval",
                "description": "10 hallucination detection questions.",
                "total": 10,
                "source": "github.com/RUCAIBox/HaluEval",
                "available": True,
            },
        ]
