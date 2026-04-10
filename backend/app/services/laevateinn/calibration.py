"""P5: Confidence Calibration -- make confidence scores MEAN something.

The gap: when Mythos says "85% confident," it's a guess. When Daena says
"85% confident," we want it to be RIGHT 85% of the time. That's calibration.

This engine tracks prediction accuracy over time and adjusts the
confidence multiplier. If Laevateinn has been overconfident (says 90%
but is right 70% of the time), the calibration factor drops below 1.0.
If underconfident, it rises above 1.0.

Integration: runs at delivery time to adjust the final confidence score.
Needs accumulated data (minimum 20 data points) to be useful.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    CalibrationRecord,
    CalibrationResult,
)

logger = get_logger(__name__)

_DEFAULT_STORE_PATH = Path("var/laevateinn/calibration.jsonl")
_MIN_DATA_POINTS = 20  # Minimum records before calibration kicks in


class ConfidenceCalibrator:
    """Adjusts confidence scores based on historical accuracy.

    Protocol:
    1. At delivery: look up calibration factor from history
    2. Apply: calibrated = raw * factor
    3. After user feedback: record whether prediction was correct
    4. Periodically: recalculate factor from accumulated records

    The calibration factor converges toward the true accuracy ratio:
        factor = actual_accuracy / average_predicted_confidence

    Example: if we predict 0.85 average and are right 0.70 of the time,
    factor = 0.70 / 0.85 = 0.82. Future 0.85 predictions become 0.70.

    Args:
        store_path: Path to calibration data store.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self._store_path = store_path or _DEFAULT_STORE_PATH
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: list[CalibrationRecord] | None = None
        self._factor: float | None = None

    def calibrate(self, raw_confidence: float) -> CalibrationResult:
        """Apply calibration to a raw confidence score.

        Args:
            raw_confidence: The unadjusted confidence from the pipeline.

        Returns:
            CalibrationResult with adjusted confidence.
        """
        records = self._load_records()

        if len(records) < _MIN_DATA_POINTS:
            # Not enough data -- return raw with low reliability
            return CalibrationResult(
                raw_confidence=raw_confidence,
                calibrated_confidence=raw_confidence,
                calibration_factor=1.0,
                data_points=len(records),
                reliability="low",
            )

        factor = self._compute_factor(records)

        calibrated = max(0.05, min(raw_confidence * factor, 0.99))

        # Determine reliability based on data volume
        if len(records) >= 100:
            reliability = "high"
        elif len(records) >= 50:
            reliability = "medium"
        else:
            reliability = "low"

        return CalibrationResult(
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            calibration_factor=factor,
            data_points=len(records),
            reliability=reliability,
        )

    def record_outcome(
        self,
        predicted_confidence: float,
        was_correct: bool,
        query_hash: str = "",
    ) -> None:
        """Record whether a prediction was correct for future calibration.

        Call this when user feedback indicates the answer was right or wrong.

        Args:
            predicted_confidence: What we predicted.
            was_correct: Whether the answer was actually correct.
            query_hash: Optional hash for deduplication.
        """
        record = CalibrationRecord(
            predicted_confidence=predicted_confidence,
            was_correct=was_correct,
            query_hash=query_hash,
        )

        try:
            with open(self._store_path, "a") as f:
                data = {
                    "predicted_confidence": record.predicted_confidence,
                    "was_correct": record.was_correct,
                    "query_hash": record.query_hash,
                    "timestamp": record.timestamp,
                }
                f.write(json.dumps(data) + "\n")
            self._cache = None  # Invalidate
            self._factor = None
        except Exception as e:
            logger.warning("calibration_write_error", error=str(e))

    def get_stats(self) -> dict:
        """Get calibration statistics for monitoring."""
        records = self._load_records()
        if not records:
            return {"data_points": 0, "factor": 1.0}

        correct = sum(1 for r in records if r.was_correct)
        avg_predicted = sum(r.predicted_confidence for r in records) / len(records)
        actual_accuracy = correct / len(records)

        return {
            "data_points": len(records),
            "factor": self._compute_factor(records),
            "average_predicted": round(avg_predicted, 3),
            "actual_accuracy": round(actual_accuracy, 3),
            "overconfident": avg_predicted > actual_accuracy,
        }

    def _compute_factor(self, records: list[CalibrationRecord]) -> float:
        """Compute the calibration factor from historical data."""
        if self._factor is not None:
            return self._factor

        if not records:
            return 1.0

        avg_predicted = sum(r.predicted_confidence for r in records) / len(records)
        if avg_predicted < 0.01:
            return 1.0

        correct = sum(1 for r in records if r.was_correct)
        actual_accuracy = correct / len(records)

        # Factor = actual / predicted -- clamp to reasonable range
        factor = actual_accuracy / avg_predicted
        factor = max(0.5, min(factor, 1.5))

        # Smooth: blend with 1.0 when data is sparse
        data_weight = min(len(records) / 100, 1.0)
        factor = (factor * data_weight) + (1.0 * (1 - data_weight))

        self._factor = round(factor, 4)
        return self._factor

    def _load_records(self) -> list[CalibrationRecord]:
        """Load calibration records from JSONL store."""
        if self._cache is not None:
            return self._cache

        records: list[CalibrationRecord] = []
        if not self._store_path.exists():
            self._cache = records
            return records

        try:
            with open(self._store_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    records.append(CalibrationRecord(
                        predicted_confidence=data["predicted_confidence"],
                        was_correct=data["was_correct"],
                        query_hash=data.get("query_hash", ""),
                        timestamp=data.get("timestamp", 0),
                    ))
        except Exception as e:
            logger.warning("calibration_load_error", error=str(e))

        # Keep only last 500 records (recency bias)
        records = records[-500:]
        self._cache = records
        return records
