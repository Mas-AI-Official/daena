"""
Prometheus metrics for Enterprise-DNA system.
Tracks lineage, immune events, and DNA health metrics.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics (optional, falls back gracefully if not available)
try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
    
    # DNA Lineage metrics
    dna_lineage_promotions_total = Counter(
        'dna_lineage_promotions_total',
        'Total number of NBMF promotions with lineage records',
        ['promotion_from', 'promotion_to', 'tenant_id']
    )
    
    dna_lineage_chain_length = Histogram(
        'dna_lineage_chain_length',
        'Length of lineage chains',
        ['tenant_id'],
        buckets=[1, 2, 3, 5, 10, 20, 50, 100]
    )
    
    # Immune system metrics
    dna_immune_events_total = Counter(
        'dna_immune_events_total',
        'Total number of immune events',
        ['tenant_id', 'threat_type', 'threat_level']
    )
    
    dna_immune_quarantine_total = Counter(
        'dna_immune_quarantine_total',
        'Total number of quarantine actions',
        ['tenant_id', 'reason']
    )
    
    dna_immune_quorum_total = Counter(
        'dna_immune_quorum_total',
        'Total number of quorum requirements',
        ['tenant_id']
    )
    
    # DNA Health metrics
    dna_health_status = Gauge(
        'dna_health_status',
        'DNA health status (1=healthy, 0=degraded)',
        ['tenant_id']
    )
    
    dna_anomalies_24h = Gauge(
        'dna_anomalies_24h',
        'Number of anomalies in last 24 hours',
        ['tenant_id']
    )
    
    # Genome/Epigenome metrics
    dna_genome_updates_total = Counter(
        'dna_genome_updates_total',
        'Total number of genome updates',
        ['tenant_id', 'agent_id']
    )
    
    dna_epigenome_updates_total = Counter(
        'dna_epigenome_updates_total',
        'Total number of epigenome updates',
        ['tenant_id']
    )
    
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client not available, DNA metrics disabled")
    
    # Dummy metrics for graceful degradation
    class DummyMetric:
        def inc(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
    
    dna_lineage_promotions_total = DummyMetric()
    dna_lineage_chain_length = DummyMetric()
    dna_immune_events_total = DummyMetric()
    dna_immune_quarantine_total = DummyMetric()
    dna_immune_quorum_total = DummyMetric()
    dna_health_status = DummyMetric()
    dna_anomalies_24h = DummyMetric()
    dna_genome_updates_total = DummyMetric()
    dna_epigenome_updates_total = DummyMetric()


def record_lineage_promotion(promotion_from: str, promotion_to: str, tenant_id: str = "default"):
    """Record a lineage promotion metric."""
    if PROMETHEUS_AVAILABLE:
        dna_lineage_promotions_total.labels(
            promotion_from=promotion_from,
            promotion_to=promotion_to,
            tenant_id=tenant_id
        ).inc()


def record_lineage_chain_length(chain_length: int, tenant_id: str = "default"):
    """Record lineage chain length."""
    if PROMETHEUS_AVAILABLE:
        dna_lineage_chain_length.labels(tenant_id=tenant_id).observe(chain_length)


def record_immune_event(tenant_id: str, threat_type: str, threat_level: str):
    """Record an immune event."""
    if PROMETHEUS_AVAILABLE:
        dna_immune_events_total.labels(
            tenant_id=tenant_id,
            threat_type=threat_type,
            threat_level=threat_level
        ).inc()


def record_quarantine(tenant_id: str, reason: str):
    """Record a quarantine action."""
    if PROMETHEUS_AVAILABLE:
        dna_immune_quarantine_total.labels(
            tenant_id=tenant_id,
            reason=reason
        ).inc()


def record_quorum(tenant_id: str):
    """Record a quorum requirement."""
    if PROMETHEUS_AVAILABLE:
        dna_immune_quorum_total.labels(tenant_id=tenant_id).inc()


def update_health_status(tenant_id: str, is_healthy: bool):
    """Update DNA health status."""
    if PROMETHEUS_AVAILABLE:
        dna_health_status.labels(tenant_id=tenant_id).set(1 if is_healthy else 0)


def update_anomalies_24h(tenant_id: str, count: int):
    """Update anomalies count for last 24 hours."""
    if PROMETHEUS_AVAILABLE:
        dna_anomalies_24h.labels(tenant_id=tenant_id).set(count)


def record_genome_update(tenant_id: str, agent_id: str):
    """Record a genome update."""
    if PROMETHEUS_AVAILABLE:
        dna_genome_updates_total.labels(
            tenant_id=tenant_id,
            agent_id=agent_id
        ).inc()


def record_epigenome_update(tenant_id: str):
    """Record an epigenome update."""
    if PROMETHEUS_AVAILABLE:
        dna_epigenome_updates_total.labels(tenant_id=tenant_id).inc()

