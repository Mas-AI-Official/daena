"""ConnectionV2 per-kind probe implementations.

Each probe replaces the default NoopProbe (registered in ``probe.py``)
for one ConnectionKind. Calling ``install_all_probes()`` is the
canonical wiring step -- safe to call multiple times.
"""

from __future__ import annotations

from app.services.connection_v2.probes.provider_probe import (
    ProviderProbe,
    install_provider_probe,
)


def install_all_probes() -> None:
    """Register every per-kind probe. Idempotent."""
    install_provider_probe()


__all__ = ["ProviderProbe", "install_all_probes", "install_provider_probe"]
