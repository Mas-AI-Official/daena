"""NetworkIntelligence -- Deep protocol-level knowledge for penetration testing.

BACKGROUND PATH ONLY -- never import in hot path

This module encodes HOW the internet works at every layer, and how
each layer can be leveraged for authorized security assessments:

Layer 1: Physical/Data Link  -> MAC spoofing, VLAN hopping
Layer 2: Network (IP)        -> IP spoofing, fragmentation, routing
Layer 3: Transport (TCP/UDP) -> Port scanning, SYN flood, UDP amplification
Layer 4: Application (HTTP)  -> Header manipulation, request smuggling
Layer 5: DNS                 -> Zone transfers, cache poisoning, rebinding
Layer 6: TLS/SSL             -> Downgrade, cert pinning bypass, BEAST/POODLE
Layer 7: Dark Web / Tor      -> .onion services, exit node analysis, hidden services
Layer 8: CDN/WAF             -> Bypass techniques, origin IP discovery

This is not a vulnerability scanner. This is KNOWLEDGE about how
every protocol works and where the weaknesses live. It informs
the ORIENT phase of the OODA loop so strategies are protocol-aware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ProtocolInsight:
    """Knowledge about a protocol and its security implications."""
    protocol: str
    layer: str  # OSI layer name
    description: str
    attack_surfaces: list[str]
    common_misconfigs: list[str]
    recon_techniques: list[str]
    tools: list[str]


@dataclass
class NetworkFingerprint:
    """What we can determine about the target's network from observation."""
    cdn_provider: str = ""
    hosting_provider: str = ""
    ip_ranges: list[str] = field(default_factory=list)
    open_ports: list[int] = field(default_factory=list)
    dns_config: dict[str, Any] = field(default_factory=dict)
    tls_version: str = ""
    http_version: str = ""
    server_os: str = ""
    network_topology: str = ""  # flat, segmented, microservices, serverless
    egress_paths: list[str] = field(default_factory=list)


@dataclass
class DarkWebIntel:
    """Intelligence gathered from dark web / deep web sources."""
    leaked_credentials: int = 0
    paste_mentions: int = 0
    breach_databases: list[str] = field(default_factory=list)
    onion_services: list[str] = field(default_factory=list)
    threat_actor_mentions: list[str] = field(default_factory=list)
    data_for_sale: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ProtocolExploitPath:
    """An exploitation path through a specific protocol weakness."""
    protocol: str
    weakness: str
    exploit_steps: list[str]
    prerequisites: list[str]
    detection_risk: str  # low, medium, high
    impact: str
    confidence: float = 0.5


# ---------------------------------------------------------------------------
# Protocol Knowledge Base
# ---------------------------------------------------------------------------

