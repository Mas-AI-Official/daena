"""ConnectionRegistryV2 service package (Phase 4b PR 1).

Behind ``settings.use_connection_registry_v2`` feature flag (default
False in production). When the flag is False, this package's functions
still execute correctly against the empty connection_v2 table -- they
just don't get called from the live UI paths.

Public API:
- ``derive_label(row, active_ops)`` -- pure function, 14 labels
- ``acquire_op_lock(...)`` / ``release_op_lock(...)`` / ``active_ops_for(...)``
- ``Probe`` interface + ``register_probe`` / ``run_probe``
- ``ConnectionRegistryV2`` -- CRUD + dual-read fallback
"""

from app.services.connection_v2.op_lock import (
    DEFAULT_TTLS,
    acquire_op_lock,
    active_ops_for,
    release_op_lock,
)
from app.services.connection_v2.probe import (
    Probe,
    ProbeResult,
    NoopProbe,
    PROBE_REGISTRY,
    register_probe,
    run_probe,
)
from app.services.connection_v2.registry import ConnectionRegistryV2
from app.services.connection_v2.state_machine import LABELS, derive_label

__all__ = [
    "derive_label",
    "LABELS",
    "DEFAULT_TTLS",
    "acquire_op_lock",
    "release_op_lock",
    "active_ops_for",
    "Probe",
    "ProbeResult",
    "NoopProbe",
    "PROBE_REGISTRY",
    "register_probe",
    "run_probe",
    "ConnectionRegistryV2",
]
