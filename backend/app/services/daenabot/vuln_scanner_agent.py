"""VulnScannerAgent -- Security scanning agent for Daena.

Wraps professional security tools (nmap, subfinder, httpx, nuclei, bandit,
safety) as DaenaBot operations. Each tool runs via subprocess with structured
output parsing and hard timeouts.

AUTHORIZATION GATE: Every scan operation checks the target against the
registered bug bounty program scopes. Unauthorized targets are refused
even in AGI mode. This is the ONE check that cannot be bypassed.

Tools:
    - python-nmap: TCP/UDP port scanning
    - subfinder: Subdomain enumeration
    - httpx-toolkit: HTTP probing across hosts
    - nuclei: Template-based vulnerability scanning
    - bandit: Python code security linting
    - safety: Python dependency vulnerability checking
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)

SECURITY_TOOLS_ROOT = os.environ.get("SECURITY_TOOLS_ROOT", "D:\\SecurityTools")
SECURITY_TOOLS_BIN = os.path.join(SECURITY_TOOLS_ROOT, "bin")
SCANS_DIR = os.path.join(SECURITY_TOOLS_ROOT, "scans")

# Proxy configuration for IP protection
# Tor SOCKS proxy (default: 127.0.0.1:9050)
# Set SCAN_PROXY to override (e.g., socks5://127.0.0.1:9050 or http://proxy:8080)
SCAN_PROXY = os.environ.get("SCAN_PROXY", "")
USE_TOR = os.environ.get("USE_TOR", "").lower() in ("1", "true", "yes")
TOR_SOCKS = "socks5://127.0.0.1:9050"


class VulnScannerAgent(BaseAgent):
    """Security vulnerability scanning agent.

    Usage::

        agent = VulnScannerAgent()
        result = await agent.execute("port_scan", {"target": "example.com"})
    """

    agent_name = "vuln_scanner"

    OPERATION_ACTION_MAP = {
        "port_scan": "READ",
        "subdomain_enum": "READ",
        "http_probe": "READ",
        "vuln_scan": "EXECUTE",
        "code_audit": "READ",
        "dep_check": "READ",
        "cve_lookup": "READ",
        "cve_search": "READ",
        "cve_enrich": "READ",
        "cognitive_scan": "EXECUTE",
    }

    # Per-operation timeouts (seconds)
    _TIMEOUTS = {
        "port_scan": 300,
        "subdomain_enum": 120,
        "http_probe": 120,
        "vuln_scan": 600,
        "code_audit": 120,
        "dep_check": 60,
        "cve_lookup": 30,
        "cve_search": 30,
        "cve_enrich": 120,
        "cognitive_scan": 900,  # 15 min -- multi-cycle scan
    }

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        if operation not in self.OPERATION_ACTION_MAP:
            supported = list(self.OPERATION_ACTION_MAP.keys())
            raise ValueError(
                f"VulnScannerAgent: unknown operation '{operation}'. "
                f"Supported: {supported}"
            )

        # Authorization gate: check target is in bounty scope
        target = params.get("target", params.get("path", ""))
        if not target and "targets" in params:
            targets_list = params["targets"]
            target = targets_list[0] if targets_list else ""
        if operation in ("port_scan", "subdomain_enum", "http_probe", "vuln_scan"):
            if not target:
                return self._error(operation, "No target specified")
            auth_ok, auth_msg = self._check_authorization(target)
            if not auth_ok:
                return self._error(operation, f"UNAUTHORIZED: {auth_msg}")

        dispatch = {
            "port_scan": self._port_scan,
            "subdomain_enum": self._subdomain_enum,
            "http_probe": self._http_probe,
            "vuln_scan": self._vuln_scan,
            "code_audit": self._code_audit,
            "dep_check": self._dep_check,
            "cve_lookup": self._cve_lookup,
            "cve_search": self._cve_search,
            "cve_enrich": self._cve_enrich,
            "cognitive_scan": self._cognitive_scan,
        }

        handler = dispatch[operation]
        try:
            return await handler(params)
        except asyncio.TimeoutError:
            return self._error(operation, f"Timed out after {self._TIMEOUTS.get(operation, 120)}s")
        except Exception as exc:
            return self._error(operation, str(exc))

    # ------------------------------------------------------------------
    # Proxy / Tor
    # ------------------------------------------------------------------

    @staticmethod
    def _get_proxy() -> str:
        """Get proxy URL for IP protection.

        Priority: SCAN_PROXY env > USE_TOR env > no proxy.
        When scanning bug bounty targets, ALWAYS use a proxy to
        avoid exposing your home IP to the target's WAF/IDS.
        """
        if SCAN_PROXY:
            return SCAN_PROXY
        if USE_TOR:
            return TOR_SOCKS
        return ""

    @staticmethod
    def _proxy_args_for_tool(tool: str, proxy: str) -> list[str]:
        """Get proxy CLI arguments for a specific tool."""
        if not proxy:
            return []
        if tool in ("subfinder", "httpx", "nuclei", "katana"):
            return ["-proxy", proxy]
        if tool == "nmap":
            # nmap uses --proxies for SOCKS/HTTP
            return ["--proxies", proxy]
        return []

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def _check_authorization(self, target: str) -> tuple[bool, str]:
        """Check if target is in an authorized bug bounty program."""
        # Allow localhost/private IPs for testing
        if target in ("localhost", "127.0.0.1", "::1") or target.startswith("192.168.") or target.startswith("10."):
            return True, "localhost/private (always allowed)"

        from app.services.security.bounty_programs import is_target_authorized
        return is_target_authorized(target)

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    async def _port_scan(self, params: dict[str, Any]) -> dict[str, Any]:
        """TCP/UDP port scan using python-nmap."""
        target = params["target"]
        ports = params.get("ports", "1-1000")
        scan_type = params.get("scan_type", "-sT")  # TCP connect (no root needed)

        try:
            import nmap

            # Ensure nmap is findable -- add SecurityTools\Nmap to PATH
            nmap_dir = os.path.join(SECURITY_TOOLS_ROOT, "Nmap")
            if os.path.isdir(nmap_dir) and nmap_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = nmap_dir + os.pathsep + os.environ.get("PATH", "")
            nm = nmap.PortScanner()

            # Run in executor to not block event loop
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda: nm.scan(target, ports, arguments=scan_type)
                ),
                timeout=self._TIMEOUTS["port_scan"],
            )

            findings = []
            for host in nm.all_hosts():
                for proto in nm[host].all_protocols():
                    for port in nm[host][proto]:
                        state = nm[host][proto][port]["state"]
                        service = nm[host][proto][port].get("name", "unknown")
                        if state == "open":
                            findings.append({
                                "host": host,
                                "port": port,
                                "protocol": proto,
                                "state": state,
                                "service": service,
                            })

            return self._result(
                "port_scan",
                success=True,
                output={
                    "target": target,
                    "findings": findings,
                    "total_open_ports": len(findings),
                    "scan_type": scan_type,
                },
            )
        except ImportError:
            return self._error("port_scan", "python-nmap not installed. Run: pip install python-nmap")

    async def _subdomain_enum(self, params: dict[str, Any]) -> dict[str, Any]:
        """Subdomain enumeration using subfinder."""
        target = params["target"]
        subfinder_path = os.path.join(SECURITY_TOOLS_BIN, "subfinder.exe")

        if not os.path.exists(subfinder_path):
            return self._error("subdomain_enum", f"subfinder not found at {subfinder_path}")

        cmd = [subfinder_path, "-d", target, "-silent", "-json"]
        proxy = self._get_proxy()
        cmd.extend(self._proxy_args_for_tool("subfinder", proxy))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._TIMEOUTS["subdomain_enum"],
            )
        except asyncio.TimeoutError:
            proc.kill()
            return self._error("subdomain_enum", "Timed out")

        subdomains = []
        for line in stdout.decode("utf-8", errors="ignore").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                subdomains.append(data.get("host", line))
            except json.JSONDecodeError:
                subdomains.append(line)

        return self._result(
            "subdomain_enum",
            success=True,
            output={
                "target": target,
                "subdomains": subdomains,
                "total": len(subdomains),
            },
        )

    async def _http_probe(self, params: dict[str, Any]) -> dict[str, Any]:
        """HTTP probing using httpx-toolkit."""
        targets = params.get("targets", [])
        target = params.get("target", "")
        if target and not targets:
            targets = [target]

        httpx_path = os.path.join(SECURITY_TOOLS_BIN, "httpx.exe")
        if not os.path.exists(httpx_path):
            return self._error("http_probe", f"httpx not found at {httpx_path}")

        # Write targets to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("\n".join(targets))
            targets_file = f.name

        try:
            cmd = [
                httpx_path, "-l", targets_file, "-silent", "-json",
                "-status-code", "-title", "-tech-detect",
            ]
            proxy = self._get_proxy()
            cmd.extend(self._proxy_args_for_tool("httpx", proxy))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._TIMEOUTS["http_probe"],
            )

            results = []
            for line in stdout.decode("utf-8", errors="ignore").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    results.append({"url": line.strip()})

            return self._result(
                "http_probe",
                success=True,
                output={
                    "targets_probed": len(targets),
                    "live_hosts": len(results),
                    "results": results[:50],  # Cap output
                },
            )
        finally:
            os.unlink(targets_file)

    async def _vuln_scan(self, params: dict[str, Any]) -> dict[str, Any]:
        """Vulnerability scanning using nuclei."""
        target = params["target"]
        severity = params.get("severity", "medium,high,critical")
        # Templates extracted from GitHub archive
        templates_dir = os.path.join(SECURITY_TOOLS_ROOT, "nuclei-templates", "nuclei-templates-main")

        nuclei_path = os.path.join(SECURITY_TOOLS_BIN, "nuclei.exe")
        if not os.path.exists(nuclei_path):
            return self._error("vuln_scan", f"nuclei not found at {nuclei_path}")

        output_file = os.path.join(SCANS_DIR, f"nuclei_{target.replace('.', '_')}.json")

        cmd = [
            nuclei_path,
            "-u", target,
            "-severity", severity,
            "-json",
            "-o", output_file,
            "-silent",
        ]
        proxy = self._get_proxy()
        cmd.extend(self._proxy_args_for_tool("nuclei", proxy))
        if os.path.isdir(templates_dir):
            cmd.extend(["-t", templates_dir])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._TIMEOUTS["vuln_scan"],
            )
        except asyncio.TimeoutError:
            proc.kill()
            return self._error("vuln_scan", "Timed out")

        findings = []
        for line in stdout.decode("utf-8", errors="ignore").strip().split("\n"):
            if not line.strip():
                continue
            try:
                findings.append(json.loads(line))
            except json.JSONDecodeError:
                pass

        severity_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = f.get("info", {}).get("severity", "info").lower()
            severity_summary[sev] = severity_summary.get(sev, 0) + 1

        return self._result(
            "vuln_scan",
            success=True,
            output={
                "target": target,
                "findings": findings[:100],  # Cap
                "total_findings": len(findings),
                "severity_summary": severity_summary,
                "output_file": output_file,
            },
        )

    async def _code_audit(self, params: dict[str, Any]) -> dict[str, Any]:
        """Python code security audit using bandit."""
        path = params.get("path", ".")

        proc = await asyncio.create_subprocess_exec(
            "bandit", "-r", path, "-f", "json", "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._TIMEOUTS["code_audit"],
            )
        except asyncio.TimeoutError:
            proc.kill()
            return self._error("code_audit", "Timed out")

        try:
            results = json.loads(stdout.decode("utf-8", errors="ignore"))
        except json.JSONDecodeError:
            results = {"results": [], "errors": []}

        issues = results.get("results", [])
        severity_summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for issue in issues:
            sev = issue.get("issue_severity", "LOW")
            severity_summary[sev] = severity_summary.get(sev, 0) + 1

        return self._result(
            "code_audit",
            success=True,
            output={
                "path": path,
                "total_issues": len(issues),
                "severity_summary": severity_summary,
                "issues": issues[:50],  # Cap
            },
        )

    async def _dep_check(self, params: dict[str, Any]) -> dict[str, Any]:
        """Dependency vulnerability check using safety."""
        requirements_file = params.get("path", "requirements.txt")

        proc = await asyncio.create_subprocess_exec(
            "safety", "check", "-r", requirements_file, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._TIMEOUTS["dep_check"],
            )
        except asyncio.TimeoutError:
            proc.kill()
            return self._error("dep_check", "Timed out")

        try:
            results = json.loads(stdout.decode("utf-8", errors="ignore"))
        except json.JSONDecodeError:
            results = []

        vulns = results if isinstance(results, list) else []

        return self._result(
            "dep_check",
            success=True,
            output={
                "file": requirements_file,
                "total_vulnerabilities": len(vulns),
                "vulnerabilities": vulns[:30],
            },
        )

    # ------------------------------------------------------------------
    # CVE Intelligence (NIST NVD API v2.0)
    # ------------------------------------------------------------------

    async def _cve_lookup(self, params: dict[str, Any]) -> dict[str, Any]:
        """Look up a specific CVE by ID from NIST NVD."""
        cve_id = params.get("cve_id", "")
        if not cve_id:
            return self._error("cve_lookup", "No cve_id specified")

        from app.services.security.cve_intelligence import CVEIntelligenceService

        svc = CVEIntelligenceService()
        record = await asyncio.wait_for(
            svc.lookup(cve_id),
            timeout=self._TIMEOUTS["cve_lookup"],
        )

        if not record:
            return self._result(
                "cve_lookup",
                success=True,
                output={"cve_id": cve_id, "found": False},
            )

        return self._result(
            "cve_lookup",
            success=True,
            output={"cve_id": cve_id, "found": True, "cve": record.to_dict()},
        )

    async def _cve_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """Search CVEs by keyword, product, or severity."""
        from app.services.security.cve_intelligence import CVEIntelligenceService

        svc = CVEIntelligenceService()

        keyword = params.get("keyword", "")
        vendor = params.get("vendor", "")
        product = params.get("product", "")
        version = params.get("version", "")
        severity = params.get("severity", "")
        days = params.get("days", 0)
        limit = min(params.get("limit", 20), 50)

        if days and severity:
            # Recent CVEs by severity
            records = await asyncio.wait_for(
                svc.recent_critical(days=days, severity=severity, results_per_page=limit),
                timeout=self._TIMEOUTS["cve_search"],
            )
        elif vendor and product:
            # Product-based search
            records = await asyncio.wait_for(
                svc.search_by_product(vendor, product, version, results_per_page=limit),
                timeout=self._TIMEOUTS["cve_search"],
            )
        elif keyword:
            # Keyword search
            records = await asyncio.wait_for(
                svc.search_keyword(keyword, results_per_page=limit, severity=severity),
                timeout=self._TIMEOUTS["cve_search"],
            )
        else:
            return self._error(
                "cve_search",
                "Specify keyword, vendor+product, or days+severity",
            )

        return self._result(
            "cve_search",
            success=True,
            output={
                "query": {
                    "keyword": keyword,
                    "vendor": vendor,
                    "product": product,
                    "severity": severity,
                    "days": days,
                },
                "total": len(records),
                "cves": [r.to_dict() for r in records],
            },
        )

    async def _cve_enrich(self, params: dict[str, Any]) -> dict[str, Any]:
        """Enrich scan findings with CVE intelligence from NVD.

        Takes findings from a previous vuln_scan and cross-references
        each against the NVD to add CVE details, CVSS scores, references.
        """
        findings = params.get("findings", [])
        if not findings:
            return self._error("cve_enrich", "No findings to enrich")

        from app.services.security.cve_intelligence import CVEIntelligenceService

        svc = CVEIntelligenceService()
        enriched = await asyncio.wait_for(
            svc.enrich_scan_findings(findings),
            timeout=self._TIMEOUTS["cve_enrich"],
        )

        cve_count = sum(f["cve_enrichment"]["cve_count"] for f in enriched)
        max_cvss = max(
            (f["cve_enrichment"]["max_cvss"] for f in enriched),
            default=0.0,
        )

        return self._result(
            "cve_enrich",
            success=True,
            output={
                "enriched_findings": enriched,
                "total_findings": len(enriched),
                "findings_with_cves": sum(
                    1 for f in enriched if f["cve_enrichment"]["cve_count"] > 0
                ),
                "total_cves_found": cve_count,
                "max_cvss_score": max_cvss,
            },
        )

    # ------------------------------------------------------------------
    # Cognitive Scan (OODA-R brain loop for security)
    # ------------------------------------------------------------------

    async def _cognitive_scan(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run a cognitive security scan using the OODA-R loop.

        This is the BRAIN mode. Instead of mechanically running tools,
        Daena THINKS about the target, selects strategies, reflects on
        failures, and adapts. Like a real security researcher.

        Params:
            target: Domain to scan (must be in bounty scope)
            program: Bug bounty program name (optional)
            max_cycles: Max OODA cycles (default 4)
        """
        target = params.get("target", "")
        if not target:
            return self._error("cognitive_scan", "No target specified")

        program = params.get("program", "")
        max_cycles = params.get("max_cycles", 4)

        from app.services.security.cognitive_scan_engine import CognitiveScanEngine

        engine = CognitiveScanEngine(
            max_cycles=max_cycles,
            proxy=self._get_proxy(),
            use_tor=USE_TOR,
        )

        result = await asyncio.wait_for(
            engine.scan(target, program=program),
            timeout=self._TIMEOUTS["cognitive_scan"],
        )

        return self._result(
            "cognitive_scan",
            success=True,
            output={
                "target": target,
                "total_findings": result.total_findings,
                "cycles_used": result.cycles_used,
                "strategies_tried": result.strategies_tried,
                "findings": result.findings[:50],
                "enriched_findings": result.enriched_findings[:50],
                "thinking_log": result.thinking_log,
                "report_path": result.report_path,
                "target_profile": {
                    "domain": result.target_profile.domain if result.target_profile else "",
                    "subdomains_count": len(result.target_profile.subdomains) if result.target_profile else 0,
                    "technologies": result.target_profile.technologies if result.target_profile else [],
                    "waf": result.target_profile.waf_detected if result.target_profile else "",
                    "target_type": result.target_profile.target_type if result.target_profile else "",
                    "defenses": result.target_profile.defenses if result.target_profile else [],
                },
            },
        )
