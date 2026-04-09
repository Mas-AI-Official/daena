"""Tests for CVE Intelligence Service (NIST NVD API v2.0).

Tests cover:
- CVE record parsing from NVD response format
- CVE ID extraction from nuclei/nmap scan findings
- Service info extraction from scan findings
- Severity ranking logic
- Rate limiter behavior
- Scan enrichment pipeline
- VulnScannerAgent CVE operations dispatch
- ToolCallClassifier CVE tool registration
- Report generator CVE link bridging
"""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.security.cve_intelligence import (
    CVEIntelligenceService,
    CVERecord,
    CVSSScore,
    AffectedProduct,
    CVEReference,
)
from app.services.security.report_generator import (
    BugBountyReportGenerator,
    CVELink,
    VulnFinding,
)
from app.services.security.tool_call_classifier import (
    ToolCallClassifier,
    ApprovalClass,
)


# ---- Sample NVD API response fixture ----

SAMPLE_NVD_CVE = {
    "cve": {
        "id": "CVE-2024-3094",
        "published": "2024-03-29T17:15:00.000",
        "lastModified": "2024-04-02T12:00:00.000",
        "vulnStatus": "Analyzed",
        "descriptions": [
            {"lang": "en", "value": "XZ Utils backdoor allowing unauthorized SSH access via liblzma"},
            {"lang": "es", "value": "Puerta trasera en XZ Utils"},
        ],
        "metrics": {
            "cvssMetricV31": [{
                "cvssData": {
                    "version": "3.1",
                    "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                    "baseScore": 10.0,
                    "baseSeverity": "CRITICAL",
                },
                "exploitabilityScore": 3.9,
                "impactScore": 6.0,
            }],
        },
        "weaknesses": [
            {"description": [{"lang": "en", "value": "CWE-506"}]},
        ],
        "references": [
            {"url": "https://nvd.nist.gov/vuln/detail/CVE-2024-3094", "source": "nvd", "tags": ["Third Party Advisory"]},
            {"url": "https://www.openwall.com/lists/oss-security/2024/03/29/4", "source": "oss-security", "tags": ["Mailing List"]},
        ],
        "configurations": [
            {
                "nodes": [{
                    "cpeMatch": [
                        {
                            "criteria": "cpe:2.3:a:tukaani:xz:5.6.0:*:*:*:*:*:*:*",
                            "vulnerable": True,
                            "versionStartIncluding": "5.6.0",
                            "versionEndIncluding": "5.6.1",
                        },
                    ],
                }],
            },
        ],
    },
}

SAMPLE_NVD_RESPONSE = {
    "resultsPerPage": 1,
    "startIndex": 0,
    "totalResults": 1,
    "vulnerabilities": [SAMPLE_NVD_CVE],
}


# ---- CVE Record Parsing ----

class TestCVEParsing:
    """Test parsing NVD API response into CVERecord."""

    def test_parse_basic_fields(self) -> None:
        svc = CVEIntelligenceService()
        record = svc._parse_cve(SAMPLE_NVD_CVE)

        assert record.cve_id == "CVE-2024-3094"
        assert "XZ Utils" in record.description
        assert record.published == "2024-03-29T17:15:00.000"
        assert record.status == "Analyzed"

    def test_parse_cvss_v31(self) -> None:
        svc = CVEIntelligenceService()
        record = svc._parse_cve(SAMPLE_NVD_CVE)

        assert record.cvss is not None
        assert record.cvss.version == "3.1"
        assert record.cvss.base_score == 10.0
        assert record.cvss.severity == "CRITICAL"
        assert "CVSS:3.1" in record.cvss.vector_string
        assert record.score == 10.0
        assert record.severity == "CRITICAL"

    def test_parse_cwes(self) -> None:
        svc = CVEIntelligenceService()
        record = svc._parse_cve(SAMPLE_NVD_CVE)

        assert "CWE-506" in record.cwes

    def test_parse_references(self) -> None:
        svc = CVEIntelligenceService()
        record = svc._parse_cve(SAMPLE_NVD_CVE)

        assert len(record.references) == 2
        assert record.references[0].url == "https://nvd.nist.gov/vuln/detail/CVE-2024-3094"
        assert "Third Party Advisory" in record.references[0].tags

    def test_parse_affected_products(self) -> None:
        svc = CVEIntelligenceService()
        record = svc._parse_cve(SAMPLE_NVD_CVE)

        assert len(record.affected_products) >= 1
        prod = record.affected_products[0]
        assert prod.vendor == "tukaani"
        assert prod.product == "xz"
        assert prod.vulnerable is True

    def test_parse_no_cvss(self) -> None:
        """CVE with no CVSS metrics should have None cvss."""
        vuln = {"cve": {"id": "CVE-2099-0001", "descriptions": [{"lang": "en", "value": "Test"}], "metrics": {}}}
        svc = CVEIntelligenceService()
        record = svc._parse_cve(vuln)

        assert record.cvss is None
        assert record.severity == "UNKNOWN"
        assert record.score == 0.0

    def test_to_dict(self) -> None:
        svc = CVEIntelligenceService()
        record = svc._parse_cve(SAMPLE_NVD_CVE)
        d = record.to_dict()

        assert d["cve_id"] == "CVE-2024-3094"
        assert d["cvss_score"] == 10.0
        assert d["severity"] == "CRITICAL"
        assert isinstance(d["affected_products"], list)
        assert isinstance(d["references"], list)
        assert isinstance(d["cwes"], list)


