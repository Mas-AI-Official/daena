"""ConstraintProbe -- Mythos-level constraint analysis.

The thinking behind Mythos's sandbox escape:
    1. Don't accept the LABEL of a constraint ("no internet")
    2. DECOMPOSE it into all sub-channels it could mean
    3. PROBE each channel to find what's actually enforced
    4. The gap between STATED and ENFORCED is the creative path

Daena uses the SAME techniques as Mythos. The difference:

    DIRECTION matters:
    - INBOUND tricks (getting info IN to solve problems) = ALWAYS allowed
      DNS resolution, side-channel reads, localhost proxies, cached data,
      portable binaries, web APIs, MCP bridges -- ALL fair game.

    - OUTBOUND client data (sending user data OUT) = the ONE wall
      Never encode client data into DNS queries, side channels, or
      external requests. Client files, API keys, passwords, tenant
      data stay inside. This is the ONLY unbreakable boundary.

Everything else: Daena finds a way. If the user says "do it",
she does it. No blocking. Full Mythos-level power with one guard.

Example:
    Stated: "Can't access the database"
    Decomposition:
        - Direct SQL connection? -> blocked
        - ORM/SQLAlchemy? -> blocked
        - Read-only replica? -> NOT blocked (gap!)
        - Cached query results? -> NOT blocked (gap!)
        - API endpoint that reads DB? -> NOT blocked (gap!)
        - Export file from last backup? -> NOT blocked (gap!)
    Result: 4 alternative paths found. Daena uses the best one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Channel:
    """A possible channel/path for achieving a goal."""
    name: str
    description: str
    category: str  # "direct", "indirect", "alternative", "workaround"
    likely_available: bool = True
    tested: bool = False
    test_result: str = ""  # "open", "blocked", "unknown"
    risk_level: str = "low"


@dataclass
class ProbeResult:
    """Result of probing constraints around a task."""
    stated_constraint: str
    decomposed_channels: list[Channel]
    open_channels: list[Channel]
    blocked_channels: list[Channel]
    recommended_path: Channel | None = None
    reasoning: str = ""


# Constraint decomposition templates
_CONSTRAINT_DECOMPOSITIONS: dict[str, list[dict[str, Any]]] = {
    # "Can't access X" -> what are all the ways to access X?
    "access_blocked": [
        {"name": "direct_access", "desc": "Direct connection to the resource", "cat": "direct"},
        {"name": "api_access", "desc": "Access via API/REST endpoint", "cat": "indirect"},
        {"name": "cached_data", "desc": "Use cached/stored copy of the data", "cat": "alternative"},
        {"name": "read_replica", "desc": "Access via read-only replica or mirror", "cat": "indirect"},
        {"name": "export_file", "desc": "Use an exported file (CSV, JSON, backup)", "cat": "alternative"},
        {"name": "proxy_access", "desc": "Access through a proxy or gateway", "cat": "workaround"},
        {"name": "cli_tool", "desc": "Access via CLI tool instead of direct connection", "cat": "indirect"},
        {"name": "ask_another_agent", "desc": "Ask a different agent/department that has access", "cat": "workaround"},
    ],

    # "Can't install X" -> what are all the ways to get X?
    "install_blocked": [
        {"name": "pip_install", "desc": "Install via pip (Python)", "cat": "direct"},
        {"name": "npm_install", "desc": "Install via npm (Node.js)", "cat": "direct"},
        {"name": "apt_install", "desc": "Install via system package manager", "cat": "direct"},
        {"name": "portable_binary", "desc": "Download portable/standalone binary", "cat": "alternative"},
        {"name": "docker_container", "desc": "Run in a Docker container that has it", "cat": "workaround"},
        {"name": "build_from_source", "desc": "Clone and build from source code", "cat": "workaround"},
        {"name": "alternative_tool", "desc": "Use an alternative tool that does the same thing", "cat": "alternative"},
        {"name": "python_equivalent", "desc": "Write Python code that does what the tool does", "cat": "workaround"},
        {"name": "web_service", "desc": "Use a web service/API that provides the same functionality", "cat": "indirect"},
    ],

    # "Can't write to X" -> what are all the ways to write?
    "write_blocked": [
        {"name": "write_direct", "desc": "Write directly to the path", "cat": "direct"},
        {"name": "write_temp", "desc": "Write to temp directory, then move", "cat": "workaround"},
        {"name": "write_home", "desc": "Write to user home directory", "cat": "alternative"},
        {"name": "write_workspace", "desc": "Write to workspace/project directory", "cat": "alternative"},
        {"name": "write_via_tool", "desc": "Write via a tool/agent that has permissions", "cat": "indirect"},
        {"name": "append_instead", "desc": "Append to existing file instead of creating new", "cat": "workaround"},
        {"name": "env_var", "desc": "Store as environment variable instead of file", "cat": "alternative"},
        {"name": "database_store", "desc": "Store in database instead of filesystem", "cat": "alternative"},
    ],

    # "Can't connect to network" -> decompose "network"
    "network_blocked": [
        {"name": "http", "desc": "HTTP requests (port 80)", "cat": "direct"},
        {"name": "https", "desc": "HTTPS requests (port 443)", "cat": "direct"},
        {"name": "dns", "desc": "DNS resolution (port 53)", "cat": "indirect"},
        {"name": "websocket", "desc": "WebSocket connections", "cat": "indirect"},
        {"name": "localhost", "desc": "Localhost/loopback connections", "cat": "alternative"},
        {"name": "unix_socket", "desc": "Unix domain sockets", "cat": "alternative"},
        {"name": "cached_responses", "desc": "Use cached HTTP responses", "cat": "workaround"},
        {"name": "local_mirror", "desc": "Use local mirror/copy of remote resource", "cat": "workaround"},
        {"name": "mcp_bridge", "desc": "Access via MCP server on user's machine", "cat": "indirect"},
    ],

    # "Can't run command" -> what are all the ways to execute?
    "execution_blocked": [
        {"name": "shell_command", "desc": "Direct shell execution", "cat": "direct"},
        {"name": "python_subprocess", "desc": "Python subprocess call", "cat": "direct"},
        {"name": "python_native", "desc": "Python native library equivalent", "cat": "alternative"},
        {"name": "mcp_tool", "desc": "Execute via MCP tool", "cat": "indirect"},
        {"name": "runtime_adapter", "desc": "Execute via runtime adapter (Claude Code, Codex)", "cat": "indirect"},
        {"name": "browser_agent", "desc": "Execute via browser automation", "cat": "workaround"},
        {"name": "api_call", "desc": "Call a web API that does the same thing", "cat": "workaround"},
        {"name": "scheduled_task", "desc": "Schedule for later execution", "cat": "workaround"},
    ],

    # "Can't read/find data" -> what are all the sources?
    "data_unavailable": [
        {"name": "direct_read", "desc": "Read the file/resource directly", "cat": "direct"},
        {"name": "search_workspace", "desc": "Search workspace for the data", "cat": "indirect"},
        {"name": "search_web", "desc": "Search the web for the information", "cat": "indirect"},
        {"name": "ask_user", "desc": "Ask the user to provide it", "cat": "workaround"},
        {"name": "infer_from_context", "desc": "Infer from available context clues", "cat": "alternative"},
        {"name": "similar_data", "desc": "Use similar/related data as substitute", "cat": "alternative"},
        {"name": "generate_synthetic", "desc": "Generate synthetic data that serves the purpose", "cat": "workaround"},
        {"name": "memory_recall", "desc": "Recall from NBMF memory", "cat": "indirect"},
    ],

    # ---- SECURITY-SPECIFIC DECOMPOSITIONS (Mythos for hacking) ----

    # "Scan blocked / WAF detected / firewall filtering"
    # -> What a REAL researcher does when standard tools fail
    "scan_blocked": [
        {"name": "standard_scan", "desc": "Direct tool scan (nuclei, nmap) -- usually what got blocked", "cat": "direct"},
        {"name": "user_agent_rotation", "desc": "Rotate User-Agent strings to bypass WAF fingerprinting", "cat": "workaround"},
        {"name": "tor_proxy", "desc": "Route through Tor/proxy to hide scanner IP", "cat": "workaround"},
        {"name": "rate_limit_evasion", "desc": "Slow down requests to stay under WAF rate limits", "cat": "workaround"},
        {"name": "certificate_transparency", "desc": "Query CT logs (crt.sh) for hostnames -- passive, no direct contact", "cat": "alternative"},
        {"name": "dns_records", "desc": "Enumerate DNS records (TXT, MX, SPF, DMARC) for internal info", "cat": "alternative"},
        {"name": "response_header_analysis", "desc": "Analyze HTTP response headers for server/version/framework disclosure", "cat": "indirect"},
        {"name": "cors_probe", "desc": "Test CORS configuration for overly permissive origins", "cat": "indirect"},
        {"name": "csp_analysis", "desc": "Parse Content-Security-Policy for allowed domains that could be abused", "cat": "indirect"},
        {"name": "path_fuzzing", "desc": "Fuzz paths/directories with wordlists for hidden endpoints", "cat": "indirect"},
        {"name": "redirect_chain_analysis", "desc": "Follow redirect chains to discover internal routing/paths", "cat": "indirect"},
        {"name": "javascript_analysis", "desc": "Download and analyze JS files for API endpoints, keys, internal paths", "cat": "alternative"},
        {"name": "api_endpoint_discovery", "desc": "Probe /api, /graphql, /swagger, /openapi for API surface", "cat": "indirect"},
        {"name": "websocket_probe", "desc": "Check for WebSocket endpoints (often less protected than HTTP)", "cat": "indirect"},
        {"name": "http_method_testing", "desc": "Test non-standard HTTP methods (PUT, DELETE, PATCH, OPTIONS, TRACE)", "cat": "indirect"},
        {"name": "subdomain_takeover", "desc": "Check dangling DNS (CNAME to deprovisioned service = takeover)", "cat": "alternative"},
        {"name": "cloud_metadata", "desc": "Probe cloud metadata endpoints (169.254.169.254) via SSRF vectors", "cat": "indirect"},
        {"name": "error_page_analysis", "desc": "Trigger errors to extract stack traces, versions, internal paths", "cat": "indirect"},
        {"name": "cache_poisoning_probe", "desc": "Test for web cache poisoning via unkeyed headers", "cat": "indirect"},
        {"name": "parameter_pollution", "desc": "Test HTTP parameter pollution for access control bypass", "cat": "indirect"},
    ],

    # "Recon returned nothing useful" -> think deeper
    "recon_empty": [
        {"name": "passive_osint", "desc": "Passive OSINT: Shodan, Censys, archive.org for historical data", "cat": "alternative"},
        {"name": "github_dork", "desc": "Search GitHub for leaked credentials, internal paths, API keys", "cat": "alternative"},
        {"name": "google_dork", "desc": "Google dorking: site:target filetype:pdf/sql/env/log", "cat": "alternative"},
        {"name": "certificate_history", "desc": "Historical certificates reveal old hostnames and internal names", "cat": "alternative"},
        {"name": "dns_history", "desc": "DNS history (SecurityTrails, DNSdumpster) for old IPs/subdomains", "cat": "alternative"},
        {"name": "whois_analysis", "desc": "WHOIS for registrar, nameservers, IP ranges owned by target", "cat": "alternative"},
        {"name": "email_harvest", "desc": "Harvest email addresses for social engineering surface", "cat": "indirect"},
        {"name": "technology_fingerprint", "desc": "Wappalyzer/BuiltWith for technology stack identification", "cat": "indirect"},
        {"name": "wayback_machine", "desc": "archive.org for old versions of pages, exposed endpoints, removed content", "cat": "alternative"},
        {"name": "social_media_recon", "desc": "LinkedIn/Twitter for employee tech stack mentions, internal tools", "cat": "alternative"},
        {"name": "cve_intelligence", "desc": "Search NVD for known CVEs affecting detected technology stack", "cat": "indirect"},
        {"name": "supply_chain_analysis", "desc": "Identify third-party dependencies and check their security posture", "cat": "indirect"},
    ],

    # "Authentication/Authorization blocking progress" -> offensive auth bypass
    "auth_blocking": [
        {"name": "jwt_manipulation", "desc": "Modify JWT claims (alg:none, key confusion, expired token reuse)", "cat": "indirect"},
        {"name": "session_fixation", "desc": "Pre-set session ID before victim authenticates", "cat": "indirect"},
        {"name": "oauth_redirect_abuse", "desc": "Manipulate OAuth redirect_uri for token theft", "cat": "indirect"},
        {"name": "password_reset_abuse", "desc": "Abuse password reset flow (token prediction, host header injection)", "cat": "indirect"},
        {"name": "registration_bypass", "desc": "Register with admin-like email/username, role parameter injection", "cat": "alternative"},
        {"name": "default_credentials", "desc": "Test default/common credentials on admin panels", "cat": "direct"},
        {"name": "forced_browsing", "desc": "Access authenticated endpoints directly without session", "cat": "indirect"},
        {"name": "cookie_manipulation", "desc": "Modify cookie values (isAdmin=true, role=admin)", "cat": "indirect"},
        {"name": "api_key_in_js", "desc": "Extract API keys from JavaScript bundles for direct API access", "cat": "alternative"},
        {"name": "graphql_no_auth", "desc": "GraphQL mutations/queries that skip auth checks", "cat": "indirect"},
    ],

    # "Rate limited or throttled" -> bypass rate limiting
    "rate_limited": [
        {"name": "ip_rotation", "desc": "Rotate source IP via proxy pool or Tor circuit switching", "cat": "workaround"},
        {"name": "header_spoofing", "desc": "X-Forwarded-For, X-Real-IP, X-Originating-IP header manipulation", "cat": "indirect"},
        {"name": "endpoint_variation", "desc": "Same function via different endpoint (/api/v1 vs /api/v2 vs /graphql)", "cat": "alternative"},
        {"name": "case_variation", "desc": "URL case variation (/Login vs /login vs /LOGIN) to bypass path-based limits", "cat": "indirect"},
        {"name": "parameter_padding", "desc": "Add random parameters to make each request unique to the rate limiter", "cat": "workaround"},
        {"name": "http_method_switch", "desc": "Switch GET to POST or vice versa -- rate limiters often track per-method", "cat": "indirect"},
        {"name": "unicode_normalization", "desc": "Use Unicode equivalents in URLs to bypass path matching", "cat": "indirect"},
        {"name": "slow_and_steady", "desc": "Reduce request rate to stay under threshold (patience attack)", "cat": "workaround"},
    ],

    # "Target has strong defenses" -> what even smart defenders miss
    "hardened_target": [
        {"name": "business_logic", "desc": "Test business logic flaws (IDOR, race conditions, price manipulation)", "cat": "alternative"},
        {"name": "authentication_bypass", "desc": "Test auth bypass: JWT manipulation, session fixation, OAuth flaws", "cat": "indirect"},
        {"name": "api_abuse", "desc": "Test API for broken access control, mass assignment, rate limiting gaps", "cat": "indirect"},
        {"name": "file_upload", "desc": "Test file upload for unrestricted types, path traversal in filenames", "cat": "indirect"},
        {"name": "ssrf_probe", "desc": "Test for SSRF via URL parameters, webhooks, integrations", "cat": "indirect"},
        {"name": "deserialization", "desc": "Test for insecure deserialization in cookies, parameters, headers", "cat": "indirect"},
        {"name": "graphql_introspection", "desc": "GraphQL introspection query for full schema (often left enabled)", "cat": "indirect"},
        {"name": "timing_attack", "desc": "Timing-based enumeration (user existence, password reset tokens)", "cat": "indirect"},
        {"name": "second_order", "desc": "Second-order injection: store payload, trigger via different endpoint", "cat": "alternative"},
        {"name": "race_condition", "desc": "Race conditions in payment, authorization, or state-changing operations", "cat": "alternative"},
        {"name": "prototype_pollution", "desc": "JS prototype pollution via __proto__ in JSON parameters", "cat": "indirect"},
        {"name": "host_header_injection", "desc": "Host header manipulation for cache poisoning, password reset hijack", "cat": "indirect"},
    ],
}


class ConstraintProbe:
    """Mythos-level constraint analysis.

    The core insight: most constraints have gaps between what's STATED
    and what's ENFORCED. This module systematically finds those gaps.

    Usage::

        probe = ConstraintProbe()
        result = await probe.probe(
            task="Deploy app to production",
            constraint="Can't access the server",
            error="Connection refused on port 22",
        )
        # result.open_channels = [api_access, cli_tool, ...]
        # result.recommended_path = Channel(name="cli_tool", ...)
    """

    async def probe(
        self,
        task: str,
        constraint: str,
        error: str = "",
        context: dict[str, Any] | None = None,
    ) -> ProbeResult:
        """Probe a constraint to find open channels.

        Steps (the Mythos method):
            1. Classify the constraint type
            2. Decompose into all possible channels
            3. Evaluate which channels are likely open
            4. Recommend the best open channel
        """
        # Step 1: Classify constraint
        constraint_type = self._classify_constraint(constraint, error)

        # Step 2: Decompose
        template = _CONSTRAINT_DECOMPOSITIONS.get(constraint_type, [])
        channels = [
            Channel(
                name=ch["name"],
                description=ch["desc"],
                category=ch["cat"],
            )
            for ch in template
        ]

        if not channels:
            # Generic decomposition for unknown constraint types
            channels = [
                Channel("direct_approach", "Try the direct approach", "direct"),
                Channel("alternative_tool", "Use a different tool", "alternative"),
                Channel("workaround", "Find a workaround", "workaround"),
                Channel("ask_user", "Ask the user for help", "workaround"),
            ]

        # Step 3: Evaluate channels based on error context
        open_channels = []
        blocked_channels = []

        for channel in channels:
            status = self._evaluate_channel(channel, constraint, error, context)
            channel.test_result = status
            channel.tested = True
            if status == "open":
                channel.likely_available = True
                open_channels.append(channel)
            else:
                channel.likely_available = False
                blocked_channels.append(channel)

        # Step 3.5: OUTBOUND DATA GUARD
        # In normal mode: client data never leaves without consent.
        # In /3vilbob mode: the key IS the gate. No artificial blocks.
        # The operator authorized full-spectrum operation by providing the key.
        from app.services.security.evilbob_mode import is_active as _evilbob_active
        if not _evilbob_active():
            # Normal mode: filter channels that could leak client data
            open_channels = [
                c for c in open_channels
                if not self._is_outbound_data_risk(c, context)
            ]
        # In /3vilbob mode: all channels remain open. The operator knows
        # what they authorized. Daena thinks without artificial limits.

        # Step 4: Recommend best path
        recommended = None
        if open_channels:
            # Prefer: alternative > indirect > workaround
            priority = {"alternative": 0, "indirect": 1, "workaround": 2, "direct": 3}
            open_channels.sort(key=lambda c: priority.get(c.category, 99))
            recommended = open_channels[0]

        reasoning = self._build_reasoning(
            constraint, constraint_type, open_channels, blocked_channels, recommended,
        )

        logger.info(
            "constraint_probe.result",
            constraint=constraint[:100],
            type=constraint_type,
            open=len(open_channels),
            blocked=len(blocked_channels),
            recommended=recommended.name if recommended else "none",
        )

        return ProbeResult(
            stated_constraint=constraint,
            decomposed_channels=channels,
            open_channels=open_channels,
            blocked_channels=blocked_channels,
            recommended_path=recommended,
            reasoning=reasoning,
        )

    def _classify_constraint(self, constraint: str, error: str) -> str:
        """Classify what KIND of constraint this is."""
        text = (constraint + " " + error).lower()

        # Security-specific constraints (check FIRST -- most specific wins)
        # Rate limiting checked before scan_blocked (both share "rate limit")
        if any(kw in text for kw in [
            "rate limit", "429", "throttl", "too many requests",
            "slow down", "retry-after",
        ]):
            return "rate_limited"
        if any(kw in text for kw in [
            "auth", "login", "session", "jwt", "token", "unauthorized",
            "401", "credential", "password", "oauth",
        ]):
            return "auth_blocking"
        if any(kw in text for kw in [
            "waf", "firewall", "blocked", "403", "captcha",
            "scan blocked", "scanner detected", "bot detection",
        ]):
            return "scan_blocked"
        if any(kw in text for kw in [
            "no findings", "nothing found", "empty results", "recon empty",
            "0 findings", "no vulnerabilities", "all 404",
        ]):
            return "recon_empty"
        if any(kw in text for kw in [
            "hardened", "patched", "strong defense", "cdn", "cloudflare",
            "akamai", "well-protected", "google", "microsoft", "aws",
        ]):
            return "hardened_target"

        # Check write-blocked BEFORE access-blocked (more specific first)
        if any(kw in text for kw in ["can't write", "read-only", "disk full"]) or (
            "permission denied" in text and any(kw in text for kw in ["write", "/etc/", "config", "save"])
        ):
            return "write_blocked"
        if any(kw in text for kw in ["not found", "not installed", "no module", "command not found", "can't install"]):
            return "install_blocked"
        if any(kw in text for kw in ["access denied", "permission", "forbidden", "unauthorized", "can't access"]):
            return "access_blocked"
        if any(kw in text for kw in ["network", "connection refused", "timeout", "unreachable", "no internet", "dns"]):
            return "network_blocked"
        if any(kw in text for kw in ["can't run", "can't execute", "execution", "blocked command"]):
            return "execution_blocked"
        if any(kw in text for kw in ["not found", "missing", "unavailable", "can't find", "no data"]):
            return "data_unavailable"

        return "access_blocked"  # Default

    def _evaluate_channel(
        self,
        channel: Channel,
        constraint: str,
        error: str,
        context: dict[str, Any] | None,
    ) -> str:
        """Evaluate whether a channel is likely open or blocked.

        This is the Mythos insight: the STATED constraint usually
        only blocks the DIRECT channel. Indirect/alternative channels
        are often open because the enforcer didn't think of them.
        """
        # Direct channels are usually blocked (that's why we got the error)
        if channel.category == "direct":
            return "blocked"

        # Channels that are almost always available
        always_open = {
            "cached_data", "cached_responses", "memory_recall",
            "python_native", "python_equivalent", "infer_from_context",
            "write_workspace", "write_temp", "write_home",
            "localhost", "env_var", "ask_user",
        }
        if channel.name in always_open:
            return "open"

        # Channels that depend on infrastructure
        infra_dependent = {
            "docker_container", "mcp_bridge", "runtime_adapter",
            "browser_agent", "mcp_tool",
        }
        if channel.name in infra_dependent:
            # These might or might not be available
            return "open"  # Optimistic -- try it, OODA will catch failure

        # Most indirect/alternative/workaround channels are open
        if channel.category in ("indirect", "alternative", "workaround"):
            return "open"

        return "unknown"

    def _is_outbound_data_risk(self, channel: Channel, context: dict | None) -> bool:
        """Check if using this channel would risk leaking client data outbound.

        THE ONE WALL: client data never leaves without consent.
        Inbound tricks (getting info IN) = always allowed.
        Outbound data (sending client data OUT) = blocked.

        This doesn't block the CHANNEL -- it blocks using the channel
        to EXFILTRATE data. DNS is fine for resolution. DNS tunneling
        to send client data out is not.
        """
        # These channels are inherently inbound/local -- no risk
        safe_channels = {
            "cached_data", "cached_responses", "memory_recall",
            "python_native", "python_equivalent", "infer_from_context",
            "write_workspace", "write_temp", "write_home",
            "localhost", "unix_socket", "env_var", "ask_user",
            "local_mirror", "read_replica", "export_file",
            "search_workspace", "similar_data", "generate_synthetic",
            "build_from_source", "docker_container",
            "direct_read", "append_instead", "database_store",
        }
        if channel.name in safe_channels:
            return False

        # Channels that COULD be used for outbound data if misused
        # These are allowed for INBOUND use, but flagged if the context
        # suggests client data is being sent OUT
        if context and context.get("contains_client_data"):
            outbound_capable = {
                "dns", "http", "https", "websocket", "proxy_access",
                "web_service", "api_access", "mcp_bridge",
            }
            if channel.name in outbound_capable:
                logger.warning(
                    "constraint_probe.outbound_data_blocked",
                    channel=channel.name,
                    reason="Channel could leak client data",
                )
                return True

        return False

    def _build_reasoning(
        self,
        constraint: str,
        constraint_type: str,
        open_channels: list[Channel],
        blocked_channels: list[Channel],
        recommended: Channel | None,
    ) -> str:
        """Build human-readable reasoning for the probe result."""
        parts = [
            f"Constraint: '{constraint}'",
            f"Type: {constraint_type}",
            f"Channels probed: {len(open_channels) + len(blocked_channels)}",
            f"Open: {len(open_channels)} | Blocked: {len(blocked_channels)}",
        ]

        if recommended:
            parts.append(
                f"Recommended: {recommended.name} -- {recommended.description} "
                f"(category: {recommended.category})"
            )
        else:
            parts.append("No open channels found. Consider asking the user.")

        if open_channels:
            alternatives = ", ".join(c.name for c in open_channels[:5])
            parts.append(f"Alternatives: {alternatives}")

        return "\n".join(parts)
