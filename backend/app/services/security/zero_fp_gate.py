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


def _has_poc_artifact(finding: dict[str, Any]) -> bool:
    """A finding carries a PoC when:
        * ``poc_artifact_sha256`` is populated (64 hex chars), or
        * ``poc_artifact`` dict has a ``sha256`` key populated, or
        * ``poc_artifact_id`` is non-empty
    """
    sha = finding.get("poc_artifact_sha256")
    if isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha.lower()):
        return True
    if finding.get("poc_artifact_id"):
        return True
    poc = finding.get("poc_artifact")
    if isinstance(poc, dict) and poc.get("sha256"):
        return True
    return False


def cross_validate_queue_linkage(
    finding: dict[str, Any],
    queue_entries_by_id: dict[str, dict[str, Any]] | None,
) -> tuple[bool, str]:
    """Cross-validate finding's PoC linkage against exploitation queue.

    When we have the exploitation queue map for the scan, a finding
    that claims to be exploit-proven must match a queue entry whose
    ``poc_artifact_sha256`` agrees. Mismatches are tamper signals:
    either the finding was mutated after the queue was written, or
    the PoC was swapped. Missing queue mapping is NOT a failure
    (some scans skip the queue phase); we only enforce when a map is
    provided.

    Returns (ok, reason).
    """
    if queue_entries_by_id is None:
        return (True, "no queue map provided; skipping cross-validation")

    f_id = str(finding.get("id", ""))
    f_sha = finding.get("poc_artifact_sha256") or (
        (finding.get("poc_artifact") or {}).get("sha256") if isinstance(finding.get("poc_artifact"), dict) else ""
    )
    if not f_id or not f_sha:
        # Nothing to cross-check.
        return (True, "finding lacks id or sha256; no cross-check")

    q_entry = queue_entries_by_id.get(f_id)
    if q_entry is None:
        return (False, f"finding id {f_id!r} not present in any queue")

    q_sha = q_entry.get("poc_artifact_sha256", "")
    if q_sha and q_sha != f_sha:
        return (
            False,
            f"finding id {f_id!r} poc_artifact_sha256 mismatch "
            f"(finding={f_sha[:16]}.., queue={str(q_sha)[:16]}..)",
        )
    return (True, "queue linkage validated")


def apply_gate(
    findings: list[dict[str, Any]],
    tier: ReportTier,
    *,
    founder_override_ids: set[str] | None = None,
    require_poc_artifact: bool = False,
    queue_entries_by_id: dict[str, dict[str, Any]] | None = None,
) -> GateResult:
    """Split findings into accepted / rejected / overrides for a tier.

    Args:
        findings: Raw findings list (post-BeyondMythos, post-correlation).
        tier: The report tier the findings are being prepared for.
        founder_override_ids: Optional set of finding IDs where the
            founder has explicitly authorized inclusion without
            evidence. Each override is audit-logged.
        require_poc_artifact: When True, OPERATOR+ findings must also
            carry a reproducible PoC artifact (``poc_artifact_sha256``
            or ``poc_artifact.sha256`` field populated). This is the
            Klyntar "no exploit, no report" runtime enforcement:
            Shannon-style proof-of-exploitation discipline backed by
            the hash-chained evidence vault so the PoC is tamper-
            evident, not just present.

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
        has_ev = _has_evidence(f)
        has_poc = _has_poc_artifact(f) if require_poc_artifact else True
        # Cross-validate queue linkage when a queue map is provided.
        # Tampering with either the finding's poc_artifact_sha256 OR
        # the queue's corresponding entry breaks this check.
        queue_ok, queue_reason = cross_validate_queue_linkage(
            f, queue_entries_by_id,
        )

        if has_ev and has_poc and queue_ok:
            accepted.append(f)
            continue
        if finding_id in overrides:
            override_list.append(f)
            logger.warning(
                "zero_fp_gate.override_used",
                finding_id=finding_id,
                tier=tier.value,
                title=f.get("title", ""),
                missing_evidence=not has_ev,
                missing_poc=not has_poc,
                queue_mismatch=(not queue_ok),
            )
            continue
        # Missing evidence / PoC / queue linkage + no override: reject.
        rejected_finding = dict(f)
        missing: list[str] = []
        if not has_ev:
            missing.append("EvidenceChain")
        if not has_poc:
            missing.append("PoC artifact")
        if not queue_ok:
            missing.append(f"Queue linkage ({queue_reason})")
        rejected_finding["rejection_reason"] = (
            f"Missing {', '.join(missing)} for tier {tier.value}. "
            "Founder override required to include."
        )
        rejected.append(rejected_finding)
        logger.info(
            "zero_fp_gate.rejected",
            finding_id=finding_id,
            tier=tier.value,
            missing=missing,
            title=f.get("title", ""),
        )

    logger.info(
        "zero_fp_gate.complete",
        tier=tier.value,
        accepted=len(accepted),
        rejected=len(rejected),
        overrides=len(override_list),
        poc_required=require_poc_artifact,
    )

    return GateResult(
        accepted=accepted,
        rejected=rejected,
        overrides=override_list,
    )
