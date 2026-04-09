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
    ) -> str:
        """Generate a PDF report and return the file path."""
        os.makedirs(REPORTS_DIR, exist_ok=True)

        safe_target = metadata.target.replace(".", "_").replace("/", "_")[:30]
        filename = f"{safe_target}_{metadata.date}.pdf"
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
            return self._generate_markdown(findings, metadata)

    def _generate_markdown(
        self,
        findings: list[VulnFinding],
        metadata: ReportMetadata,
    ) -> str:
        """Fallback: generate markdown report if reportlab unavailable."""
        safe_target = metadata.target.replace(".", "_").replace("/", "_")[:30]
        filename = f"{safe_target}_{metadata.date}.md"
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
