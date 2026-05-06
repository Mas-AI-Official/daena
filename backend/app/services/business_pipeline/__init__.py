"""Business pipeline -- Sprint-19 PR-1 (2026-05-06).

The growth loop:

  discoverer -> deduper -> scorer -> top-N cap -> Opportunity rows

Public surface (re-exports):

  * ``run_discovery_loop`` -- full async cycle
  * ``DiscoveredOpportunity`` -- pre-DB shape
  * ``OPPORTUNITY_TYPES`` -- locked enum
"""

from app.services.business_pipeline.discoverer import (
    DiscoveredOpportunity,
    register_source,
    registered_sources,
    SOURCE_REGISTRY,
)
from app.services.business_pipeline.scorer import score_opportunity
from app.services.business_pipeline.orchestrator import (
    DEFAULT_TOP_N,
    run_discovery_loop,
)
from app.models.business import OPPORTUNITY_TYPES

__all__ = [
    "DiscoveredOpportunity",
    "OPPORTUNITY_TYPES",
    "DEFAULT_TOP_N",
    "register_source",
    "registered_sources",
    "run_discovery_loop",
    "score_opportunity",
    "SOURCE_REGISTRY",
]