class ProtocolKnowledgeBase:
    """Encyclopedic knowledge of internet protocols and their weaknesses.

    This is what a senior penetration tester carries in their head.
    Now Daena carries it too.
    """

    _PROTOCOLS: list[ProtocolInsight] = [
        # --- Layer 3: Network ---
        ProtocolInsight(
            protocol="IPv4",
            layer="network",
            description="Internet Protocol v4. 32-bit addresses. Fragmentation support.",
            attack_surfaces=[
                "IP spoofing (source address forgery)",
                "Fragmentation attacks (overlapping fragments bypass IDS)",
                "TTL-based network mapping (traceroute)",
                "Source routing (deprecated but some stacks accept)",
            ],
            common_misconfigs=[
                "No egress filtering (allows spoofed packets out)",
                "IP forwarding enabled on non-router hosts",
                "Broadcast amplification enabled (Smurf attacks)",
            ],
            recon_techniques=[
                "traceroute: map network hops to target",
                "TTL analysis: determine OS from initial TTL value",
                "IP ID sequence analysis: detect shared hosting",
                "Fragmentation probes: test firewall fragment handling",
            ],
            tools=["nmap", "hping3", "scapy", "traceroute"],
        ),
        ProtocolInsight(
            protocol="IPv6",
            layer="network",
            description="Internet Protocol v6. 128-bit addresses. Often misconfigured.",
            attack_surfaces=[
                "IPv6 often not firewalled (admin forgot to add IPv6 rules)",
                "IPv6 tunnel detection (6to4, Teredo, ISATAP)",
                "Router advertisement spoofing",
                "IPv6 extension header abuse",
            ],
            common_misconfigs=[
                "IPv6 enabled but no firewall rules (common!)",
                "Dual-stack with IPv6 bypassing IPv4 WAF",
                "IPv6 not monitored by IDS/IPS",
                "Link-local addresses exposed to internet",
            ],
            recon_techniques=[
                "AAAA record lookup: check if IPv6 bypasses CDN",
                "IPv6 scanning: often less protected than IPv4",
                "Tunnel detection: find 6to4/Teredo endpoints",
            ],
            tools=["nmap -6", "thc-ipv6", "alive6"],
        ),

        # --- Layer 4: Transport ---
        ProtocolInsight(
            protocol="TCP",
            layer="transport",
            description="Transmission Control Protocol. Connection-oriented. 3-way handshake.",
            attack_surfaces=[
                "SYN scanning (half-open, stealthy)",
                "TCP sequence prediction (session hijacking)",
                "RST injection (connection termination)",
                "Window size manipulation",
                "Urgent pointer abuse",
            ],
            common_misconfigs=[
                "TCP timestamps enabled (uptime disclosure)",
                "Predictable ISN (initial sequence numbers)",
                "TIME_WAIT state exploitation",
                "Keep-alive revealing internal architecture",
            ],
            recon_techniques=[
                "SYN scan: determine open ports without full connection",
                "FIN/XMAS/NULL scan: bypass stateless firewalls",
                "TCP window scan: distinguish filtered from closed",
                "TCP timestamp analysis: calculate server uptime",
                "Banner grabbing: read service identification strings",
            ],
            tools=["nmap", "masscan", "hping3", "netcat"],
        ),
        ProtocolInsight(
            protocol="UDP",
            layer="transport",
            description="User Datagram Protocol. Connectionless. No handshake.",
            attack_surfaces=[
                "UDP amplification (DNS, NTP, SSDP, memcached)",
                "UDP-based service enumeration",
                "SNMP community string guessing",
                "DNS over UDP manipulation",
            ],
            common_misconfigs=[
                "SNMP with default community string 'public'",
                "Open DNS resolver (amplification source)",
                "NTP monlist enabled (100x amplification)",
                "SSDP exposed to internet",
            ],
            recon_techniques=[
                "UDP port scan: slower but reveals hidden services",
                "SNMP walk: enumerate entire device configuration",
                "NTP query: server time, version, peers",
                "DNS version query: BIND version disclosure",
            ],
            tools=["nmap -sU", "snmpwalk", "ntpq", "dig"],
        ),

        # --- Layer 7: Application ---
        ProtocolInsight(
            protocol="HTTP/1.1",
            layer="application",
            description="Hypertext Transfer Protocol. Text-based. Keep-alive connections.",
            attack_surfaces=[
                "Request smuggling (CL.TE, TE.CL, TE.TE desync)",
                "Header injection (CRLF injection)",
                "Verb tampering (PUT, DELETE, TRACE enabled)",
                "Host header attacks (password reset poisoning)",
                "Cache poisoning (web cache deception)",
                "Range header DoS (Apache Killer)",
            ],
            common_misconfigs=[
                "TRACE method enabled (Cross-Site Tracing)",
                "Missing CORS headers or wildcard CORS",
                "Missing Content-Security-Policy",
                "X-Forwarded-For trusted without validation",
                "Host header not validated (virtual host routing)",
            ],
            recon_techniques=[
                "OPTIONS request: discover allowed methods",
                "Host header fuzzing: find virtual hosts",
                "Transfer-Encoding probing: test for smuggling",
                "Cache key analysis: identify cacheable responses",
            ],
            tools=["curl", "burp", "httpx", "smuggler"],
        ),
        ProtocolInsight(
            protocol="HTTP/2",
            layer="application",
            description="Binary framing, multiplexed streams, HPACK header compression.",
            attack_surfaces=[
                "H2C smuggling (cleartext HTTP/2 upgrade)",
                "Stream multiplexing abuse (resource exhaustion)",
                "HPACK bombing (header table overflow)",
                "HTTP/2 to HTTP/1.1 translation attacks",
                "Rapid Reset (CVE-2023-44487)",
            ],
            common_misconfigs=[
                "H2C (cleartext HTTP/2) enabled on reverse proxy",
                "HTTP/2 enabled but backend speaks HTTP/1.1 (translation gap)",
                "No stream limit configured",
            ],
            recon_techniques=[
                "ALPN negotiation: detect HTTP/2 support",
                "H2C upgrade probe: test cleartext HTTP/2",
                "Stream flood test: measure resource limits",
            ],
            tools=["h2spec", "nghttp", "curl --http2"],
        ),
        ProtocolInsight(
            protocol="HTTP/3 (QUIC)",
            layer="application",
            description="UDP-based transport. TLS 1.3 built-in. 0-RTT connections.",
            attack_surfaces=[
                "0-RTT replay attacks (cached data reuse)",
                "Connection ID manipulation",
                "UDP-based amplification potential",
                "Migration attack (connection migration to attacker IP)",
            ],
            common_misconfigs=[
                "0-RTT enabled without replay protection",
                "QUIC but HTTP/1.1 fallback path not secured",
                "Connection migration without re-authentication",
            ],
            recon_techniques=[
                "Alt-Svc header: detect QUIC support",
                "UDP port 443 probe: test QUIC availability",
                "0-RTT test: check replay vulnerability",
            ],
            tools=["curl --http3", "quiche", "aioquic"],
        ),

        # --- DNS ---
        ProtocolInsight(
            protocol="DNS",
            layer="application",
            description="Domain Name System. Hierarchical name resolution. UDP/TCP port 53.",
            attack_surfaces=[
                "Zone transfer (AXFR) -- full domain dump if misconfigured",
                "DNS rebinding (bypass same-origin policy)",
                "Cache poisoning (Kaminsky attack variants)",
                "Subdomain takeover (dangling CNAME to deprovisioned service)",
                "DNS tunneling (data exfiltration over DNS queries)",
                "NSEC walking (enumerate DNSSEC-signed zones)",
            ],
            common_misconfigs=[
                "Zone transfer allowed to any IP (AXFR open)",
                "Wildcard DNS (*.domain resolves -- masks subdomain takeover)",
                "CNAME to deprovisioned AWS/Azure/GCP services",
                "No DNSSEC (vulnerable to spoofing)",
                "Recursive resolver exposed to internet",
            ],
            recon_techniques=[
                "Zone transfer attempt: dig AXFR @nameserver domain",
                "Subdomain brute-force: amass, subfinder, gobuster dns",
                "NSEC walking: ldns-walk for DNSSEC zones",
                "Reverse DNS: PTR records reveal hostnames on IPs",
                "DNS history: SecurityTrails, ViewDNS for old records",
                "SPF/DKIM/DMARC check: email security posture",
            ],
            tools=["dig", "nslookup", "amass", "subfinder", "dnsrecon", "fierce"],
        ),

        # --- TLS/SSL ---
        ProtocolInsight(
            protocol="TLS",
            layer="transport_security",
            description="Transport Layer Security. Encryption, authentication, integrity.",
            attack_surfaces=[
                "TLS downgrade (POODLE, DROWN, Logjam)",
                "Certificate validation bypass",
                "Weak cipher suites (RC4, DES, export ciphers)",
                "Session renegotiation attack",
                "Certificate transparency monitoring bypass",
                "SNI-based virtual host discovery",
            ],
            common_misconfigs=[
                "TLS 1.0/1.1 still enabled",
                "Self-signed or expired certificates",
                "Wildcard certs covering too many services",
                "Missing HSTS or HSTS without includeSubdomains",
                "OCSP stapling not enabled",
                "Weak DH parameters (< 2048 bit)",
            ],
            recon_techniques=[
                "SSL Labs scan: comprehensive TLS assessment",
                "Certificate transparency: crt.sh for all issued certs",
                "SNI enumeration: test different hostnames on same IP",
                "JARM fingerprinting: identify server TLS implementation",
                "Cipher suite enumeration: find weak ciphers",
            ],
            tools=["testssl.sh", "sslyze", "openssl", "tlsx"],
        ),

        # --- WebSocket ---
        ProtocolInsight(
            protocol="WebSocket",
            layer="application",
            description="Full-duplex communication over single TCP connection. WS/WSS.",
            attack_surfaces=[
                "Cross-Site WebSocket Hijacking (CSWSH)",
                "WebSocket message injection",
                "Origin header bypass",
                "No per-message authentication",
                "Message type confusion",
            ],
            common_misconfigs=[
                "No Origin header validation",
                "WebSocket endpoint accessible without auth",
                "Sensitive data sent over ws:// (not wss://)",
                "No rate limiting on WebSocket messages",
                "Debug WebSocket endpoints in production",
            ],
            recon_techniques=[
                "WebSocket endpoint discovery: check Upgrade: websocket headers",
                "Origin bypass testing: send from different origins",
                "Message fuzzing: inject malformed messages",
            ],
            tools=["wscat", "websocat", "burp"],
        ),

        # --- GraphQL ---
        ProtocolInsight(
            protocol="GraphQL",
            layer="application",
            description="Query language for APIs. Single endpoint. Introspection support.",
            attack_surfaces=[
                "Introspection query: dump entire schema",
                "Batch query attacks (nested queries for DoS)",
                "Authorization bypass via field-level access",
                "Injection through variables",
                "Alias-based brute force (rate limit bypass)",
            ],
            common_misconfigs=[
                "Introspection enabled in production",
                "No query depth/complexity limits",
                "No field-level authorization",
                "Mutation endpoints without CSRF protection",
                "Error messages expose internal schema details",
            ],
            recon_techniques=[
                "Introspection query: __schema, __type",
                "Field suggestion exploitation: typo-based discovery",
                "Batch query testing: parallel mutation execution",
            ],
            tools=["graphql-voyager", "inql", "graphw00f", "clairvoyance"],
        ),
    ]

    def get_all_protocols(self) -> list[ProtocolInsight]:
        """Return all protocol knowledge."""
        return self._PROTOCOLS

    def get_protocol(self, name: str) -> ProtocolInsight | None:
        """Get knowledge for a specific protocol."""
        name_lower = name.lower()
        for p in self._PROTOCOLS:
            if p.protocol.lower() == name_lower or name_lower in p.protocol.lower():
                return p
        return None

    def get_relevant_protocols(self, technologies: list[str], profile: dict[str, Any]) -> list[ProtocolInsight]:
        """Select protocols relevant to the target based on tech stack."""
        relevant = []
        tech_str = " ".join(t.lower() for t in technologies)
        profile_str = str(profile).lower()

        for p in self._PROTOCOLS:
            score = 0
            # Always include HTTP and DNS
            if p.protocol in ("HTTP/1.1", "DNS", "TLS"):
                score += 2
            # HTTP/2 if modern
            if p.protocol == "HTTP/2" and ("http/2" in profile_str or "h2" in tech_str):
                score += 3
            # HTTP/3 if detected
            if p.protocol == "HTTP/3 (QUIC)" and ("http/3" in profile_str or "quic" in tech_str):
                score += 3
            # GraphQL if detected
            if p.protocol == "GraphQL" and ("graphql" in tech_str or "graphql" in profile_str):
                score += 3
            # WebSocket if detected
            if p.protocol == "WebSocket" and ("websocket" in tech_str or "ws" in profile_str):
                score += 3
            # IPv6 if dual-stack
            if p.protocol == "IPv6" and "ipv6" in profile_str:
                score += 2
            # UDP services if relevant
            if p.protocol == "UDP" and any(s in tech_str for s in ("snmp", "ntp", "dns", "ssdp")):
                score += 2
            # TCP always relevant
            if p.protocol == "TCP":
                score += 1

            if score >= 1:
                relevant.append(p)

        return relevant

    def generate_protocol_attack_surface(
        self,
        technologies: list[str],
        target_profile: dict[str, Any],
    ) -> list[ProtocolExploitPath]:
        """Generate protocol-level exploit paths based on target analysis."""
        paths: list[ProtocolExploitPath] = []
        relevant = self.get_relevant_protocols(technologies, target_profile)

        waf = target_profile.get("waf_detected", "")
        http_version = target_profile.get("http_version", "")

        for proto in relevant:
            for surface in proto.attack_surfaces:
                # Score each attack surface based on target context
                confidence = 0.3  # Base

                # Boost if WAF detected (protocol-level attacks bypass WAFs)
                if waf and proto.layer in ("transport", "network"):
                    confidence += 0.2

                # Boost for HTTP smuggling if reverse proxy detected
                if "smuggling" in surface.lower():
                    if any(t in str(technologies).lower() for t in ("nginx", "apache", "haproxy", "cloudflare")):
                        confidence += 0.2

                # Boost for GraphQL introspection
                if "introspection" in surface.lower() and "graphql" in str(technologies).lower():
                    confidence += 0.3

                # Boost for DNS zone transfer
                if "zone transfer" in surface.lower():
                    confidence += 0.1

                if confidence >= 0.3:
                    paths.append(ProtocolExploitPath(
                        protocol=proto.protocol,
                        weakness=surface,
                        exploit_steps=proto.recon_techniques[:3],
                        prerequisites=[f"Target uses {proto.protocol}"],
                        detection_risk="low" if proto.layer in ("network", "transport") else "medium",
                        impact=f"Protocol-level exploitation via {proto.protocol}",
                        confidence=min(confidence, 0.9),
                    ))

        # Sort by confidence
        paths.sort(key=lambda p: p.confidence, reverse=True)
        return paths[:15]


