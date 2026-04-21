"""BugBountyReportGenerator -- Professional PDF vulnerability reports.

Generates reports formatted for bug bounty submissions (Google VRP,
HackerOne, Bugcrowd). Each finding includes title, severity, CVSS,
reproduction steps, impact, and remediation.

Output: PDF to D:\\SecurityTools\\reports\\
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

REPORTS_DIR = os.environ.get("SECURITY_REPORTS_DIR", "D:\\SecurityTools\\reports")


@dataclass
class CVELink:
    """A linked CVE from NVD enrichment."""
    cve_id: str
    cvss_score: float = 0.0
    severity: str = ""
    description: str = ""
    reference_url: str = ""


@dataclass
class VulnFinding:
    """A single vulnerability finding."""
    title: str
    severity: str  # Critical, High, Medium, Low, Informational
    description: str
    reproduction_steps: list[str] = field(default_factory=list)
    impact: str = ""
    remediation: str = ""
    affected_url: str = ""
    cwe_id: str = ""
    cvss_score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    discovered_by: str = ""  # Tool that found it
    discovered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    linked_cves: list[CVELink] = field(default_factory=list)


@dataclass
class ReportMetadata:
    """Metadata for the vulnerability report."""
    program_name: str = ""
    target: str = ""
    researcher: str = "Masoud Masoori / MAS-AI Technologies"
    tool: str = "MAS-AI Security Assessment Platform"
    date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    methodology: str = "Automated + AI-assisted vulnerability assessment"
    # Optional unique-filename components. When set, the report
    # writer appends them to the filename so back-to-back scans of
    # the same target on the same day do NOT overwrite each other.
    # tier values: SCOUT / ANALYST / OPERATOR / ARCHITECT / EVILBOB.
    tier: str = ""
    job_id: str = ""


class BugBountyReportGenerator:
    """Generate professional PDF vulnerability reports.

    Usage::

        gen = BugBountyReportGenerator()
        path = gen.generate(
            findings=[VulnFinding(...)],
            metadata=ReportMetadata(program_name="Google VRP", target="cloud.google.com"),
        )
    """

    def generate(
        self,
        findings: list[VulnFinding],
        metadata: ReportMetadata,
        evidence_summary: dict[str, Any] | None = None,
    ) -> str:
        """Generate a PDF report and return the file path."""
        os.makedirs(REPORTS_DIR, exist_ok=True)

        safe_target = metadata.target.replace(".", "_").replace("/", "_")[:30]
        # Tier + short-job-id suffix prevents back-to-back scans of
        # the same target on the same day from overwriting each
        # other's report file.
        suffix = ""
        if metadata.tier:
            suffix += f"_{metadata.tier}"
        if metadata.job_id:
            suffix += f"_{metadata.job_id[:8]}"
        filename = f"{safe_target}_{metadata.date}{suffix}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.colors import HexColor
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak,
            )

            doc = SimpleDocTemplate(filepath, pagesize=A4,
                                     topMargin=0.75*inch, bottomMargin=0.75*inch)
            styles = getSampleStyleSheet()

            # Custom styles
            title_style = ParagraphStyle(
                "CustomTitle", parent=styles["Title"],
                fontSize=20, spaceAfter=20,
                textColor=HexColor("#0F1419"),
            )
            heading_style = ParagraphStyle(
                "CustomHeading", parent=styles["Heading2"],
                fontSize=14, spaceAfter=10, spaceBefore=16,
                textColor=HexColor("#D4A843"),
            )
            body_style = styles["Normal"]

            severity_colors = {
                "critical": "#DC2626",
                "high": "#EA580C",
                "medium": "#CA8A04",
                "low": "#2563EB",
                "informational": "#6B7280",
            }

            elements = []

            # Title page
            elements.append(Paragraph(
                "Vulnerability Assessment Report",
                title_style,
            ))
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(
                f"<b>Program:</b> {metadata.program_name}", body_style,
            ))
            elements.append(Paragraph(
                f"<b>Target:</b> {metadata.target}", body_style,
            ))
            elements.append(Paragraph(
                f"<b>Date:</b> {metadata.date}", body_style,
            ))
            elements.append(Paragraph(
                f"<b>Researcher:</b> {metadata.researcher}", body_style,
            ))
            elements.append(Paragraph(
                f"<b>Tool:</b> {metadata.tool}", body_style,
            ))
            elements.append(Spacer(1, 24))

            # Executive Summary
            elements.append(Paragraph("Executive Summary", heading_style))
            sev_counts = {}
            for f in findings:
                sev = f.severity.lower()
                sev_counts[sev] = sev_counts.get(sev, 0) + 1

            summary_text = (
                f"This assessment identified <b>{len(findings)}</b> findings across "
                f"the target <b>{metadata.target}</b>. "
            )
            for sev in ["critical", "high", "medium", "low", "informational"]:
                if sev in sev_counts:
                    color = severity_colors.get(sev, "#000000")
                    summary_text += (
                        f'<font color="{color}"><b>{sev.upper()}: {sev_counts[sev]}</b></font>  '
                    )
            elements.append(Paragraph(summary_text, body_style))
            elements.append(Spacer(1, 12))

            # Severity summary table
            table_data = [["Severity", "Count"]]
            for sev in ["Critical", "High", "Medium", "Low", "Informational"]:
                count = sev_counts.get(sev.lower(), 0)
                if count > 0:
                    table_data.append([sev, str(count)])

            if len(table_data) > 1:
                t = Table(table_data, colWidths=[200, 100])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F1419")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                elements.append(t)

            # Methodology -- generic, never expose internal engine names
            elements.append(Spacer(1, 16))
            elements.append(Paragraph("Methodology", heading_style))
            elements.append(Paragraph(metadata.methodology, body_style))
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                "Tools used: nmap, subfinder, httpx-toolkit, nuclei, custom analysis. "
                "All scanning performed under authorized bug bounty program rules.",
                body_style,
            ))

            # Findings
            elements.append(PageBreak())
            elements.append(Paragraph("Detailed Findings", heading_style))

            for i, finding in enumerate(findings, 1):
                sev_color = severity_colors.get(finding.severity.lower(), "#000000")

                elements.append(Spacer(1, 12))
                elements.append(Paragraph(
                    f'<b>Finding #{i}:</b> {finding.title} '
                    f'[<font color="{sev_color}"><b>{finding.severity.upper()}</b></font>]',
                    body_style,
                ))

                if finding.cvss_score > 0:
                    elements.append(Paragraph(
                        f"<b>CVSS:</b> {finding.cvss_score}", body_style,
                    ))
                if finding.cwe_id:
                    elements.append(Paragraph(
                        f"<b>CWE:</b> {finding.cwe_id}", body_style,
                    ))
                if finding.affected_url:
                    elements.append(Paragraph(
                        f"<b>Affected URL:</b> {finding.affected_url}", body_style,
                    ))

                elements.append(Spacer(1, 6))
                elements.append(Paragraph(
                    f"<b>Description:</b> {finding.description}", body_style,
                ))

                if finding.reproduction_steps:
                    elements.append(Spacer(1, 4))
                    elements.append(Paragraph("<b>Reproduction Steps:</b>", body_style))
                    for j, step in enumerate(finding.reproduction_steps, 1):
                        elements.append(Paragraph(f"  {j}. {step}", body_style))

                if finding.impact:
                    elements.append(Paragraph(
                        f"<b>Impact:</b> {finding.impact}", body_style,
                    ))
                if finding.remediation:
                    elements.append(Paragraph(
                        f"<b>Remediation:</b> {finding.remediation}", body_style,
                    ))
                if finding.discovered_by:
                    elements.append(Paragraph(
                        f"<b>Discovered by:</b> {finding.discovered_by}", body_style,
                    ))

                # CVE enrichment data
                if finding.linked_cves:
                    elements.append(Spacer(1, 4))
                    elements.append(Paragraph("<b>Related CVEs (NVD):</b>", body_style))
                    cve_table_data = [["CVE ID", "CVSS", "Severity"]]
                    for cve_link in finding.linked_cves[:10]:
                        cve_table_data.append([
                            cve_link.cve_id,
                            str(cve_link.cvss_score),
                            cve_link.severity,
                        ])
                    if len(cve_table_data) > 1:
                        cve_t = Table(cve_table_data, colWidths=[150, 60, 100])
                        cve_t.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1A2332")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#D4A843")),
                            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]))
                        elements.append(cve_t)
                    if finding.linked_cves[0].reference_url:
                        elements.append(Paragraph(
                            f"<i>Ref: {finding.linked_cves[0].reference_url}</i>",
                            body_style,
                        ))

            # Evidence Chain (if /3vilbob mode captured evidence)
            if evidence_summary and evidence_summary.get("total_evidence", 0) > 0:
                elements.append(PageBreak())
                elements.append(Paragraph("Evidence Chain", heading_style))
                elements.append(Paragraph(
                    f"<b>Scan ID:</b> {evidence_summary.get('scan_id', 'N/A')}",
                    body_style,
                ))
                elements.append(Paragraph(
                    f"<b>Total Evidence Items:</b> {evidence_summary['total_evidence']}",
                    body_style,
                ))
                elements.append(Paragraph(
                    f"<b>Chain Hash (SHA-256):</b> <font face='Courier'>"
                    f"{evidence_summary.get('chain_hash', 'N/A')}</font>",
                    body_style,
                ))
                vault_path = evidence_summary.get("vault_path", "")
                if vault_path:
                    elements.append(Paragraph(
                        f"<b>Vault Path:</b> {vault_path}",
                        body_style,
                    ))
                elements.append(Spacer(1, 8))

                # Evidence type breakdown
                by_type = evidence_summary.get("by_type", {})
                if by_type:
                    type_data = [["Evidence Type", "Count"]]
                    for etype, count in sorted(by_type.items()):
                        type_data.append([etype.replace("_", " ").title(), str(count)])
                    et = Table(type_data, colWidths=[200, 80])
                    et.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1A2332")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#D4A843")),
                        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    elements.append(et)
                    elements.append(Spacer(1, 8))

                # Individual evidence items (truncated for readability)
                items = evidence_summary.get("items", [])
                for idx, item in enumerate(items[:25], 1):
                    etype = item.get("type", "unknown")
                    ts = item.get("timestamp", "")[:19]
                    sha = item.get("sha256", "")[:16]
                    desc = item.get("description", "")[:120]
                    encrypted_tag = " [ENCRYPTED]" if item.get("encrypted") else ""
                    elements.append(Paragraph(
                        f"<b>#{idx}</b> [{etype.upper()}] {ts} "
                        f"<font face='Courier'>{sha}...</font>{encrypted_tag}",
                        body_style,
                    ))
                    if desc:
                        elements.append(Paragraph(f"  {desc}", body_style))

                if len(items) > 25:
                    elements.append(Paragraph(
                        f"<i>... and {len(items) - 25} more evidence items in vault.</i>",
                        body_style,
                    ))

                elements.append(Spacer(1, 8))
                elements.append(Paragraph(
                    "<b>Note:</b> All evidence items are SHA-256 hashed and "
                    "chained. The chain hash above proves no evidence was "
                    "modified after capture. Encrypted tokens require the "
                    "EVIDENCE_ENCRYPTION_KEY to decrypt.",
                    body_style,
                ))

            # Footer
            elements.append(Spacer(1, 30))
            elements.append(Paragraph(
                "---",
                body_style,
            ))
            elements.append(Paragraph(
                f"Generated by MAS-AI Technologies Inc. on {metadata.date}",
                body_style,
            ))

            doc.build(elements)
            logger.info("report_generator.pdf_created", path=filepath, findings=len(findings))
            return filepath

        except ImportError:
            # Fallback: generate markdown report
            return self._generate_markdown(findings, metadata, evidence_summary)

    def _generate_markdown(
        self,
        findings: list[VulnFinding],
        metadata: ReportMetadata,
        evidence_summary: dict[str, Any] | None = None,
    ) -> str:
        """Fallback: generate markdown report if reportlab unavailable."""
        safe_target = metadata.target.replace(".", "_").replace("/", "_")[:30]
        suffix = ""
        if metadata.tier:
            suffix += f"_{metadata.tier}"
        if metadata.job_id:
            suffix += f"_{metadata.job_id[:8]}"
        filename = f"{safe_target}_{metadata.date}{suffix}.md"
        filepath = os.path.join(REPORTS_DIR, filename)

        lines = [
            f"# Vulnerability Assessment Report",
            f"",
            f"**Program:** {metadata.program_name}",
            f"**Target:** {metadata.target}",
            f"**Date:** {metadata.date}",
            f"**Researcher:** {metadata.researcher}",
            f"",
            f"## Findings ({len(findings)} total)",
            f"",
        ]

        for i, f in enumerate(findings, 1):
            lines.extend([
                f"### Finding #{i}: {f.title} [{f.severity.upper()}]",
                f"",
                f"**Description:** {f.description}",
                f"**Impact:** {f.impact}",
                f"**Remediation:** {f.remediation}",
                f"**Affected:** {f.affected_url}",
            ])
            if f.linked_cves:
                lines.append("")
                lines.append("**Related CVEs:**")
                lines.append("| CVE ID | CVSS | Severity |")
                lines.append("|--------|------|----------|")
                for cve_link in f.linked_cves[:10]:
                    lines.append(
                        f"| {cve_link.cve_id} | {cve_link.cvss_score} | {cve_link.severity} |"
                    )
            lines.append("")

        # Evidence chain section
        if evidence_summary and evidence_summary.get("total_evidence", 0) > 0:
            lines.extend([
                "",
                "## Evidence Chain",
                "",
                f"**Scan ID:** {evidence_summary.get('scan_id', 'N/A')}",
                f"**Total Evidence:** {evidence_summary['total_evidence']} items",
                f"**Chain Hash:** `{evidence_summary.get('chain_hash', 'N/A')}`",
                f"**Vault:** {evidence_summary.get('vault_path', 'N/A')}",
                "",
            ])
            by_type = evidence_summary.get("by_type", {})
            if by_type:
                lines.append("| Type | Count |")
                lines.append("|------|-------|")
                for etype, count in sorted(by_type.items()):
                    lines.append(f"| {etype} | {count} |")
                lines.append("")

            for idx, item in enumerate(evidence_summary.get("items", [])[:25], 1):
                enc = " [ENC]" if item.get("encrypted") else ""
                lines.append(
                    f"{idx}. **{item.get('type', '?').upper()}** "
                    f"`{item.get('sha256', '')[:16]}...` "
                    f"{item.get('description', '')[:100]}{enc}"
                )
            lines.append("")

        lines.append(f"---\nGenerated by MAS-AI Technologies Inc. on {metadata.date}")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        logger.info("report_generator.markdown_created", path=filepath)
        return filepath

    @staticmethod
    def cve_links_from_enrichment(enrichment: dict) -> list[CVELink]:
        """Convert CVE enrichment data (from cve_intelligence) into CVELinks.

        Usage::

            enriched = await cve_svc.enrich_scan_findings(findings)
            for finding in enriched:
                links = BugBountyReportGenerator.cve_links_from_enrichment(
                    finding["cve_enrichment"]
                )
                vuln_finding.linked_cves = links
        """
        links = []
        for cve in enrichment.get("cves", []):
            ref_url = ""
            refs = cve.get("references", [])
            if refs:
                ref_url = refs[0].get("url", "")
            links.append(CVELink(
                cve_id=cve.get("cve_id", ""),
                cvss_score=cve.get("cvss_score", 0.0),
                severity=cve.get("severity", ""),
                description=cve.get("description", "")[:200],
                reference_url=ref_url,
            ))
        return links


# ---------------------------------------------------------------------------
# Remediation Report Generator (the $20K report)
# ---------------------------------------------------------------------------

class RemediationReportGenerator:
    """Generate a remediation roadmap -- the solutions report.

    Security consultants charge $5K for findings and $20K for
    the remediation roadmap. This generates both.

    The findings report says WHAT is broken.
    The remediation report says HOW to fix it, in priority order,
    with code examples, configuration changes, and timelines.
    """

    # Remediation templates by vulnerability type
    _REMEDIATION_DB: dict[str, dict[str, Any]] = {
        "header_analysis": {
            "category": "Configuration",
            "priority": "P2",
            "effort": "Low (< 1 hour)",
            "fix": (
                "Add security headers to your web server or application:\n"
                "```\n"
                "# Nginx\n"
                "add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;\n"
                "add_header X-Frame-Options \"DENY\" always;\n"
                "add_header X-Content-Type-Options \"nosniff\" always;\n"
                "add_header Content-Security-Policy \"default-src 'self'\" always;\n"
                "add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;\n"
                "```\n"
                "For Express.js, use the `helmet` middleware:\n"
                "```javascript\n"
                "const helmet = require('helmet');\n"
                "app.use(helmet());\n"
                "```"
            ),
            "verification": "Re-scan headers after deployment. All security headers should be present.",
        },
        "path_discovery": {
            "category": "Access Control",
            "priority": "P1",
            "effort": "Medium (1-4 hours)",
            "fix": (
                "1. Remove or restrict access to exposed paths:\n"
                "   - /.env, /.git: Add deny rules in web server config\n"
                "   - /admin, /debug: Require authentication + IP whitelist\n"
                "   - /api/docs, /swagger: Disable in production\n"
                "   - /metrics, /health: Internal-only or auth-protected\n\n"
                "2. Nginx deny rules:\n"
                "```\n"
                "location ~ /\\. { deny all; }\n"
                "location /admin { allow 10.0.0.0/8; deny all; }\n"
                "```\n"
                "3. Remove debug endpoints before production deploy."
            ),
            "verification": "All exposed paths should return 404 or 403 after fix.",
        },
        "credential_exposure": {
            "category": "Secrets Management",
            "priority": "P0 (IMMEDIATE)",
            "effort": "High (4-8 hours)",
            "fix": (
                "1. IMMEDIATELY rotate all exposed credentials:\n"
                "   - API keys, database passwords, tokens\n"
                "   - Assume they are already compromised\n\n"
                "2. Move secrets to a secrets manager:\n"
                "   - AWS Secrets Manager, HashiCorp Vault, or GCP Secret Manager\n"
                "   - Never store in .env files deployed to production\n\n"
                "3. Add .env to .gitignore (check git history for past commits)\n"
                "4. Use git-secrets or trufflehog to scan for leaked secrets\n"
                "5. Enable secret scanning on GitHub/GitLab"
            ),
            "verification": "Verify all old credentials are revoked and new ones are in secrets manager.",
        },
        "vulnerability_verification": {
            "category": "Application Security",
            "priority": "P0",
            "effort": "Varies",
            "fix": (
                "Address the specific vulnerability identified:\n"
                "- SQL Injection: Use parameterized queries / prepared statements\n"
                "- XSS: Sanitize output, use Content-Security-Policy\n"
                "- SSRF: Validate and whitelist URLs, block internal IPs\n"
                "- IDOR: Implement proper authorization checks per resource\n"
                "- RCE: Never pass user input to system commands\n\n"
                "General defense-in-depth:\n"
                "1. Input validation at every boundary\n"
                "2. Output encoding appropriate to context\n"
                "3. Principle of least privilege for all accounts\n"
                "4. Web Application Firewall as defense layer"
            ),
            "verification": "Re-test the specific vulnerability. Should no longer be exploitable.",
        },
        "unauthorized_access": {
            "category": "Authentication / Authorization",
            "priority": "P0",
            "effort": "Medium-High",
            "fix": (
                "1. Implement authentication on ALL endpoints:\n"
                "   - JWT validation middleware on every route\n"
                "   - No endpoint should be accessible without auth (except public pages)\n\n"
                "2. Implement authorization (RBAC/ABAC):\n"
                "   - Check user role before every action\n"
                "   - Admin endpoints require admin role, not just authentication\n\n"
                "3. Rate limit authentication endpoints\n"
                "4. Implement account lockout after N failed attempts\n"
                "5. Use MFA for admin and sensitive operations"
            ),
            "verification": "Attempt to access protected resources without auth. Should get 401/403.",
        },
        "api_exposure": {
            "category": "API Security",
            "priority": "P1",
            "effort": "Low-Medium",
            "fix": (
                "1. Disable API documentation in production:\n"
                "```python\n"
                "# FastAPI\n"
                "app = FastAPI(docs_url=None, redoc_url=None) if PRODUCTION else FastAPI()\n"
                "```\n\n"
                "2. If docs must be available, require authentication\n"
                "3. Rate limit API endpoints\n"
                "4. Validate all input with strict schemas\n"
                "5. Return minimal error information in production"
            ),
            "verification": "API docs endpoints should be inaccessible in production.",
        },
        "attack_chain": {
            "category": "Architecture",
            "priority": "P0",
            "effort": "High",
            "fix": (
                "Attack chains exploit COMBINATIONS of weaknesses. Fix each link:\n"
                "1. Address each individual finding in the chain\n"
                "2. Add defense-in-depth: even if one control fails, others hold\n"
                "3. Implement monitoring/alerting on the chain path\n"
                "4. Conduct threat modeling to identify other chains"
            ),
            "verification": "Re-test the full chain. Breaking any link should break the chain.",
        },
        "emergent_vulnerability": {
            "category": "Architecture / Integration",
            "priority": "P0-P1",
            "effort": "High",
            "fix": (
                "Emergent vulnerabilities exist in component interactions:\n"
                "1. Review all data flows between components\n"
                "2. Apply input validation at EVERY component boundary\n"
                "3. Never trust data from another internal component without validation\n"
                "4. Implement integration tests that test component combinations\n"
                "5. Conduct architecture review focused on data flow"
            ),
            "verification": "Test the specific component interaction identified.",
        },
        "post_exploitation": {
            "category": "Incident Response",
            "priority": "P0 (IMMEDIATE)",
            "effort": "High",
            "fix": (
                "Post-exploitation was successful -- attacker impact was proven.\n"
                "1. Treat this as a confirmed breach scenario\n"
                "2. Review logs for the timeframe of the assessment\n"
                "3. Rotate all credentials that could have been accessed\n"
                "4. Implement monitoring for the exploitation path\n"
                "5. Address the root vulnerability that enabled access"
            ),
            "verification": "Re-test the full exploitation path. Should be blocked at every stage.",
        },
    }

    def generate(
        self,
        findings: list[VulnFinding],
        scan_findings: list[dict[str, Any]],
        metadata: ReportMetadata,
        dev_profile: dict[str, Any] | None = None,
        supply_chain: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate a remediation roadmap report."""
        os.makedirs(REPORTS_DIR, exist_ok=True)

        safe_target = metadata.target.replace(".", "_").replace("/", "_")[:30]
        filename = f"{safe_target}_{metadata.date}_REMEDIATION.md"
        filepath = os.path.join(REPORTS_DIR, filename)

        lines = [
            f"# Remediation Roadmap: {metadata.target}",
            f"**Date:** {metadata.date}",
            f"**Prepared by:** {metadata.researcher}",
            f"**Tool:** {metadata.tool}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
        ]

        # Severity counts
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = f.severity.lower()
            if sev in severity_counts:
                severity_counts[sev] += 1
            elif sev == "informational":
                severity_counts["info"] += 1

        lines.append(
            f"This assessment identified **{len(findings)} findings**: "
            f"{severity_counts['critical']} Critical, {severity_counts['high']} High, "
            f"{severity_counts['medium']} Medium, {severity_counts['low']} Low, "
            f"{severity_counts['info']} Informational."
        )
        lines.append("")

        # Developer profile insights
        if dev_profile:
            lines.append("## Developer Profile Assessment")
            lines.append("")
            lines.append(f"- **Experience Level:** {dev_profile.get('experience', 'unknown')}")
            lines.append(f"- **Primary Framework:** {dev_profile.get('framework', 'unknown')}")
            lines.append(f"- **Security Awareness:** {dev_profile.get('security_awareness', 'unknown')}")
            lines.append("")
            predictions = dev_profile.get("predictions", [])
            if predictions:
                lines.append("**Predicted additional risks based on developer profile:**")
                for p in predictions[:5]:
                    lines.append(f"- {p}")
                lines.append("")

        # Supply chain risks
        if supply_chain:
            lines.append("## Supply Chain Risks")
            lines.append("")
            for sc in supply_chain[:10]:
                risk = sc.get("risk_notes", "")
                if risk:
                    lines.append(f"- **{sc.get('service_name', '?')}** ({sc.get('category', '')}): {risk}")
            lines.append("")

        # Remediation roadmap by priority
        lines.append("## Remediation Roadmap")
        lines.append("")
        lines.append("Fixes are ordered by priority. Address P0 items within 24 hours.")
        lines.append("")

        # Group findings by remediation priority
        by_priority: dict[str, list] = {"P0": [], "P1": [], "P2": [], "P3": []}

        for i, sf in enumerate(scan_findings):
            finding_type = sf.get("type", "")
            info = sf.get("info", {})
            severity = info.get("severity", "low")

            remediation = self._REMEDIATION_DB.get(finding_type, self._REMEDIATION_DB.get("vulnerability_verification", {}))
            priority = remediation.get("priority", "P2")
            # Override priority based on severity
            if severity == "critical":
                priority = "P0 (IMMEDIATE)"
            elif severity == "high" and "P0" not in priority:
                priority = "P1"

            pkey = priority.split()[0] if " " in priority else priority
            if pkey not in by_priority:
                pkey = "P2"
            by_priority.setdefault(pkey, []).append({
                "finding": sf,
                "remediation": remediation,
                "priority": priority,
                "index": i + 1,
            })

        for prio in ["P0", "P1", "P2", "P3"]:
            items = by_priority.get(prio, [])
            if not items:
                continue

            lines.append(f"### {prio} -- {'IMMEDIATE' if prio == 'P0' else 'This Week' if prio == 'P1' else 'This Month' if prio == 'P2' else 'Backlog'}")
            lines.append("")

            for item in items:
                sf = item["finding"]
                rem = item["remediation"]
                info = sf.get("info", {})
                lines.append(f"#### Finding #{item['index']}: {info.get('name', sf.get('type', ''))}")
                lines.append(f"**Severity:** {info.get('severity', 'unknown')} | "
                             f"**Category:** {rem.get('category', '?')} | "
                             f"**Effort:** {rem.get('effort', '?')}")
                lines.append("")
                if sf.get("url"):
                    lines.append(f"**Affected:** `{sf['url']}`")
                    lines.append("")
                lines.append("**How to fix:**")
                lines.append("")
                lines.append(rem.get("fix", "Address the vulnerability identified in the findings report."))
                lines.append("")
                lines.append(f"**Verification:** {rem.get('verification', 'Re-test after fix.')}")
                lines.append("")
                lines.append("---")
                lines.append("")

        lines.append(f"\nGenerated by MAS-AI Technologies Inc. on {metadata.date}")
        lines.append("This remediation roadmap accompanies the findings report.")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        logger.info("remediation_report.created", path=filepath)
        return filepath


class DualReportGenerator:
    """Generate both reports in one call.

    Report 1: What's broken (findings + evidence + chains)
    Report 2: How to fix it (remediation + code examples + timelines)
    """

    def __init__(self) -> None:
        self.findings_gen = BugBountyReportGenerator()
        self.remediation_gen = RemediationReportGenerator()

    def generate_both(
        self,
        vuln_findings: list[VulnFinding],
        scan_findings: list[dict[str, Any]],
        metadata: ReportMetadata,
        evidence_summary: dict[str, Any] | None = None,
        dev_profile: dict[str, Any] | None = None,
        supply_chain: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        """Generate both findings and remediation reports.

        Returns dict with 'findings_report' and 'remediation_report' paths.
        """
        findings_path = self.findings_gen.generate(
            vuln_findings, metadata, evidence_summary,
        )
        remediation_path = self.remediation_gen.generate(
            vuln_findings, scan_findings, metadata,
            dev_profile=dev_profile,
            supply_chain=supply_chain,
        )

        logger.info(
            "dual_report.generated",
            findings=findings_path,
            remediation=remediation_path,
        )

        return {
            "findings_report": findings_path,
            "remediation_report": remediation_path,
        }
