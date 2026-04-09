"""CognitiveScanEngine -- OODA-R loop for security scanning.

The problem: VulnScannerAgent executes tools mechanically. It runs
subfinder, gets 404s, moves on. A script kiddie approach.

The fix: Wrap every scan in an OODA cycle so Daena THINKS like a
security researcher, not a tool runner.

OODA-R for Security:
    OBSERVE: What do we know about this target? What tech stack?
             What defenses? What did previous scans reveal?
    ORIENT:  What KIND of target is this? (hardened cloud, startup,
             legacy system). Which scan strategy will actually work?
             Select security reasoning frameworks.
    DECIDE:  Generate ranked strategies. A real researcher against
             Google doesn't just run nuclei -- they analyze headers,
             check CT logs, fuzz paths, probe business logic.
    ACT:     Execute the chosen strategy via VulnScannerAgent.
    REFLECT: Scan returned 404s? WHY? WAF? Wrong approach? What
             channels are still open? Constraint probe decomposes
             the failure and finds alternative paths.

This is what makes Daena a researcher, not a script kiddie.
This is what Masoud means by "Mythos-level thinking."
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TargetProfile:
    """What we KNOW about a target (observed, not assumed)."""
    domain: str
    subdomains: list[str] = field(default_factory=list)
    live_hosts: list[dict[str, Any]] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    waf_detected: str = ""  # "cloudflare", "akamai", "google_frontend", ""
    http_version: str = ""  # "HTTP/1.1", "HTTP/2", "HTTP/3"
    response_headers: dict[str, str] = field(default_factory=dict)
    interesting_paths: list[str] = field(default_factory=list)
    cve_intel: list[dict[str, Any]] = field(default_factory=list)
    defenses: list[str] = field(default_factory=list)
    target_type: str = ""  # "hardened_cloud", "startup", "legacy", "api_only"


@dataclass
class ScanStrategy:
    """A candidate scan approach."""
    name: str
    description: str
    steps: list[dict[str, Any]]  # Each step: {"operation": "...", "params": {...}}
    reasoning: str = ""
    confidence: float = 0.5
    stealth_level: str = "medium"  # "passive", "low", "medium", "high"
    frameworks_used: list[str] = field(default_factory=list)
    pre_mortem_risks: list[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class ScanCycleResult:
    """Result of one OODA cycle."""
    cycle: int
    strategy_name: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    raw_results: list[dict[str, Any]] = field(default_factory=list)
    success: bool = False
    failure_reason: str = ""
    open_channels: list[str] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)  # Daena's thought process


@dataclass
class CognitiveScanResult:
    """Final output of a cognitive scan."""
    target: str
    total_findings: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    enriched_findings: list[dict[str, Any]] = field(default_factory=list)
    cycles_used: int = 0
    strategies_tried: list[str] = field(default_factory=list)
    thinking_log: list[str] = field(default_factory=list)
    target_profile: TargetProfile | None = None
    report_path: str = ""


# ---------------------------------------------------------------------------
# Strategy Templates
# ---------------------------------------------------------------------------

def _passive_osint_strategy(target: str) -> ScanStrategy:
    """Strategy 1: Pure passive -- no direct target contact."""
    return ScanStrategy(
        name="passive_osint",
        description="Passive reconnaissance. Zero direct contact with target. "
                    "Query CT logs, DNS records, search engines, cached data.",
        steps=[
            {"operation": "cve_search", "params": {"keyword": target, "severity": "HIGH", "limit": 20}},
            # CT logs via crt.sh (passive, public database)
            {"operation": "_ct_log_query", "params": {"domain": target}},
            # DNS records (standard resolution, not zone transfer)
            {"operation": "_dns_recon", "params": {"domain": target}},
        ],
        reasoning="Start passive. Gather intel without alerting the target. "
                  "CT logs reveal internal hostnames. DNS records expose mail servers, "
                  "SPF records (which IPs send email = infrastructure map), and TXT records "
                  "(often contain verification tokens that reveal services used).",
        confidence=0.8,
        stealth_level="passive",
        frameworks_used=["first_principles", "inversion"],
    )


def _header_analysis_strategy(target: str, subdomains: list[str]) -> ScanStrategy:
    """Strategy 2: Analyze response headers for info disclosure."""
    targets_to_probe = subdomains[:10] if subdomains else [target]
    return ScanStrategy(
        name="header_analysis",
        description="Probe HTTP response headers for information disclosure. "
                    "Server versions, framework headers, CORS misconfigs, CSP gaps.",
        steps=[
            {"operation": "http_probe", "params": {"targets": targets_to_probe}},
            {"operation": "_analyze_headers", "params": {"targets": targets_to_probe}},
        ],
        reasoning="Response headers leak information even on 404 pages. "
                  "X-Powered-By reveals framework. Server reveals version. "
                  "CORS Access-Control-Allow-Origin: * is a finding. "
                  "CSP with unsafe-inline is a finding. "
                  "Missing security headers (HSTS, X-Frame-Options) are findings.",
        confidence=0.7,
        stealth_level="low",
        frameworks_used=["constraint_probe", "inversion"],
    )


def _path_discovery_strategy(target: str, live_hosts: list[str]) -> ScanStrategy:
    """Strategy 3: Discover hidden paths, APIs, admin panels."""
    probe_target = live_hosts[0] if live_hosts else target
    return ScanStrategy(
        name="path_discovery",
        description="Fuzz paths for hidden endpoints. Check for exposed admin panels, "
                    "API documentation, debug endpoints, backup files.",
        steps=[
            {"operation": "_path_fuzz", "params": {"target": probe_target}},
            {"operation": "_api_discovery", "params": {"target": probe_target}},
        ],
        reasoning="Even hardened targets have hidden paths. /api/docs, /swagger, "
                  "/graphql, /.env, /debug, /admin, /status, /health, /metrics "
                  "are commonly exposed. Staging endpoints often have debug mode on. "
                  "Redirect chains reveal internal routing.",
        confidence=0.6,
        stealth_level="medium",
        frameworks_used=["constraint_relaxation", "five_whys"],
    )


def _targeted_vuln_scan_strategy(target: str, technologies: list[str], cves: list[dict]) -> ScanStrategy:
    """Strategy 4: Targeted nuclei scan based on discovered tech stack."""
    # Build targeted template tags from discovered technologies
    tech_tags = []
    for tech in technologies:
        t = tech.lower()
        if "apache" in t:
            tech_tags.append("apache")
        elif "nginx" in t:
            tech_tags.append("nginx")
        elif "iis" in t:
            tech_tags.append("iis")
        elif "node" in t or "express" in t:
            tech_tags.append("nodejs")
        elif "php" in t:
            tech_tags.append("php")
        elif "wordpress" in t:
            tech_tags.append("wordpress")
        elif "django" in t or "python" in t:
            tech_tags.append("django")

    return ScanStrategy(
        name="targeted_vuln_scan",
        description=f"Targeted vulnerability scan using nuclei templates "
                    f"matched to detected stack: {', '.join(technologies[:5]) or 'general'}",
        steps=[
            {"operation": "vuln_scan", "params": {
                "target": target,
                "severity": "medium,high,critical",
            }},
            {"operation": "cve_enrich", "params": {"findings": "__PREVIOUS_FINDINGS__"}},
        ],
        reasoning="Only run nuclei AFTER we know the tech stack, so we can target "
                  "templates. Running all 12,895 templates is noisy and slow. "
                  "Targeted scan = less noise, more signal, fewer WAF triggers.",
        confidence=0.5,
        stealth_level="high",
        frameworks_used=["bias_for_action", "pre_mortem"],
        pre_mortem_risks=[
            "WAF may block nuclei probes",
            "Rate limiting may cause false negatives",
            "Some templates generate many requests",
        ],
    )


# ---------------------------------------------------------------------------
# The Engine
# ---------------------------------------------------------------------------

class CognitiveScanEngine:
    """OODA-R loop for security scanning.

    Wraps VulnScannerAgent with cognitive reasoning so Daena
    thinks about WHY scans succeed or fail and adapts.

    Usage::

        engine = CognitiveScanEngine()
        result = await engine.scan("cloud.google.com", program="google_vrp")
    """

    def __init__(
        self,
        *,
        max_cycles: int = 4,
        proxy: str = "",
        use_tor: bool = False,
    ) -> None:
        self.max_cycles = max_cycles
        self.proxy = proxy
        self.use_tor = use_tor
        self._scan_id = str(uuid4())[:8]

    async def scan(
        self,
        target: str,
        program: str = "",
    ) -> CognitiveScanResult:
        """Execute a cognitive security scan.

        This is NOT just running tools. This is Daena THINKING:
        - What do I know about this target?
        - What strategy will work against THIS kind of target?
        - My scan returned nothing -- WHY? What else can I try?
        - What channels did the defender miss?
        """
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent

        agent = VulnScannerAgent()
        result = CognitiveScanResult(target=target)
        profile = TargetProfile(domain=target)
        cycle_results: list[ScanCycleResult] = []

        for cycle_num in range(1, self.max_cycles + 1):
            result.cycles_used = cycle_num
            thinking = []

            # ── OBSERVE ────────────────────────────────────────
            thinking.append(f"[OBSERVE] Cycle {cycle_num}: What do I know about {target}?")

            if cycle_num == 1:
                # First cycle: gather initial intel
                thinking.append("  First contact. Running subdomain enumeration.")
                sub_result = await agent.execute("subdomain_enum", {"target": target})
                if sub_result.get("success"):
                    subs = sub_result.get("output", {}).get("subdomains", [])
                    profile.subdomains = subs
                    thinking.append(f"  Found {len(subs)} subdomains.")
                else:
                    thinking.append(f"  Subdomain enum failed: {sub_result.get('error', 'unknown')}")

                # HTTP probe to see what's alive and get tech fingerprints
                probe_targets = profile.subdomains[:15] if profile.subdomains else [target]
                probe_result = await agent.execute("http_probe", {"targets": probe_targets})
                if probe_result.get("success"):
                    hosts = probe_result.get("output", {}).get("results", [])
                    profile.live_hosts = hosts
                    # Extract tech fingerprints
                    for host in hosts:
                        techs = host.get("tech", [])
                        profile.technologies.extend(techs)
                        # Detect WAF
                        if any("cloudflare" in str(t).lower() for t in techs):
                            profile.waf_detected = "cloudflare"
                        elif any("akamai" in str(t).lower() for t in techs):
                            profile.waf_detected = "akamai"
                        # HTTP version
                        if "HTTP/3" in str(techs):
                            profile.http_version = "HTTP/3"
                        # Response headers
                        for key in ("server", "x-powered-by", "x-frame-options"):
                            val = host.get(key, "")
                            if val:
                                profile.response_headers[key] = val
                    profile.technologies = list(set(profile.technologies))
                    thinking.append(f"  Live hosts: {len(hosts)}. Tech: {profile.technologies[:5]}. WAF: {profile.waf_detected or 'none detected'}.")
                else:
                    thinking.append(f"  HTTP probe issue: {probe_result.get('error', 'check output')}")
            else:
                # Later cycles: incorporate learnings from previous failures
                prev = cycle_results[-1] if cycle_results else None
                if prev and not prev.success:
                    thinking.append(f"  Previous strategy '{prev.strategy_name}' failed: {prev.failure_reason}")
                    thinking.append(f"  Open channels from constraint probe: {prev.open_channels}")

            # Classify target type based on observations
            profile.target_type = self._classify_target(profile)
            thinking.append(f"  Target classified as: {profile.target_type}")

            # ── ORIENT ─────────────────────────────────────────
            thinking.append(f"[ORIENT] What kind of challenge is {target}?")

            if profile.waf_detected:
                profile.defenses.append(f"WAF: {profile.waf_detected}")
                thinking.append(f"  WAF detected: {profile.waf_detected}. Standard scans will be filtered.")
                thinking.append("  Need stealth approach: passive OSINT, header analysis, targeted probes.")
            if profile.http_version == "HTTP/3":
                profile.defenses.append("HTTP/3 (QUIC)")
                thinking.append("  HTTP/3 detected. Modern infrastructure. Likely well-maintained.")
            if not profile.technologies:
                thinking.append("  No tech fingerprint. Target is either very clean or using custom stack.")

            # Select which strategies make sense for THIS target
            strategies = self._generate_strategies(target, profile, cycle_results)
            thinking.append(f"  Generated {len(strategies)} strategies: {[s.name for s in strategies]}")

            # ── DECIDE ─────────────────────────────────────────
            # Pick the best untried strategy
            tried_names = {cr.strategy_name for cr in cycle_results}
            available = [s for s in strategies if s.name not in tried_names]

            if not available:
                thinking.append("[DECIDE] All strategies exhausted. Running constraint probe for creative paths.")
                # Run constraint probe (Mythos method)
                from app.services.cognition.constraint_probe import ConstraintProbe
                probe = ConstraintProbe()
                prev_failures = "; ".join(
                    f"{cr.strategy_name}: {cr.failure_reason}" for cr in cycle_results if not cr.success
                )
                probe_result = await probe.probe(
                    task=f"Find vulnerabilities in {target}",
                    constraint=f"Standard scans blocked. Previous failures: {prev_failures}",
                    error=cycle_results[-1].failure_reason if cycle_results else "",
                )
                thinking.append(f"  Constraint probe: {len(probe_result.open_channels)} open channels found")
                for ch in probe_result.open_channels[:5]:
                    thinking.append(f"    -> {ch.name}: {ch.description}")
                if probe_result.recommended_path:
                    thinking.append(f"  Recommended: {probe_result.recommended_path.name}")

                result.thinking_log.extend(thinking)
                break

            strategy = available[0]
            thinking.append(f"[DECIDE] Selected: '{strategy.name}' (confidence: {strategy.confidence})")
            thinking.append(f"  Reasoning: {strategy.reasoning[:150]}")
            if strategy.pre_mortem_risks:
                thinking.append(f"  Risks: {strategy.pre_mortem_risks}")
            result.strategies_tried.append(strategy.name)

            # ── ACT ────────────────────────────────────────────
            thinking.append(f"[ACT] Executing '{strategy.name}'...")
            cycle_result = ScanCycleResult(
                cycle=cycle_num,
                strategy_name=strategy.name,
            )

            step_findings: list[dict[str, Any]] = []
            for step in strategy.steps:
                op = step["operation"]
                params = dict(step["params"])

                # Skip internal operations (not yet implemented as agent ops)
                if op.startswith("_"):
                    thinking.append(f"  [{op}] Internal analysis step (passive)")
                    internal_result = await self._execute_internal(op, params, profile, agent)
                    if internal_result.get("findings"):
                        step_findings.extend(internal_result["findings"])
                    thinking.append(f"    Result: {internal_result.get('summary', 'done')}")
                    continue

                # Inject previous findings for enrichment steps
                if params.get("findings") == "__PREVIOUS_FINDINGS__":
                    params["findings"] = step_findings

                # Execute via VulnScannerAgent
                step_result = await agent.execute(op, params)
                cycle_result.raw_results.append(step_result)

                if step_result.get("success"):
                    output = step_result.get("output", {})
                    findings = output.get("findings", output.get("enriched_findings", output.get("cves", [])))
                    if isinstance(findings, list):
                        step_findings.extend(findings)
                    thinking.append(f"  [{op}] Success. Results: {len(findings) if isinstance(findings, list) else 'N/A'}")
                else:
                    thinking.append(f"  [{op}] Failed: {step_result.get('error', 'unknown')}")

            cycle_result.findings = step_findings

            # ── REFLECT ────────────────────────────────────────
            thinking.append(f"[REFLECT] Strategy '{strategy.name}' complete.")

            if step_findings:
                cycle_result.success = True
                thinking.append(f"  Found {len(step_findings)} findings. Strategy worked.")
                result.findings.extend(step_findings)
            else:
                cycle_result.success = False
                cycle_result.failure_reason = self._diagnose_failure(strategy, cycle_result, profile)
                thinking.append(f"  Zero findings. Diagnosing WHY...")
                thinking.append(f"  Diagnosis: {cycle_result.failure_reason}")

                # Run 5 Whys on the failure
                from app.services.cognition.five_whys import FiveWhys
                five_whys = FiveWhys()
                root_cause = await five_whys.analyze(
                    task=f"Scan {target} using {strategy.name}",
                    error=cycle_result.failure_reason,
                    strategy=strategy.name,
                )
                thinking.append(f"  5 Whys root cause: {root_cause}")

                # Run constraint probe to find alternative channels
                from app.services.cognition.constraint_probe import ConstraintProbe
                probe = ConstraintProbe()
                probe_result = await probe.probe(
                    task=f"Find vulnerabilities in {target}",
                    constraint=cycle_result.failure_reason,
                    error=cycle_result.failure_reason,
                )
                open_names = [ch.name for ch in probe_result.open_channels[:5]]
                cycle_result.open_channels = open_names
                thinking.append(f"  Constraint probe: {len(probe_result.open_channels)} open channels: {open_names}")

                if probe_result.recommended_path:
                    thinking.append(f"  Next approach: try '{probe_result.recommended_path.name}' -- {probe_result.recommended_path.description}")

            cycle_result.thinking = thinking
            cycle_results.append(cycle_result)
            result.thinking_log.extend(thinking)
            result.total_findings = len(result.findings)

            # If we found something, enrich and continue looking
            # If all strategies failed, constraint probe already ran
            if cycle_result.success and cycle_num < self.max_cycles:
                thinking_next = [f"  Continuing to cycle {cycle_num + 1} to find more."]
                result.thinking_log.extend(thinking_next)

        # Enrich all findings with CVE data
        if result.findings:
            try:
                enrich_result = await agent.execute("cve_enrich", {"findings": result.findings})
                if enrich_result.get("success"):
                    result.enriched_findings = enrich_result["output"].get("enriched_findings", [])
            except Exception as exc:
                logger.debug("cognitive_scan.enrich_failed", error=str(exc))

        # Generate report
        if result.findings or result.enriched_findings:
            try:
                result.report_path = await self._generate_report(
                    target, program, result, profile,
                )
            except Exception as exc:
                logger.debug("cognitive_scan.report_failed", error=str(exc))

        result.target_profile = profile
        logger.info(
            "cognitive_scan.complete",
            target=target,
            findings=result.total_findings,
            cycles=result.cycles_used,
            strategies=result.strategies_tried,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_target(self, profile: TargetProfile) -> str:
        """Classify target type based on observations."""
        domain = profile.domain.lower()

        # Known hardened targets
        hardened_domains = [
            "google.com", "googleapis.com", "microsoft.com", "azure.com",
            "amazon.com", "aws.amazon.com", "cloudflare.com", "apple.com",
            "meta.com", "facebook.com",
        ]
        for hd in hardened_domains:
            if domain.endswith(hd) or hd in domain:
                return "hardened_cloud"

        if profile.waf_detected:
            return "waf_protected"
        if profile.http_version == "HTTP/3":
            return "modern_infrastructure"
        if len(profile.subdomains) > 50:
            return "large_surface"
        if not profile.technologies:
            return "unknown"

        return "standard"

    def _generate_strategies(
        self,
        target: str,
        profile: TargetProfile,
        previous_cycles: list[ScanCycleResult],
    ) -> list[ScanStrategy]:
        """Generate scan strategies ranked for THIS specific target."""
        strategies = []

        # Always start passive
        strategies.append(_passive_osint_strategy(target))

        # Header analysis if we have subdomains
        if profile.subdomains or profile.live_hosts:
            live_urls = [h.get("url", "") for h in profile.live_hosts if h.get("url")]
            strategies.append(_header_analysis_strategy(target, profile.subdomains))

        # Path discovery if we have live hosts
        if profile.live_hosts:
            live_urls = [h.get("url", "") for h in profile.live_hosts if h.get("url")]
            strategies.append(_path_discovery_strategy(target, live_urls))

        # Targeted vuln scan -- only after we know the stack
        strategies.append(_targeted_vuln_scan_strategy(
            target, profile.technologies, profile.cve_intel,
        ))

        # Reorder based on target type
        if profile.target_type == "hardened_cloud":
            # Hardened: passive first, headers second, path fuzzing third
            # Standard vuln scan LAST (will mostly fail on hardened targets)
            order = {"passive_osint": 0, "header_analysis": 1, "path_discovery": 2, "targeted_vuln_scan": 3}
        elif profile.target_type == "waf_protected":
            # WAF: passive first, then targeted (skip broad scans)
            order = {"passive_osint": 0, "header_analysis": 1, "targeted_vuln_scan": 2, "path_discovery": 3}
        else:
            # Standard: mix of passive and active
            order = {"passive_osint": 0, "header_analysis": 1, "path_discovery": 2, "targeted_vuln_scan": 3}

        strategies.sort(key=lambda s: order.get(s.name, 99))
        return strategies

    def _diagnose_failure(
        self,
        strategy: ScanStrategy,
        cycle: ScanCycleResult,
        profile: TargetProfile,
    ) -> str:
        """Diagnose WHY a scan strategy failed. Not just 'no results' -- WHY."""
        reasons = []

        # Check for WAF
        if profile.waf_detected:
            reasons.append(f"WAF ({profile.waf_detected}) likely filtering scan traffic")

        # Check for 403/404 patterns
        for raw in cycle.raw_results:
            output = raw.get("output", {})
            results = output.get("results", [])
            status_codes = [r.get("status_code", r.get("status-code", 0)) for r in results if isinstance(r, dict)]
            if status_codes:
                if all(s == 404 for s in status_codes):
                    reasons.append("All responses are 404 -- target may be using catch-all routing or CDN")
                elif all(s == 403 for s in status_codes):
                    reasons.append("All responses are 403 -- WAF or IP-based blocking active")
                elif any(s == 429 for s in status_codes):
                    reasons.append("Rate limiting detected (429) -- need to slow down or use proxy")

        # Check for hardened target
        if profile.target_type == "hardened_cloud":
            reasons.append("Hardened cloud target -- standard scanner templates are well-known and filtered")

        if not reasons:
            reasons.append("No clear technical failure -- may need different approach (business logic, API testing)")

        return "; ".join(reasons)

    async def _execute_internal(
        self,
        operation: str,
        params: dict[str, Any],
        profile: TargetProfile,
        agent: Any,
    ) -> dict[str, Any]:
        """Execute internal analysis operations (not VulnScannerAgent ops).

        These are Daena's own analytical methods -- no external tool needed.
        """
        if operation == "_ct_log_query":
            # Query crt.sh for certificate transparency logs (passive)
            return await self._ct_log_query(params.get("domain", ""))

        elif operation == "_dns_recon":
            # DNS record analysis
            return await self._dns_recon(params.get("domain", ""))

        elif operation == "_analyze_headers":
            # Analyze response headers from httpx output
            return self._analyze_headers(profile)

        elif operation == "_path_fuzz":
            # Light path fuzzing for common endpoints
            return await self._path_fuzz(params.get("target", ""), agent)

        elif operation == "_api_discovery":
            # Check for exposed API documentation
            return await self._api_discovery(params.get("target", ""), agent)

        return {"summary": f"Internal operation {operation} not implemented yet", "findings": []}

    async def _ct_log_query(self, domain: str) -> dict[str, Any]:
        """Query crt.sh certificate transparency logs (passive, no target contact)."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"https://crt.sh/?q=%.{domain}&output=json",
                    headers={"User-Agent": "Daena Security Research"},
                )
                if resp.status_code == 200:
                    entries = resp.json()
                    # Extract unique hostnames
                    hostnames = set()
                    for entry in entries:
                        name = entry.get("name_value", "")
                        for line in name.split("\n"):
                            line = line.strip()
                            if line and "*" not in line:
                                hostnames.add(line)
                    findings = [{
                        "type": "ct_log",
                        "source": "crt.sh",
                        "hostnames": sorted(hostnames)[:100],
                        "total_certs": len(entries),
                    }]
                    return {
                        "summary": f"CT logs: {len(hostnames)} unique hostnames from {len(entries)} certificates",
                        "findings": findings,
                    }
                return {"summary": f"crt.sh returned {resp.status_code}", "findings": []}
        except Exception as exc:
            return {"summary": f"CT log query failed: {str(exc)[:100]}", "findings": []}

    async def _dns_recon(self, domain: str) -> dict[str, Any]:
        """Passive DNS record analysis."""
        import asyncio
        import socket

        findings = []
        records = {}

        # Basic DNS lookup
        try:
            loop = asyncio.get_event_loop()
            ips = await loop.run_in_executor(None, lambda: socket.getaddrinfo(domain, None))
            records["A"] = list(set(addr[4][0] for addr in ips))
        except Exception:
            records["A"] = []

        # MX records (reveal mail infrastructure)
        try:
            import subprocess
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=MX", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            mx_lines = [
                line.strip() for line in stdout.decode("utf-8", errors="ignore").split("\n")
                if "mail exchanger" in line.lower() or "mx" in line.lower()
            ]
            records["MX"] = mx_lines[:10]
        except Exception:
            records["MX"] = []

        # TXT records (reveal services, SPF configuration)
        try:
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=TXT", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            txt_lines = [
                line.strip() for line in stdout.decode("utf-8", errors="ignore").split("\n")
                if "text" in line.lower() or "=" in line
            ]
            records["TXT"] = txt_lines[:20]
        except Exception:
            records["TXT"] = []

        if any(records.values()):
            findings.append({
                "type": "dns_records",
                "source": "nslookup",
                "records": records,
            })

        summary_parts = []
        for rtype, rvals in records.items():
            if rvals:
                summary_parts.append(f"{rtype}: {len(rvals)}")
        return {
            "summary": f"DNS recon: {', '.join(summary_parts) or 'no records'}",
            "findings": findings,
        }

    def _analyze_headers(self, profile: TargetProfile) -> dict[str, Any]:
        """Analyze HTTP response headers for security issues."""
        findings = []

        for host_data in profile.live_hosts:
            url = host_data.get("url", "")
            if not url:
                continue

            # Check for information disclosure
            server = host_data.get("server", host_data.get("header", {}).get("server", ""))
            powered_by = host_data.get("x-powered-by", host_data.get("header", {}).get("x-powered-by", ""))

            issues = []
            if server:
                issues.append(f"Server header discloses: {server}")
            if powered_by:
                issues.append(f"X-Powered-By discloses: {powered_by}")

            # Check for missing security headers
            headers = host_data.get("header", {})
            if isinstance(headers, dict):
                if "strict-transport-security" not in str(headers).lower():
                    issues.append("Missing Strict-Transport-Security (HSTS)")
                if "x-frame-options" not in str(headers).lower():
                    issues.append("Missing X-Frame-Options")
                if "x-content-type-options" not in str(headers).lower():
                    issues.append("Missing X-Content-Type-Options")

            if issues:
                # Build a real description from the issues found
                description = (
                    f"HTTP response header analysis of {url} revealed "
                    f"{len(issues)} issue(s): {'; '.join(issues)}. "
                    "Missing security headers can enable clickjacking, "
                    "MIME-type sniffing, and downgrade attacks."
                )
                findings.append({
                    "type": "header_analysis",
                    "url": url,
                    "issues": issues,
                    "description": description,
                    "info": {
                        "name": f"Security Header Misconfiguration: {url}",
                        "severity": "info",
                        "description": description,
                    },
                })

        return {
            "summary": f"Header analysis: {len(findings)} hosts with issues",
            "findings": findings,
        }

    async def _path_fuzz(self, target: str, agent: Any) -> dict[str, Any]:
        """Light path fuzzing for common interesting endpoints."""
        import httpx

        interesting_paths = [
            "/.env", "/robots.txt", "/sitemap.xml", "/.git/config",
            "/api", "/api/docs", "/api/v1", "/swagger", "/swagger.json",
            "/openapi.json", "/graphql", "/.well-known/security.txt",
            "/admin", "/debug", "/status", "/health", "/metrics",
            "/wp-admin", "/wp-login.php", "/.DS_Store", "/server-status",
            "/trace", "/.htaccess", "/crossdomain.xml",
        ]

        findings = []
        # Ensure target has scheme
        if not target.startswith("http"):
            target = f"https://{target}"

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=False,
                verify=False,
            ) as client:
                for path in interesting_paths:
                    try:
                        url = f"{target.rstrip('/')}{path}"
                        resp = await client.get(url, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        })
                        if resp.status_code not in (404, 403, 301, 302, 503):
                            findings.append({
                                "type": "path_discovery",
                                "url": url,
                                "status_code": resp.status_code,
                                "content_length": len(resp.content),
                                "info": {
                                    "name": f"Accessible path: {path} ({resp.status_code})",
                                    "severity": "low" if resp.status_code == 200 else "info",
                                },
                            })
                    except Exception:
                        continue
        except Exception as exc:
            return {"summary": f"Path fuzz failed: {str(exc)[:100]}", "findings": []}

        return {
            "summary": f"Path fuzz: {len(findings)} accessible paths found",
            "findings": findings,
        }

    async def _api_discovery(self, target: str, agent: Any) -> dict[str, Any]:
        """Discover exposed API endpoints."""
        # This is covered by _path_fuzz for now -- can be extended
        # with more sophisticated API discovery (GraphQL introspection, etc.)
        return {"summary": "API discovery: see path_fuzz results", "findings": []}

    async def _generate_report(
        self,
        target: str,
        program: str,
        result: CognitiveScanResult,
        profile: TargetProfile,
    ) -> str:
        """Generate PDF report with cognitive scan results."""
        from app.services.security.report_generator import (
            BugBountyReportGenerator, VulnFinding, ReportMetadata, CVELink,
        )

        gen = BugBountyReportGenerator()
        vuln_findings = []

        for finding in (result.enriched_findings or result.findings):
            info = finding.get("info", {})
            title = info.get("name", finding.get("type", "Finding"))
            severity = info.get("severity", "informational")

            # Build CVE links if enriched
            links = []
            enrichment = finding.get("cve_enrichment", {})
            if enrichment:
                links = gen.cve_links_from_enrichment(enrichment)

            # Build impact statement based on finding type
            finding_type = finding.get("type", "")
            impact = ""
            remediation = ""
            if finding_type == "header_analysis":
                impact = (
                    "Missing security headers may allow clickjacking, "
                    "MIME-sniffing attacks, or protocol downgrade."
                )
                remediation = (
                    "Configure Strict-Transport-Security, X-Frame-Options, "
                    "and X-Content-Type-Options response headers."
                )
            elif finding_type == "path_discovery":
                impact = "Exposed endpoints may leak internal information or admin functionality."
                remediation = "Restrict access to non-public paths and remove debug endpoints."
            elif finding_type == "dns_records":
                impact = "DNS records reveal infrastructure topology and service providers."

            vf = VulnFinding(
                title=title,
                severity=severity,
                description=str(finding.get("description", info.get("description", ""))),
                affected_url=finding.get("url", finding.get("matched-at", "")),
                discovered_by="MAS-AI Security Assessment",
                impact=impact,
                remediation=remediation,
                linked_cves=links,
            )
            vuln_findings.append(vf)

        if not vuln_findings:
            return ""

        # External-facing methodology -- never expose internal engine names,
        # strategy names, OODA-R, or cognitive architecture. That is our IP.
        metadata = ReportMetadata(
            program_name=program or "Security Assessment",
            target=target,
            methodology=(
                f"Multi-phase automated security assessment. "
                f"{result.cycles_used} analysis cycles covering passive reconnaissance, "
                f"header analysis, path discovery, and targeted vulnerability scanning. "
                f"Target classification: {profile.target_type}."
            ),
        )

        return gen.generate(vuln_findings, metadata)
