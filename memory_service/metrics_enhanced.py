"""
Enhanced Metrics with Histogram Support for Better SLO Monitoring.

Promotes p95 to histograms (expose buckets) for better SLO burn-rate alerts.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Any, List

from memory_service.metrics import _COUNTERS, _LATENCIES, snapshot as base_snapshot


# Histogram buckets for latency (in milliseconds)
LATENCY_BUCKETS = [5, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000]


def _compute_histogram(values: List[float], buckets: List[int]) -> Dict[str, int]:
    """Compute histogram for latency values."""
    histogram = {f"le_{bucket}": 0 for bucket in buckets}
    histogram["+Inf"] = len(values)
    
    for value_ms in values:
        value_ms_scaled = value_ms * 1000  # Convert to milliseconds
        for bucket in buckets:
            if value_ms_scaled <= bucket:
                histogram[f"le_{bucket}"] += 1
    
    return histogram


def snapshot_with_histograms() -> Dict[str, Any]:
    """Get metrics snapshot with histogram buckets."""
    base = base_snapshot()
    
    # Add histograms for latency metrics
    for metric, values in _LATENCIES.items():
        if not values:
            continue
        
        histogram = _compute_histogram(values, LATENCY_BUCKETS)
        base[f"{metric}_histogram"] = histogram
        
        # Add bucket counts
        for bucket in LATENCY_BUCKETS:
            base[f"{metric}_bucket_le_{bucket}"] = histogram[f"le_{bucket}"]
    
    return base


def get_slo_burn_rate(
    metric_name: str,
    slo_threshold_ms: float,
    window_minutes: int = 5
) -> Dict[str, Any]:
    """
    Calculate SLO burn rate for a metric.
    
    Burn rate indicates how fast error budget is being consumed.
    """
    if metric_name not in _LATENCIES:
        return {"error": f"Metric {metric_name} not found"}
    
    values = _LATENCIES[metric_name]
    if not values:
        return {"error": "No data available"}
    
    # Filter to recent window (simplified - in production would use time windows)
    recent_values = values[-100:] if len(values) > 100 else values
    
    # Count violations
    violations = sum(1 for v in recent_values if v * 1000 > slo_threshold_ms)
    total = len(recent_values)
    violation_rate = violations / total if total > 0 else 0.0
    
    # Calculate burn rate (simplified)
    # In production, this would use actual time windows
    burn_rate = violation_rate * (60 / window_minutes)  # Violations per hour
    
    return {
        "metric": metric_name,
        "slo_threshold_ms": slo_threshold_ms,
        "window_minutes": window_minutes,
        "total_samples": total,
        "violations": violations,
        "violation_rate": violation_rate,
        "burn_rate_per_hour": burn_rate,
        "status": "critical" if burn_rate > 1.0 else "warning" if burn_rate > 0.5 else "ok"
    }

