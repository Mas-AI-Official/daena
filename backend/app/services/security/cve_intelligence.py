"""CVE Intelligence Service -- NIST NVD API v2.0 integration.

Provides real-time CVE lookup, search, and scan enrichment using the
National Vulnerability Database. Every finding from nuclei/nmap/httpx
can be cross-referenced against known CVEs with CVSS scores, affected
products, and remediation references.

NIST NVD API v2.0:
    - Base URL: https://services.nvd.nist.gov/rest/json/cves/2.0
    - Rate limit: 5 req/30s (no key), 50 req/30s (with key)
    - No authentication required (API key optional for higher rate)

This is what closes the gap with HexStrike's CVE intelligence feed.
Daena goes further: OODA engine can reason about which CVEs actually
apply to the target based on detected services, not just pattern match.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_API_KEY = os.environ.get("NVD_API_KEY", "")  # Optional, raises rate limit

# Rate limiter: 5 req/30s without key, 50/30s with key
_MAX_REQUESTS = 50 if NVD_API_KEY else 5
_WINDOW_SECONDS = 30
_request_timestamps: list[float] = []
_rate_lock = asyncio.Lock()


async def _rate_limit() -> None:
    """Enforce NVD rate limits."""
    async with _rate_lock:
        now = time.monotonic()
        # Prune old timestamps
        while _request_timestamps and _request_timestamps[0] < now - _WINDOW_SECONDS:
            _request_timestamps.pop(0)
        if len(_request_timestamps) >= _MAX_REQUESTS:
            wait = _WINDOW_SECONDS - (now - _request_timestamps[0]) + 0.1
            if wait > 0:
                logger.info("cve_intel.rate_limit", wait_seconds=round(wait, 1))
                await asyncio.sleep(wait)
        _request_timestamps.append(time.monotonic())


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CVEReference:
    """A reference URL for a CVE."""
    url: str
    source: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class CVSSScore:
    """CVSS scoring for a CVE."""
    version: str = ""  # "3.1", "3.0", "2.0"
    vector_string: str = ""
    base_score: float = 0.0
    severity: str = ""  # CRITICAL, HIGH, MEDIUM, LOW, NONE
    exploitability_score: float = 0.0
    impact_score: float = 0.0


@dataclass
class AffectedProduct:
    """A product/version affected by a CVE (from CPE match)."""
    vendor: str = ""
    product: str = ""
    version_start: str = ""
    version_end: str = ""
    cpe_uri: str = ""
    vulnerable: bool = True


@dataclass
class CVERecord:
    """A single CVE entry from NVD."""
    cve_id: str
    description: str = ""
    published: str = ""
    last_modified: str = ""
    cvss: CVSSScore | None = None
    cwes: list[str] = field(default_factory=list)
    references: list[CVEReference] = field(default_factory=list)
    affected_products: list[AffectedProduct] = field(default_factory=list)
    source: str = "NVD"
    status: str = ""  # Analyzed, Modified, Awaiting Analysis, etc.

    @property
    def severity(self) -> str:
        if self.cvss:
            return self.cvss.severity
        return "UNKNOWN"

    @property
    def score(self) -> float:
        if self.cvss:
            return self.cvss.base_score
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cve_id": self.cve_id,
            "description": self.description,
            "published": self.published,
            "last_modified": self.last_modified,
            "severity": self.severity,
            "cvss_score": self.score,
            "cvss_vector": self.cvss.vector_string if self.cvss else "",
            "cwes": self.cwes,
            "affected_products": [
                {"vendor": p.vendor, "product": p.product, "cpe": p.cpe_uri}
                for p in self.affected_products
            ],
            "references": [
                {"url": r.url, "source": r.source, "tags": r.tags}
                for r in self.references
            ],
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# NVD API Client
# ---------------------------------------------------------------------------

class CVEIntelligenceService:
    """NIST NVD CVE intelligence service.

    Provides CVE lookup, keyword search, CPE-based search, severity
    filtering, and scan result enrichment.

    Usage::

        svc = CVEIntelligenceService()

        # Lookup specific CVE
        cve = await svc.lookup("CVE-2024-3094")

        # Search by keyword
        results = await svc.search_keyword("Apache Log4j remote code execution")

        # Search by product (CPE)
        results = await svc.search_by_product("apache", "httpd", "2.4.49")

        # Enrich scan findings with CVE data
        enriched = await svc.enrich_scan_findings(nuclei_findings)

        # Get recent critical CVEs
        results = await svc.recent_critical(days=7)
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def _request(self, params: dict[str, str]) -> dict[str, Any]:
        """Make a rate-limited request to NVD API."""
        await _rate_limit()

        headers = {"Accept": "application/json"}
        if NVD_API_KEY:
            headers["apiKey"] = NVD_API_KEY

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(NVD_BASE_URL, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def _parse_cve(self, vuln: dict[str, Any]) -> CVERecord:
        """Parse a single CVE entry from NVD response."""
        cve_data = vuln.get("cve", {})
        cve_id = cve_data.get("id", "")

        # Description (English preferred)
        desc = ""
        for d in cve_data.get("descriptions", []):
            if d.get("lang") == "en":
                desc = d.get("value", "")
                break
        if not desc:
            descs = cve_data.get("descriptions", [])
            desc = descs[0].get("value", "") if descs else ""

        # CVSS (prefer v3.1 > v3.0 > v2.0)
        cvss = None
        metrics = cve_data.get("metrics", {})
        for version_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            metric_list = metrics.get(version_key, [])
            if metric_list:
                m = metric_list[0]
                cvss_data = m.get("cvssData", {})
                cvss = CVSSScore(
                    version=cvss_data.get("version", ""),
                    vector_string=cvss_data.get("vectorString", ""),
                    base_score=cvss_data.get("baseScore", 0.0),
                    severity=cvss_data.get("baseSeverity", m.get("baseSeverity", "")).upper(),
                    exploitability_score=m.get("exploitabilityScore", 0.0),
                    impact_score=m.get("impactScore", 0.0),
                )
                break

        # CWEs
        cwes = []
        for weakness in cve_data.get("weaknesses", []):
            for wd in weakness.get("description", []):
                cwe_val = wd.get("value", "")
                if cwe_val and cwe_val != "NVD-CWE-noinfo":
                    cwes.append(cwe_val)

        # References
        refs = []
        for r in cve_data.get("references", []):
            refs.append(CVEReference(
                url=r.get("url", ""),
                source=r.get("source", ""),
                tags=r.get("tags", []),
            ))

        # Affected products (CPE configurations)
        products = []
        for config in cve_data.get("configurations", []):
            for node in config.get("nodes", []):
                for match in node.get("cpeMatch", []):
                    cpe = match.get("criteria", "")
                    parts = cpe.split(":") if cpe else []
                    vendor = parts[3] if len(parts) > 3 else ""
                    product = parts[4] if len(parts) > 4 else ""
                    products.append(AffectedProduct(
                        vendor=vendor,
                        product=product,
                        version_start=match.get("versionStartIncluding", ""),
                        version_end=match.get("versionEndIncluding", match.get("versionEndExcluding", "")),
                        cpe_uri=cpe,
                        vulnerable=match.get("vulnerable", True),
                    ))

        return CVERecord(
            cve_id=cve_id,
            description=desc,
            published=cve_data.get("published", ""),
            last_modified=cve_data.get("lastModified", ""),
            cvss=cvss,
            cwes=cwes,
            references=refs,
            affected_products=products,
            source="NVD",
            status=cve_data.get("vulnStatus", ""),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def lookup(self, cve_id: str) -> CVERecord | None:
        """Look up a specific CVE by ID.

        Args:
            cve_id: CVE identifier (e.g., "CVE-2024-3094").

        Returns:
            CVERecord or None if not found.
        """
        cve_id = cve_id.upper().strip()
        if not cve_id.startswith("CVE-"):
            cve_id = f"CVE-{cve_id}"

        try:
            data = await self._request({"cveId": cve_id})
            vulns = data.get("vulnerabilities", [])
            if vulns:
                record = self._parse_cve(vulns[0])
                logger.info("cve_intel.lookup", cve_id=cve_id, severity=record.severity)
                return record
            return None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            logger.error("cve_intel.lookup_error", cve_id=cve_id, status=exc.response.status_code)
            raise
        except Exception as exc:
            logger.error("cve_intel.lookup_error", cve_id=cve_id, error=str(exc))
            raise

    async def search_keyword(
        self,
        keyword: str,
        *,
        results_per_page: int = 20,
        start_index: int = 0,
        severity: str = "",
    ) -> list[CVERecord]:
        """Search CVEs by keyword in description.

        Args:
            keyword: Search term (e.g., "Log4j remote code execution").
            results_per_page: Max results (1-2000, default 20).
            severity: Filter by CVSS v3 severity (CRITICAL, HIGH, MEDIUM, LOW).

        Returns:
            List of matching CVERecords.
        """
        params: dict[str, str] = {
            "keywordSearch": keyword,
            "resultsPerPage": str(min(results_per_page, 2000)),
            "startIndex": str(start_index),
        }
        if severity:
            params["cvssV3Severity"] = severity.upper()

        try:
            data = await self._request(params)
            records = [self._parse_cve(v) for v in data.get("vulnerabilities", [])]
            total = data.get("totalResults", 0)
            logger.info(
                "cve_intel.keyword_search",
                keyword=keyword,
                returned=len(records),
                total=total,
            )
            return records
        except Exception as exc:
            logger.error("cve_intel.search_error", keyword=keyword, error=str(exc))
            raise

    async def search_by_product(
        self,
        vendor: str,
        product: str,
        version: str = "",
        *,
        results_per_page: int = 20,
    ) -> list[CVERecord]:
        """Search CVEs by product using virtual CPE match.

        Args:
            vendor: Vendor name (e.g., "apache").
            product: Product name (e.g., "httpd").
            version: Specific version (e.g., "2.4.49"). Optional.

        Returns:
            List of CVERecords affecting this product.
        """
        # Build keyword search that targets specific product
        keyword = f"{vendor} {product}"
        if version:
            keyword += f" {version}"

        params: dict[str, str] = {
            "keywordSearch": keyword,
            "resultsPerPage": str(min(results_per_page, 2000)),
        }

        try:
            data = await self._request(params)
            all_records = [self._parse_cve(v) for v in data.get("vulnerabilities", [])]

            # Post-filter: keep only CVEs that actually affect this vendor/product
            vendor_lower = vendor.lower()
            product_lower = product.lower()
            filtered = []
            for rec in all_records:
                # Check CPE matches
                for ap in rec.affected_products:
                    if vendor_lower in ap.vendor.lower() and product_lower in ap.product.lower():
                        if version:
                            # Version range check (simplified)
                            if version in ap.cpe_uri or not ap.version_end:
                                filtered.append(rec)
                                break
                        else:
                            filtered.append(rec)
                            break
                else:
                    # Fallback: check description
                    desc_lower = rec.description.lower()
                    if vendor_lower in desc_lower and product_lower in desc_lower:
                        filtered.append(rec)

            logger.info(
                "cve_intel.product_search",
                vendor=vendor,
                product=product,
                version=version,
                raw=len(all_records),
                filtered=len(filtered),
            )
            return filtered
        except Exception as exc:
            logger.error("cve_intel.product_search_error", error=str(exc))
            raise

    async def recent_critical(
        self,
        days: int = 7,
        severity: str = "CRITICAL",
        results_per_page: int = 50,
    ) -> list[CVERecord]:
        """Get recent CVEs by severity.

        Args:
            days: Look back N days (default 7).
            severity: CVSS v3 severity filter (default CRITICAL).

        Returns:
            List of recent CVERecords sorted by score descending.
        """
        from datetime import datetime, timedelta, timezone

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        params: dict[str, str] = {
            "pubStartDate": start.strftime("%Y-%m-%dT00:00:00.000"),
            "pubEndDate": end.strftime("%Y-%m-%dT23:59:59.999"),
            "cvssV3Severity": severity.upper(),
            "resultsPerPage": str(min(results_per_page, 2000)),
        }

        try:
            data = await self._request(params)
            records = [self._parse_cve(v) for v in data.get("vulnerabilities", [])]
            records.sort(key=lambda r: r.score, reverse=True)
            logger.info(
                "cve_intel.recent_critical",
                days=days,
                severity=severity,
                count=len(records),
            )
            return records
        except Exception as exc:
            logger.error("cve_intel.recent_critical_error", error=str(exc))
            raise

    async def enrich_scan_findings(
        self,
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Enrich scan findings with CVE intelligence.

        Takes raw findings from nuclei/nmap/httpx and cross-references
        each against NVD to add CVE IDs, CVSS scores, and references.

        This is Daena's edge over HexStrike: not just wrapping the API,
        but intelligently matching scan output to known vulnerabilities.

        Args:
            findings: List of scan finding dicts (from vuln_scanner_agent).
                Each may have: template_id, info.name, info.severity,
                matched_at, host, port, service.

        Returns:
            Enriched findings with 'cve_enrichment' key added.
        """
        enriched = []
        for finding in findings:
            enriched_finding = dict(finding)

            # Extract CVE IDs already in the finding (nuclei often includes them)
            cve_ids = self._extract_cve_ids(finding)

            # Extract service/product info for product-based lookup
            service_info = self._extract_service_info(finding)

            cve_data: list[dict[str, Any]] = []

            # Look up any CVE IDs already referenced
            if cve_ids:
                lookups = await asyncio.gather(
                    *[self.lookup(cve_id) for cve_id in cve_ids[:5]],  # Cap at 5
                    return_exceptions=True,
                )
                for result in lookups:
                    if isinstance(result, CVERecord):
                        cve_data.append(result.to_dict())

            # If no CVE IDs found, try keyword search from finding name
            if not cve_data and service_info:
                try:
                    keyword = f"{service_info['product']} {service_info.get('version', '')}"
                    results = await self.search_keyword(keyword.strip(), results_per_page=5)
                    for r in results:
                        cve_data.append(r.to_dict())
                except Exception:
                    pass  # Non-critical enrichment failure

            enriched_finding["cve_enrichment"] = {
                "cve_count": len(cve_data),
                "cves": cve_data[:10],  # Cap enrichment data
                "max_cvss": max((c["cvss_score"] for c in cve_data), default=0.0),
                "max_severity": self._highest_severity(cve_data),
            }
            enriched.append(enriched_finding)

        logger.info(
            "cve_intel.enrich_complete",
            findings=len(findings),
            enriched_with_cves=sum(1 for f in enriched if f["cve_enrichment"]["cve_count"] > 0),
        )
        return enriched

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_cve_ids(finding: dict[str, Any]) -> list[str]:
        """Extract CVE IDs from a scan finding."""
        import re
        cve_pattern = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
        cve_ids: list[str] = []

        # Check common locations in nuclei output
        info = finding.get("info", {})
        for field_name in ("name", "description", "reference", "classification"):
            val = info.get(field_name, "")
            if isinstance(val, str):
                cve_ids.extend(cve_pattern.findall(val))
            elif isinstance(val, dict):
                # classification.cve-id
                for k, v in val.items():
                    if isinstance(v, str):
                        cve_ids.extend(cve_pattern.findall(v))
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, str):
                                cve_ids.extend(cve_pattern.findall(item))

        # Check references list
        refs = info.get("reference", [])
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str):
                    cve_ids.extend(cve_pattern.findall(ref))

        # Check template-id (nuclei templates often named after CVEs)
        template_id = finding.get("template-id", finding.get("templateID", ""))
        if isinstance(template_id, str):
            cve_ids.extend(cve_pattern.findall(template_id))

        # Deduplicate preserving order
        seen = set()
        unique = []
        for cve_id in cve_ids:
            upper = cve_id.upper()
            if upper not in seen:
                seen.add(upper)
                unique.append(upper)
        return unique

    # Words that are NOT real products -- skip these for CVE keyword search.
    # Searching NVD for "Header" or "Analysis" returns thousands of irrelevant CVEs.
    _NOISE_KEYWORDS = frozenset({
        "header", "analysis", "security", "missing", "misconfiguration",
        "discovery", "path", "finding", "test", "check", "scan", "probe",
        "info", "informational", "low", "medium", "high", "critical",
        "dns", "dns_records", "records", "http", "https", "ftp", "smtp",
        "some", "unknown", "general", "other", "none", "default",
    })

    @staticmethod
    def _extract_service_info(finding: dict[str, Any]) -> dict[str, str]:
        """Extract service/product info from a scan finding.

        Only returns a product if we can identify an actual software name
        (e.g., "TornadoServer", "nginx", "Apache"). Generic words like
        "Header" or "Analysis" are filtered out to avoid polluting CVE
        searches with irrelevant results.
        """
        info = finding.get("info", {})
        name = info.get("name", "")
        tags = info.get("tags", [])

        product = ""
        version = ""

        # Priority 1: nuclei tags (highest quality -- explicit product identifiers)
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag not in ("cve", "rce", "sqli", "xss", "lfi"):
                    product = tag
                    break

        # Priority 2: tech stack from httpx fingerprinting (e.g., "TornadoServer:6.5.5")
        if not product:
            techs = finding.get("tech", finding.get("technologies", []))
            if isinstance(techs, list):
                for tech in techs:
                    tech_str = str(tech).strip()
                    if tech_str.lower() not in CVEIntelligenceService._NOISE_KEYWORDS:
                        if ":" in tech_str:
                            parts = tech_str.split(":", 1)
                            product = parts[0]
                            version = parts[1]
                        else:
                            product = tech_str
                        break

        # Priority 3: service field from nmap output
        service = finding.get("service", "")
        if service and not product:
            product = service

        # Priority 4: finding name -- last resort, heavily filtered
        if not product and name:
            import re
            tokens = re.split(r"[\s:/\-]+", name)
            for token in tokens:
                token_clean = token.strip().lower()
                if (
                    len(token_clean) > 2
                    and token_clean not in CVEIntelligenceService._NOISE_KEYWORDS
                    and not token_clean.startswith("http")
                    and "." not in token_clean  # Skip URLs/domains
                ):
                    product = token.strip()
                    break

        # Extract version from product string if colon-separated
        if product and ":" in product:
            parts = product.split(":", 1)
            product = parts[0]
            version = parts[1] if len(parts) > 1 else ""

        if not product:
            return {}

        return {"product": product, "version": version}

    @staticmethod
    def _highest_severity(cve_data: list[dict[str, Any]]) -> str:
        """Get highest severity from CVE list."""
        order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0, "UNKNOWN": -1}
        highest = "UNKNOWN"
        highest_val = -1
        for c in cve_data:
            sev = c.get("severity", "UNKNOWN").upper()
            val = order.get(sev, -1)
            if val > highest_val:
                highest_val = val
                highest = sev
        return highest