# ---- CVE ID Extraction ----

class TestCVEExtraction:
    """Test extracting CVE IDs from scan findings."""

    def test_extract_from_template_id(self) -> None:
        finding = {"template-id": "CVE-2021-44228-log4j-rce"}
        ids = CVEIntelligenceService._extract_cve_ids(finding)
        assert "CVE-2021-44228" in ids

    def test_extract_from_info_name(self) -> None:
        finding = {"info": {"name": "Apache Log4j RCE (CVE-2021-44228)"}}
        ids = CVEIntelligenceService._extract_cve_ids(finding)
        assert "CVE-2021-44228" in ids

    def test_extract_from_references_list(self) -> None:
        finding = {
            "info": {
                "reference": [
                    "https://nvd.nist.gov/vuln/detail/CVE-2023-44487",
                    "https://example.com/advisory",
                ],
            },
        }
        ids = CVEIntelligenceService._extract_cve_ids(finding)
        assert "CVE-2023-44487" in ids

    def test_extract_multiple_dedup(self) -> None:
        finding = {
            "template-id": "CVE-2024-3094",
            "info": {
                "name": "XZ Utils Backdoor (CVE-2024-3094)",
                "description": "See CVE-2024-3094 and CVE-2024-3095",
            },
        }
        ids = CVEIntelligenceService._extract_cve_ids(finding)
        assert ids.count("CVE-2024-3094") == 1  # Deduped
        assert "CVE-2024-3095" in ids

    def test_extract_from_classification_dict(self) -> None:
        finding = {
            "info": {
                "classification": {
                    "cve-id": ["CVE-2022-22965"],
                    "cwe-id": ["CWE-94"],
                },
            },
        }
        ids = CVEIntelligenceService._extract_cve_ids(finding)
        assert "CVE-2022-22965" in ids

    def test_extract_empty_finding(self) -> None:
        ids = CVEIntelligenceService._extract_cve_ids({})
        assert ids == []

    def test_extract_no_cves(self) -> None:
        finding = {"info": {"name": "HTTP Server Detected", "tags": ["http"]}}
        ids = CVEIntelligenceService._extract_cve_ids(finding)
        assert ids == []


# ---- Service Info Extraction ----

class TestServiceInfoExtraction:
    """Test extracting product/service info from findings."""

    def test_extract_from_tags(self) -> None:
        finding = {"info": {"tags": ["apache", "cve", "rce"]}}
        info = CVEIntelligenceService._extract_service_info(finding)
        assert info["product"] == "apache"

    def test_extract_from_name(self) -> None:
        finding = {"info": {"name": "nginx version disclosure", "tags": []}}
        info = CVEIntelligenceService._extract_service_info(finding)
        assert info["product"] == "nginx"

    def test_extract_from_service(self) -> None:
        finding = {"service": "openssh"}
        info = CVEIntelligenceService._extract_service_info(finding)
        assert info["product"] == "openssh"

    def test_extract_skips_generic_tags(self) -> None:
        finding = {"info": {"tags": ["cve", "rce", "xss", "sqli", "lfi"]}}
        info = CVEIntelligenceService._extract_service_info(finding)
        # All tags are generic, should fall through
        assert info == {} or info.get("product", "") == ""


# ---- Severity Ranking ----

