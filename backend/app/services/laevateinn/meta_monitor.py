"""Meta-Laevateinn Monitor -- Laevateinn watching Laevateinn.

Tracks which pipeline stages help vs hurt, which models win debates
most often, whether the difficulty estimator is calibrated, and
generates constitutional self-improvement rules from failure patterns.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from uuid import uuid4

import aiosqlite

from app.core.logging import get_logger
from app.services.laevateinn.types import LaevateinnTrace

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StageMetric:
    """Aggregated performance for a single pipeline stage."""

    stage_name: str
    invocations: int
    avg_latency_ms: float
    improvement_rate: float  # % of times this stage improved the output
    skip_rate: float  # % of times this stage was skipped (trivial queries)


@dataclass(slots=True)
class ModelMetric:
    """Aggregated debate performance for a single model."""

    model_id: str
    debate_wins: int
    debate_losses: int
    win_rate: float
    avg_confidence: float
    avg_latency_ms: float
    judge_uses: int  # times used as AMD judge


@dataclass(slots=True)
class DifficultyCalibration:
    """A single difficulty prediction vs actual outcome."""

    predicted: str  # trivial / standard / hard / brutal
    actual_depth_used: int
    was_calibrated: bool  # did the prediction match what was actually needed?


@dataclass(slots=True)
class MetaReport:
    """Periodic self-assessment report."""

    period_start: float
    period_end: float
    total_queries: int
    stage_metrics: list[StageMetric]
    model_metrics: list[ModelMetric]
    calibration_accuracy: float
    improvement_suggestions: list[str]
    generated_rules: list[str]


# ---------------------------------------------------------------------------
# Difficulty-to-depth mapping for calibration checks
# ---------------------------------------------------------------------------

_DIFFICULTY_EXPECTED_DEPTH: dict[str, tuple[int, int]] = {
    "TRIVIAL": (0, 0),
    "STANDARD": (1, 1),
    "HARD": (2, 3),
    "BRUTAL": (4, 5),
}

# ---------------------------------------------------------------------------
# SQL schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           TEXT PRIMARY KEY,
    timestamp    REAL NOT NULL,
    query_hash   TEXT NOT NULL,
    difficulty   TEXT NOT NULL,
    stages       TEXT NOT NULL,
    total_latency_ms INTEGER NOT NULL,
    confidence   REAL NOT NULL,
    winner_model TEXT NOT NULL,
    depth_used   INTEGER NOT NULL,
    depth_budget INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS model_debates (
    id         TEXT PRIMARY KEY,
    timestamp  REAL NOT NULL,
    winner     TEXT NOT NULL,
    losers     TEXT NOT NULL,
    confidence REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS difficulty_calibrations (
    id           TEXT PRIMARY KEY,
    timestamp    REAL NOT NULL,
    predicted    TEXT NOT NULL,
    actual_depth INTEGER NOT NULL
);
"""

# ---------------------------------------------------------------------------
# MetaMonitor
# ---------------------------------------------------------------------------


