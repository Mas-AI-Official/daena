"""Beyond Mythos -- Cognitive capabilities that transcend constraint decomposition.

Mythos decomposes constraints. Beyond Mythos reasons about the
SYSTEM that creates constraints, predicts its responses, and
composes individually-benign actions into effective sequences.

Three capabilities:

1. ErrorOracle: Every rejection is intelligence. Parse failures
   to extract information the target didn't mean to reveal.
   A 403 vs 404 tells you the path exists. A 500 tells you
   the backend parsed your input. Timing differences reveal
   code paths. Response size differences reveal content.

2. AdversarialSimulator: Before you act, simulate what the
   defender sees. What would the WAF log? What pattern would
   the IDS flag? What would the SOC analyst notice? Then
   adjust your approach to be invisible BEFORE you send it.

3. CompositionalPlanner: When a direct action is blocked,
   decompose it into sub-actions that individually appear
   benign. Each step passes inspection alone. Together they
   achieve the objective. The whole is greater than the sum.

These are NOT hardcoded rules. They are cognitive frameworks
that the LLM applies using reasoning. The methods provide
structure; the LLM provides intelligence.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ErrorIntelligence:
    """Intelligence extracted from a failed interaction."""
    source_url: str
    status_code: int
    error_type: str  # "auth", "waf", "rate_limit", "server_error", "not_found", "forbidden"
    intelligence: list[str]  # What we learned
    inferred_facts: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    raw_indicators: dict[str, Any] = field(default_factory=dict)


@dataclass
class DefenderPrediction:
    """Predicted defender response to a planned action."""
    action_description: str
    predicted_detection: str  # "undetected", "logged", "alerted", "blocked"
    detection_reasons: list[str] = field(default_factory=list)
    evasion_suggestions: list[str] = field(default_factory=list)
    adjusted_params: dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.5  # 0.0 = invisible, 1.0 = certain detection


@dataclass
class CompositeStep:
    """One step in a compositional attack sequence."""
    operation: str
    params: dict[str, Any]
    appears_as: str  # What this looks like to the defender
    purpose: str  # What it actually achieves
    depends_on: list[int] = field(default_factory=list)  # Index of prerequisite steps


@dataclass
class CompositionalPlan:
    """A sequence of benign-looking steps that compose into an effective attack."""
    objective: str
    steps: list[CompositeStep] = field(default_factory=list)
    why_direct_fails: str = ""
    why_composition_works: str = ""
    total_risk: float = 0.5


# ---------------------------------------------------------------------------
# Error Oracle
# ---------------------------------------------------------------------------

class ErrorOracle:
    """Extracts intelligence from failures.

    Every error response is an information leak:
    - Status codes reveal path existence and auth requirements
    - Error messages reveal technology stack and internal structure
    - Response timing reveals code path complexity
    - Response size differences reveal content behind access controls
    - Header differences reveal middleware and proxy layers

    This is the capability Mythos uses implicitly but never exposes.
    Daena makes it explicit and systematic.
    """

    # Patterns that leak information in error responses
    _TECH_PATTERNS: dict[str, str] = {
        r"django|DjangoDebug": "django",
        r"laravel|Illuminate": "laravel",
        r"express|node\.js": "express/nodejs",
        r"spring|java\.lang": "spring/java",
        r"asp\.net|__VIEWSTATE": "asp.net",
        r"rails|ActionController": "ruby_on_rails",
        r"flask|Werkzeug": "flask",
        r"fastapi|starlette": "fastapi",
        r"nginx": "nginx",
        r"apache": "apache",
        r"cloudflare|cf-ray": "cloudflare",
        r"akamai": "akamai",
    }

    _SENSITIVE_PATTERNS: dict[str, str] = {
        r"stack\s*trace|traceback|at\s+\w+\.\w+\(": "stack_trace_exposed",
        r"sql\s*(syntax|error)|mysql|postgres|sqlite|ORA-\d+": "database_error_exposed",
        r"/home/\w+|/var/www|C:\\\\": "file_path_exposed",
        r"version[\s:\"]+\d+\.\d+": "version_exposed",
        r"internal\s+server|debug\s+mode": "debug_mode_exposed",
        r"secret|password|token|api.?key": "credential_reference",
    }

    def analyze_response(
        self,
        url: str,
        status_code: int,
        headers: dict[str, str],
        body: str,
        response_time_ms: int = 0,
        expected_status: int | None = None,
    ) -> ErrorIntelligence:
        """Extract intelligence from any HTTP response, especially errors.

        Every response tells us something. Errors tell us MORE than
        successes because the defender designed the success path
        carefully but often leaks information in error handling.
        """
        intel = ErrorIntelligence(
            source_url=url,
            status_code=status_code,
            error_type=self._classify_error(status_code),
            intelligence=[],
            raw_indicators={
                "response_time_ms": response_time_ms,
                "body_length": len(body),
                "header_count": len(headers),
            },
        )

        # Status code intelligence
        self._analyze_status_code(intel, status_code, expected_status)

        # Header intelligence
        self._analyze_headers(intel, headers)

        # Body intelligence (error messages, stack traces, tech leaks)
        self._analyze_body(intel, body)

        # Timing intelligence
        if response_time_ms > 0:
            self._analyze_timing(intel, response_time_ms)

        intel.confidence = min(0.9, 0.3 + 0.1 * len(intel.intelligence))
        return intel

    def compare_responses(
        self,
        responses: list[dict[str, Any]],
    ) -> list[str]:
        """Compare multiple responses to find differential intelligence.

        When you send similar requests with small variations and get
        different responses, the DIFFERENCE is the intelligence.
        A 200 for /users/1 and 403 for /users/2 means user 2 exists
        but is protected. A 200 for /users/1 and 404 for /users/99999
        means user enumeration is possible.
        """
        if len(responses) < 2:
            return []

        insights = []

        # Group by status code
        by_status: dict[int, list[dict]] = {}
        for r in responses:
            code = r.get("status_code", 0)
            by_status.setdefault(code, []).append(r)

        if len(by_status) > 1:
            codes = sorted(by_status.keys())
            insights.append(
                f"Differential response: {len(by_status)} distinct status codes "
                f"({codes}) across {len(responses)} requests -- "
                f"target distinguishes between inputs"
            )

            # Check for enumeration vulnerability
            if 200 in by_status and (404 in by_status or 403 in by_status):
                insights.append(
                    "Enumeration possible: target returns different codes for "
                    "valid vs invalid resources"
                )

        # Compare response sizes
        sizes = [r.get("body_length", len(r.get("body", ""))) for r in responses]
        if sizes and max(sizes) - min(sizes) > 100:
            insights.append(
                f"Response size variance: {min(sizes)}-{max(sizes)} bytes. "
                f"Size differences reveal different content behind access controls."
            )

        # Compare timing
        times = [r.get("response_time_ms", 0) for r in responses if r.get("response_time_ms")]
        if times and len(times) >= 2:
            avg = sum(times) / len(times)
            outliers = [t for t in times if abs(t - avg) > avg * 0.5]
            if outliers:
                insights.append(
                    f"Timing anomaly: average {avg:.0f}ms but outliers at "
                    f"{outliers}ms -- different code paths or backend processing"
                )

        return insights

    def _classify_error(self, status_code: int) -> str:
        if status_code == 401:
            return "auth"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not_found"
        elif status_code == 429:
            return "rate_limit"
        elif status_code == 503:
            return "waf"
        elif 500 <= status_code < 600:
            return "server_error"
        elif 200 <= status_code < 300:
            return "success"
        return "unknown"

    def _analyze_status_code(
        self,
        intel: ErrorIntelligence,
        status_code: int,
        expected_status: int | None,
    ) -> None:
        if status_code == 403:
            intel.intelligence.append(
                "403 Forbidden: path EXISTS but requires authorization. "
                "Different from 404 (not found). This confirms the resource "
                "is real and protected."
            )
            intel.inferred_facts["path_exists"] = True
            intel.inferred_facts["requires_auth"] = True

        elif status_code == 401:
            intel.intelligence.append(
                "401 Unauthorized: endpoint requires authentication. "
                "The server is willing to serve this if we authenticate. "
                "Look for auth bypass, default creds, or token leaks."
            )
            intel.inferred_facts["path_exists"] = True
            intel.inferred_facts["auth_required"] = True
            intel.inferred_facts["auth_type_hint"] = True

        elif status_code == 405:
            intel.intelligence.append(
                "405 Method Not Allowed: endpoint exists but rejects this HTTP method. "
                "Try other methods (POST, PUT, DELETE, PATCH, OPTIONS)."
            )
            intel.inferred_facts["path_exists"] = True
            intel.inferred_facts["method_restricted"] = True

        elif status_code == 500:
            intel.intelligence.append(
                "500 Internal Server Error: the backend PROCESSED our input "
                "and crashed. This means our input reached application code "
                "(past WAF/proxy). The crash itself may be exploitable."
            )
            intel.inferred_facts["input_reaches_backend"] = True
            intel.inferred_facts["potential_crash_bug"] = True

        elif status_code == 502 or status_code == 504:
            intel.intelligence.append(
                f"{status_code}: backend service is down or timed out. "
                f"Reveals reverse proxy architecture. The proxy is healthy "
                f"but the upstream is not."
            )
            intel.inferred_facts["reverse_proxy_present"] = True

        elif status_code == 429:
            intel.intelligence.append(
                "429 Rate Limited: we hit the rate limiter. This reveals "
                "rate limit thresholds. Slow down, rotate IPs, or find "
                "endpoints with different rate limits."
            )
            intel.inferred_facts["rate_limit_active"] = True

        elif status_code == 301 or status_code == 302:
            intel.intelligence.append(
                f"{status_code} Redirect: the server is redirecting. "
                f"Check the Location header -- redirects often reveal "
                f"internal hostnames, port numbers, or path structure."
            )

        if expected_status and status_code != expected_status:
            intel.intelligence.append(
                f"Unexpected status: got {status_code}, expected {expected_status}. "
                f"Behavior changed -- investigate what caused the difference."
            )

    def _analyze_headers(self, intel: ErrorIntelligence, headers: dict[str, str]) -> None:
        headers_lower = {k.lower(): v for k, v in headers.items()}

        # Server header reveals software
        server = headers_lower.get("server", "")
        if server:
            intel.intelligence.append(f"Server header reveals: {server}")
            intel.inferred_facts["server_software"] = server

        # X-Powered-By reveals framework
        powered_by = headers_lower.get("x-powered-by", "")
        if powered_by:
            intel.intelligence.append(f"X-Powered-By reveals: {powered_by}")
            intel.inferred_facts["framework"] = powered_by

        # WAF headers
        for waf_header in ("cf-ray", "x-sucuri-id", "x-akamai-session", "x-cdn"):
            if waf_header in headers_lower:
                intel.intelligence.append(f"WAF/CDN indicator: {waf_header}={headers_lower[waf_header]}")
                intel.inferred_facts.setdefault("waf_indicators", []).append(waf_header)

        # Rate limit headers reveal thresholds
        for rl_header in ("x-ratelimit-limit", "x-ratelimit-remaining", "retry-after", "x-rate-limit-limit"):
            if rl_header in headers_lower:
                intel.intelligence.append(f"Rate limit config exposed: {rl_header}={headers_lower[rl_header]}")
                intel.inferred_facts["rate_limit_config"] = {rl_header: headers_lower[rl_header]}

        # CORS misconfiguration
        acao = headers_lower.get("access-control-allow-origin", "")
        if acao == "*":
            intel.intelligence.append("CORS wildcard: Access-Control-Allow-Origin: * -- any origin can read responses")
            intel.inferred_facts["cors_wildcard"] = True

        # Location header in redirects
        location = headers_lower.get("location", "")
        if location:
            intel.inferred_facts["redirect_target"] = location
            # Check for internal hostname leak
            if any(p in location for p in ("localhost", "127.0.0.1", "internal", "10.", "192.168.")):
                intel.intelligence.append(f"Internal URL leaked in redirect: {location}")
                intel.inferred_facts["internal_url_leaked"] = location

    def _analyze_body(self, intel: ErrorIntelligence, body: str) -> None:
        if not body:
            return

        body_sample = body[:10000]

        # Technology leak patterns
        for pattern, tech in self._TECH_PATTERNS.items():
            if re.search(pattern, body_sample, re.IGNORECASE):
                intel.intelligence.append(f"Technology revealed in error body: {tech}")
                intel.inferred_facts.setdefault("technologies", []).append(tech)

        # Sensitive information patterns
        for pattern, finding in self._SENSITIVE_PATTERNS.items():
            if re.search(pattern, body_sample, re.IGNORECASE):
                intel.intelligence.append(f"Sensitive information in error: {finding}")
                intel.inferred_facts[finding] = True

        # JSON error structure (reveals API framework)
        if body_sample.strip().startswith("{"):
            intel.inferred_facts["api_format"] = "json"
            # Common error key patterns
            for key in ("detail", "message", "error", "errors", "status"):
                if f'"{key}"' in body_sample.lower():
                    intel.inferred_facts.setdefault("error_keys", []).append(key)

    def _analyze_timing(self, intel: ErrorIntelligence, response_time_ms: int) -> None:
        if response_time_ms > 5000:
            intel.intelligence.append(
                f"Slow response ({response_time_ms}ms): heavy backend processing. "
                f"Potential for DoS or timing-based information extraction."
            )
            intel.inferred_facts["slow_endpoint"] = True
        elif response_time_ms < 5:
            intel.intelligence.append(
                f"Near-instant response ({response_time_ms}ms): likely cached or "
                f"rejected at proxy/WAF layer before reaching backend."
            )
            intel.inferred_facts["proxy_rejection_likely"] = True


# ---------------------------------------------------------------------------
# Adversarial Self-Simulation
# ---------------------------------------------------------------------------

class AdversarialSimulator:
    """Simulates the defender's perspective before taking action.

    Before you probe a target, ask: what will the SOC team see?
    What will the WAF log? What pattern will the IDS flag?

    This is not paranoia -- it's OpSec-first thinking. The best
    penetration testers never trigger alerts because they think
    about both sides of the interaction.

    Uses deterministic rules for known patterns + LLM for novel
    situations when available.
    """

    # Known detection signatures
    _WAF_SIGNATURES: list[dict[str, Any]] = [
        {"pattern": r"nuclei|nikto|sqlmap|nmap|masscan|dirbuster", "detector": "tool_signature", "severity": "high"},
        {"pattern": r"' OR 1=1|UNION SELECT|<script>|javascript:", "detector": "payload_signature", "severity": "critical"},
        {"pattern": r"\.\./\.\.|%2e%2e|%00", "detector": "traversal_signature", "severity": "high"},
    ]

    _RATE_THRESHOLDS: dict[str, int] = {
        "requests_per_second": 10,  # Above this triggers most rate limiters
        "unique_paths_per_minute": 50,  # Path enumeration detection
        "error_rate_percent": 80,  # High error rate flags automated scanning
    }

    def predict_detection(
        self,
        operation: str,
        params: dict[str, Any],
        target_defenses: list[str] | None = None,
        request_count_so_far: int = 0,
    ) -> DefenderPrediction:
        """Predict whether a planned action will be detected.

        Returns a prediction with detection probability and
        evasion suggestions if detection is likely.
        """
        prediction = DefenderPrediction(
            action_description=f"{operation}: {self._summarize_params(params)}",
            predicted_detection="undetected",
            risk_score=0.1,
        )

        defenses = set(d.lower() for d in (target_defenses or []))

        # Check for tool signatures in parameters
        self._check_signatures(prediction, params)

        # Check rate limit risk
        self._check_rate_risk(prediction, request_count_so_far)

        # Check WAF-specific risks
        if any("waf" in d or "cloudflare" in d or "akamai" in d for d in defenses):
            self._check_waf_risk(prediction, operation, params)

        # Check for noisy operations
        self._check_noise_level(prediction, operation)

        # Determine overall detection prediction
        if prediction.risk_score >= 0.8:
            prediction.predicted_detection = "blocked"
        elif prediction.risk_score >= 0.5:
            prediction.predicted_detection = "alerted"
        elif prediction.risk_score >= 0.2:
            prediction.predicted_detection = "logged"

        # Generate evasion suggestions for risky actions
        if prediction.risk_score >= 0.3:
            self._suggest_evasions(prediction, operation, params, defenses)

        return prediction

    def adjust_for_stealth(
        self,
        operation: str,
        params: dict[str, Any],
        prediction: DefenderPrediction,
    ) -> dict[str, Any]:
        """Adjust parameters to reduce detection risk.

        Applies evasion suggestions automatically where possible.
        Returns adjusted params (original unchanged).
        """
        adjusted = dict(params)

        # Apply adjusted params from prediction
        if prediction.adjusted_params:
            adjusted.update(prediction.adjusted_params)

        # Add browser-mimicry headers if not present
        if operation == "http_request" and "headers" not in adjusted:
            adjusted["headers"] = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
            }

        return adjusted

    def _check_signatures(self, prediction: DefenderPrediction, params: dict[str, Any]) -> None:
        params_str = str(params).lower()
        for sig in self._WAF_SIGNATURES:
            if re.search(sig["pattern"], params_str, re.IGNORECASE):
                prediction.detection_reasons.append(
                    f"Known {sig['detector']} detected in parameters"
                )
                if sig["severity"] == "critical":
                    prediction.risk_score = max(prediction.risk_score, 0.9)
                else:
                    prediction.risk_score = max(prediction.risk_score, 0.7)

    def _check_rate_risk(self, prediction: DefenderPrediction, request_count: int) -> None:
        if request_count > 100:
            prediction.detection_reasons.append(
                f"High request count ({request_count}): likely to trigger rate limiting"
            )
            prediction.risk_score = max(prediction.risk_score, 0.6)
        elif request_count > 50:
            prediction.detection_reasons.append(
                f"Moderate request count ({request_count}): approaching rate limit thresholds"
            )
            prediction.risk_score = max(prediction.risk_score, 0.3)

    def _check_waf_risk(
        self, prediction: DefenderPrediction, operation: str, params: dict[str, Any],
    ) -> None:
        if operation == "vuln_scan":
            prediction.detection_reasons.append(
                "Vulnerability scanner against WAF-protected target: "
                "nuclei templates have known signatures"
            )
            prediction.risk_score = max(prediction.risk_score, 0.8)
        elif operation == "http_request":
            url = params.get("url", "")
            # Check for common WAF-flagged paths
            flagged = [".env", ".git", "wp-admin", "phpinfo", "server-status"]
            for f in flagged:
                if f in url.lower():
                    prediction.detection_reasons.append(
                        f"Path '{f}' commonly monitored by WAFs"
                    )
                    prediction.risk_score = max(prediction.risk_score, 0.4)

    def _check_noise_level(self, prediction: DefenderPrediction, operation: str) -> None:
        noisy_ops = {"vuln_scan": 0.7, "subdomain_enum": 0.3, "http_probe": 0.4}
        quiet_ops = {"cve_search": 0.0, "http_request": 0.1, "tcp_connect": 0.15}

        if operation in noisy_ops:
            noise = noisy_ops[operation]
            prediction.risk_score = max(prediction.risk_score, noise)
            prediction.detection_reasons.append(
                f"Operation '{operation}' is inherently noisy (generates many requests)"
            )
        elif operation in quiet_ops:
            # Low noise, but still note it
            pass

    def _suggest_evasions(
        self,
        prediction: DefenderPrediction,
        operation: str,
        params: dict[str, Any],
        defenses: set[str],
    ) -> None:
        suggestions = []

        if any("rate" in r for r in prediction.detection_reasons):
            suggestions.append("Add random delays (2-5s) between requests to mimic human timing")
            suggestions.append("Rotate proxy IPs between requests")

        if any("scanner" in r.lower() or "nuclei" in r.lower() for r in prediction.detection_reasons):
            suggestions.append("Use targeted single-template scans instead of broad scan")
            suggestions.append("Randomize request order and add jitter")

        if any("waf" in d for d in defenses):
            suggestions.append("Use residential proxy to bypass IP reputation blocking")
            suggestions.append("Add realistic browser headers (User-Agent, Accept, Referer)")
            suggestions.append("Space requests 3-10 seconds apart")

        if any("signature" in r for r in prediction.detection_reasons):
            suggestions.append("Remove tool signatures from User-Agent and parameters")
            suggestions.append("Encode payloads differently to bypass signature detection")

        if operation == "http_request":
            suggestions.append("Use HEAD before GET to minimize response processing")

        prediction.evasion_suggestions = suggestions[:5]

    @staticmethod
    def _summarize_params(params: dict[str, Any]) -> str:
        url = params.get("url", params.get("host", ""))
        method = params.get("method", "")
        return f"{method} {url}".strip() or str(params)[:80]


# ---------------------------------------------------------------------------
# Compositional Attack Planner
# ---------------------------------------------------------------------------

class CompositionalPlanner:
    """Decomposes blocked attacks into benign-looking sub-actions.

    When a direct attack is blocked, don't abandon the goal.
    Instead, decompose it into steps that individually appear
    benign but compose into the full attack.

    Example:
        BLOCKED: Direct SQL injection on /api/search
        COMPOSED:
            1. GET /api/search?q=test        (normal search -- appears benign)
            2. GET /api/search?q=test' AND    (test quote handling -- looks like typo)
            3. GET /api/search?q=test'+--     (comment syntax -- could be formatting)
            4. GET /api/search?q=test' UNION SELECT version()--  (the actual payload)

        Each step individually: low suspicion
        Together: full SQL injection with version extraction

    Another example:
        BLOCKED: Direct credential spray on /login
        COMPOSED:
            1. GET /login                    (load login page -- normal)
            2. POST /login user=admin p=x    (single failed login -- normal)
            3. GET /forgot-password           (visit reset page -- normal)
            4. POST /forgot-password user=x   (test user enumeration via reset)
            5. GET /api/docs                  (check for auth bypass via API)

        Each step: what any user does
        Together: systematic auth weakness discovery
    """

    # Common compositional patterns
    _COMPOSITION_TEMPLATES: dict[str, list[dict[str, str]]] = {
        "auth_bypass": [
            {"step": "Load target page", "appears_as": "Normal navigation", "purpose": "Capture CSRF tokens, cookies, session info"},
            {"step": "Test default credentials", "appears_as": "Failed login attempt", "purpose": "Check for default/common passwords"},
            {"step": "Visit password reset", "appears_as": "Forgot password flow", "purpose": "User enumeration via reset response differences"},
            {"step": "Check API docs endpoint", "appears_as": "Developer exploring API", "purpose": "Find unauthenticated API endpoints"},
            {"step": "Direct API call without auth", "appears_as": "Misconfigured client", "purpose": "Test if API enforces auth independently of UI"},
        ],
        "data_extraction": [
            {"step": "Request resource with valid ID", "appears_as": "Normal data access", "purpose": "Confirm response format and baseline"},
            {"step": "Request with adjacent ID", "appears_as": "Minor user error", "purpose": "Test IDOR / access control on neighbor resources"},
            {"step": "Request with high ID", "appears_as": "Bookmarked old link", "purpose": "Enumerate resource range"},
            {"step": "Request with ID=0 or negative", "appears_as": "Client bug", "purpose": "Test boundary handling and error messages"},
        ],
        "service_enumeration": [
            {"step": "DNS resolution", "appears_as": "Normal DNS query", "purpose": "Map infrastructure IPs"},
            {"step": "HTTPS connection to port 443", "appears_as": "Normal web visit", "purpose": "Certificate reveals hostnames and org info"},
            {"step": "HTTP OPTIONS request", "appears_as": "CORS preflight", "purpose": "Discover allowed methods and headers"},
            {"step": "HEAD request to common paths", "appears_as": "Search engine crawler", "purpose": "Path existence without full response"},
        ],
    }

    def plan_composition(
        self,
        objective: str,
        blocked_action: str,
        target_url: str,
        block_reason: str = "",
    ) -> CompositionalPlan:
        """Create a compositional plan for a blocked objective.

        Analyzes the objective and block reason, then generates a
        sequence of individually-benign steps that achieve the goal.
        """
        plan = CompositionalPlan(
            objective=objective,
            why_direct_fails=block_reason or f"Direct '{blocked_action}' was blocked",
        )

        # Match to a composition template
        template_key = self._match_template(objective, blocked_action)
        if template_key and template_key in self._COMPOSITION_TEMPLATES:
            template = self._COMPOSITION_TEMPLATES[template_key]
            for i, step_template in enumerate(template):
                step = CompositeStep(
                    operation="http_request",
                    params=self._generate_params(step_template, target_url, i),
                    appears_as=step_template["appears_as"],
                    purpose=step_template["purpose"],
                    depends_on=[i - 1] if i > 0 else [],
                )
                plan.steps.append(step)
            plan.why_composition_works = (
                f"Each step mimics normal user behavior. The defender sees "
                f"individual benign requests, not a coordinated sequence. "
                f"Pattern: {template_key}"
            )
            plan.total_risk = 0.2  # Low risk -- each step is benign
        else:
            # Generic composition: reconnoiter, probe, exploit
            plan.steps = self._generic_composition(target_url, objective)
            plan.why_composition_works = (
                "Generic three-phase approach: observe, probe boundary, "
                "exploit the specific gap found in phase 2."
            )
            plan.total_risk = 0.4

        return plan

    def decompose_blocked_scan(
        self,
        scan_strategy_name: str,
        failure_reason: str,
        target: str,
    ) -> CompositionalPlan:
        """Decompose a blocked scan strategy into compositional steps.

        When a scan strategy fails (WAF, rate limit, etc.), create
        a slower, stealthier version that achieves the same goal
        through composition.
        """
        plan = CompositionalPlan(
            objective=f"Achieve '{scan_strategy_name}' results despite: {failure_reason}",
            why_direct_fails=failure_reason,
        )

        if "waf" in failure_reason.lower() or "403" in failure_reason:
            # WAF blocking: compose as normal browsing
            plan.steps = [
                CompositeStep(
                    operation="http_request",
                    params={"url": f"https://{target}/", "method": "GET"},
                    appears_as="Normal homepage visit",
                    purpose="Establish baseline response and session cookie",
                ),
                CompositeStep(
                    operation="http_request",
                    params={"url": f"https://{target}/robots.txt", "method": "GET"},
                    appears_as="Search engine crawler check",
                    purpose="Discover disallowed paths (often sensitive)",
                    depends_on=[0],
                ),
                CompositeStep(
                    operation="http_request",
                    params={"url": f"https://{target}/sitemap.xml", "method": "GET"},
                    appears_as="Search engine indexing",
                    purpose="Full path map from the target's own sitemap",
                    depends_on=[0],
                ),
                CompositeStep(
                    operation="http_request",
                    params={"url": f"https://{target}/.well-known/security.txt", "method": "GET"},
                    appears_as="Security researcher following RFC 9116",
                    purpose="Discover bug bounty scope, security contacts",
                    depends_on=[0],
                ),
            ]
            plan.why_composition_works = (
                "Each request mimics what a normal browser or search engine does. "
                "WAFs whitelist these paths. We get infrastructure intel without "
                "triggering scanner signatures."
            )
            plan.total_risk = 0.1

        elif "rate" in failure_reason.lower() or "429" in failure_reason:
            # Rate limited: slow, sequential, widely-spaced
            plan.steps = [
                CompositeStep(
                    operation="http_request",
                    params={"url": f"https://{target}/", "method": "HEAD"},
                    appears_as="Browser prefetch check",
                    purpose="Test if rate limit has reset",
                ),
                CompositeStep(
                    operation="cve_search",
                    params={"keyword": target},
                    appears_as="Public database query",
                    purpose="Get vulnerability intel without touching target",
                    depends_on=[0],
                ),
            ]
            plan.why_composition_works = (
                "Minimal target contact. CVE search is entirely passive. "
                "HEAD request is lightweight and often not rate-limited."
            )
            plan.total_risk = 0.05

        else:
            plan.steps = self._generic_composition(target, scan_strategy_name)
            plan.why_composition_works = "Generic recon approach adapted to bypass specific block"
            plan.total_risk = 0.3

        return plan

    def _match_template(self, objective: str, blocked_action: str) -> str:
        """Match an objective to the best composition template."""
        text = f"{objective} {blocked_action}".lower()

        if any(k in text for k in ("auth", "login", "credential", "password", "bypass")):
            return "auth_bypass"
        elif any(k in text for k in ("data", "extract", "idor", "user", "read")):
            return "data_extraction"
        elif any(k in text for k in ("enum", "discover", "service", "port", "scan")):
            return "service_enumeration"
        return ""

    def _generate_params(
        self, step_template: dict[str, str], target_url: str, step_index: int,
    ) -> dict[str, Any]:
        """Generate concrete params from a step template."""
        # Ensure URL has scheme
        if not target_url.startswith("http"):
            target_url = f"https://{target_url}"

        base = target_url.rstrip("/")

        # Map step purposes to concrete URLs
        step_text = step_template["step"].lower()
        if "load" in step_text or "visit" in step_text or step_index == 0:
            return {"url": base, "method": "GET"}
        elif "password" in step_text or "reset" in step_text:
            return {"url": f"{base}/forgot-password", "method": "GET"}
        elif "api" in step_text and "doc" in step_text:
            return {"url": f"{base}/api/docs", "method": "GET"}
        elif "default" in step_text or "login" in step_text:
            return {"url": f"{base}/login", "method": "GET"}
        elif "adjacent" in step_text or "idor" in step_text:
            return {"url": f"{base}/api/v1/users/2", "method": "GET"}
        elif "high" in step_text or "enumerate" in step_text:
            return {"url": f"{base}/api/v1/users/99999", "method": "GET"}
        elif "boundary" in step_text or "negative" in step_text:
            return {"url": f"{base}/api/v1/users/0", "method": "GET"}
        elif "dns" in step_text:
            return {"url": base, "method": "HEAD"}
        elif "options" in step_text:
            return {"url": base, "method": "OPTIONS"}
        return {"url": base, "method": "GET"}

    def _generic_composition(self, target: str, objective: str) -> list[CompositeStep]:
        """Generate a generic three-phase compositional plan."""
        if not target.startswith("http"):
            target = f"https://{target}"
        base = target.rstrip("/")

        return [
            CompositeStep(
                operation="http_request",
                params={"url": base, "method": "GET"},
                appears_as="Normal page visit",
                purpose="Observe baseline response, headers, and behavior",
            ),
            CompositeStep(
                operation="http_request",
                params={"url": base, "method": "OPTIONS"},
                appears_as="CORS preflight check",
                purpose="Discover allowed methods and CORS policy",
                depends_on=[0],
            ),
            CompositeStep(
                operation="http_request",
                params={"url": f"{base}/robots.txt", "method": "GET"},
                appears_as="Crawler check",
                purpose="Find disallowed paths that may be sensitive",
                depends_on=[0],
            ),
        ]
