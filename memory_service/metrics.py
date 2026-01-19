from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Dict, List

MAX_SAMPLES = 1000

_COUNTERS: DefaultDict[str, int] = defaultdict(int)
_LATENCIES: DefaultDict[str, List[float]] = defaultdict(list)
_CPU_TIMES: DefaultDict[str, List[float]] = defaultdict(list)  # CPU time per operation
_COSTS: DefaultDict[str, float] = defaultdict(float)  # Track costs by category
_OPERATION_COUNTS: DefaultDict[str, int] = defaultdict(int)  # Operation counts (encode, decode, etc.)


def incr(counter: str, amount: int = 1) -> None:
    _COUNTERS[counter] += amount


def observe(metric: str, seconds: float) -> None:
    """Observe latency metric with overflow protection."""
    try:
        bucket = _LATENCIES[metric]
        bucket.append(seconds)
        if len(bucket) > MAX_SAMPLES:
            del bucket[0]
    except (MemoryError, AttributeError, TypeError) as e:
        # Graceful degradation: if metrics fail, don't crash the system
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Metrics observation failed for {metric}: {e}")


def observe_cpu_time(metric: str, cpu_seconds: float) -> None:
    """Track CPU time (process time) separately from wall-clock time."""
    try:
        bucket = _CPU_TIMES[metric]
        bucket.append(cpu_seconds)
        if len(bucket) > MAX_SAMPLES:
            del bucket[0]
    except (MemoryError, AttributeError, TypeError) as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"CPU time observation failed for {metric}: {e}")


def incr_operation(operation: str, amount: int = 1) -> None:
    """Track operation counts (e.g., encode, decode, compress)."""
    _OPERATION_COUNTS[operation] += amount


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((percentile / 100.0) * (len(ordered) - 1)))
    return ordered[index]


def track_cost(category: str, amount: float) -> None:
    """Track costs by category (e.g., 'llm_api', 'storage', 'compute')."""
    _COSTS[category] += amount


def snapshot() -> Dict[str, Any]:
    """Generate metrics snapshot with error handling."""
    try:
        snap: Dict[str, Any] = dict(_COUNTERS)
        for metric, values in _LATENCIES.items():
            if not values:
                continue
            try:
                snap[f"{metric}_p95_ms"] = _percentile(values, 95.0) * 1000.0
                snap[f"{metric}_avg_ms"] = (sum(values) / len(values)) * 1000.0
            except (ValueError, TypeError, ZeroDivisionError) as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to compute percentile for {metric}: {e}")
        
        # CPU time metrics
        for metric, values in _CPU_TIMES.items():
            if not values:
                continue
            try:
                snap[f"{metric}_cpu_p95_ms"] = _percentile(values, 95.0) * 1000.0
                snap[f"{metric}_cpu_avg_ms"] = (sum(values) / len(values)) * 1000.0
            except (ValueError, TypeError, ZeroDivisionError) as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to compute CPU percentile for {metric}: {e}")
        
        # Operation counts
        snap["operations"] = dict(_OPERATION_COUNTS)
        
        # Hot vs cold access tracking (for load balancing)
        l1_hits = snap.get("l1_hits", 0)
        nbmf_reads = snap.get("nbmf_reads", 0)
        # Estimate: L1 reads are "hot", L3 reads are "cold" (L2 is warm)
        hot_access_count = l1_hits
        cold_access_count = max(0, nbmf_reads - l1_hits)  # Approximate cold reads
        snap["access_patterns"] = {
            "hot_access_count": hot_access_count,
            "cold_access_count": cold_access_count,
            "hot_cold_ratio": hot_access_count / cold_access_count if cold_access_count > 0 else (float('inf') if hot_access_count > 0 else 0.0),
            "total_accesses": nbmf_reads
        }
    except Exception as e:
        # Return minimal snapshot on failure
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Metrics snapshot generation failed: {e}")
        return {"error": str(e), "status": "degraded"}
    divergence = snap.get("divergence_events", 0)
    writes = snap.get("nbmf_writes", 0)
    snap["divergence_rate"] = divergence / writes if writes else 0.0

    # CAS efficiency metrics
    cas_hits = snap.get("llm_cas_hit", 0)
    cas_misses = snap.get("llm_cas_miss", 0)
    near_dup_reuse = snap.get("llm_near_dup_reuse", 0)
    total_llm_requests = cas_hits + cas_misses + near_dup_reuse
    if total_llm_requests > 0:
        snap["llm_cas_hit_rate"] = (cas_hits + near_dup_reuse) / total_llm_requests
        snap["llm_exact_match_rate"] = cas_hits / total_llm_requests
        snap["llm_near_dup_rate"] = near_dup_reuse / total_llm_requests

    # Cost tracking metrics
    snap["costs"] = dict(_COSTS)
    snap["total_cost_usd"] = sum(_COSTS.values())
    
    # Calculate cost savings from CAS reuse
    if cas_hits + near_dup_reuse > 0:
        # Estimate: each CAS hit saves ~$0.01-0.10 depending on model
        # Using conservative estimate of $0.05 per request saved
        estimated_savings = (cas_hits + near_dup_reuse) * 0.05
        snap["estimated_cost_savings_usd"] = round(estimated_savings, 2)
        if snap["total_cost_usd"] > 0:
            snap["cost_savings_percentage"] = round((estimated_savings / snap["total_cost_usd"]) * 100, 2)
        else:
            snap["cost_savings_percentage"] = 0.0

    return snap