class MetaMonitor:
    """Laevateinn self-monitoring and constitutional rule generation."""

    def __init__(self, db_path: str = "data/laevateinn_meta.db") -> None:
        self._db_path = db_path
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create database tables if they do not exist."""
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA_SQL)
            await db.commit()
        self._initialized = True
        logger.info("MetaMonitor initialized (db=%s)", self._db_path)

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    async def record_pipeline_run(self, trace: LaevateinnTrace) -> None:
        """Extract metrics from a full pipeline trace and persist them."""
        query_hash = hashlib.sha256(trace.query.encode()).hexdigest()[:16]

        difficulty = "STANDARD"
        depth_budget = 1
        if trace.compute_profile is not None:
            difficulty = trace.compute_profile.difficulty.value
            depth_budget = trace.compute_profile.recursion_depth

        winner_model = ""
        confidence = 0.0
        if trace.debate is not None:
            winner_model = trace.debate.winner_model
            confidence = trace.debate.confidence
        elif trace.delivery is not None:
            confidence = trace.delivery.confidence_score

        depth_used = 0
        if trace.depth is not None:
            depth_used = trace.depth.depth_used

        stages_json = json.dumps(
            [
                {
                    "name": s,
                    "latency_ms": self._stage_latency(trace, s),
                }
                for s in trace.stages_executed
            ]
        )

        row_id = uuid4().hex
        now = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO pipeline_runs "
                "(id, timestamp, query_hash, difficulty, stages, "
                "total_latency_ms, confidence, winner_model, depth_used, depth_budget) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row_id,
                    now,
                    query_hash,
                    difficulty,
                    stages_json,
                    trace.total_latency_ms,
                    confidence,
                    winner_model,
                    depth_used,
                    depth_budget,
                ),
            )
            await db.commit()

        # Also record difficulty calibration from the trace
        await self.record_difficulty_prediction(difficulty, depth_used)

        logger.debug("Recorded pipeline run %s (difficulty=%s)", row_id, difficulty)

    async def record_model_debate(
        self, winner: str, losers: list[str], confidence: float
    ) -> None:
        """Record the outcome of a single adversarial model debate."""
        row_id = uuid4().hex
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO model_debates (id, timestamp, winner, losers, confidence) "
                "VALUES (?, ?, ?, ?, ?)",
                (row_id, now, winner, json.dumps(losers), confidence),
            )
            await db.commit()
        logger.debug("Recorded debate win for %s over %s", winner, losers)

    async def record_difficulty_prediction(
        self, predicted: str, actual_depth: int
    ) -> None:
        """Record a difficulty prediction vs what depth was actually used."""
        row_id = uuid4().hex
        now = time.time()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO difficulty_calibrations "
                "(id, timestamp, predicted, actual_depth) VALUES (?, ?, ?, ?)",
                (row_id, now, predicted.upper(), actual_depth),
            )
            await db.commit()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    async def get_stage_metrics(self, *, days: int = 7) -> list[StageMetric]:
        """Compute per-stage performance metrics over the given window."""
        cutoff = time.time() - days * 86400
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT stages, difficulty FROM pipeline_runs WHERE timestamp >= ?",
                (cutoff,),
            )
            rows = await cursor.fetchall()

        # Accumulate per-stage stats
        stats: dict[str, dict[str, float]] = {}
        total_runs = len(rows)

        for row in rows:
            stages: list[dict[str, object]] = json.loads(row["stages"])
            difficulty = row["difficulty"]
            seen_in_run: set[str] = set()

            for stage in stages:
                name = str(stage["name"])
                latency = float(stage.get("latency_ms", 0))
                seen_in_run.add(name)

                if name not in stats:
                    stats[name] = {
                        "invocations": 0,
                        "total_latency": 0.0,
                        "improvements": 0,
                        "skips": 0,
                    }

                stats[name]["invocations"] += 1
                stats[name]["total_latency"] += latency

                # A stage with latency > 0 that ran is considered an improvement
                # unless it was a trivial query (where it adds overhead)
                if difficulty == "TRIVIAL":
                    stats[name]["skips"] += 1
                elif latency > 0:
                    stats[name]["improvements"] += 1

        # Build remaining skip counts for stages that exist but were not in a run
        all_known = set(stats.keys())
        for row in rows:
            stages_list: list[dict[str, object]] = json.loads(row["stages"])
            present = {str(s["name"]) for s in stages_list}
            for missing in all_known - present:
                stats[missing]["skips"] += 1

        result: list[StageMetric] = []
        for name, s in sorted(stats.items()):
            inv = int(s["invocations"])
            avg_lat = s["total_latency"] / inv if inv else 0.0
            improvement = s["improvements"] / inv * 100 if inv else 0.0
            skip = s["skips"] / total_runs * 100 if total_runs else 0.0
            result.append(
                StageMetric(
                    stage_name=name,
                    invocations=inv,
                    avg_latency_ms=round(avg_lat, 2),
                    improvement_rate=round(improvement, 2),
                    skip_rate=round(skip, 2),
                )
            )
        return result

    async def get_model_metrics(self, *, days: int = 7) -> list[ModelMetric]:
        """Compute per-model debate performance over the given window."""
        cutoff = time.time() - days * 86400
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT winner, losers, confidence FROM model_debates "
                "WHERE timestamp >= ?",
                (cutoff,),
            )
            rows = await cursor.fetchall()

        # Also pull judge info from pipeline_runs
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT winner_model, total_latency_ms FROM pipeline_runs "
                "WHERE timestamp >= ? AND winner_model != ''",
                (cutoff,),
            )
            run_rows = await cursor.fetchall()

        model_stats: dict[str, dict[str, float]] = {}

        def _ensure(mid: str) -> None:
            if mid not in model_stats:
                model_stats[mid] = {
                    "wins": 0,
                    "losses": 0,
                    "total_confidence": 0.0,
                    "total_latency": 0.0,
                    "latency_count": 0,
                    "judge_uses": 0,
                }

        for row in rows:
            winner = row["winner"]
            losers: list[str] = json.loads(row["losers"])
            conf = float(row["confidence"])

            _ensure(winner)
            model_stats[winner]["wins"] += 1
            model_stats[winner]["total_confidence"] += conf

            for loser in losers:
                _ensure(loser)
                model_stats[loser]["losses"] += 1

        for row in run_rows:
            mid = row["winner_model"]
            _ensure(mid)
            model_stats[mid]["judge_uses"] += 1
            model_stats[mid]["total_latency"] += float(row["total_latency_ms"])
            model_stats[mid]["latency_count"] += 1

        result: list[ModelMetric] = []
        for mid, s in sorted(model_stats.items()):
            total = s["wins"] + s["losses"]
            win_rate = s["wins"] / total * 100 if total else 0.0
            avg_conf = (
                s["total_confidence"] / s["wins"] if s["wins"] else 0.0
            )
            avg_lat = (
                s["total_latency"] / s["latency_count"]
                if s["latency_count"]
                else 0.0
            )
            result.append(
                ModelMetric(
                    model_id=mid,
                    debate_wins=int(s["wins"]),
                    debate_losses=int(s["losses"]),
                    win_rate=round(win_rate, 2),
                    avg_confidence=round(avg_conf, 4),
                    avg_latency_ms=round(avg_lat, 2),
                    judge_uses=int(s["judge_uses"]),
                )
            )
        return result

    async def get_calibration_accuracy(self, *, days: int = 7) -> float:
        """Return the % of difficulty predictions that matched actual depth."""
        cutoff = time.time() - days * 86400
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT predicted, actual_depth FROM difficulty_calibrations "
                "WHERE timestamp >= ?",
                (cutoff,),
            )
            rows = await cursor.fetchall()

        if not rows:
            return 100.0  # no data means nothing miscalibrated yet

        correct = 0
        for row in rows:
            predicted = row["predicted"]
            actual = int(row["actual_depth"])
            lo, hi = _DIFFICULTY_EXPECTED_DEPTH.get(predicted, (0, 99))
            if lo <= actual <= hi:
                correct += 1

        return round(correct / len(rows) * 100, 2)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    async def generate_report(self, *, days: int = 7) -> MetaReport:
        """Generate a comprehensive meta-report for the given time window."""
        cutoff = time.time() - days * 86400
        now = time.time()

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM pipeline_runs WHERE timestamp >= ?",
                (cutoff,),
            )
            row = await cursor.fetchone()
            total_queries = row[0] if row else 0

        stage_metrics = await self.get_stage_metrics(days=days)
        model_metrics = await self.get_model_metrics(days=days)
        calibration = await self.get_calibration_accuracy(days=days)
        rules = await self.generate_rules(days=days)

        suggestions = self._build_suggestions(stage_metrics, model_metrics, calibration)

        return MetaReport(
            period_start=cutoff,
            period_end=now,
            total_queries=total_queries,
            stage_metrics=stage_metrics,
            model_metrics=model_metrics,
            calibration_accuracy=calibration,
            improvement_suggestions=suggestions,
            generated_rules=rules,
        )

    # ------------------------------------------------------------------
    # Constitutional self-improvement
    # ------------------------------------------------------------------

    async def generate_rules(self, *, days: int = 7) -> list[str]:
        """Generate constitutional self-improvement rules from failure patterns."""
        stage_metrics = await self.get_stage_metrics(days=days)
        model_metrics = await self.get_model_metrics(days=days)
        calibration = await self.get_calibration_accuracy(days=days)

        rules: list[str] = []

        # Rule: skip underperforming stages
        for sm in stage_metrics:
            if sm.invocations >= 5 and sm.improvement_rate < 30.0:
                rules.append(
                    f"RULE: Stage '{sm.stage_name}' improved output only "
                    f"{sm.improvement_rate:.1f}% of the time over {sm.invocations} "
                    f"runs. Consider skipping for low-complexity queries."
                )

        # Rule: promote dominant models to default judge
        for mm in model_metrics:
            total = mm.debate_wins + mm.debate_losses
            if total >= 5 and mm.win_rate > 70.0:
                rules.append(
                    f"RULE: Model '{mm.model_id}' wins {mm.win_rate:.1f}% of debates "
                    f"({mm.debate_wins}W/{mm.debate_losses}L). "
                    f"Recommend as default AMD judge."
                )

        # Rule: recalibrate difficulty thresholds
        if calibration < 60.0:
            rules.append(
                f"RULE: Difficulty calibration accuracy is {calibration:.1f}% "
                f"(below 60% threshold). Recalibrate difficulty thresholds -- "
                f"predictions are not matching actual compute depth required."
            )

        # Rule: flag models with very low win rates
        for mm in model_metrics:
            total = mm.debate_wins + mm.debate_losses
            if total >= 5 and mm.win_rate < 20.0:
                rules.append(
                    f"RULE: Model '{mm.model_id}' wins only {mm.win_rate:.1f}% "
                    f"of debates. Consider removing from debate pool or "
                    f"restricting to specific query types."
                )

        # Rule: stages with very high skip rates may be redundant
        for sm in stage_metrics:
            if sm.invocations >= 5 and sm.skip_rate > 80.0:
                rules.append(
                    f"RULE: Stage '{sm.stage_name}' is skipped {sm.skip_rate:.1f}% "
                    f"of the time. Evaluate whether it should be lazy-loaded "
                    f"rather than always initialized."
                )

        if not rules:
            rules.append(
                "RULE: No constitutional improvements needed. All metrics "
                "are within acceptable thresholds."
            )

        logger.info("Generated %d constitutional rules", len(rules))
        return rules

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stage_latency(trace: LaevateinnTrace, stage_name: str) -> int:
        """Extract latency for a named stage from the trace."""
        mapping: dict[str, int] = {
            "comprehension": (
                trace.comprehension.processing_time_ms
                if trace.comprehension
                else 0
            ),
            "debate": (
                trace.debate.total_latency_ms if trace.debate else 0
            ),
            "depth": (
                trace.depth.total_latency_ms if trace.depth else 0
            ),
        }
        return mapping.get(stage_name.lower(), 0)

    @staticmethod
    def _build_suggestions(
        stages: list[StageMetric],
        models: list[ModelMetric],
        calibration: float,
    ) -> list[str]:
        """Build human-readable improvement suggestions from metrics."""
        suggestions: list[str] = []

        slow_stages = [s for s in stages if s.avg_latency_ms > 500]
        if slow_stages:
            names = ", ".join(s.stage_name for s in slow_stages)
            suggestions.append(
                f"Stages with avg latency >500ms: {names}. "
                f"Investigate caching or parallel execution."
            )

        low_improvement = [
            s for s in stages if s.invocations >= 5 and s.improvement_rate < 30.0
        ]
        if low_improvement:
            names = ", ".join(s.stage_name for s in low_improvement)
            suggestions.append(
                f"Stages with <30% improvement rate: {names}. "
                f"These may be adding latency without value."
            )

        if calibration < 60.0:
            suggestions.append(
                f"Difficulty calibration is {calibration:.1f}%. "
                f"The difficulty estimator needs retraining or threshold adjustment."
            )

        dominant = [
            m for m in models if m.debate_wins + m.debate_losses >= 5 and m.win_rate > 70.0
        ]
        if dominant:
            names = ", ".join(m.model_id for m in dominant)
            suggestions.append(
                f"Model(s) dominating debates: {names}. "
                f"Consider promoting to default or reducing debate rounds."
            )

        if not suggestions:
            suggestions.append("All metrics within healthy ranges. No action needed.")

        return suggestions
