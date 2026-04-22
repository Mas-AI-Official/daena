"""Security Report Tiers: 5 levels of security intelligence output.

Tier system determines WHAT the client sees and WHAT depth of analysis
is performed. This is the product tier system for Intelligence-as-a-Service.

    T1 Scout:     Find vulnerabilities only (report listing)
    T2 Analyst:   Find + explain + remediation steps
    T3 Operator:  Find + explain + solution + auto-fix suggestions
    T4 Architect: Full analysis + fix + verify fix works + retest
    T5 3vilbob:   Offensive mode -- find + exploit path (FOUNDER ONLY)

Each tier maps to specific Laevateinn pipeline stages:
    T1: Stages 0-3 (comprehension + debate)
    T2: Stages 0-5 (+ validation gauntlet)
    T3: Stages 0-7 (+ adversarial gate + consensus)
    T4: Full pipeline + post-fix verification loop
    T5: Inverted pipeline (falsification engine used offensively)

Integration:
    SecurityDashboard API -> ReportTierEngine -> Laevateinn pipeline
    The tier determines which skip_stages set is passed to the pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ReportTier(str, Enum):
    """Security report tier levels."""
    SCOUT = "SCOUT"            # T1: Find only
    ANALYST = "ANALYST"        # T2: Find + explain + remediate
    OPERATOR = "OPERATOR"      # T3: Find + explain + fix
    ARCHITECT = "ARCHITECT"    # T4: Full + verify
    EVILBOB = "EVILBOB"        # T5: Offensive (FOUNDER ONLY)


class FindingSeverity(str, Enum):
    """Severity classification for security findings."""
    CRITICAL = "CRITICAL"    # Actively exploitable, immediate risk
    HIGH = "HIGH"            # Exploitable with some effort
    MEDIUM = "MEDIUM"        # Vulnerability present, limited risk
    LOW = "LOW"              # Best practice violation
    INFO = "INFO"            # Informational finding


@dataclass
class SecurityFinding:
    """A single security finding with tiered detail levels."""
    id: str = ""
    title: str = ""
    severity: FindingSeverity = FindingSeverity.INFO
    location: str = ""           # File:line or network endpoint
    description: str = ""        # T1+: what was found
    explanation: str = ""        # T2+: why it matters
    remediation: str = ""        # T2+: how to fix conceptually
    fix_code: str = ""           # T3+: actual fix code
    fix_verified: bool = False   # T4+: was the fix tested?
    exploit_path: str = ""       # T5: how to exploit (FOUNDER ONLY)
    confidence: float = 0.0      # Laevateinn pipeline confidence
    verified_by_models: int = 0  # How many models confirmed this
    falsification_survived: bool = False  # Did adversarial gate confirm?
    reasoning_chain: list[str] = field(default_factory=list)  # Visible pipeline trace
    cve_references: list[str] = field(default_factory=list)
    # Provenance fields added 2026-04-21: real_scanner / bandit / semgrep /
    # gitleaks / http_probe set these so the UI can distinguish rule-based
    # deterministic findings from LLM-derived ones. The Zero-FP gate also
    # reads ``evidence_chain_id`` to auto-admit findings without founder override.
    source_tool: str = ""        # real_scanner / bandit / semgrep / http_probe / ...
    source_rule: str = ""        # gitleaks:aws-access-key / bandit:B608 / ...
    raw_line: str = ""           # The matched line (truncated)
    evidence_chain_id: str = ""  # Links to EvidenceChain vault entry


@dataclass
class SecurityReport:
    """Complete security intelligence report at a specific tier."""
    tier: ReportTier
    target: str                  # What was scanned
    scan_timestamp: float = field(default_factory=time.time)
    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    findings: list[SecurityFinding] = field(default_factory=list)
    pipeline_stages_used: list[str] = field(default_factory=list)
    total_models_used: int = 0
    total_pipeline_time_ms: int = 0
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Pipeline stage mapping per tier ────────────────────────────

# Stages to SKIP for each tier (fewer skips = more analysis)
TIER_SKIP_STAGES: dict[ReportTier, set[str]] = {
    ReportTier.SCOUT: {
        "analogy", "counterfactual", "outcome_sim",
        "consensus", "calibration",
    },
    ReportTier.ANALYST: {
        "analogy", "outcome_sim",
    },
    ReportTier.OPERATOR: {
        "analogy",
    },
    ReportTier.ARCHITECT: set(),  # Full pipeline, no skips
    ReportTier.EVILBOB: set(),    # Full pipeline, inverted
}

# Required user role for each tier
TIER_REQUIRED_ROLES: dict[ReportTier, list[str]] = {
    ReportTier.SCOUT: ["USER", "ADMIN", "FOUNDER"],
    ReportTier.ANALYST: ["USER", "ADMIN", "FOUNDER"],
    ReportTier.OPERATOR: ["ADMIN", "FOUNDER"],
    ReportTier.ARCHITECT: ["ADMIN", "FOUNDER"],
    ReportTier.EVILBOB: ["FOUNDER"],  # FOUNDER ONLY
}


class ReportTierEngine:
    """Generates security reports at different intelligence tiers.

    Maps each tier to the appropriate Laevateinn pipeline configuration,
    filters findings based on tier level, and formats the output.

    Usage::

        engine = ReportTierEngine()

        # Check authorization
        if engine.authorize("ADMIN", ReportTier.OPERATOR):
            # Get pipeline configuration for this tier
            config = engine.get_pipeline_config(ReportTier.OPERATOR)
            # ... run pipeline with config ...
            # Format findings into report
            report = engine.build_report(
                tier=ReportTier.OPERATOR,
                target="app.py",
                raw_findings=findings,
            )
    """

    def authorize(self, user_role: str, tier: ReportTier) -> bool:
        """Check if a user role can access this tier.

        Args:
            user_role: The user's role (USER, ADMIN, FOUNDER).
            tier: Requested report tier.

        Returns:
            True if authorized.
        """
        allowed = TIER_REQUIRED_ROLES.get(tier, ["FOUNDER"])
        authorized = user_role in allowed

        if not authorized:
            logger.warning(
                "report_tier.unauthorized",
                user_role=user_role,
                tier=tier.value,
            )

        return authorized

    def get_pipeline_config(self, tier: ReportTier) -> dict[str, Any]:
        """Get Laevateinn pipeline configuration for a tier.

        Returns:
            Dict with skip_stages and other pipeline parameters.
        """
        from app.services.laevateinn.types import Difficulty

        config: dict[str, Any] = {
            "skip_stages": TIER_SKIP_STAGES.get(tier, set()),
            "intent_type": "SECURITY_SCAN",
        }

        if tier == ReportTier.SCOUT:
            config["force_difficulty"] = Difficulty.STANDARD
        elif tier == ReportTier.ANALYST:
            config["force_difficulty"] = Difficulty.HARD
        elif tier in (ReportTier.OPERATOR, ReportTier.ARCHITECT):
            config["force_difficulty"] = Difficulty.BRUTAL
        elif tier == ReportTier.EVILBOB:
            config["force_difficulty"] = Difficulty.BRUTAL
            config["offensive_mode"] = True

        return config

    def build_report(
        self,
        tier: ReportTier,
        target: str,
        raw_findings: list[dict[str, Any]],
        *,
        pipeline_stages: list[str] | None = None,
        pipeline_time_ms: int = 0,
        models_used: int = 0,
    ) -> SecurityReport:
        """Build a formatted security report from raw findings.

        Filters finding details based on tier level:
        - T1 Scout: title, severity, location only
        - T2 Analyst: + description, explanation, remediation
        - T3 Operator: + fix_code
        - T4 Architect: + fix_verified, full reasoning chain
        - T5 3vilbob: + exploit_path

        Args:
            tier: Report tier.
            target: What was scanned.
            raw_findings: Raw findings from pipeline.
            pipeline_stages: Which Laevateinn stages ran.
            pipeline_time_ms: Total pipeline execution time.
            models_used: Number of models that participated.

        Returns:
            SecurityReport with tier-appropriate detail level.
        """
        findings: list[SecurityFinding] = []

        for raw in raw_findings:
            finding = SecurityFinding(
                id=raw.get("id", ""),
                title=raw.get("title", ""),
                severity=FindingSeverity(
                    raw.get("severity", "INFO").upper()
                ),
                location=raw.get("location", ""),
                confidence=raw.get("confidence", 0.0),
                verified_by_models=raw.get("verified_by_models", 0),
                falsification_survived=raw.get("falsification_survived", False),
                # Provenance always carried through regardless of tier so
                # the UI can render "from real_scanner / gitleaks / ..." and
                # the Zero-FP gate sees evidence_chain_id on the dataclass.
                source_tool=raw.get("source_tool", ""),
                source_rule=raw.get("source_rule", ""),
                raw_line=raw.get("raw_line", ""),
                evidence_chain_id=raw.get("evidence_chain_id", ""),
            )

            # T2+: Add explanations
            if tier in (
                ReportTier.ANALYST, ReportTier.OPERATOR,
                ReportTier.ARCHITECT, ReportTier.EVILBOB,
            ):
                finding.description = raw.get("description", "")
                finding.explanation = raw.get("explanation", "")
                finding.remediation = raw.get("remediation", "")
                finding.cve_references = raw.get("cve_references", [])

            # T3+: Add fix code
            if tier in (
                ReportTier.OPERATOR, ReportTier.ARCHITECT,
                ReportTier.EVILBOB,
            ):
                finding.fix_code = raw.get("fix_code", "")

            # T4+: Add verification and full chain
            if tier in (ReportTier.ARCHITECT, ReportTier.EVILBOB):
                finding.fix_verified = raw.get("fix_verified", False)
                finding.reasoning_chain = raw.get("reasoning_chain", [])

            # T5: Add exploit path (FOUNDER ONLY)
            if tier == ReportTier.EVILBOB:
                finding.exploit_path = raw.get("exploit_path", "")

            findings.append(finding)

        # Sort by severity (CRITICAL first)
        severity_order = {
            FindingSeverity.CRITICAL: 0,
            FindingSeverity.HIGH: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 3,
            FindingSeverity.INFO: 4,
        }
        findings.sort(key=lambda f: severity_order.get(f.severity, 99))

        # Count by severity
        counts = {s: 0 for s in FindingSeverity}
        for f in findings:
            counts[f.severity] += 1

        # Generate summary
        summary = self._generate_summary(tier, target, findings, counts)
        recommendations = self._generate_recommendations(tier, findings)

        report = SecurityReport(
            tier=tier,
            target=target,
            total_findings=len(findings),
            critical=counts[FindingSeverity.CRITICAL],
            high=counts[FindingSeverity.HIGH],
            medium=counts[FindingSeverity.MEDIUM],
            low=counts[FindingSeverity.LOW],
            info=counts[FindingSeverity.INFO],
            findings=findings,
            pipeline_stages_used=pipeline_stages or [],
            total_models_used=models_used,
            total_pipeline_time_ms=pipeline_time_ms,
            summary=summary,
            recommendations=recommendations,
        )

        logger.info(
            "report_tier.built",
            tier=tier.value,
            target=target,
            total=len(findings),
            critical=counts[FindingSeverity.CRITICAL],
            high=counts[FindingSeverity.HIGH],
        )

        return report

    def _generate_summary(
        self,
        tier: ReportTier,
        target: str,
        findings: list[SecurityFinding],
        counts: dict[FindingSeverity, int],
    ) -> str:
        """Generate a human-readable summary for the report."""
        total = len(findings)
        if total == 0:
            return f"No security findings detected in {target}."

        critical_high = counts[FindingSeverity.CRITICAL] + counts[FindingSeverity.HIGH]
        parts = [
            f"Security scan of {target} found {total} finding(s): "
            f"{counts[FindingSeverity.CRITICAL]} critical, "
            f"{counts[FindingSeverity.HIGH]} high, "
            f"{counts[FindingSeverity.MEDIUM]} medium, "
            f"{counts[FindingSeverity.LOW]} low, "
            f"{counts[FindingSeverity.INFO]} informational."
        ]

        if critical_high > 0:
            parts.append(
                f" {critical_high} finding(s) require immediate attention."
            )

        # Tier-specific additions
        if tier in (ReportTier.ARCHITECT, ReportTier.EVILBOB):
            verified = sum(1 for f in findings if f.falsification_survived)
            parts.append(
                f" {verified}/{total} findings survived adversarial verification."
            )

        return "".join(parts)

    def _generate_recommendations(
        self,
        tier: ReportTier,
        findings: list[SecurityFinding],
    ) -> list[str]:
        """Generate actionable recommendations."""
        recs: list[str] = []

        critical = [f for f in findings if f.severity == FindingSeverity.CRITICAL]
        if critical:
            recs.append(
                f"IMMEDIATE: Address {len(critical)} critical finding(s) before deployment."
            )

        high = [f for f in findings if f.severity == FindingSeverity.HIGH]
        if high:
            recs.append(
                f"HIGH PRIORITY: Remediate {len(high)} high-severity finding(s) within 48 hours."
            )

        if tier in (ReportTier.OPERATOR, ReportTier.ARCHITECT):
            fixable = [f for f in findings if f.fix_code]
            if fixable:
                recs.append(
                    f"AUTO-FIX AVAILABLE: {len(fixable)} finding(s) have generated fix code. "
                    f"Review and apply."
                )

        if not recs:
            recs.append("No critical issues found. Continue routine monitoring.")

        return recs