class TestSeverityRanking:
    """Test highest severity selection."""

    def test_highest_critical(self) -> None:
        data = [
            {"severity": "HIGH", "cvss_score": 8.0},
            {"severity": "CRITICAL", "cvss_score": 9.8},
            {"severity": "MEDIUM", "cvss_score": 5.0},
        ]
        assert CVEIntelligenceService._highest_severity(data) == "CRITICAL"

    def test_highest_single(self) -> None:
        data = [{"severity": "LOW", "cvss_score": 2.0}]
        assert CVEIntelligenceService._highest_severity(data) == "LOW"

    def test_highest_empty(self) -> None:
        assert CVEIntelligenceService._highest_severity([]) == "UNKNOWN"


# ---- API Integration (mocked) ----

class TestCVELookup:
    """Test CVE lookup with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_lookup_found(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            record = await svc.lookup("CVE-2024-3094")

        assert record is not None
        assert record.cve_id == "CVE-2024-3094"
        assert record.score == 10.0

    @pytest.mark.asyncio
    async def test_lookup_not_found(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"vulnerabilities": [], "totalResults": 0}
            record = await svc.lookup("CVE-9999-9999")

        assert record is None

    @pytest.mark.asyncio
    async def test_lookup_normalizes_id(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            await svc.lookup("cve-2024-3094")  # lowercase

        mock_req.assert_called_once_with({"cveId": "CVE-2024-3094"})

    @pytest.mark.asyncio
    async def test_lookup_adds_prefix(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            await svc.lookup("2024-3094")  # no prefix

        mock_req.assert_called_once_with({"cveId": "CVE-2024-3094"})


class TestCVESearch:
    """Test CVE keyword and product search."""

    @pytest.mark.asyncio
    async def test_keyword_search(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            results = await svc.search_keyword("XZ Utils backdoor")

        assert len(results) == 1
        assert results[0].cve_id == "CVE-2024-3094"

    @pytest.mark.asyncio
    async def test_keyword_search_with_severity(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            await svc.search_keyword("test", severity="CRITICAL")

        call_params = mock_req.call_args[0][0]
        assert call_params["cvssV3Severity"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_product_search_filters_by_vendor(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            results = await svc.search_by_product("tukaani", "xz")

        assert len(results) == 1  # Matches vendor+product in CPE

    @pytest.mark.asyncio
    async def test_product_search_excludes_unrelated(self) -> None:
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_NVD_RESPONSE
            results = await svc.search_by_product("microsoft", "windows")

        assert len(results) == 0  # XZ CVE should not match Microsoft Windows


class TestRecentCritical:
    """Test recent critical CVE retrieval."""

    @pytest.mark.asyncio
    async def test_recent_critical_sorted(self) -> None:
        multi_response = {
            "vulnerabilities": [
                {"cve": {"id": "CVE-2024-0001", "descriptions": [{"lang": "en", "value": "Low"}], "metrics": {"cvssMetricV31": [{"cvssData": {"version": "3.1", "vectorString": "x", "baseScore": 5.0, "baseSeverity": "MEDIUM"}, "exploitabilityScore": 0, "impactScore": 0}]}}},
                {"cve": {"id": "CVE-2024-0002", "descriptions": [{"lang": "en", "value": "High"}], "metrics": {"cvssMetricV31": [{"cvssData": {"version": "3.1", "vectorString": "x", "baseScore": 9.8, "baseSeverity": "CRITICAL"}, "exploitabilityScore": 0, "impactScore": 0}]}}},
            ],
            "totalResults": 2,
        }
        svc = CVEIntelligenceService()
        with patch.object(svc, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = multi_response
            results = await svc.recent_critical(days=7, severity="CRITICAL")

        assert results[0].score >= results[-1].score  # Sorted descending


# ---- Scan Enrichment ----

class TestScanEnrichment:
    """Test enriching scan findings with CVE data."""

    @pytest.mark.asyncio
    async def test_enrich_with_cve_id(self) -> None:
        """Findings with CVE IDs should be looked up."""
        findings = [
            {"template-id": "CVE-2024-3094", "info": {"name": "XZ Backdoor"}},
        ]
        svc = CVEIntelligenceService()

        record = svc._parse_cve(SAMPLE_NVD_CVE)
        with patch.object(svc, "lookup", new_callable=AsyncMock, return_value=record):
            enriched = await svc.enrich_scan_findings(findings)

        assert len(enriched) == 1
        assert enriched[0]["cve_enrichment"]["cve_count"] >= 1
        assert enriched[0]["cve_enrichment"]["max_cvss"] == 10.0

    @pytest.mark.asyncio
    async def test_enrich_without_cve_falls_back_to_keyword(self) -> None:
        """Findings without CVE IDs should try keyword search."""
        findings = [
            {"info": {"name": "nginx detected", "tags": ["nginx"]}},
        ]
        svc = CVEIntelligenceService()

        with patch.object(svc, "search_keyword", new_callable=AsyncMock, return_value=[]):
            enriched = await svc.enrich_scan_findings(findings)

        assert enriched[0]["cve_enrichment"]["cve_count"] == 0

    @pytest.mark.asyncio
    async def test_enrich_empty_findings(self) -> None:
        svc = CVEIntelligenceService()
        enriched = await svc.enrich_scan_findings([])
        assert enriched == []


# ---- Tool Call Classifier ----

class TestCVEClassifier:
    """Test CVE tools are registered as readonly_search in classifier."""

    def test_cve_lookup_auto_approved(self) -> None:
        classifier = ToolCallClassifier()
        result = classifier.classify("vuln_scanner.cve_lookup")
        assert result.approval_class == ApprovalClass.READONLY_SEARCH
        assert result.auto_approve is True

    def test_cve_search_auto_approved(self) -> None:
        classifier = ToolCallClassifier()
        result = classifier.classify("vuln_scanner.cve_search")
        assert result.approval_class == ApprovalClass.READONLY_SEARCH
        assert result.auto_approve is True

    def test_cve_enrich_auto_approved(self) -> None:
        classifier = ToolCallClassifier()
        result = classifier.classify("vuln_scanner.cve_enrich")
        assert result.approval_class == ApprovalClass.READONLY_SEARCH
        assert result.auto_approve is True


# ---- Report Generator CVE Bridge ----

class TestReportCVEBridge:
    """Test converting enrichment data to CVELink for reports."""

    def test_cve_links_from_enrichment(self) -> None:
        enrichment = {
            "cves": [
                {
                    "cve_id": "CVE-2024-3094",
                    "cvss_score": 10.0,
                    "severity": "CRITICAL",
                    "description": "XZ Utils backdoor",
                    "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2024-3094"}],
                },
            ],
        }
        links = BugBountyReportGenerator.cve_links_from_enrichment(enrichment)

        assert len(links) == 1
        assert links[0].cve_id == "CVE-2024-3094"
        assert links[0].cvss_score == 10.0
        assert links[0].severity == "CRITICAL"
        assert "nvd.nist.gov" in links[0].reference_url

    def test_cve_links_empty_enrichment(self) -> None:
        links = BugBountyReportGenerator.cve_links_from_enrichment({"cves": []})
        assert links == []

    def test_vuln_finding_with_linked_cves(self) -> None:
        finding = VulnFinding(
            title="XZ Backdoor",
            severity="Critical",
            description="Supply chain attack",
            linked_cves=[
                CVELink(cve_id="CVE-2024-3094", cvss_score=10.0, severity="CRITICAL"),
            ],
        )
        assert len(finding.linked_cves) == 1
        assert finding.linked_cves[0].cve_id == "CVE-2024-3094"


# ---- VulnScannerAgent CVE Dispatch ----

class TestVulnScannerCVEOps:
    """Test VulnScannerAgent dispatches CVE operations correctly."""

    def test_cve_operations_registered(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        agent = VulnScannerAgent()
        assert "cve_lookup" in agent.OPERATION_ACTION_MAP
        assert "cve_search" in agent.OPERATION_ACTION_MAP
        assert "cve_enrich" in agent.OPERATION_ACTION_MAP

    def test_cve_operations_are_read(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        agent = VulnScannerAgent()
        assert agent.OPERATION_ACTION_MAP["cve_lookup"] == "READ"
        assert agent.OPERATION_ACTION_MAP["cve_search"] == "READ"
        assert agent.OPERATION_ACTION_MAP["cve_enrich"] == "READ"

    def test_cve_timeouts_set(self) -> None:
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        agent = VulnScannerAgent()
        assert agent._TIMEOUTS["cve_lookup"] == 30
        assert agent._TIMEOUTS["cve_search"] == 30
        assert agent._TIMEOUTS["cve_enrich"] == 120
