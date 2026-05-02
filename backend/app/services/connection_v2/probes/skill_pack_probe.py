"""SkillPackProbe -- structured "not callable" outcome for skill_pack rows.

PR-CONN-V2-SEED-IMPORT (2026-05-02): skill packs are capability or
instruction bundles that ship docs / prompt templates / playbooks --
they are NOT callable surfaces by themselves. The default behavior of
``run_probe`` (post PR-CONNECTIONS-TRUTH-CLEANUP) returns
``probe_unavailable`` when no probe is registered for a kind. That is
already honest, but a registered SkillPackProbe gives a clearer reason
("skill_pack: capability bundle, not a callable surface") and proves
the design intent: skill_pack rows have a probe handler that
deliberately refuses to flip ``callable=true``.

Contract:
- Always returns ``ProbeResult(success=False, failure_dim="callable",
  failure_reason="skill_pack: capability/instruction bundle, not a
  callable surface").
- Never raises.
- Never inspects ``row.config`` for callable-ness because skill packs
  are categorically not callable.
"""

from __future__ import annotations

from app.models.connection_v2 import ConnectionKind, ConnectionV2
from app.services.connection_v2.probe import Probe, ProbeResult


SKILL_PACK_FAILURE_REASON = (
    "skill_pack: capability/instruction bundle, not a callable surface"
)


class SkillPackProbe(Probe):
    """Probe that always reports skill_pack rows as non-callable."""

    kind = ConnectionKind.SKILL_PACK

    async def run(self, row: ConnectionV2) -> ProbeResult:
        return ProbeResult(
            success=False,
            failure_dim="callable",
            failure_reason=SKILL_PACK_FAILURE_REASON,
        )


def install_skill_pack_probe() -> None:
    """Register the SkillPackProbe. Idempotent (last write wins)."""
    from app.services.connection_v2.probe import register_probe
    register_probe(SkillPackProbe())


__all__ = [
    "SKILL_PACK_FAILURE_REASON",
    "SkillPackProbe",
    "install_skill_pack_probe",
]
