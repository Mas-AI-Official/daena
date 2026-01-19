"""
Prometheus metrics for SEC-Loop.

Tracks:
- sec_promoted_total: Total abstracts promoted
- sec_rejected_total: Total abstracts rejected
- sec_retention_delta: Retention drift metric
"""

from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Prometheus metrics (optional, falls back to memory_service metrics if not available)
try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
    
    # Counters
    sec_promoted_total = Counter(
        'sec_promoted_total',
        'Total number of abstracts promoted to NBMF L2',
        ['department', 'status']
    )
    
    sec_rejected_total = Counter(
        'sec_rejected_total',
        'Total number of abstracts rejected',
        ['department', 'reason']
    )
    
    sec_cycles_total = Counter(
        'sec_cycles_total',
        'Total number of SEC-Loop cycles run',
        ['department', 'status']
    )
    
    # Histograms
    sec_retention_delta = Histogram(
        'sec_retention_delta',
        'Retention drift delta vs baseline',
        ['department'],
        buckets=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1]
    )
    
    sec_knowledge_incorporation = Histogram(
        'sec_knowledge_incorporation',
        'Knowledge incorporation improvement %',
        ['department'],
        buckets=[0.01, 0.02, 0.03, 0.05, 0.10, 0.20]
    )
    
    sec_cycle_duration = Histogram(
        'sec_cycle_duration_seconds',
        'SEC-Loop cycle duration in seconds',
        ['department'],
        buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
    )
    
    # Gauges
    sec_pending_decisions = Gauge(
        'sec_pending_decisions',
        'Number of pending council decisions',
        ['department']
    )
    
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available, using fallback metrics")
    
    # Fallback to memory_service metrics
    from memory_service.metrics import incr, observe
    
    def sec_promoted_total(*args, **kwargs):
        incr("sec_promoted_total", 1)
    
    def sec_rejected_total(*args, **kwargs):
        incr("sec_rejected_total", 1)
    
    def sec_cycles_total(*args, **kwargs):
        incr("sec_cycles_total", 1)
    
    def sec_retention_delta(*args, **kwargs):
        observe("sec_retention_delta", kwargs.get("value", 0.0))
    
    def sec_knowledge_incorporation(*args, **kwargs):
        observe("sec_knowledge_incorporation", kwargs.get("value", 0.0))
    
    def sec_cycle_duration(*args, **kwargs):
        observe("sec_cycle_duration_seconds", kwargs.get("value", 0.0))
    
    def sec_pending_decisions(*args, **kwargs):
        pass  # Gauge not available in fallback


def record_promotion(department: str, status: str = "success"):
    """Record a promotion metric."""
    try:
        if PROMETHEUS_AVAILABLE:
            sec_promoted_total.labels(department=department, status=status).inc()
        else:
            sec_promoted_total()
    except Exception as e:
        logger.warning(f"Error recording promotion metric: {e}")


def record_rejection(department: str, reason: str = "unknown"):
    """Record a rejection metric."""
    try:
        if PROMETHEUS_AVAILABLE:
            sec_rejected_total.labels(department=department, reason=reason).inc()
        else:
            sec_rejected_total()
    except Exception as e:
        logger.warning(f"Error recording rejection metric: {e}")


def record_cycle(department: str, status: str = "completed", duration: float = 0.0):
    """Record a cycle metric."""
    try:
        if PROMETHEUS_AVAILABLE:
            sec_cycles_total.labels(department=department, status=status).inc()
            sec_cycle_duration.labels(department=department).observe(duration)
        else:
            sec_cycles_total()
            sec_cycle_duration(value=duration)
    except Exception as e:
        logger.warning(f"Error recording cycle metric: {e}")


def record_retention_delta(department: str, delta: float):
    """Record retention drift delta."""
    try:
        if PROMETHEUS_AVAILABLE:
            sec_retention_delta.labels(department=department).observe(delta)
        else:
            sec_retention_delta(value=delta)
    except Exception as e:
        logger.warning(f"Error recording retention delta: {e}")


def record_knowledge_incorporation(department: str, improvement: float):
    """Record knowledge incorporation improvement."""
    try:
        if PROMETHEUS_AVAILABLE:
            sec_knowledge_incorporation.labels(department=department).observe(improvement)
        else:
            sec_knowledge_incorporation(value=improvement)
    except Exception as e:
        logger.warning(f"Error recording knowledge incorporation: {e}")


def update_pending_decisions(department: str, count: int):
    """Update pending decisions gauge."""
    try:
        if PROMETHEUS_AVAILABLE:
            sec_pending_decisions.labels(department=department).set(count)
    except Exception as e:
        logger.warning(f"Error updating pending decisions: {e}")

