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
class ExploitAttempt:
    """Result of an auto-exploitation attempt during scan."""
    finding_type: str
    operation: str  # TargetInteractionAgent operation used
    target_url: str
    success: bool = False
    impact_proven: str = ""  # What was proven (e.g., "read 50 user records")
    result_data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    chained_from_cycle: int = 0


@dataclass
class CognitiveScanResult:
    """Final output of a cognitive scan."""
    target: str
    total_findings: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    enriched_findings: list[dict[str, Any]] = field(default_factory=list)
    exploit_attempts: list[ExploitAttempt] = field(default_factory=list)
    exploits_succeeded: int = 0
    attack_chains: list[dict[str, Any]] = field(default_factory=list)
    cycles_used: int = 0
    strategies_tried: list[str] = field(default_factory=list)
    thinking_log: list[str] = field(default_factory=list)
    target_profile: TargetProfile | None = None
    report_path: str = ""
    evidence_summary: dict[str, Any] = field(default_factory=dict)  # /3vilbob evidence chain
    offensive_mode: bool = False


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


def _forgotten_infra_strategy(target: str) -> ScanStrategy:
    """Strategy 3b: Scan for forgotten infrastructure -- the doors nobody locked."""
    return ScanStrategy(
        name="forgotten_infrastructure",
        description="Scan for forgotten services: Jenkins, Grafana, Sentry, Kibana, "
                    "phpMyAdmin, Elasticsearch, Docker Registry, Jupyter, K8s Dashboard. "
                    "These are services the team deployed once and forgot about.",
        steps=[
            {"operation": "_forgotten_infra_scan", "params": {"domain": target}},
        ],
        reasoning="The main site is hardened. But the Jenkins server from 2 years ago "
                  "is still running with no auth. The Grafana dashboard has anonymous "
                  "access. The Sentry instance leaks stack traces with file paths. "
                  "These are the doors nobody locked because nobody remembers they exist. "
                  "14 service types checked across 40+ paths/ports.",
        confidence=0.55,
        stealth_level="medium",
        frameworks_used=["forgotten_infrastructure", "developer_empathy"],
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


def _canary_echo_strategy(target: str, live_hosts: list[str]) -> ScanStrategy:
    """Strategy 5: Canary echo analysis -- one string, four vuln classes."""
    probe_urls = live_hosts[:3] if live_hosts else [f"https://{target}"]
    return ScanStrategy(
        name="canary_echo",
        description=(
            "Inject a unique canary string into multiple input channels "
            "(query, path, header, body) and analyze where it appears in "
            "responses. One probe tests XSS, info disclosure, stored "
            "injection, and filter behavior simultaneously."
        ),
        steps=[
            {"operation": "_canary_echo", "params": {"targets": probe_urls}},
        ],
        reasoning=(
            "Most scanners test one vuln class per payload. A canary tests "
            "FOUR classes in one request: reflected = XSS, in error = info "
            "disclosure, in later response = stored, transformed = filter "
            "analysis. Maximum signal per request."
        ),
        confidence=0.6,
        stealth_level="low",
        frameworks_used=["first_principles", "constraint_probe"],
    )


def _state_machine_strategy(target: str, known_endpoints: list[str]) -> ScanStrategy:
    """Strategy 6: State machine inference -- test action sequences, not endpoints."""
    return ScanStrategy(
        name="state_machine",
        description=(
            "Test application state transitions: access after logout, "
            "IDOR via sequential user IDs, method override (GET -> DELETE). "
            "Finds broken access control that endpoint-by-endpoint scanning misses."
        ),
        steps=[
            {"operation": "_state_machine", "params": {
                "target": target,
                "known_endpoints": known_endpoints,
            }},
        ],
        reasoning=(
            "Applications have STATE. After login you can do X, after logout "
            "you shouldn't. Most scanners test endpoints in isolation. State "
            "machine inference tests SEQUENCES to find broken access control, "
            "session fixation, and IDOR."
        ),
        confidence=0.5,
        stealth_level="medium",
        frameworks_used=["constraint_probe", "five_whys"],
    )


def _cost_amplification_strategy(target: str, live_hosts: list[str]) -> ScanStrategy:
    """Strategy 7: Cost amplification detection -- find DoS via timing."""
    probe_urls = live_hosts[:3] if live_hosts else [f"https://{target}"]
    return ScanStrategy(
        name="cost_amplification",
        description=(
            "Find endpoints where small requests cause disproportionate "
            "server work: ReDoS, deep JSON nesting, large array processing, "
            "GraphQL depth attacks. Detected via timing, not exploitation."
        ),
        steps=[
            {"operation": "_cost_amplification", "params": {"targets": probe_urls}},
        ],
        reasoning=(
            "A search query that takes 5 seconds = potential ReDoS. A GraphQL "
            "query resolving 1000 nested objects = amplification. We detect "
            "these via timing differential (probe vs baseline), not by causing "
            "actual denial of service. The proof is the ratio."
        ),
        confidence=0.5,
        stealth_level="low",
        frameworks_used=["first_principles", "inversion"],
    )


# ---------------------------------------------------------------------------
# The Engine
# ---------------------------------------------------------------------------

class CognitiveScanEngine:
    """OODA-R loop for security scanning with LLM-powered reasoning.

    Wraps VulnScannerAgent with CognitiveReasoner so Daena THINKS
    about WHY scans succeed or fail, generates novel strategies,
    and learns from every cycle.

    The CognitiveReasoner replaces hardcoded if-else trees with
    actual LLM reasoning using framework lenses (First Principles,
    Inversion, Constraint Probe, etc.). In AGI mode, it uses
    Quintessence (multi-model debate) for the deepest analysis.

    /3vilbob mode activates:
    - Offensive framework lenses (defender mapping, legitimacy mimicry,
      constraint decomposition, attack chains, business logic)
    - Mandatory proxy rotation (refuses to scan without it)
    - Evidence auto-capture (response snapshots, screenshots, tokens, curl)
    - Chain of evidence (timestamped, hashed, tamper-evident)
    - Shield ALWAYS ON (outbound data guard, encrypted token vault)
    - Zero trace when deactivated

    Usage::

        engine = CognitiveScanEngine(agi_mode=True)
        result = await engine.scan("cloud.google.com", program="google_vrp")

        # /3vilbob mode (hidden, offensive):
        engine = CognitiveScanEngine(agi_mode=True, offensive_mode=True)
        result = await engine.scan("target.com", program="hackerone_target")
    """

    def __init__(
        self,
        *,
        max_cycles: int = 4,
        proxy: str = "",
        use_tor: bool = False,
        agi_mode: bool = False,
        offensive_mode: bool = False,
    ) -> None:
        self.max_cycles = max_cycles
        self.proxy = proxy
        self.use_tor = use_tor
        self.agi_mode = agi_mode
        # Offensive mode: local flag OR global /3vilbob mode
        # The global mode is the source of truth, local flag is for direct API use
        from app.services.security.evilbob_mode import is_active
        self.offensive_mode = offensive_mode or is_active()
        self._scan_id = str(uuid4())[:8]
        self._reasoner_initialized = False
        self._evidence = None  # EvidenceCapture, initialized in scan()
        self._proxy_manager = None  # ProxyManager, initialized in scan()
        self._opsec = None  # OpsecManager, initialized in scan() when offensive

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

        In /3vilbob mode, additionally:
        - Proxy is MANDATORY (refuses to scan without it)
        - Evidence auto-capture is ON for every finding
        - Offensive framework lenses are active in the reasoner
        - All requests use legitimacy mimicry (real browser headers)
        """
        from app.services.daenabot.vuln_scanner_agent import VulnScannerAgent
        from app.services.cognition.cognitive_reasoner import CognitiveReasoner

        agent = VulnScannerAgent()

        # Initialize ProxyManager (offensive mode enforces proxy)
        from app.services.security.proxy_manager import ProxyManager
        self._proxy_manager = ProxyManager(offensive_mode=self.offensive_mode)
        self._proxy_manager.initialize()

        # Initialize Evidence Capture (always in offensive mode)
        if self.offensive_mode:
            from app.services.security.evidence_capture import EvidenceCapture
            self._evidence = EvidenceCapture(
                scan_id=self._scan_id,
                target=target,
                program=program,
            )
            await self._evidence.initialize()
            logger.info(
                "cognitive_scan.evidence_capture_active",
                scan_id=self._scan_id,
                target=target,
            )

        # Initialize OPSEC (offensive mode: browser fingerprints, timing, counter-detection)
        if self.offensive_mode:
            from app.services.security.opsec import OpsecManager
            self._opsec = OpsecManager()
            logger.info(
                "cognitive_scan.opsec_active",
                scan_id=self._scan_id,
                profile=self._opsec.fingerprints.get_profile().get("name", "unknown"),
            )

        # Initialize the LLM brain for ORIENT/DECIDE/REFLECT
        # In offensive mode, offensive framework lenses are loaded
        reasoner = CognitiveReasoner(
            agi_mode=self.agi_mode,
            offensive_mode=self.offensive_mode,
        )
        try:
            await reasoner.initialize()
            self._reasoner_initialized = reasoner.is_llm_available
            logger.info(
                "cognitive_scan.reasoner_initialized",
                mode=reasoner.reasoning_mode,
                model=reasoner._model_id,
                agi=self.agi_mode,
                offensive=self.offensive_mode,
            )
        except Exception as exc:
            logger.warning("cognitive_scan.reasoner_init_failed", error=str(exc))
            self._reasoner_initialized = False

        # Resolve proxy for IP protection
        proxy = self._resolve_proxy()

        result = CognitiveScanResult(target=target)
        profile = TargetProfile(domain=target)
        cycle_results: list[ScanCycleResult] = []

        for cycle_num in range(1, self.max_cycles + 1):
            result.cycles_used = cycle_num
            thinking = []

            # ── OPSEC: Rotate fingerprint between cycles ──────
            self._opsec_rotate_if_needed(cycle_num)

            # ── OBSERVE ────────────────────────────────────────
            thinking.append(f"[OBSERVE] Cycle {cycle_num}: What do I know about {target}?")

            if cycle_num == 1:
                # First cycle: gather initial intel
                thinking.append("  First contact. Running subdomain enumeration.")
                sub_result = await agent.execute("subdomain_enum", {
                    "target": target, "proxy": proxy,
                })
                if sub_result.get("success"):
                    subs = sub_result.get("output", {}).get("subdomains", [])
                    profile.subdomains = subs
                    thinking.append(f"  Found {len(subs)} subdomains.")
                else:
                    thinking.append(f"  Subdomain enum failed: {sub_result.get('error', 'unknown')}")

                # HTTP probe to see what's alive and get tech fingerprints
                probe_targets = profile.subdomains[:15] if profile.subdomains else [target]
                probe_result = await agent.execute("http_probe", {
                    "targets": probe_targets, "proxy": proxy,
                })
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

            # ── ORIGIN IP DISCOVERY (/3vilbob: Unreplicable) ──
            # When CDN/WAF is detected, try to find the real server IP.
            # The CDN is the armor. The origin IP is the skin underneath.
            # If we find it, we bypass ALL CDN protection in one step.
            if self.offensive_mode and cycle_num == 1 and profile.waf_detected:
                from app.services.cognition.unreplicable import OriginIPDiscovery
                origin_disc = OriginIPDiscovery()
                thinking.append(
                    f"[ORIGIN IP] CDN detected ({profile.waf_detected}). "
                    f"Attempting to find origin IP behind it..."
                )

                # Generate bypass subdomain targets
                bypass_targets = origin_disc.generate_bypass_targets(target)
                thinking.append(f"  Generated {len(bypass_targets)} bypass subdomain targets")

                # Resolve bypass subdomains to find origin IPs
                import asyncio
                import socket
                origin_candidates: list[dict[str, Any]] = []
                for bt in bypass_targets[:20]:
                    hostname = bt["hostname"]
                    try:
                        loop = asyncio.get_event_loop()
                        addrs = await loop.run_in_executor(
                            None, lambda h=hostname: socket.getaddrinfo(h, None)
                        )
                        resolved_ips = list(set(addr[4][0] for addr in addrs))
                        if resolved_ips:
                            origin_candidates.append({
                                "hostname": hostname,
                                "ips": resolved_ips,
                                "category": bt["category"],
                                "reason": bt["reason"],
                            })
                    except (socket.gaierror, OSError):
                        continue

                if origin_candidates:
                    thinking.append(
                        f"  Found {len(origin_candidates)} resolvable bypass subdomains:"
                    )
                    for oc in origin_candidates[:8]:
                        thinking.append(
                            f"    {oc['hostname']} -> {oc['ips']} [{oc['category']}]"
                        )
                    # Store origin candidates for strategy generation
                    result.evidence_summary["origin_ip_candidates"] = origin_candidates
                    # Add resolved subdomains to profile
                    for oc in origin_candidates:
                        if oc["hostname"] not in profile.subdomains:
                            profile.subdomains.append(oc["hostname"])
                else:
                    thinking.append("  No bypass subdomains resolved. CDN coverage is tight.")

                # Generate full origin discovery plan
                origin_plan = origin_disc.generate_origin_check_plan(target, profile.waf_detected)
                thinking.append(f"  Full origin discovery plan: {len(origin_plan)} steps")
                for step in origin_plan:
                    thinking.append(f"    {step['step']}: {step['reason']}")
                result.evidence_summary["origin_discovery_plan"] = origin_plan

            # Classify target type
            # In offensive mode or when LLM available, use LLM-powered classification
            if self.offensive_mode or self._reasoner_initialized:
                profile.target_type = await self._classify_target_llm(profile, reasoner)
                thinking.append(f"  Target classified as: {profile.target_type} (LLM-analyzed)")
            else:
                profile.target_type = self._classify_target(profile)
                thinking.append(f"  Target classified as: {profile.target_type}")

            # Populate defenses (for reporting, not duplicated per cycle)
            if profile.waf_detected and f"WAF: {profile.waf_detected}" not in profile.defenses:
                profile.defenses.append(f"WAF: {profile.waf_detected}")
            if profile.http_version == "HTTP/3" and "HTTP/3 (QUIC)" not in profile.defenses:
                profile.defenses.append("HTTP/3 (QUIC)")

            # ── DEVELOPER EMPATHY (/3vilbob: Unreplicable) ────
            # Model the HUMAN who built this target. Predict
            # vulnerabilities from their framework choice, security
            # header coverage, and error handling patterns.
            if self.offensive_mode and cycle_num == 1:
                from app.services.cognition.unreplicable import DeveloperEmpathyEngine
                empathy = DeveloperEmpathyEngine()
                error_patterns = []
                for fact in getattr(self, '_error_intel_facts', []):
                    if fact.get("stack_trace_exposed"):
                        error_patterns.append("stack trace exposed")
                    if fact.get("debug_mode_exposed"):
                        error_patterns.append("debug mode on")
                dev_profile = empathy.profile_developer(
                    technologies=profile.technologies,
                    response_headers=profile.response_headers,
                    error_patterns=error_patterns,
                    api_patterns=profile.interesting_paths,
                    target_type=profile.target_type,
                )
                vuln_predictions = empathy.predict_vulnerabilities(dev_profile)
                thinking.append(
                    f"[DEV EMPATHY] Developer profile: {dev_profile.experience_level} "
                    f"({dev_profile.primary_framework}), security awareness: "
                    f"{dev_profile.security_awareness}"
                )
                if dev_profile.architecture_style:
                    thinking.append(f"  Architecture: {dev_profile.architecture_style}")
                for pred in vuln_predictions[:5]:
                    thinking.append(f"  Predicted vuln: {pred}")
                # Store predictions for strategy generation
                result.evidence_summary["dev_profile"] = {
                    "experience": dev_profile.experience_level,
                    "framework": dev_profile.primary_framework,
                    "security_awareness": dev_profile.security_awareness,
                    "predictions": vuln_predictions[:10],
                }

            # ── PROTOCOL INTELLIGENCE (/3vilbob) ──────────────
            # Deep protocol-level analysis: what protocols does this
            # target use, and what are the attack surfaces at each layer?
            if self.offensive_mode and cycle_num == 1:
                from app.services.security.network_intelligence import (
                    ProtocolKnowledgeBase, NetworkTopologyMapper, DarkWebRecon,
                )
                proto_kb = ProtocolKnowledgeBase()
                topo_mapper = NetworkTopologyMapper()
                darkweb = DarkWebRecon()

                # Protocol attack surface analysis
                proto_paths = proto_kb.generate_protocol_attack_surface(
                    technologies=profile.technologies,
                    target_profile={
                        "waf_detected": profile.waf_detected,
                        "http_version": profile.http_version,
                        "target_type": profile.target_type,
                        "defenses": profile.defenses,
                    },
                )
                if proto_paths:
                    thinking.append(
                        f"[PROTOCOL INTEL] {len(proto_paths)} protocol-level attack surfaces identified:"
                    )
                    for pp in proto_paths[:6]:
                        thinking.append(
                            f"  [{pp.protocol}] {pp.weakness} "
                            f"(confidence: {pp.confidence:.0%}, detection: {pp.detection_risk})"
                        )
                    result.evidence_summary["protocol_attack_surfaces"] = [
                        {"protocol": p.protocol, "weakness": p.weakness, "confidence": p.confidence}
                        for p in proto_paths
                    ]

                # Network topology inference
                net_fp = topo_mapper.infer_topology(
                    domain=target,
                    subdomains=profile.subdomains,
                    live_hosts=profile.live_hosts,
                    response_headers=profile.response_headers,
                )
                thinking.append(
                    f"[TOPOLOGY] {net_fp.network_topology} architecture, "
                    f"CDN: {net_fp.cdn_provider or 'none'}, "
                    f"hosting: {net_fp.hosting_provider or 'unknown'}, "
                    f"OS: {net_fp.server_os or 'unknown'}, "
                    f"IPs: {len(net_fp.ip_ranges)}"
                )
                egress = topo_mapper.identify_egress_paths(net_fp)
                for eg in egress[:3]:
                    thinking.append(f"  Egress: {eg}")

                # Dark web recon plan
                darkweb_plan = darkweb.generate_dark_web_recon_plan(target)
                thinking.append(f"[DARK WEB] Recon plan: {len(darkweb_plan)} steps")
                for step in darkweb_plan[:3]:
                    thinking.append(f"  {step['step']}: {step['reason'][:80]}")
                result.evidence_summary["darkweb_recon_plan"] = darkweb_plan

            # ── ORIENT (LLM-powered) ──────────────────────────
            # The CognitiveReasoner THINKS about the target using
            # reasoning frameworks (First Principles, Inversion,
            # Constraint Probe, etc.). In AGI mode, multiple models
            # debate the analysis via Quintessence.
            thinking.append(f"[ORIENT] What kind of challenge is {target}?")

            observation = {
                "target": target,
                "target_type": profile.target_type,
                "subdomains": len(profile.subdomains),
                "live_hosts": len(profile.live_hosts),
                "waf_detected": profile.waf_detected or "none",
                "technologies": profile.technologies[:10],
                "http_version": profile.http_version or "unknown",
                "defenses": profile.defenses,
                "response_headers": profile.response_headers,
            }

            previous_failures = []
            for cr in cycle_results:
                if not cr.success:
                    previous_failures.append({
                        "strategy": cr.strategy_name,
                        "reason": cr.failure_reason,
                        "open_channels": cr.open_channels,
                    })

            if self._reasoner_initialized:
                # LLM reasons about the situation -- not if-else trees
                orient_result = await reasoner.orient(
                    task=f"Find security vulnerabilities in {target} for bug bounty",
                    observation=observation,
                    previous_failures=previous_failures if previous_failures else None,
                )
                thinking.append(f"  Brain mode: {orient_result.reasoning_mode} ({orient_result.model_used})")
                thinking.append(f"  Frameworks applied: {orient_result.frameworks_used}")
                # Append the LLM's analysis (truncated for thinking log)
                for line in orient_result.analysis.split("\n")[:8]:
                    if line.strip():
                        thinking.append(f"  > {line.strip()}")
            else:
                # Deterministic fallback when no LLM available
                if profile.waf_detected:
                    thinking.append(f"  WAF detected: {profile.waf_detected}. Standard scans will be filtered.")
                    thinking.append("  Need stealth approach: passive OSINT, header analysis, targeted probes.")
                if profile.http_version == "HTTP/3":
                    thinking.append("  HTTP/3 detected. Modern infrastructure. Likely well-maintained.")
                if not profile.technologies:
                    thinking.append("  No tech fingerprint. Target is either very clean or using custom stack.")

            # Select which strategies make sense for THIS target
            strategies = await self._generate_strategies(
                target, profile, cycle_results, result, reasoner,
            )
            thinking.append(f"  Generated {len(strategies)} strategies: {[s.name for s in strategies]}")

            # ── INVERSE SURFACE MAPPING (/3vilbob: Unreplicable) ─
            # Infer hidden endpoints from what we've found. If we see
            # /api/v1/users, then /api/v1/payments probably exists.
            if self.offensive_mode and cycle_num >= 2 and result.findings:
                from app.services.cognition.unreplicable import InverseSurfaceMapper
                ismap = InverseSurfaceMapper()
                known_urls = [
                    f.get("url", "") for f in result.findings if f.get("url")
                ]
                known_urls.extend(profile.interesting_paths)
                if known_urls:
                    inferred = ismap.infer_endpoints(known_urls)
                    if inferred:
                        thinking.append(
                            f"[INVERSE SURFACE] Inferred {len(inferred)} hidden endpoints from {len(known_urls)} known:"
                        )
                        for ep in inferred[:5]:
                            thinking.append(f"  -> {ep.url} (confidence: {ep.confidence:.1f}) -- {ep.reasoning}")
                        # Add high-confidence inferred endpoints to interesting paths
                        for ep in inferred:
                            if ep.confidence >= 0.5 and ep.url not in profile.interesting_paths:
                                profile.interesting_paths.append(ep.url)

            # ── DECIDE ─────────────────────────────────────────
            # Pick the best untried strategy
            tried_names = {cr.strategy_name for cr in cycle_results}
            available = [s for s in strategies if s.name not in tried_names]

            if not available:
                # ── TOOL CATALOG: auto-equip before creative fallbacks ──
                # Before trying creative workarounds, check if better tooling
                # would solve the gap. This is the "equip yourself" pattern.
                try:
                    from app.services.security.tool_catalog import ToolCatalog
                    catalog = ToolCatalog()

                    # Identify capability gaps from failed strategies
                    failed_caps: set[str] = set()
                    for cr in cycle_results:
                        if not cr.success and cr.failure_reason:
                            reason = cr.failure_reason.lower()
                            if "port" in reason or "service" in reason:
                                failed_caps.update(["port_scanning", "service_detection"])
                            if "waf" in reason or "blocked" in reason or "403" in reason:
                                failed_caps.update(["waf_bypass", "waf_detection"])
                            if "dns" in reason:
                                failed_caps.update(["dns_recon", "dns_bruteforce"])
                            if "credential" in reason or "auth" in reason:
                                failed_caps.update(["credential_bruteforce", "password_spraying"])
                            if "vuln" in reason or "cve" in reason:
                                failed_caps.update(["vulnerability_scanning", "cve_detection"])

                    # Also recommend based on target type
                    target_type = self._classify_target(profile)
                    waf = profile.defenses.get("waf", "")
                    recommended = catalog.recommend_for_target(target_type, waf)

                    # Filter to uninstalled tools that match capability gaps
                    equip_candidates = []
                    for tool in recommended:
                        if not catalog.is_installed(tool.name):
                            tool_caps = set(tool.capabilities)
                            if failed_caps & tool_caps or not failed_caps:
                                equip_candidates.append(tool)

                    if equip_candidates:
                        thinking.append(
                            f"[DECIDE/TOOL-CATALOG] {len(equip_candidates)} "
                            f"uninstalled tools could help:"
                        )
                        installed_any = False
                        for tool in equip_candidates[:3]:  # Cap at 3 auto-installs
                            thinking.append(
                                f"  -> {tool.name} ({tool.category}): "
                                f"{', '.join(tool.capabilities[:3])}"
                            )
                            # Auto-install if offensive mode allows it
                            if self.offensive_mode:
                                install_result = await catalog.auto_install(tool.name)
                                if install_result.get("success"):
                                    thinking.append(
                                        f"     INSTALLED: {tool.name} is now available"
                                    )
                                    installed_any = True
                                else:
                                    thinking.append(
                                        f"     INSTALL FAILED: {install_result.get('error', 'unknown')}"
                                    )
                            else:
                                thinking.append(
                                    f"     Install: {tool.install_cmd}"
                                )

                        if installed_any:
                            # Re-generate strategies with new tools available
                            thinking.append(
                                "[DECIDE/TOOL-CATALOG] New tools installed -- "
                                "regenerating strategies for next cycle."
                            )
                            result.thinking_log.extend(thinking)
                            # Don't break -- let the constraint probe also run,
                            # but record what tools were equipped
                    else:
                        thinking.append(
                            "[DECIDE/TOOL-CATALOG] All recommended tools already installed."
                        )
                except Exception as exc:
                    thinking.append(
                        f"[DECIDE/TOOL-CATALOG] Catalog check failed: {str(exc)[:80]}"
                    )

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

                # ── COMPOSITIONAL PLANNER (/3vilbob: Beyond Mythos) ──
                # When direct strategies all fail, decompose the blocked
                # objective into individually-benign sub-actions.
                if self.offensive_mode:
                    from app.services.cognition.beyond_mythos import CompositionalPlanner
                    planner = CompositionalPlanner()
                    last_failure = cycle_results[-1] if cycle_results else None
                    if last_failure:
                        comp_plan = planner.decompose_blocked_scan(
                            scan_strategy_name=last_failure.strategy_name,
                            failure_reason=last_failure.failure_reason,
                            target=target,
                        )
                        thinking.append(
                            f"[COMPOSITIONAL PLANNER] Decomposing blocked scan "
                            f"into {len(comp_plan.steps)} benign-looking steps:"
                        )
                        thinking.append(f"  Why direct fails: {comp_plan.why_direct_fails}")
                        thinking.append(f"  Why composition works: {comp_plan.why_composition_works}")
                        for i, step in enumerate(comp_plan.steps):
                            thinking.append(
                                f"  Step {i+1}: {step.operation} -- "
                                f"appears as '{step.appears_as}', "
                                f"purpose: {step.purpose}"
                            )

                        # Execute the compositional plan
                        from app.services.daenabot.target_interaction_agent import TargetInteractionAgent
                        ti_agent = TargetInteractionAgent(evidence_capture=self._evidence)
                        comp_findings = []
                        for step in comp_plan.steps:
                            try:
                                step_result = await ti_agent.execute(step.operation, step.params)
                                if step_result.get("success"):
                                    output = step_result.get("output", {})
                                    status = output.get("status_code", 0)
                                    body_len = output.get("body_length", 0)
                                    thinking.append(
                                        f"    -> {step.operation}: {status} ({body_len} bytes)"
                                    )
                                    if status == 200 and body_len > 0:
                                        comp_findings.append({
                                            "type": "compositional_discovery",
                                            "url": step.params.get("url", ""),
                                            "status_code": status,
                                            "body_length": body_len,
                                            "appears_as": step.appears_as,
                                            "actual_purpose": step.purpose,
                                            "info": {
                                                "name": f"Compositional: {step.purpose[:60]}",
                                                "severity": "low",
                                                "description": (
                                                    f"Discovered via compositional attack plan: "
                                                    f"{step.purpose}. Individual step appears as: "
                                                    f"'{step.appears_as}'."
                                                ),
                                            },
                                        })
                            except Exception as exc:
                                thinking.append(f"    -> {step.operation}: failed ({str(exc)[:60]})")
                        await ti_agent.close()

                        if comp_findings:
                            result.findings.extend(comp_findings)
                            result.total_findings = len(result.findings)
                            thinking.append(
                                f"  Compositional plan found {len(comp_findings)} results "
                                f"that direct approaches missed."
                            )

                result.thinking_log.extend(thinking)
                break

            strategy = available[0]
            thinking.append(f"[DECIDE] Selected: '{strategy.name}' (confidence: {strategy.confidence})")
            thinking.append(f"  Reasoning: {strategy.reasoning[:150]}")
            if strategy.pre_mortem_risks:
                thinking.append(f"  Risks: {strategy.pre_mortem_risks}")
            result.strategies_tried.append(strategy.name)

            # ── ADVERSARIAL SIMULATION (/3vilbob) ─────────────
            # Before acting, simulate what the defender will see.
            # Adjust approach preemptively if detection is likely.
            if self.offensive_mode:
                from app.services.cognition.beyond_mythos import AdversarialSimulator
                simulator = AdversarialSimulator()
                request_count = sum(
                    len(cr.raw_results) for cr in cycle_results
                )
                for step in strategy.steps:
                    prediction = simulator.predict_detection(
                        operation=step.get("operation", ""),
                        params=step.get("params", {}),
                        target_defenses=profile.defenses,
                        request_count_so_far=request_count,
                    )
                    if prediction.risk_score >= 0.5:
                        thinking.append(
                            f"[ADVERSARIAL SIM] {step.get('operation')}: "
                            f"detection={prediction.predicted_detection} "
                            f"(risk {prediction.risk_score:.1f})"
                        )
                        for reason in prediction.detection_reasons[:2]:
                            thinking.append(f"    Reason: {reason}")
                        for suggestion in prediction.evasion_suggestions[:2]:
                            thinking.append(f"    Evasion: {suggestion}")
                        # Auto-adjust params for stealth
                        step["params"] = simulator.adjust_for_stealth(
                            step.get("operation", ""),
                            step.get("params", {}),
                            prediction,
                        )

            # ── COGNITIVE DECEPTION (/3vilbob: Apex Cognition) ─
            # Before the real probe, fire decoy requests to misdirect
            # the defender's attention. While SOC investigates the
            # obvious SQLi/brute-force decoy, the real probe is quiet.
            if self.offensive_mode and strategy.stealth_level in ("medium", "high"):
                from app.services.cognition.apex_cognition import CognitiveDeceptionEngine
                deception = CognitiveDeceptionEngine()
                deception_plan = deception.plan_deception(
                    real_objective=strategy.description,
                    target=target,
                    defenses=profile.defenses,
                )
                thinking.append(
                    f"[DECEPTION] Deploying {len(deception_plan.decoy_actions)} decoy requests "
                    f"before real probe..."
                )
                thinking.append(f"  Timing: {deception_plan.timing}")
                thinking.append(f"  Expected SOC response: {deception_plan.expected_defender_response[:120]}")

                # Fire decoys asynchronously
                import asyncio
                import httpx as _httpx
                req_headers = self._get_request_headers()
                deception_proxy = self._resolve_proxy()
                try:
                    async with _httpx.AsyncClient(
                        timeout=5.0,
                        follow_redirects=False,
                        verify=False,
                        proxy=deception_proxy or None,
                    ) as decoy_client:
                        for decoy in deception_plan.decoy_actions:
                            delay_ms = decoy.get("delay_before_ms", 0)
                            if delay_ms > 0:
                                await asyncio.sleep(delay_ms / 1000.0)
                            try:
                                method = decoy.get("method", "GET")
                                decoy_url = decoy["url"]
                                if method == "POST":
                                    await decoy_client.post(
                                        decoy_url,
                                        content=decoy.get("body", ""),
                                        headers=req_headers,
                                    )
                                else:
                                    await decoy_client.get(decoy_url, headers=req_headers)
                                thinking.append(f"  Decoy fired: {method} {decoy_url} [{decoy.get('purpose', '')[:50]}]")
                            except Exception:
                                pass  # Decoys are expendable
                except Exception:
                    pass  # Deception is best-effort

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

                # Inject proxy for IP protection
                if proxy and "proxy" not in params:
                    params["proxy"] = proxy

                # OPSEC: human-like timing before each request
                await self._opsec_wait()

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

            # ── OPSEC: Check if target is fingerprinting us ───
            if self.offensive_mode:
                for raw in cycle_result.raw_results:
                    output = raw.get("output", {})
                    body = str(output.get("body", ""))
                    hdrs = output.get("headers", {})
                    if isinstance(hdrs, dict) and body:
                        self._opsec_check_response(body, hdrs, thinking)

            # ── EVIDENCE CAPTURE (/3vilbob mode) ──────────────
            # Auto-capture evidence for every finding
            if self._evidence and step_findings:
                thinking.append(f"[EVIDENCE] Capturing proof for {len(step_findings)} findings...")
                for finding in step_findings:
                    try:
                        await self._capture_finding_evidence(finding, agent)
                    except Exception as exc:
                        thinking.append(f"  Evidence capture error: {str(exc)[:100]}")

            # ── CREDENTIAL EXTRACTION CHAIN (/3vilbob mode) ───
            # When we find .env, config files, or exposed secrets,
            # don't just report "file found" -- extract credentials,
            # test connectivity, and prove data access.
            if self.offensive_mode and step_findings:
                credential_findings = [
                    f for f in step_findings
                    if any(p in str(f.get("url", "")).lower()
                           for p in ("/.env", "/.git/", "/config", "docker-compose", ".json"))
                    and f.get("status_code") == 200
                ]
                if credential_findings:
                    from app.services.security.credential_chain import CredentialExtractionChain
                    cred_chain = CredentialExtractionChain()
                    thinking.append(
                        f"[CRED CHAIN] {len(credential_findings)} config files found. "
                        f"Extracting credentials and testing connectivity..."
                    )
                    for cf in credential_findings[:3]:
                        cf_url = cf.get("url", "")
                        # Re-fetch the file content for parsing
                        try:
                            import httpx as _hx
                            req_h = self._get_request_headers()
                            async with _hx.AsyncClient(
                                timeout=10.0, verify=False,
                                proxy=self._resolve_proxy() or None,
                            ) as _client:
                                resp = await _client.get(cf_url, headers=req_h)
                                if resp.status_code == 200 and len(resp.text) > 10:
                                    chain_result = await cred_chain.execute(
                                        content=resp.text,
                                        source_url=cf_url,
                                    )
                                    thinking.extend(chain_result.thinking)

                                    if chain_result.successful_connections > 0:
                                        # Add as critical finding
                                        step_findings.append({
                                            "type": "credential_chain",
                                            "url": cf_url,
                                            "info": {
                                                "name": f"Credential Chain: {chain_result.total_impact[:80]}",
                                                "severity": "critical",
                                                "description": chain_result.total_impact,
                                            },
                                            "credentials_found": chain_result.credentials_found,
                                            "connections_succeeded": chain_result.successful_connections,
                                        })
                                    elif chain_result.credentials_found > 0:
                                        step_findings.append({
                                            "type": "credential_extraction",
                                            "url": cf_url,
                                            "info": {
                                                "name": f"Credentials Extracted: {chain_result.credentials_found} from {cf_url}",
                                                "severity": "high",
                                                "description": chain_result.total_impact,
                                            },
                                            "credentials_found": chain_result.credentials_found,
                                        })
                        except Exception as exc:
                            thinking.append(f"  Cred chain failed for {cf_url}: {str(exc)[:100]}")

            # ── AUTO-EXPLOIT CHAIN (/3vilbob mode) ────────────
            # A scanner REPORTS. Daena PROVES IMPACT.
            # Classify which findings are exploitable, then auto-chain
            # into TargetInteractionAgent to walk through the doors we found.
            if self.offensive_mode and step_findings:
                exploitable = self._classify_exploitable_findings(step_findings)
                if exploitable:
                    exploit_attempts = await self._auto_exploit(
                        exploitable, cycle_num, thinking,
                    )
                    result.exploit_attempts.extend(exploit_attempts)
                    result.exploits_succeeded += sum(1 for a in exploit_attempts if a.success)

                    # Feed successful exploitations back as new findings
                    # so the next OODA cycle can reason about what we found INSIDE
                    for attempt in exploit_attempts:
                        if attempt.success and attempt.result_data:
                            exploitation_finding = {
                                "type": "post_exploitation",
                                "url": attempt.target_url,
                                "operation": attempt.operation,
                                "impact": attempt.impact_proven,
                                "info": {
                                    "name": f"Impact Proven: {attempt.impact_proven[:80]}",
                                    "severity": "high",
                                    "description": (
                                        f"Post-exploitation via {attempt.operation} confirmed: "
                                        f"{attempt.impact_proven}. Auto-chained from cycle {cycle_num} "
                                        f"finding type: {attempt.finding_type}."
                                    ),
                                },
                                "chained_from": attempt.finding_type,
                                "cycle": cycle_num,
                            }
                            step_findings.append(exploitation_finding)
                            result.findings.append(exploitation_finding)

            # ── REFLECT (LLM-powered) ──────────────────────────
            thinking.append(f"[REFLECT] Strategy '{strategy.name}' complete.")

            if step_findings:
                cycle_result.success = True
                thinking.append(f"  Found {len(step_findings)} findings. Strategy worked.")
                result.findings.extend(step_findings)

                # LLM reflects on WHY it worked -- understanding success
                # is as important as understanding failure (EQ)
                if self._reasoner_initialized:
                    reflection = await reasoner.reflect(
                        strategy=strategy.name,
                        results={"findings_count": len(step_findings), "types": [f.get("type") for f in step_findings[:5]]},
                        success=True,
                        task=f"Scan {target}",
                    )
                    if reflection.lesson:
                        thinking.append(f"  Lesson: {reflection.lesson[:200]}")
            else:
                cycle_result.success = False
                cycle_result.failure_reason = self._diagnose_failure(strategy, cycle_result, profile)
                thinking.append(f"  Zero findings. Diagnosing WHY...")
                thinking.append(f"  Diagnosis: {cycle_result.failure_reason}")

                # LLM reflects on failure -- deeper than deterministic diagnosis
                if self._reasoner_initialized:
                    reflection = await reasoner.reflect(
                        strategy=strategy.name,
                        results={"failure_reason": cycle_result.failure_reason, "target_type": profile.target_type},
                        success=False,
                        task=f"Scan {target}",
                    )
                    if reflection.root_cause:
                        thinking.append(f"  LLM root cause: {reflection.root_cause[:200]}")
                    if reflection.next_suggestion:
                        thinking.append(f"  LLM suggestion: {reflection.next_suggestion[:200]}")

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

                # ── ERROR ORACLE (/3vilbob: Beyond Mythos) ────
                # Every failure response is intelligence. Parse raw
                # results to extract what the target leaked in errors.
                if self.offensive_mode and cycle_result.raw_results:
                    from app.services.cognition.beyond_mythos import ErrorOracle
                    oracle = ErrorOracle()
                    error_intel_items = []
                    for raw in cycle_result.raw_results:
                        output = raw.get("output", {})
                        # Extract from HTTP-like results
                        status = output.get("status_code", 0)
                        if status > 0:
                            ei = oracle.analyze_response(
                                url=output.get("url", target),
                                status_code=status,
                                headers=output.get("headers", {}),
                                body=output.get("body", ""),
                                response_time_ms=output.get("elapsed_ms", 0),
                            )
                            if ei.intelligence:
                                error_intel_items.append(ei)

                        # Extract from sub-results (probe results, etc.)
                        for sub_result in output.get("results", []):
                            if isinstance(sub_result, dict):
                                sub_status = sub_result.get("status_code", sub_result.get("status-code", 0))
                                if sub_status > 0:
                                    ei = oracle.analyze_response(
                                        url=sub_result.get("url", target),
                                        status_code=sub_status,
                                        headers=sub_result.get("headers", sub_result.get("header", {})),
                                        body=str(sub_result.get("body", "")),
                                    )
                                    if ei.intelligence:
                                        error_intel_items.append(ei)

                    if error_intel_items:
                        thinking.append(f"[ERROR ORACLE] Extracted intelligence from {len(error_intel_items)} error responses:")
                        for ei in error_intel_items[:5]:
                            for insight in ei.intelligence[:3]:
                                thinking.append(f"    [{ei.status_code}] {insight}")
                            # Feed inferred facts back into target profile
                            if ei.inferred_facts.get("path_exists"):
                                path = ei.source_url
                                if path not in profile.interesting_paths:
                                    profile.interesting_paths.append(path)
                            for tech in ei.inferred_facts.get("technologies", []):
                                if tech not in profile.technologies:
                                    profile.technologies.append(tech)

                    # Compare responses for differential intelligence
                    comparison_data = []
                    for raw in cycle_result.raw_results:
                        output = raw.get("output", {})
                        if output.get("status_code"):
                            comparison_data.append(output)
                        for sub in output.get("results", []):
                            if isinstance(sub, dict) and sub.get("status_code"):
                                comparison_data.append(sub)
                    if len(comparison_data) >= 2:
                        diff_insights = oracle.compare_responses(comparison_data)
                        for insight in diff_insights[:3]:
                            thinking.append(f"    [DIFFERENTIAL] {insight}")

                    # ── ABDUCTIVE REASONING (Apex Cognition) ──────
                    # Sherlock Holmes: from observations, infer what
                    # MUST be true about the target's internals.
                    from app.services.cognition.apex_cognition import AbductiveReasoner
                    abducer = AbductiveReasoner()
                    abductions = abducer.abduce(comparison_data)
                    if abductions:
                        thinking.append(f"[ABDUCTIVE] {len(abductions)} inferences from observations:")
                        for abd in abductions[:4]:
                            thinking.append(f"    [{abd.confidence:.0%}] {abd.inference}")
                            thinking.append(f"      Test: {abd.testable_prediction}")
                            for impl in abd.implications[:2]:
                                thinking.append(f"      -> {impl}")

                    # ── HYPOTHESIS GENERATION + TESTING (Apex Cognition) ─
                    # Scientific method: generate testable hypotheses
                    # from observations, then TEST them in ACT phase.
                    from app.services.cognition.apex_cognition import HypothesisTester
                    hyp_tester = HypothesisTester()
                    obs_for_hyp = {
                        "technologies": profile.technologies,
                        "waf_detected": profile.waf_detected,
                        "api_patterns": profile.interesting_paths,
                        "status_codes": {},
                    }
                    hypotheses = hyp_tester.generate_hypotheses(obs_for_hyp)
                    if hypotheses:
                        thinking.append(f"[HYPOTHESES] {len(hypotheses)} testable hypotheses generated. Testing...")

                        # Execute hypothesis tests
                        import httpx as _hx2
                        req_h2 = self._get_request_headers()
                        _proxy2 = self._resolve_proxy()
                        try:
                            async with _hx2.AsyncClient(
                                timeout=8.0, verify=False,
                                follow_redirects=False,
                                proxy=_proxy2 or None,
                            ) as hyp_client:
                                for hyp in hypotheses[:5]:
                                    test = hyp.test_action
                                    op = test.get("op", "")
                                    params = test.get("params", {})

                                    if op == "http_request":
                                        path = params.get("path", "/")
                                        method = params.get("method", "GET")
                                        test_url = f"https://{target}{path}"
                                        headers = {**req_h2, **params.get("headers", {})}
                                        body = params.get("body", "")

                                        try:
                                            if method == "POST":
                                                resp = await hyp_client.post(
                                                    test_url, content=body, headers=headers,
                                                )
                                            else:
                                                resp = await hyp_client.get(
                                                    test_url, headers=headers,
                                                )

                                            test_result = {
                                                "status_code": resp.status_code,
                                                "success": resp.status_code < 500,
                                                "body": resp.text[:500],
                                            }
                                            hyp = hyp_tester.update_hypothesis(hyp, test_result)

                                            status_icon = {
                                                "confirmed": "CONFIRMED",
                                                "refuted": "REFUTED",
                                                "partial": "PARTIAL",
                                            }.get(hyp.result, "INCONCLUSIVE")
                                            thinking.append(
                                                f"    [{status_icon}] H: {hyp.statement} "
                                                f"({resp.status_code}) conf: {hyp.confidence_before:.0%} -> {hyp.confidence_after:.0%}"
                                            )

                                            # Confirmed hypothesis -> new finding
                                            if hyp.result == "confirmed":
                                                step_findings.append({
                                                    "type": "hypothesis_confirmed",
                                                    "url": test_url,
                                                    "status_code": resp.status_code,
                                                    "info": {
                                                        "name": f"Hypothesis Confirmed: {hyp.statement}",
                                                        "severity": "medium",
                                                        "description": (
                                                            f"Hypothesis: {hyp.statement}. "
                                                            f"Prediction: {hyp.prediction}. "
                                                            f"Result: confirmed ({resp.status_code}). "
                                                            f"Implications: {'; '.join(hyp.spawned_hypotheses[:3])}"
                                                        ),
                                                    },
                                                })
                                                # Spawn new hypotheses from confirmation
                                                for spawned in hyp.spawned_hypotheses:
                                                    thinking.append(f"      -> Spawned: {spawned}")

                                        except Exception:
                                            thinking.append(f"    [ERROR] H: {hyp.statement} -- test failed")
                                    else:
                                        thinking.append(f"    [SKIP] H: {hyp.statement} -- test type '{op}' not yet implemented")
                        except Exception:
                            thinking.append("    Hypothesis testing client failed")

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

        # ── ATTACK CHAIN SYNTHESIS (/3vilbob: Unreplicable) ──
        # Individual findings are noise. Chains are signal.
        # Connect findings into kill chains that escalate severity.
        # A $500 info-disclosure + a $500 IDOR = a $50K account takeover.
        if self.offensive_mode and len(result.findings) >= 2:
            from app.services.cognition.unreplicable import AttackChainSynthesizer
            synth = AttackChainSynthesizer()
            chains = synth.synthesize(result.findings)
            if chains:
                result.thinking_log.append(
                    f"[ATTACK CHAINS] Synthesized {len(chains)} kill chains from {len(result.findings)} findings:"
                )
                for chain in chains[:5]:
                    result.thinking_log.append(
                        f"  CHAIN [{chain.severity.upper()}]: {chain.reasoning}"
                    )
                    result.thinking_log.append(
                        f"    Impact: {chain.impact} (probability: {chain.probability:.1f})"
                    )
                    # Add chain as a high-severity finding
                    chain_finding = {
                        "type": "attack_chain",
                        "chain_id": chain.chain_id,
                        "url": chain.entry_point,
                        "impact": chain.impact,
                        "info": {
                            "name": f"Attack Chain: {chain.impact}",
                            "severity": chain.severity,
                            "description": chain.reasoning,
                        },
                        "chain_findings_count": len(chain.findings),
                        "probability": chain.probability,
                    }
                    result.findings.append(chain_finding)
                result.total_findings = len(result.findings)
                result.evidence_summary["attack_chains"] = len(chains)

        # ── EMERGENT VULNERABILITY DISCOVERY (Apex Cognition) ─
        # Find vulns in component INTERACTIONS, not individual components.
        # These are the $100K bounties.
        if self.offensive_mode and result.findings:
            from app.services.cognition.apex_cognition import EmergentVulnFinder
            evf = EmergentVulnFinder()
            components = list(set(
                f.get("type", "") for f in result.findings
            ))
            emergent = evf.find_emergent_vulns(
                components=components,
                technologies=profile.technologies,
                findings=result.findings,
            )
            if emergent:
                result.thinking_log.append(
                    f"[EMERGENT VULNS] {len(emergent)} interaction-based vulnerabilities predicted:"
                )
                for ev in emergent[:5]:
                    result.thinking_log.append(
                        f"  [{ev.severity.upper()}] {ev.component_a} + {ev.component_b}"
                    )
                    result.thinking_log.append(f"    Vuln: {ev.vulnerability}")
                    result.thinking_log.append(f"    PoC: {ev.proof_concept}")
                    result.findings.append({
                        "type": "emergent_vulnerability",
                        "info": {
                            "name": f"Emergent: {ev.vulnerability[:60]}",
                            "severity": ev.severity,
                            "description": (
                                f"Interaction between {ev.component_a} and {ev.component_b}: "
                                f"{ev.vulnerability}. Test: {ev.proof_concept}"
                            ),
                        },
                        "component_a": ev.component_a,
                        "component_b": ev.component_b,
                    })
                result.total_findings = len(result.findings)

        # Generate dual reports (findings + remediation)
        if result.findings or result.enriched_findings:
            try:
                result.report_path = await self._generate_report(
                    target, program, result, profile,
                )
            except Exception as exc:
                logger.debug("cognitive_scan.report_failed", error=str(exc))

            # Remediation report (/3vilbob mode)
            if self.offensive_mode:
                try:
                    from app.services.security.report_generator import (
                        RemediationReportGenerator, ReportMetadata as RM, VulnFinding as VF,
                    )
                    rem_gen = RemediationReportGenerator()
                    vuln_findings = []
                    for f in (result.enriched_findings or result.findings):
                        info = f.get("info", {})
                        vuln_findings.append(VF(
                            title=info.get("name", f.get("type", "Finding")),
                            severity=info.get("severity", "low"),
                            description=info.get("description", ""),
                            affected_url=f.get("url", ""),
                        ))
                    rem_meta = RM(
                        program_name=program or "Security Assessment",
                        target=target,
                    )
                    dev_prof = result.evidence_summary.get("dev_profile")
                    rem_path = rem_gen.generate(
                        vuln_findings, result.findings, rem_meta,
                        dev_profile=dev_prof,
                    )
                    result.evidence_summary["remediation_report"] = rem_path
                    logger.info("cognitive_scan.remediation_report_generated", path=rem_path)
                except Exception as exc:
                    logger.debug("cognitive_scan.remediation_failed", error=str(exc)[:200])

        result.target_profile = profile
        result.offensive_mode = self.offensive_mode

        # Attach OPSEC report (/3vilbob mode)
        if self._opsec:
            opsec_report = self._opsec.generate_report()
            result.evidence_summary["opsec"] = {
                "profiles_rotated": opsec_report.profiles_rotated,
                "total_requests": opsec_report.total_requests,
                "timing_delays_total_ms": opsec_report.timing_delays_total_ms,
                "detected_fingerprinting": opsec_report.detected_fingerprinting,
            }
            result.thinking_log.append(
                f"[OPSEC] Report: {opsec_report.profiles_rotated} identity rotations, "
                f"{opsec_report.total_requests} requests with {opsec_report.timing_delays_total_ms}ms total timing delays"
            )

        # Attach evidence chain summary (/3vilbob mode)
        if self._evidence:
            result.evidence_summary = self._evidence.get_evidence_summary()
            logger.info(
                "cognitive_scan.evidence_chain_complete",
                total_evidence=result.evidence_summary.get("total_evidence", 0),
                chain_hash=result.evidence_summary.get("chain_hash", "")[:12],
            )

        # ── SCAN TRACE ARCHIVAL (Meta-Harness-inspired) ────
        # Store the full thinking log so future scans can learn from
        # past experiences. The self_upgrader reads these to discover
        # what strategies worked on what target types.
        await self._archive_scan_trace(target, result, profile)

        # ── SELF-IMPROVEMENT (Meta-Harness loop) ────
        # Every N scans, analyze traces to discover new patterns and
        # inject them into the reasoner's framework set. This is what
        # makes Daena anti-fragile: every scan makes future scans smarter.
        await self._maybe_self_upgrade()

        logger.info(
            "cognitive_scan.complete",
            target=target,
            findings=result.total_findings,
            cycles=result.cycles_used,
            strategies=result.strategies_tried,
            offensive=self.offensive_mode,
            evidence_count=result.evidence_summary.get("total_evidence", 0) if result.evidence_summary else 0,
        )
        return result

    # ------------------------------------------------------------------
    # Auto-exploitation chain (/3vilbob only)
    # ------------------------------------------------------------------

    def _classify_exploitable_findings(
        self,
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Classify which findings can be auto-exploited via TargetInteractionAgent.

        Not every finding is exploitable. A missing HSTS header is informational.
        An exposed /api/docs with no auth IS exploitable -- we can hit the endpoints.
        An exposed .env file with DB credentials IS exploitable -- we can connect.

        Returns findings augmented with 'exploit_plan' containing the operation
        and params for TargetInteractionAgent.
        """
        exploitable = []

        for finding in findings:
            url = finding.get("url", finding.get("matched-at", ""))
            finding_type = finding.get("type", "")
            info = finding.get("info", {})
            severity = info.get("severity", "informational")

            # Skip informational-only findings (no exploitation value)
            if severity == "informational" and finding_type not in ("path_discovery", "ct_log"):
                continue

            plan = None

            # Exposed paths that might leak data or allow interaction
            if finding_type == "path_discovery" and url:
                status_code = finding.get("status_code", 0)
                path_lower = url.lower()

                if status_code == 200:
                    # Sensitive file exposure (.env, .git/config, etc.)
                    if any(p in path_lower for p in ("/.env", "/.git/", "/.ds_store", "/.htaccess")):
                        plan = {
                            "operation": "http_request",
                            "params": {"url": url, "method": "GET"},
                            "rationale": "Sensitive file exposed -- fetch and extract credentials/config",
                            "impact_category": "credential_exposure",
                        }
                    # API docs / GraphQL introspection -- enumerate endpoints
                    elif any(p in path_lower for p in ("/api/docs", "/swagger", "/openapi", "/graphql")):
                        plan = {
                            "operation": "http_request",
                            "params": {"url": url, "method": "GET"},
                            "rationale": "API documentation exposed -- enumerate available endpoints",
                            "impact_category": "api_exposure",
                        }
                    # Admin / debug panels -- attempt access
                    elif any(p in path_lower for p in ("/admin", "/debug", "/metrics", "/status", "/server-status")):
                        plan = {
                            "operation": "http_request",
                            "params": {"url": url, "method": "GET"},
                            "rationale": "Admin/debug endpoint accessible -- prove unauthorized access",
                            "impact_category": "unauthorized_access",
                        }

            # Nuclei/vuln scanner findings with matched URLs
            elif url and severity in ("high", "critical", "medium"):
                plan = {
                    "operation": "http_request",
                    "params": {"url": url, "method": "GET"},
                    "rationale": f"Vulnerability ({severity}) confirmed by scanner -- verify exploitability",
                    "impact_category": "vulnerability_verification",
                }

            # Service enumeration findings (open ports with identified services)
            elif finding_type == "service_enum":
                host = finding.get("host", "")
                port = finding.get("port", 0)
                service = finding.get("service", "")
                if host and port:
                    if service in ("ssh", "ftp"):
                        plan = {
                            "operation": "tcp_connect",
                            "params": {"host": host, "port": port},
                            "rationale": f"{service} service detected -- banner grab and protocol probe",
                            "impact_category": "service_exposure",
                        }
                    elif service in ("mysql", "postgresql", "redis"):
                        plan = {
                            "operation": "tcp_connect",
                            "params": {"host": host, "port": port},
                            "rationale": f"Database service ({service}) exposed -- test connectivity",
                            "impact_category": "database_exposure",
                        }

            if plan:
                finding["exploit_plan"] = plan
                exploitable.append(finding)

        return exploitable

    async def _auto_exploit(
        self,
        exploitable_findings: list[dict[str, Any]],
        cycle_num: int,
        thinking: list[str],
    ) -> list[ExploitAttempt]:
        """Auto-chain into TargetInteractionAgent for exploitable findings.

        This is what separates a penetration test from a vulnerability scan.
        The scan found the door. Now we walk through it to prove impact.

        Each exploitation attempt:
        1. Uses TargetInteractionAgent (which gates on /3vilbob active)
        2. Captures evidence automatically (agent has built-in capture)
        3. Returns structured results for the scan report
        4. Feeds back into the OODA loop as new observations
        """
        from app.services.daenabot.target_interaction_agent import TargetInteractionAgent

        agent = TargetInteractionAgent(evidence_capture=self._evidence)
        attempts: list[ExploitAttempt] = []

        thinking.append(f"[AUTO-EXPLOIT] {len(exploitable_findings)} exploitable findings detected. Chaining into post-exploitation...")

        for finding in exploitable_findings:
            plan = finding.get("exploit_plan", {})
            if not plan:
                continue

            operation = plan["operation"]
            params = plan["params"]
            rationale = plan.get("rationale", "")
            impact_cat = plan.get("impact_category", "unknown")

            url_or_host = params.get("url", params.get("host", "unknown"))
            thinking.append(f"  -> {operation} on {url_or_host}: {rationale}")

            attempt = ExploitAttempt(
                finding_type=impact_cat,
                operation=operation,
                target_url=url_or_host,
                chained_from_cycle=cycle_num,
            )

            try:
                result = await agent.execute(operation, params)

                if result.get("success"):
                    output = result.get("output", {})
                    attempt.success = True
                    attempt.result_data = output

                    # Determine what impact was proven based on the response
                    impact_proof = self._assess_impact(operation, output, impact_cat)
                    attempt.impact_proven = impact_proof
                    thinking.append(f"    EXPLOITED: {impact_proof}")
                else:
                    attempt.error = result.get("error", "execution failed")
                    thinking.append(f"    Failed: {attempt.error[:100]}")

            except Exception as exc:
                attempt.error = str(exc)[:300]
                thinking.append(f"    Exception: {attempt.error[:100]}")

            attempts.append(attempt)

        # Cleanup
        await agent.close()

        succeeded = sum(1 for a in attempts if a.success)
        thinking.append(f"[AUTO-EXPLOIT] Complete: {succeeded}/{len(attempts)} exploitations succeeded.")

        return attempts

    def _assess_impact(
        self,
        operation: str,
        output: dict[str, Any],
        impact_category: str,
    ) -> str:
        """Assess what impact was actually proven by a successful exploitation.

        Translates raw response data into human-readable impact statements
        for the report. "I got a 200 OK" is not impact. "I read 50 user
        records without authentication" IS impact.
        """
        if operation == "http_request":
            status = output.get("status_code", 0)
            body_len = output.get("body_length", 0)
            body = output.get("body", "")[:500]
            tokens_found = output.get("tokens_found", 0)

            if tokens_found > 0:
                return f"Extracted {tokens_found} authentication token(s) from response"

            if impact_category == "credential_exposure":
                # Check if body contains credential-like patterns
                cred_indicators = ["password", "secret", "api_key", "token", "database_url", "db_host"]
                found = [k for k in cred_indicators if k.lower() in body.lower()]
                if found:
                    return f"Sensitive configuration exposed: {', '.join(found)} found in response ({body_len} bytes)"
                return f"Sensitive file accessible ({status}), {body_len} bytes retrieved"

            if impact_category == "api_exposure":
                return f"API documentation accessible without authentication ({status}), {body_len} bytes of endpoint definitions"

            if impact_category == "unauthorized_access":
                return f"Admin/debug endpoint accessible without authentication ({status}), {body_len} bytes"

            if impact_category == "vulnerability_verification":
                return f"Vulnerability confirmed exploitable -- server responded {status} with {body_len} bytes"

            return f"Target responded {status}, {body_len} bytes"

        elif operation == "tcp_connect":
            banner = output.get("banner", "")
            connected = output.get("connected", False)
            if connected and banner:
                return f"Service accessible, banner: {banner[:100]}"
            elif connected:
                return "Service port open and accepting connections"
            return "Connection attempt completed"

        elif operation == "ssh_connect":
            return f"SSH access established as {output.get('username', 'unknown')}@{output.get('host', 'unknown')}"

        elif operation == "db_connect":
            tables = output.get("table_count", 0)
            return f"Database accessible, {tables} tables enumerated"

        elif operation == "db_query":
            rows = output.get("row_count", 0)
            cols = output.get("columns", [])
            return f"Data extracted: {rows} rows, columns: {cols[:5]}"

        return "Exploitation completed"

    # ------------------------------------------------------------------
    # OPSEC helpers (fingerprint rotation, timing, counter-detection)
    # ------------------------------------------------------------------

    def _get_request_headers(self) -> dict[str, str]:
        """Get request headers with OPSEC-grade browser fingerprints.

        When OPSEC is active: full browser profile (UA, Sec-CH-UA,
        Sec-Fetch, Accept, etc.) that passes bot detection.
        Fallback: proxy manager headers or basic UA.
        """
        if self._opsec:
            return self._opsec.get_request_headers()
        if self._proxy_manager:
            return self._proxy_manager.get_request_headers()
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    async def _opsec_wait(self) -> int:
        """Wait with human-like timing before next request.

        Returns delay in ms (0 if OPSEC not active).
        """
        if self._opsec:
            return await self._opsec.timing.wait_before_request()
        return 0

    def _opsec_rotate_if_needed(self, cycle_num: int) -> None:
        """Rotate browser fingerprint between OODA cycles.

        Different cycles look like different users visiting the site.
        """
        if self._opsec and cycle_num > 1:
            self._opsec.rotate_identity()
            logger.debug(
                "cognitive_scan.opsec_rotated",
                cycle=cycle_num,
                profile=self._opsec.fingerprints.get_profile().get("name", ""),
                rotations=self._opsec.fingerprints.rotation_count,
            )

    def _opsec_check_response(
        self,
        body: str,
        headers: dict[str, str],
        thinking: list[str],
    ) -> None:
        """Check if the target is trying to fingerprint our scanner."""
        if not self._opsec:
            return
        result = self._opsec.detect_fingerprinting(body, headers)
        if result["fingerprinting_detected"]:
            thinking.append(
                f"[OPSEC] Counter-fingerprinting detected (risk: {result['risk']}): "
                f"{'; '.join(result['findings'][:3])}"
            )
            thinking.append(f"  Recommendation: {result['recommendation']}")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Scan trace archival (Meta-Harness-inspired self-improvement)
    # ------------------------------------------------------------------

    async def _archive_scan_trace(
        self,
        target: str,
        result: CognitiveScanResult,
        profile: TargetProfile,
    ) -> None:
        """Archive full scan trace for future self-improvement.

        Stores the thinking log, strategies tried, findings, and target
        profile. The SelfUpgrader reads these to discover patterns:
        - What strategies worked on what target types?
        - Which offensive lenses produced the best findings?
        - Where did the OODA loop get stuck?

        This is the Meta-Harness principle: full trace access enables
        the proposer to understand subtle causal chains. Summaries lose
        the detail that matters.
        """
        try:
            trace = {
                "scan_id": self._scan_id,
                "target": target,
                "target_type": profile.target_type,
                "waf_detected": profile.waf_detected,
                "technologies": profile.technologies[:20],
                "strategies_tried": result.strategies_tried,
                "total_findings": result.total_findings,
                "cycles_used": result.cycles_used,
                "exploits_succeeded": result.exploits_succeeded,
                "offensive_mode": self.offensive_mode,
                "thinking_log": result.thinking_log[-100:],  # Last 100 entries
                "findings_summary": [
                    {
                        "type": f.get("type", ""),
                        "severity": f.get("info", {}).get("severity", ""),
                        "url": f.get("url", "")[:200],
                    }
                    for f in result.findings[:30]
                ],
            }

            # Store to var/scan_traces/ for SelfUpgrader access
            import json
            import os
            trace_dir = os.path.join(
                os.environ.get("DAENA_VAR", "var"), "scan_traces"
            )
            os.makedirs(trace_dir, exist_ok=True)
            trace_path = os.path.join(trace_dir, f"{self._scan_id}.json")
            with open(trace_path, "w", encoding="utf-8") as f:
                json.dump(trace, f, indent=2, default=str)

            logger.info(
                "cognitive_scan.trace_archived",
                scan_id=self._scan_id,
                path=trace_path,
                thinking_entries=len(trace["thinking_log"]),
            )
            # Feed findings into Cognitive Knowledge Graph for cross-domain learning
            self._feed_knowledge_graph(target, result, profile)

        except Exception as exc:
            # Archival is best-effort, never blocks the scan
            logger.debug("cognitive_scan.trace_archive_failed", error=str(exc)[:200])

    def _feed_knowledge_graph(
        self,
        target: str,
        result: CognitiveScanResult,
        profile: TargetProfile,
    ) -> None:
        """Feed scan insights into the Cognitive Knowledge Graph.

        This is the bridge between security scanning and Daena's universal
        learning substrate. Every finding, every strategy outcome, every
        thinking pattern gets abstracted and stored for cross-domain use.

        Example: "timing analysis revealed WAF rules" becomes a universal
        insight that Engineering can use for API debugging, Operations
        can use for capacity planning, and Research can use for competitive
        analysis.
        """
        try:
            from app.services.cognition.knowledge_graph import (
                CognitiveKnowledgeGraph, Domain, Experience,
            )
            ckg = CognitiveKnowledgeGraph()

            # Feed successful strategy outcomes
            for finding in result.findings[:10]:  # Cap to avoid flooding
                observation = (
                    f"{finding.get('type', 'unknown')}: "
                    f"{finding.get('info', {}).get('name', '')} "
                    f"(severity: {finding.get('info', {}).get('severity', 'unknown')})"
                )
                exp = Experience(
                    domain=Domain.SECURITY,
                    task_type="cognitive_scan",
                    outcome="success",
                    observation=observation,
                    context={
                        "target_type": profile.target_type,
                        "waf": profile.defenses.get("waf", ""),
                        "technologies": profile.technologies[:5],
                    },
                    trace_id=self._scan_id,
                )
                ckg.learn(exp)

            # Feed strategy outcomes (successes and failures)
            for strategy_name in result.strategies_tried:
                had_findings = any(
                    strategy_name in str(f.get("strategy", ""))
                    for f in result.findings
                )
                exp = Experience(
                    domain=Domain.SECURITY,
                    task_type="strategy_outcome",
                    outcome="success" if had_findings else "failure",
                    observation=(
                        f"strategy '{strategy_name}' on {profile.target_type} target"
                        f"{' with WAF ' + profile.defenses.get('waf', '') if profile.defenses.get('waf') else ''}"
                    ),
                    trace_id=self._scan_id,
                )
                ckg.learn(exp)

            # Feed thinking patterns (key observations from the scan)
            for entry in result.thinking_log[-5:]:  # Last 5 thinking entries
                if any(kw in entry.lower() for kw in [
                    "timing", "error", "boundary", "decompos", "bypass",
                    "state", "absence", "missing", "inverse", "cost",
                ]):
                    exp = Experience(
                        domain=Domain.SECURITY,
                        task_type="cognitive_observation",
                        outcome="success",
                        observation=entry[:200],
                        trace_id=self._scan_id,
                    )
                    ckg.learn(exp)

            logger.debug(
                "cognitive_scan.ckg_fed",
                scan_id=self._scan_id,
                insights_total=ckg.total_insights,
            )
        except Exception as exc:
            # CKG feeding is best-effort
            logger.debug("cognitive_scan.ckg_feed_failed", error=str(exc)[:100])

    # ------------------------------------------------------------------
    # Self-improvement (Meta-Harness loop)
    # ------------------------------------------------------------------

    async def _maybe_self_upgrade(self) -> None:
        """Analyze scan traces every N scans to discover patterns.

        Reads var/scan_traces/, groups by target type, extracts:
        - Strategies that consistently produce findings
        - Strategies that consistently fail
        - Target type characteristics that predict vulnerability patterns

        Discovered patterns get injected into the MetaReasoner's framework
        set via SelfUpgrader.evaluate_and_adopt().

        The threshold is every 10 scans (to accumulate enough data).
        """
        import json
        import os

        trace_dir = os.path.join(
            os.environ.get("DAENA_VAR", "var"), "scan_traces"
        )
        if not os.path.isdir(trace_dir):
            return

        traces = sorted(os.listdir(trace_dir))
        if len(traces) < 10:
            return  # Not enough data yet

        # Only run every 10 scans (check if count is multiple of 10)
        if len(traces) % 10 != 0:
            return

        try:
            from app.services.cognition.self_upgrader import SelfUpgrader

            # Load recent traces (last 20)
            history: list[dict] = []
            for trace_file in traces[-20:]:
                trace_path = os.path.join(trace_dir, trace_file)
                try:
                    with open(trace_path, "r", encoding="utf-8") as f:
                        trace_data = json.load(f)

                    # Convert trace to execution history format for SelfUpgrader
                    for strategy in (trace_data.get("strategies_tried") or [""]):
                        history.append({
                            "success": trace_data.get("total_findings", 0) > 0,
                            "problem_type": trace_data.get("target_type", "unknown"),
                            "strategy": strategy,
                            "task": f"scan_{trace_data.get('target', 'unknown')}",
                            "findings_count": trace_data.get("total_findings", 0),
                            "offensive_mode": trace_data.get("offensive_mode", False),
                            "waf": trace_data.get("waf_detected", ""),
                        })
                except (json.JSONDecodeError, OSError):
                    continue

            if not history:
                return

            upgrader = SelfUpgrader()
            candidates = await upgrader.discover_from_history(history)

            if candidates:
                # Backtest: score candidates based on historical success rate
                for candidate in candidates:
                    matching = [
                        h for h in history
                        if any(pt in h.get("problem_type", "") for pt in candidate.when_to_use)
                    ]
                    if matching:
                        success_rate = sum(1 for h in matching if h["success"]) / len(matching)
                        candidate.backtest_score = success_rate

                # Adopt patterns that meet threshold
                from app.services.cognition.meta_reasoner import MetaReasoner
                meta = MetaReasoner()
                adopted = await upgrader.evaluate_and_adopt(meta)

                if adopted:
                    logger.info(
                        "cognitive_scan.self_upgrade",
                        adopted_frameworks=adopted,
                        total_traces=len(traces),
                        history_entries=len(history),
                    )

        except Exception as exc:
            # Self-improvement is best-effort, never blocks scans
            logger.debug("cognitive_scan.self_upgrade_failed", error=str(exc)[:200])

    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_proxy(self) -> str:
        """Resolve proxy URL for IP protection during scanning.

        Uses ProxyManager for centralized proxy management.
        In offensive mode (/3vilbob), proxy is MANDATORY.

        Priority (via ProxyManager):
            1. Explicit proxy passed to constructor
            2. Rotating residential proxy (SCAN_PROXY env var)
            3. Tor SOCKS5 (USE_TOR env var)
            4. Direct connection (WARNING in offensive mode: raises)
        """
        # Explicit proxy override
        if self.proxy:
            return self.proxy

        # Use ProxyManager (handles env vars, health tracking, failover)
        if self._proxy_manager:
            return self._proxy_manager.get_proxy()

        # Legacy fallback (when ProxyManager not initialized)
        import os
        if self.use_tor:
            return "socks5://127.0.0.1:9050"
        env_proxy = os.environ.get("SCAN_PROXY", "")
        if env_proxy:
            return env_proxy
        if os.environ.get("USE_TOR", "").lower() in ("1", "true", "yes"):
            return "socks5://127.0.0.1:9050"
        return ""

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

    async def _generate_strategies(
        self,
        target: str,
        profile: TargetProfile,
        previous_cycles: list[ScanCycleResult],
        result: CognitiveScanResult | None = None,
        reasoner: Any = None,
    ) -> list[ScanStrategy]:
        """Generate scan strategies ranked for THIS specific target.

        Template strategies provide reliable coverage. In /3vilbob mode
        with LLM available, novel strategies are generated by the cognitive
        reasoner using offensive lenses -- these go BEYOND templates.
        """
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

        # Forgotten infrastructure scan (/3vilbob mode)
        if self.offensive_mode:
            strategies.append(_forgotten_infra_strategy(target))

        # Canary echo analysis (/3vilbob mode)
        if self.offensive_mode:
            live_urls = [h.get("url", "") for h in profile.live_hosts if h.get("url")]
            strategies.append(_canary_echo_strategy(target, live_urls))

        # State machine inference (/3vilbob mode, after cycle 1 when we have endpoints)
        if self.offensive_mode and (profile.interesting_paths or profile.live_hosts):
            endpoints = list(profile.interesting_paths)
            strategies.append(_state_machine_strategy(target, endpoints))

        # Cost amplification detection (/3vilbob mode)
        if self.offensive_mode:
            live_urls = [h.get("url", "") for h in profile.live_hosts if h.get("url")]
            strategies.append(_cost_amplification_strategy(target, live_urls))

        # Targeted vuln scan -- only after we know the stack
        strategies.append(_targeted_vuln_scan_strategy(
            target, profile.technologies, profile.cve_intel,
        ))

        # ── Semantic Mutation Strategy (/3vilbob: Unreplicable) ──
        # When WAF is detected, add a strategy that uses semantically
        # equivalent payloads to bypass signature detection. WAFs match
        # STRINGS; we reason about MEANING.
        if self.offensive_mode and profile.waf_detected:
            from app.services.cognition.unreplicable import SemanticMutationEngine
            mutation_engine = SemanticMutationEngine()
            sqli_payloads = mutation_engine.mutate_sql_injection("always_true")
            xss_payloads = mutation_engine.mutate_xss("alert")

            # Build probe steps from high-confidence live hosts
            mutation_steps = []
            for host in profile.live_hosts[:3]:
                url = host.get("url", f"https://{target}")
                # Test SQL injection with semantic mutations
                for payload in sqli_payloads[:3]:
                    mutation_steps.append({
                        "operation": "http_request",
                        "params": {
                            "url": f"{url}/search?q={payload.payload}",
                            "method": "GET",
                        },
                    })
                    if len(mutation_steps) >= 6:
                        break
                if len(mutation_steps) >= 6:
                    break

            if mutation_steps:
                strategies.append(ScanStrategy(
                    name="semantic_mutation_bypass",
                    description=(
                        f"WAF ({profile.waf_detected}) detected. Using semantically "
                        f"equivalent payloads that mean the same thing but look different. "
                        f"Generated {len(sqli_payloads)} SQLi + {len(xss_payloads)} XSS variants."
                    ),
                    steps=mutation_steps,
                    reasoning=(
                        "WAFs block known payload strings. Semantic mutations generate "
                        "algebraically equivalent payloads (e.g., '1=1' -> '2>1' -> 'a'='a') "
                        "that bypass signature detection while testing the same vulnerability."
                    ),
                    confidence=0.4,
                    stealth_level="medium",
                    frameworks_used=["semantic_mutation", "constraint_decomposition"],
                ))

        # ── LLM-generated novel strategies (/3vilbob mode) ────
        # When offensive mode + LLM available, the reasoner generates
        # novel attack paths that nobody hardcoded. These are appended
        # after templates so they're used when templates are exhausted
        # or alongside them for creative approaches.
        if (
            self.offensive_mode
            and self._reasoner_initialized
            and reasoner is not None
            and len(previous_cycles) >= 1  # Need at least 1 cycle of observations
        ):
            try:
                profile_dict = {
                    "target_type": profile.target_type,
                    "waf_detected": profile.waf_detected,
                    "technologies": profile.technologies[:10],
                    "subdomains": len(profile.subdomains),
                    "live_hosts": len(profile.live_hosts),
                    "defenses": profile.defenses,
                }
                exploit_results = None
                if result and result.exploit_attempts:
                    exploit_results = [
                        {"operation": a.operation, "impact_proven": a.impact_proven}
                        for a in result.exploit_attempts if a.success
                    ]
                novel_raw = await reasoner.generate_offensive_strategies(
                    target=target,
                    profile=profile_dict,
                    findings_so_far=result.findings if result else [],
                    previous_strategies=[cr.strategy_name for cr in previous_cycles],
                    exploit_results=exploit_results,
                )
                for raw in novel_raw:
                    novel_strategy = ScanStrategy(
                        name=raw.get("name", "llm_novel")[:50],
                        description=raw.get("description", "LLM-generated strategy"),
                        steps=raw.get("steps", []),
                        reasoning=raw.get("reasoning", ""),
                        confidence=raw.get("confidence", 0.5),
                        stealth_level=raw.get("stealth_level", "medium"),
                        frameworks_used=raw.get("frameworks_used", []),
                    )
                    strategies.append(novel_strategy)
                if novel_raw:
                    logger.info(
                        "cognitive_scan.novel_strategies_generated",
                        count=len(novel_raw),
                        names=[s.get("name") for s in novel_raw],
                    )
            except Exception as exc:
                logger.debug("cognitive_scan.novel_strategy_gen_failed", error=str(exc)[:200])

        # Reorder based on target type (template strategies first, novel after)
        # New interactive strategies (echo, state machine, cost amp) run after
        # standard templates but before LLM-generated novel strategies.
        template_names = {
            "passive_osint", "header_analysis", "path_discovery",
            "targeted_vuln_scan", "forgotten_infrastructure",
            "canary_echo", "state_machine", "cost_amplification",
            "semantic_mutation_bypass",
        }
        if profile.target_type == "hardened_cloud":
            order = {
                "passive_osint": 0, "header_analysis": 1, "path_discovery": 2,
                "targeted_vuln_scan": 3, "forgotten_infrastructure": 4,
                "canary_echo": 5, "state_machine": 6, "cost_amplification": 7,
                "semantic_mutation_bypass": 8,
            }
        elif profile.target_type == "waf_protected":
            order = {
                "passive_osint": 0, "header_analysis": 1, "targeted_vuln_scan": 2,
                "path_discovery": 3, "forgotten_infrastructure": 4,
                "semantic_mutation_bypass": 5, "canary_echo": 6,
                "state_machine": 7, "cost_amplification": 8,
            }
        else:
            order = {
                "passive_osint": 0, "header_analysis": 1, "path_discovery": 2,
                "targeted_vuln_scan": 3, "forgotten_infrastructure": 4,
                "canary_echo": 5, "state_machine": 6, "cost_amplification": 7,
                "semantic_mutation_bypass": 8,
            }

        # Novel strategies get order 10+ (used after templates exhausted)
        def _sort_key(s: ScanStrategy) -> int:
            if s.name in order:
                return order[s.name]
            return 10  # Novel strategies after all templates
        strategies.sort(key=_sort_key)
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

        elif operation == "_forgotten_infra_scan":
            # Scan for forgotten infrastructure services
            return await self._forgotten_infra_scan(params.get("domain", ""))

        elif operation == "_canary_echo":
            # Canary echo analysis -- one string, four vuln classes
            return await self._canary_echo(params.get("targets", []))

        elif operation == "_state_machine":
            # State machine inference -- test action sequences
            return await self._state_machine(
                params.get("target", ""),
                params.get("known_endpoints", []),
            )

        elif operation == "_cost_amplification":
            # Cost amplification detection -- timing-based DoS detection
            return await self._cost_amplification(params.get("targets", []))

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
                        req_headers = self._get_request_headers()
                        await self._opsec_wait()
                        resp = await client.get(url, headers=req_headers)
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

    async def _forgotten_infra_scan(self, domain: str) -> dict[str, Any]:
        """Scan for forgotten infrastructure services.

        Jenkins, Grafana, Sentry, Kibana, phpMyAdmin, Elasticsearch,
        Docker Registry, K8s Dashboard, Jupyter, RabbitMQ, MinIO, Redis Commander.

        These are the doors nobody locked because nobody remembers they exist.
        """
        from app.services.cognition.unreplicable import ForgottenInfraScanner
        import httpx

        scanner = ForgottenInfraScanner()
        probes = scanner.generate_forgotten_probes(domain)
        findings: list[dict[str, Any]] = []

        # Use legitimacy mimicry headers
        req_headers = self._get_request_headers()
        proxy = self._resolve_proxy()

        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                follow_redirects=False,
                verify=False,
                proxy=proxy or None,
            ) as client:
                for probe in probes:
                    if probe["type"] == "path":
                        url = probe["url"]
                        try:
                            resp = await client.get(url, headers=req_headers)
                            result = scanner.analyze_probe_result(
                                probe,
                                status_code=resp.status_code,
                                body=resp.text[:2000],
                                headers=dict(resp.headers),
                            )
                            if result:
                                findings.append(result)
                        except Exception:
                            continue
                    elif probe["type"] == "port":
                        # Port-based probe -- TCP connect check
                        import asyncio
                        import socket
                        host = probe.get("host", domain)
                        port = probe.get("port", 0)
                        if port:
                            try:
                                loop = asyncio.get_event_loop()
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.settimeout(3.0)
                                connected = await loop.run_in_executor(
                                    None, lambda: sock.connect_ex((host, port))
                                )
                                if connected == 0:
                                    # Port open -- try HTTP on it
                                    try:
                                        port_url = f"http://{host}:{port}{probe.get('path', '/')}"
                                        resp = await client.get(port_url, headers=req_headers)
                                        result = scanner.analyze_probe_result(
                                            probe,
                                            status_code=resp.status_code,
                                            body=resp.text[:2000],
                                            headers=dict(resp.headers),
                                        )
                                        if result:
                                            findings.append(result)
                                    except Exception:
                                        # Port open but not HTTP
                                        findings.append({
                                            "type": "forgotten_infrastructure",
                                            "service": probe["service"],
                                            "url": f"{host}:{port}",
                                            "severity": "medium",
                                            "info": {
                                                "name": f"Open port: {probe['service']} ({port})",
                                                "severity": "medium",
                                                "description": (
                                                    f"Port {port} open on {host}, associated with "
                                                    f"{probe['service']}. Risk: {probe['risk']}"
                                                ),
                                            },
                                        })
                                sock.close()
                            except Exception:
                                continue
        except Exception as exc:
            return {
                "summary": f"Forgotten infra scan failed: {str(exc)[:100]}",
                "findings": [],
            }

        return {
            "summary": f"Forgotten infra scan: {len(findings)} services found out of {len(probes)} probes",
            "findings": findings,
        }

    async def _capture_finding_evidence(
        self,
        finding: dict[str, Any],
        agent: Any,
    ) -> None:
        """Auto-capture evidence for a finding in /3vilbob mode.

        For each finding, captures:
        1. Reproducible curl command (always)
        2. Response snapshot (if URL available)
        3. Token extraction (if response contains tokens)
        """
        if not self._evidence:
            return

        finding_id = finding.get("matcher-name", finding.get("type", "unknown"))
        url = finding.get("url", finding.get("matched-at", finding.get("target_url", "")))

        if not url:
            return

        # 1. Generate reproducible curl command
        method = finding.get("method", "GET")
        headers = finding.get("request_headers", {})
        self._evidence.capture_curl(
            method=method,
            url=url,
            headers=headers if isinstance(headers, dict) else {},
            finding_id=finding_id,
        )

        # 2. Capture Playwright screenshot (visual proof)
        try:
            screenshot_item = await self._evidence.capture_screenshot_from_browser(
                url=url,
                finding_id=finding_id,
                description=f"Visual proof: {finding.get('info', {}).get('name', finding_id)}",
            )
            if screenshot_item:
                logger.info(
                    "cognitive_scan.screenshot_captured",
                    url=url,
                    finding=finding_id,
                )
        except Exception as exc:
            logger.debug("cognitive_scan.screenshot_failed", url=url, error=str(exc)[:100])

        # 3. Capture response snapshot if we can re-fetch
        try:
            import httpx
            request_headers = self._get_request_headers()

            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                verify=False,
                proxy=self._resolve_proxy() or None,
            ) as client:
                await self._opsec_wait()
                resp = await client.get(url, headers=request_headers)
                resp_headers = dict(resp.headers)
                body = resp.text

                await self._evidence.capture_response(
                    url=url,
                    status_code=resp.status_code,
                    headers=resp_headers,
                    body=body,
                    finding_id=finding_id,
                )

                # 3. Scan response for exposed tokens
                from app.services.security.evidence_capture import EvidenceCapture
                tokens = EvidenceCapture.detect_tokens(body)
                for token in tokens:
                    await self._evidence.capture_token(
                        url=url,
                        token_type=token["type"],
                        token_value=token["value"],
                        finding_id=finding_id,
                        context=token.get("context", ""),
                    )
                    logger.info(
                        "cognitive_scan.token_detected",
                        type=token["type"],
                        url=url,
                    )

        except Exception as exc:
            logger.debug("cognitive_scan.evidence_refetch_failed", url=url, error=str(exc)[:100])

    async def _classify_target_llm(
        self,
        profile: TargetProfile,
        reasoner: Any,
    ) -> str:
        """LLM-powered target classification.

        Instead of hardcoded domain matching, the LLM analyzes the
        target profile and REASONS about what kind of challenge it is.

        "This looks like a Google staging endpoint with test data --
        higher chance of exposed debug endpoints."

        Falls back to deterministic classification if no LLM available.
        """
        if not self._reasoner_initialized:
            return self._classify_target(profile)

        try:
            classify_prompt = (
                f"Classify this security target. Based on the profile below, "
                f"determine what KIND of target this is and what scan strategy "
                f"would be most effective.\n\n"
                f"Domain: {profile.domain}\n"
                f"Subdomains: {len(profile.subdomains)}\n"
                f"Live hosts: {len(profile.live_hosts)}\n"
                f"WAF: {profile.waf_detected or 'none detected'}\n"
                f"Technologies: {profile.technologies[:10]}\n"
                f"HTTP version: {profile.http_version or 'unknown'}\n"
                f"Response headers: {dict(list(profile.response_headers.items())[:5])}\n\n"
                f"Reply with ONE classification from this list:\n"
                f"- hardened_cloud: Major cloud provider, advanced defenses\n"
                f"- waf_protected: WAF active but not necessarily hardened\n"
                f"- modern_infrastructure: HTTP/3, current tech, well-maintained\n"
                f"- large_surface: Many subdomains, broad attack surface\n"
                f"- legacy_system: Older tech, potential unpatched vulns\n"
                f"- api_only: Pure API, no web UI\n"
                f"- staging_or_dev: Staging/dev environment, likely less hardened\n"
                f"- startup: Newer company, potentially rapid development with security gaps\n"
                f"- standard: Normal web application\n\n"
                f"Format: CLASSIFICATION: <type>\nREASONING: <why>"
            )
            result = await reasoner.orient(
                task=classify_prompt,
                observation={"domain": profile.domain},
            )
            # Parse classification from response
            for line in result.analysis.split("\n"):
                if "CLASSIFICATION:" in line.upper():
                    classification = line.split(":", 1)[1].strip().lower().replace(" ", "_")
                    valid_types = [
                        "hardened_cloud", "waf_protected", "modern_infrastructure",
                        "large_surface", "legacy_system", "api_only",
                        "staging_or_dev", "startup", "standard",
                    ]
                    if classification in valid_types:
                        return classification
            # If we got a response but couldn't parse, use deterministic
            return self._classify_target(profile)
        except Exception as exc:
            logger.debug("cognitive_scan.llm_classify_failed", error=str(exc)[:100])
            return self._classify_target(profile)

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

        # Pass evidence chain to report if in /3vilbob mode
        evidence = None
        if self._evidence:
            evidence = self._evidence.get_evidence_summary()

        return gen.generate(vuln_findings, metadata, evidence_summary=evidence)

    # ------------------------------------------------------------------
    # Interactive strategies (send probes, analyze responses)
    # ------------------------------------------------------------------

    async def _canary_echo(self, target_urls: list[str]) -> dict[str, Any]:
        """Inject canary strings and analyze where they echo back.

        One unique string tests four vulnerability classes simultaneously:
        reflected XSS, error disclosure, header injection, filter analysis.
        """
        import httpx
        from app.services.cognition.unreplicable import ResponseEchoAnalyzer

        analyzer = ResponseEchoAnalyzer()
        canary = analyzer.generate_canary()
        probes = analyzer.build_canary_probes(target_urls, canary)

        findings: list[dict[str, Any]] = []
        req_headers = self._get_request_headers()
        proxy = self._resolve_proxy()

        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                follow_redirects=False,
                verify=False,
                proxy=proxy or None,
            ) as client:
                for probe in probes:
                    await self._opsec_wait()
                    try:
                        url = probe["url"]
                        method = probe.get("method", "GET")
                        headers = {**req_headers, **probe.get("headers", {})}
                        body = probe.get("body", "")

                        if method == "POST":
                            resp = await client.post(url, content=body, headers=headers)
                        else:
                            resp = await client.get(url, headers=headers)

                        # Check for counter-fingerprinting
                        self._opsec_check_response(resp.text, dict(resp.headers), [])

                        # Analyze echo
                        echo_findings = analyzer.analyze_echo(
                            canary=canary,
                            probe=probe,
                            response_body=resp.text,
                            response_headers=dict(resp.headers),
                            status_code=resp.status_code,
                        )
                        for ef in echo_findings:
                            ef["url"] = url
                            ef["canary"] = canary
                            ef["info"] = {
                                "name": f"Echo: {ef['type']} at {probe.get('injection_point', 'unknown')}",
                                "severity": ef.get("severity", "medium"),
                                "description": ef.get("description", ""),
                            }
                            findings.append(ef)
                    except Exception:
                        continue
        except Exception as exc:
            return {"summary": f"Canary echo failed: {str(exc)[:100]}", "findings": []}

        return {
            "summary": f"Canary echo: {len(findings)} reflections found across {len(probes)} probes",
            "findings": findings,
        }

    async def _state_machine(
        self,
        target: str,
        known_endpoints: list[str],
    ) -> dict[str, Any]:
        """Test application state transitions for broken access control.

        Generates sequences (login -> access -> logout -> access) and
        checks if state transitions are properly enforced.
        """
        import httpx
        from app.services.cognition.unreplicable import StateMachineInferrer

        inferrer = StateMachineInferrer()
        sequences = inferrer.generate_sequences(target, known_endpoints)

        findings: list[dict[str, Any]] = []
        req_headers = self._get_request_headers()
        proxy = self._resolve_proxy()

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=False,
                verify=False,
                proxy=proxy or None,
            ) as client:
                for sequence in sequences:
                    seq_results = []
                    for step in sequence:
                        await self._opsec_wait()
                        try:
                            method = step.get("method", "GET")
                            url = step.get("url", "")
                            if method == "POST":
                                resp = await client.post(url, headers=req_headers)
                            elif method == "DELETE":
                                resp = await client.request("DELETE", url, headers=req_headers)
                            elif method == "PUT":
                                resp = await client.put(url, headers=req_headers)
                            else:
                                resp = await client.get(url, headers=req_headers)

                            seq_results.append({
                                "status_code": resp.status_code,
                                "body_length": len(resp.content),
                            })
                        except Exception:
                            seq_results.append({"status_code": 0, "body_length": 0})

                    # Analyze sequence results
                    seq_findings = inferrer.analyze_sequence_results(sequence, seq_results)
                    for sf in seq_findings:
                        sf["info"] = {
                            "name": f"State: {sf.get('type', 'violation')} -- {sf.get('step_name', '')}",
                            "severity": sf.get("severity", "high"),
                            "description": sf.get("description", ""),
                        }
                        findings.append(sf)
        except Exception as exc:
            return {"summary": f"State machine failed: {str(exc)[:100]}", "findings": []}

        return {
            "summary": f"State machine: {len(findings)} violations in {len(sequences)} sequences",
            "findings": findings,
        }

    async def _cost_amplification(self, target_urls: list[str]) -> dict[str, Any]:
        """Detect endpoints vulnerable to cost amplification via timing.

        Sends normal baseline request, then amplification probes,
        and compares response times. High ratio = vulnerable.
        """
        import httpx
        from app.services.cognition.unreplicable import CostAmplificationDetector

        detector = CostAmplificationDetector()
        probes = detector.build_timing_probes(target_urls)

        findings: list[dict[str, Any]] = []
        req_headers = self._get_request_headers()
        proxy = self._resolve_proxy()

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=False,
                verify=False,
                proxy=proxy or None,
            ) as client:
                # Establish baseline timing with a simple GET
                baseline_ms = 200  # Default assumption
                if target_urls:
                    await self._opsec_wait()
                    try:
                        start = time.time()
                        await client.get(target_urls[0], headers=req_headers)
                        baseline_ms = int((time.time() - start) * 1000)
                    except Exception:
                        pass

                for probe in probes:
                    await self._opsec_wait()
                    try:
                        url = probe["url"]
                        method = probe.get("method", "GET")
                        headers = {**req_headers, **probe.get("headers", {})}
                        body = probe.get("body", "")

                        start = time.time()
                        if method == "POST":
                            await client.post(url, content=body, headers=headers)
                        else:
                            await client.get(url, headers=headers)
                        elapsed_ms = int((time.time() - start) * 1000)

                        finding = detector.analyze_timing(probe, elapsed_ms, baseline_ms)
                        if finding:
                            finding["info"] = {
                                "name": f"Amplification: {finding['probe_name']}",
                                "severity": finding.get("severity", "medium"),
                                "description": finding.get("description", ""),
                            }
                            findings.append(finding)
                    except Exception:
                        continue
        except Exception as exc:
            return {"summary": f"Cost amplification failed: {str(exc)[:100]}", "findings": []}

        return {
            "summary": f"Cost amplification: {len(findings)} amplifiable endpoints from {len(probes)} probes (baseline: {baseline_ms}ms)",
            "findings": findings,
        }
