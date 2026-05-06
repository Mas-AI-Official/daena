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
# Side-effect import: registers the opportunity_discovery handler
# with routine_autonomy on first import.
from app.services.business_pipeline import routine_handler  # noqa: F401
# Sprint-20 PR-2: register public source adapters declared in
# backend/.opportunity_sources.json (gitignored). Missing config file
# is a no-op -- manual_seed remains the only source until the operator
# opts in.
from app.services.business_pipeline.sources import (
    register_public_sources_from_config,
)
register_public_sources_from_config()
from app.models.business import OPPORTUNITY_TYPES

__all__ = [
    "DiscoveredOpportunity",
    "OPPORTUNITY_TYPES",
    "DEFAULT_TOP_N",
    "register_source",
    "registered_sources",
    "register_public_sources_from_config",
    "run_discovery_loop",
    "score_opportunity",
    "SOURCE_REGISTRY",
]
