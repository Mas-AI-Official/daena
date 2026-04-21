"""Zero-false-positive gate for security findings.

Enforces the "no exploit, no report" policy: any finding at tier
OPERATOR or higher must carry a matching ``EvidenceChain`` entry (or
an explicit founder override). Findings without evidence are
rejected before PDF generation. Prevents the failure mode shared by
every other autonomous-pentest tool in the 2026 landscape: shipping
unverified, LLM-hallucinated findings into customer reports.

Output shape of ``apply_gate``:
    accepted:  findings that passed the gate, ready for the report
    rejected:  findings blocked for missing evidence (with reason)
    overrides: findings that passed only because of founder override
               (still logged for audit)

All three lists are mutually exclusive.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.services.security.report_tiers import ReportTier

logger = get_logger(__name__)


# Tiers at which the gate is enforced. SCOUT and ANALYST are
# preliminary; OPERATOR+ feeds into remediation workflows that must
# be true.
_GATED_TIERS: set[ReportTier] = {
    ReportTier.OPERATOR,
    ReportTier.ARCHITECT,
    ReportTier.EVILBOB,
}


@dataclass
class GateResult:
    accepted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    overrides: list[dict[str, Any]]

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def override_count(self) -> int:
        return len(self.overrides)


def _has_evidence(finding: dict[str, Any]) -> bool:
    """A finding carries evidence when either:
        * ``evidence_chain_id`` is non-empty, or
        * ``evidence`` dict contains at least one non-empty value, or
        * ``falsification_survived`` is True (adversarial gate passed)
    """
    if finding.get("evidence_chain_id"):
        return True
    if finding.get("falsification_survived") is True:
        return True
    ev = finding.get("evidence")
    if isinstance(ev, dict) and any(bool(v) for v in ev.values()):
        return True
    if isinstance(ev, list) and any(ev):
        return True
    return False


def apply_gate(
    findings: list[dict[str, Any]],
    tier: ReportTier,
    *,
    founder_override_ids: set[str] | None = None,
) -> GateResult:
    """Split findings into accepted / rejected / overrides for a tier.

    Args:
        findings: Raw findings list (post-BeyondMythos, post-correlation).
        tier: The report tier the findings are being prepared for.
        founder_override_ids: Optional set of finding IDs where the
            founder has explicitly authorized inclusion without
            evidence. Each override is audit-logged.

    Returns:
        GateResult with three disjoint finding buckets.
    """
    overrides = founder_override_ids or set()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    override_list: list[dict[str, Any]] = []

    # SCOUT and ANALYST tiers: no gate. Everything passes through.
    if tier not in _GATED_TIERS:
        return GateResult(accepted=list(findings), rejected=[], overrides=[])

    for f in findings:
        finding_id = str(f.get("id", ""))
        if _has_evidence(f):
            accepted.append(f)
            continue
        if finding_id in overrides:
            override_list.append(f)
            logger.warning(
                "zero_fp_gate.override_used",
                finding_id=finding_id,
                tier=tier.value,
                title=f.get("title", ""),
            )
            continue
        # No evidence + no override: reject.
        rejected_finding = dict(f)
        rejected_finding["rejection_reason"] = (
            "No EvidenceChain entry for tier "
            f"{tier.value}. Founder override required to include."
        )
        rejected.append(rejected_finding)
        logger.info(
            "zero_fp_gate.rejected",
            finding_id=finding_id,
            tier=tier.value,
            title=f.get("title", ""),
        )

    logger.info(
        "zero_fp_gate.complete",
        tier=tier.value,
        accepted=len(accepted),
        rejected=len(rejected),
        overrides=len(override_list),
    )

    return GateResult(
        accepted=accepted,
        rejected=rejected,
        overrides=override_list,
    )