# ---------------------------------------------------------------------------
# Dark Web Intelligence
# ---------------------------------------------------------------------------

class DarkWebRecon:
    """Knowledge and techniques for dark web / deep web intelligence gathering.

    This is OSINT from the other side of the internet. NOT accessing
    illegal content -- querying PUBLIC breach databases, paste sites,
    and threat intelligence feeds.

    Sources (all legal, most have free tiers):
    - Have I Been Pwned API (breach data)
    - IntelX (paste sites, breach compilations)
    - Shodan (internet-wide scanning data)
    - Censys (certificate and host data)
    - Hunter.io (email enumeration)
    - LeakLookup (breach search)
    """

    # Breach databases that can be queried legally
    _BREACH_SOURCES: list[dict[str, str]] = [
        {"name": "Have I Been Pwned", "url": "https://haveibeenpwned.com/api/v3", "type": "breach_check"},
        {"name": "IntelX", "url": "https://intelx.io", "type": "paste_search"},
        {"name": "DeHashed", "url": "https://dehashed.com/api", "type": "credential_search"},
        {"name": "LeakLookup", "url": "https://leak-lookup.com/api", "type": "breach_search"},
        {"name": "Snusbase", "url": "https://snusbase.com/api", "type": "credential_search"},
    ]

    # Threat intelligence sources
    _THREAT_INTEL_SOURCES: list[dict[str, str]] = [
        {"name": "Shodan", "url": "https://api.shodan.io", "type": "host_search"},
        {"name": "Censys", "url": "https://search.censys.io/api", "type": "cert_search"},
        {"name": "GreyNoise", "url": "https://api.greynoise.io", "type": "noise_check"},
        {"name": "AbuseIPDB", "url": "https://api.abuseipdb.com/api/v2", "type": "reputation"},
        {"name": "VirusTotal", "url": "https://www.virustotal.com/api/v3", "type": "multi_scan"},
        {"name": "URLhaus", "url": "https://urlhaus-api.abuse.ch/v1", "type": "malware_url"},
    ]

    def generate_dark_web_recon_plan(self, target: str) -> list[dict[str, Any]]:
        """Generate a dark web reconnaissance plan for a target domain.

        This is legal OSINT -- querying public databases for leaked data
        associated with the target organization.
        """
        plan = []

        # Step 1: Check for breached credentials
        plan.append({
            "step": "Check breach databases",
            "action": "breach_search",
            "query": f"@{target}",
            "sources": [s["name"] for s in self._BREACH_SOURCES],
            "reason": (
                "Leaked credentials from past breaches can be used for "
                "credential stuffing, password spraying, or as evidence "
                "of inadequate security practices."
            ),
            "legal_basis": "Querying public breach notification APIs",
        })

        # Step 2: Email enumeration
        plan.append({
            "step": "Enumerate employee emails",
            "action": "email_enum",
            "methods": [
                f"Hunter.io: search for @{target} patterns",
                f"LinkedIn + Google dorking: site:linkedin.com \"{target}\"",
                f"GitHub search: \"{target}\" email in:file",
                "Certificate Transparency: email addresses in cert fields",
            ],
            "reason": "Employee emails are usernames. Combined with breach data = credential attacks.",
        })

        # Step 3: Paste site search
        plan.append({
            "step": "Search paste sites",
            "action": "paste_search",
            "queries": [target, f"@{target}", f"*.{target}"],
            "sources": ["Pastebin (via Google cache)", "IntelX", "GitHub Gists"],
            "reason": (
                "Developers accidentally paste API keys, database URLs, "
                "internal documentation, and credentials to paste sites."
            ),
        })

        # Step 4: Code repository search
        plan.append({
            "step": "Search code repositories for secrets",
            "action": "code_search",
            "queries": [
                f'"{target}" password',
                f'"{target}" api_key',
                f'"{target}" secret',
                f'"{target}" database_url',
                f'"{target}" AWS_SECRET',
            ],
            "sources": ["GitHub", "GitLab", "Bitbucket"],
            "reason": "Developers commit secrets to public repos. GitGuardian reports 10M+ secrets exposed per year.",
        })

        # Step 5: Shodan/Censys search
        plan.append({
            "step": "Internet-wide scan data",
            "action": "passive_scan",
            "queries": [
                f"Shodan: hostname:{target}",
                f"Shodan: ssl.cert.subject.CN:{target}",
                f"Censys: services.tls.certificates.leaf.subject.common_name:{target}",
            ],
            "reason": (
                "Shodan and Censys continuously scan the entire internet. "
                "Their databases reveal all services, open ports, SSL certs, "
                "and banners associated with the target -- without sending "
                "a single packet to the target yourself."
            ),
        })

        # Step 6: Threat actor intelligence
        plan.append({
            "step": "Check threat actor activity",
            "action": "threat_intel",
            "checks": [
                f"GreyNoise: check if target IPs are scanning the internet (compromised?)",
                f"AbuseIPDB: check target IP reputation",
                f"VirusTotal: check target domain for malware associations",
            ],
            "reason": "If the target is already compromised by another actor, that changes the assessment entirely.",
        })

        return plan

    def analyze_breach_impact(
        self,
        breaches: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        """Analyze the impact of discovered breaches on the target."""
        analysis = {
            "total_breaches": len(breaches),
            "credential_types": [],
            "most_recent": "",
            "password_reuse_risk": "unknown",
            "recommendations": [],
        }

        for breach in breaches:
            data_types = breach.get("data_classes", breach.get("data_types", []))
            if "Passwords" in data_types or "password" in str(data_types).lower():
                analysis["credential_types"].append("passwords")
                analysis["recommendations"].append(
                    "Credential stuffing: test breached email:password pairs "
                    "against login endpoints, VPN, email, and cloud services."
                )
            if "Email addresses" in data_types:
                analysis["credential_types"].append("emails")

        analysis["credential_types"] = list(set(analysis["credential_types"]))

        if "passwords" in analysis["credential_types"]:
            analysis["password_reuse_risk"] = "high"
            analysis["recommendations"].append(
                "Password spraying: use common mutations of breached passwords "
                "(Season+Year, Company+123, etc.) against all discovered endpoints."
            )

        return analysis


# ---------------------------------------------------------------------------
# Network Topology Mapper
# ---------------------------------------------------------------------------

class NetworkTopologyMapper:
    """Infer the target's network architecture from external observations.

    From the outside, we can determine:
    - CDN vs direct hosting
    - Load balancer presence (response time variance, server headers)
    - Microservices vs monolith (multiple subdomains vs single domain)
    - Cloud provider (IP range, headers, error pages)
    - Network segmentation (different IPs for different services)
    - Firewall posture (filtered vs closed ports)
    """

    # Cloud provider IP range indicators
    _CLOUD_INDICATORS: dict[str, list[str]] = {
        "aws": ["amazonaws.com", "aws", "ec2", "elb", "cloudfront", "s3"],
        "gcp": ["google", "googleapis", "cloud.google", "appspot", "run.app"],
        "azure": ["azure", "microsoft", "windows.net", "azurewebsites", "blob.core"],
        "digitalocean": ["digitalocean", "do-"],
        "cloudflare": ["cloudflare", "cf-ray"],
        "vercel": ["vercel", "now.sh"],
        "netlify": ["netlify"],
        "heroku": ["heroku", "herokuapp"],
    }

    def infer_topology(
        self,
        domain: str,
        subdomains: list[str],
        live_hosts: list[dict[str, Any]],
        response_headers: dict[str, str],
        dns_records: dict[str, Any] | None = None,
    ) -> NetworkFingerprint:
        """Infer network topology from external observations."""
        fp = NetworkFingerprint()

        # Detect cloud provider from headers and subdomains
        all_text = " ".join([
            str(response_headers),
            " ".join(subdomains),
            domain,
        ]).lower()

        for provider, indicators in self._CLOUD_INDICATORS.items():
            if any(ind in all_text for ind in indicators):
                fp.hosting_provider = provider
                break

        # Detect CDN from headers
        headers_lower = {k.lower(): v.lower() for k, v in response_headers.items()}
        if "cf-ray" in headers_lower or "cf-cache-status" in headers_lower:
            fp.cdn_provider = "cloudflare"
        elif "x-amz-cf-id" in headers_lower:
            fp.cdn_provider = "cloudfront"
        elif "x-akamai" in str(headers_lower) or "akamai" in str(headers_lower):
            fp.cdn_provider = "akamai"
        elif "x-fastly-request-id" in headers_lower:
            fp.cdn_provider = "fastly"

        # Detect server OS from headers
        server = headers_lower.get("server", "")
        if "nginx" in server:
            fp.server_os = "linux"
        elif "apache" in server:
            fp.server_os = "linux"
        elif "iis" in server or "microsoft" in server:
            fp.server_os = "windows"

        # HTTP version
        fp.http_version = headers_lower.get("alt-svc", "")
        if "h3" in fp.http_version:
            fp.http_version = "HTTP/3"
        elif "h2" in str(headers_lower):
            fp.http_version = "HTTP/2"
        else:
            fp.http_version = "HTTP/1.1"

        # Infer topology from subdomain count
        if len(subdomains) > 100:
            fp.network_topology = "large_enterprise"
        elif len(subdomains) > 30:
            fp.network_topology = "microservices"
        elif len(subdomains) > 10:
            fp.network_topology = "segmented"
        else:
            fp.network_topology = "simple"

        # Collect unique IPs
        for host in live_hosts:
            ip = host.get("ip", host.get("a", []))
            if isinstance(ip, list):
                fp.ip_ranges.extend(ip)
            elif ip:
                fp.ip_ranges.append(ip)
        fp.ip_ranges = list(set(fp.ip_ranges))

        return fp

    def identify_egress_paths(self, fingerprint: NetworkFingerprint) -> list[str]:
        """Identify potential data exfiltration paths based on topology."""
        paths = []

        if fingerprint.cdn_provider:
            paths.append(
                f"CDN ({fingerprint.cdn_provider}) may cache responses -- "
                f"test cache poisoning for stored XSS or data leakage"
            )

        if fingerprint.network_topology == "microservices":
            paths.append(
                "Microservices architecture: SSRF through internal service mesh "
                "can reach services not exposed to the internet"
            )

        if fingerprint.hosting_provider == "aws":
            paths.append(
                "AWS: check for SSRF to metadata endpoint (169.254.169.254) "
                "to extract IAM credentials"
            )
        elif fingerprint.hosting_provider == "gcp":
            paths.append(
                "GCP: check for SSRF to metadata endpoint (metadata.google.internal) "
                "to extract service account tokens"
            )

        if fingerprint.server_os == "windows":
            paths.append(
                "Windows server: check for SMB relay, NTLM hash capture, "
                "and RDP exposure on non-standard ports"
            )

        return paths


# ---------------------------------------------------------------------------
# Tor / Hidden Service Knowledge
# ---------------------------------------------------------------------------

class TorIntelligence:
    """Knowledge about Tor network and hidden services for threat intelligence.

    This is DEFENSIVE intelligence -- understanding how adversaries
    use Tor to attack the target, and how to check if the target
    has any .onion presence (which may indicate shadow IT or compromise).
    """

    def generate_tor_recon_plan(self, target: str) -> list[dict[str, Any]]:
        """Generate Tor-related reconnaissance steps."""
        return [
            {
                "step": "Check for .onion mirrors",
                "action": "onion_search",
                "queries": [
                    f"Google: site:*.onion \"{target}\"",
                    f"Ahmia.fi search: {target}",
                    f"DarkSearch.io: {target}",
                ],
                "reason": (
                    "Some organizations run .onion mirrors (Facebook, NYT). "
                    "Shadow IT may also expose internal services as hidden services."
                ),
            },
            {
                "step": "Check Tor exit node reputation",
                "action": "exit_node_check",
                "method": "Cross-reference target IPs with Tor exit node list",
                "reason": (
                    "If target IPs appear in Tor exit node lists, the server "
                    "may be compromised and used as a Tor relay."
                ),
            },
            {
                "step": "Check for leaked .onion addresses",
                "action": "onion_leak_search",
                "queries": [
                    f"GitHub: \"{target}\" .onion",
                    f"Pastebin: \"{target}\" onion",
                ],
                "reason": "Developers may accidentally reference internal .onion services in code or docs.",
            },
        ]

    def assess_tor_usage_risk(self, target: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
        """Assess the risk of Tor-related activity for the target."""
        has_onion = any("onion" in str(f).lower() for f in findings)
        has_exit_node = any("exit" in str(f).lower() and "tor" in str(f).lower() for f in findings)

        risk = "low"
        if has_onion:
            risk = "medium"
        if has_exit_node:
            risk = "high"

        return {
            "tor_risk": risk,
            "has_onion_presence": has_onion,
            "is_exit_node": has_exit_node,
            "implications": [
                "Onion presence may indicate shadow IT or intentional privacy service",
                "Exit node status indicates compromise -- server is routing anonymous traffic",
            ] if risk != "low" else [],
        }
