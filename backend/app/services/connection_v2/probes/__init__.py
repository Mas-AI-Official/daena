"""ConnectionV2 per-kind probe implementations.

Each probe replaces the default NoopProbe (registered in ``probe.py``)
for one ConnectionKind. Calling ``install_all_probes()`` is the
canonical wiring step -- safe to call multiple times.
"""

from __future__ import annotations

from app.services.connection_v2.probes.cli_runtime_probe import (
    CliRuntimeProbe,
    install_cli_runtime_probe,
)
from app.services.connection_v2.probes.mcp_server_probe import (
    McpServerProbe,
    install_mcp_server_probe,
)
from app.services.connection_v2.probes.oauth_app_probe import (
    OAuthAppProbe,
    install_oauth_app_probe,
)
from app.services.connection_v2.probes.provider_probe import (
    ProviderProbe,
    install_provider_probe,
)
from app.services.connection_v2.probes.skill_pack_probe import (
    SkillPackProbe,
    install_skill_pack_probe,
)


def install_all_probes() -> None:
    """Register every per-kind probe. Idempotent."""
    install_provider_probe()
    install_skill_pack_probe()
    install_mcp_server_probe()
    install_cli_runtime_probe()
    install_oauth_app_probe()


__all__ = [
    "CliRuntimeProbe",
    "McpServerProbe",
    "OAuthAppProbe",
    "ProviderProbe",
    "SkillPackProbe",
    "install_all_probes",
    "install_cli_runtime_probe",
    "install_mcp_server_probe",
    "install_oauth_app_probe",
    "install_provider_probe",
    "install_skill_pack_probe",
]
