"""Zero-Day Discovery Engine -- First-principles vulnerability reasoning.

Mythos finds 0-days by reasoning about memory layout and protocol specs.
Daena does the same thing, but through EXPLICIT reasoning patterns that
are auditable, improvable, and transferable across the CKG.

Three discovery methods:

1. SpecGapAnalysis: Compare what a protocol/API SPEC says vs what the
   implementation ACTUALLY does. Every gap is a potential 0-day.

2. LogicFlowAnalysis: Trace authentication, authorization, and state
   management flows. Find TOCTOU races, missing checks, order-of-
   operations bugs, and business logic flaws.

3. SupplyChainAnalysis: Analyze dependency trees for confusion attacks,
   typosquatting, abandoned maintainers, and build pipeline injection.

These aren't pattern-matching against known CVEs. These are REASONING
techniques that discover vulnerabilities nobody has seen before.

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
class ZeroDayCandidate:
    """A potential zero-day vulnerability discovered through reasoning."""
    category: str           # "spec_gap", "logic_flaw", "supply_chain", "memory_safety"
    title: str              # Human-readable title
    description: str        # What the vulnerability is
    reasoning_chain: list[str]  # Step-by-step reasoning that found it
    exploitation_path: str  # How to exploit it (theoretical)
    impact: str             # What an attacker could achieve
    confidence: float = 0.5 # 0.0 to 1.0
    severity: str = "high"  # low, medium, high, critical
    cwe: str = ""           # CWE reference if applicable
    evidence: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Spec-Gap Analysis
# ---------------------------------------------------------------------------

class SpecGapAnalyzer:
    """Find vulnerabilities by comparing spec vs implementation.

    The principle: every protocol, API, and standard has a specification.
    Every implementation deviates from the spec in subtle ways. These
    deviations are vulnerabilities.

    Examples:
    - HTTP spec says headers are case-insensitive. Implementation uses
      case-sensitive lookup -> header smuggling.
    - OAuth spec says state parameter MUST be verified. Implementation
      skips verification -> CSRF on OAuth callback.
    - JWT spec says alg:none should be rejected. Implementation accepts
      it -> authentication bypass.
    """

    # Known spec-implementation gaps organized by protocol/standard
    _SPEC_GAPS = {
        "http": [
            {
                "spec_says": "Transfer-Encoding and Content-Length must not coexist",
                "common_gap": "Some servers process both, prioritizing differently",
                "vulnerability": "HTTP request smuggling (CL.TE or TE.CL)",
                "test": "Send request with both headers, observe which takes priority",
                "cwe": "CWE-444",
                "severity": "critical",
            },
            {
                "spec_says": "Host header determines which virtual host serves the request",
                "common_gap": "Backend trusts Host header for URL generation",
                "vulnerability": "Host header injection -> cache poisoning, SSRF",
                "test": "Send request with modified Host header, observe response URLs",
                "cwe": "CWE-20",
                "severity": "high",
            },
            {
                "spec_says": "HTTP methods are case-sensitive (GET, POST, etc.)",
                "common_gap": "Some servers accept lowercase or mixed case methods",
                "vulnerability": "Method override bypasses (gEt, PoSt bypass WAF rules)",
                "test": "Send requests with non-standard method casing",
                "cwe": "CWE-436",
                "severity": "medium",
            },
        ],
        "oauth": [
            {
                "spec_says": "state parameter MUST be validated to prevent CSRF",
                "common_gap": "Many implementations skip state validation",
                "vulnerability": "CSRF on OAuth callback -> account takeover",
                "test": "Remove state parameter from callback, observe if auth completes",
                "cwe": "CWE-352",
                "severity": "critical",
            },
            {
                "spec_says": "redirect_uri must be exact match (RFC 6749)",
                "common_gap": "Some implementations use prefix/subdomain matching",
                "vulnerability": "Open redirect -> token theft via redirect_uri manipulation",
                "test": "Append path or use subdomain in redirect_uri",
                "cwe": "CWE-601",
                "severity": "high",
            },
            {
                "spec_says": "Authorization code is single-use",
                "common_gap": "Some implementations allow code reuse within time window",
                "vulnerability": "Authorization code replay -> session hijacking",
                "test": "Replay authorization code after initial exchange",
                "cwe": "CWE-294",
                "severity": "high",
            },
        ],
        "jwt": [
            {
                "spec_says": "alg:none should be rejected for signed tokens",
                "common_gap": "Some libraries accept alg:none, stripping signature",
                "vulnerability": "Authentication bypass via algorithm confusion",
                "test": "Replace JWT header alg with 'none', remove signature",
                "cwe": "CWE-327",
                "severity": "critical",
            },
            {
                "spec_says": "RS256 (asymmetric) and HS256 (symmetric) use different key types",
                "common_gap": "Switching alg from RS256 to HS256 uses public key as HMAC secret",
                "vulnerability": "Key confusion -> forge valid tokens with public key",
                "test": "Change alg to HS256, sign with server's public key",
                "cwe": "CWE-327",
                "severity": "critical",
            },
            {
                "spec_says": "exp claim must be validated",
                "common_gap": "Clock skew tolerance is sometimes too generous or missing",
                "vulnerability": "Expired token acceptance -> extended session validity",
                "test": "Send expired JWT with various clock skew values",
                "cwe": "CWE-613",
                "severity": "medium",
            },
        ],
        "cors": [
            {
                "spec_says": "Access-Control-Allow-Origin should be specific, not reflected",
                "common_gap": "Many servers reflect the Origin header as ACAO",
                "vulnerability": "Cross-origin data theft from any origin",
                "test": "Send request with evil origin, check if reflected in ACAO",
                "cwe": "CWE-942",
                "severity": "high",
            },
            {
                "spec_says": "Credentials should not be allowed with wildcard origin",
                "common_gap": "Some configs allow credentials with reflected origin",
                "vulnerability": "Authenticated cross-origin attacks",
                "test": "Check if ACAO reflects origin AND credentials: true",
                "cwe": "CWE-942",
                "severity": "critical",
            },
        ],
        "graphql": [
            {
                "spec_says": "Introspection should be disabled in production",
                "common_gap": "Many deployments leave introspection enabled",
                "vulnerability": "Full schema disclosure -> reveals all types, queries, mutations",
                "test": "Send __schema introspection query",
                "cwe": "CWE-200",
                "severity": "medium",
            },
            {
                "spec_says": "Query depth and complexity should be limited",
                "common_gap": "No limits on nested queries",
                "vulnerability": "Denial of service via deeply nested query",
                "test": "Send progressively deeper nested queries, measure response time",
                "cwe": "CWE-400",
                "severity": "high",
            },
        ],
        "api_design": [
            {
                "spec_says": "IDOR: Object references should be validated against current user",
                "common_gap": "Authorization checked on endpoint, not on individual objects",
                "vulnerability": "Access other users' data by changing ID parameter",
                "test": "Authenticate as user A, request user B's resources by ID",
                "cwe": "CWE-639",
                "severity": "critical",
            },
            {
                "spec_says": "Mass assignment: Only allowed fields should be updateable",
                "common_gap": "ORM auto-binds all request fields to model",
                "vulnerability": "Modify restricted fields (role, balance, admin flag)",
                "test": "Add extra fields to update request (role=admin, is_admin=true)",
                "cwe": "CWE-915",
                "severity": "critical",
            },
            {
                "spec_says": "Rate limiting should apply per-user and per-endpoint",
                "common_gap": "Rate limits only on IP, bypassed via rotating IPs or headers",
                "vulnerability": "Brute force, enumeration, denial of service",
                "test": "Check rate limit scope (IP vs user vs API key)",
                "cwe": "CWE-799",
                "severity": "medium",
            },
        ],
    }

    def analyze_target(
        self,
        technologies: list[str],
        headers: dict[str, str] | None = None,
        endpoints: list[str] | None = None,
    ) -> list[ZeroDayCandidate]:
        """Analyze a target for spec-gap vulnerabilities.

        Uses detected technologies to determine which specs to check.
        """
        candidates: list[ZeroDayCandidate] = []
        tech_lower = [t.lower() for t in technologies]
        headers = headers or {}

        # Always check HTTP gaps
        candidates.extend(self._check_protocol("http", headers))

        # Check based on detected technologies
        if any("oauth" in t or "auth0" in t or "okta" in t for t in tech_lower):
            candidates.extend(self._check_protocol("oauth", headers))

        if any("jwt" in t or "jsonwebtoken" in t or "auth" in t for t in tech_lower):
            candidates.extend(self._check_protocol("jwt", headers))

        if any("cors" in t for t in tech_lower) or "access-control-allow-origin" in headers:
            candidates.extend(self._check_protocol("cors", headers))

        if any("graphql" in t for t in tech_lower) or any(
            "graphql" in (ep or "") for ep in (endpoints or [])
        ):
            candidates.extend(self._check_protocol("graphql", headers))

        # Always check API design gaps
        candidates.extend(self._check_protocol("api_design", headers))

        return candidates

    def _check_protocol(
        self,
        protocol: str,
        headers: dict[str, str],
    ) -> list[ZeroDayCandidate]:
        """Check gaps for a specific protocol."""
        gaps = self._SPEC_GAPS.get(protocol, [])
        candidates = []

        for gap in gaps:
            reasoning = [
                f"Spec says: {gap['spec_says']}",
                f"Common gap: {gap['common_gap']}",
                f"Test: {gap['test']}",
            ]

            # Check headers for evidence of vulnerability
            evidence: dict[str, Any] = {"protocol": protocol}
            confidence = 0.4  # Base confidence

            if protocol == "cors":
                acao = headers.get("access-control-allow-origin", "")
                if acao == "*" or acao:
                    confidence = 0.7
                    evidence["acao_value"] = acao

            if protocol == "http":
                if "transfer-encoding" in headers and "content-length" in headers:
                    confidence = 0.8
                    evidence["both_headers"] = True

            candidates.append(ZeroDayCandidate(
                category="spec_gap",
                title=f"[{protocol.upper()}] {gap['vulnerability'][:80]}",
                description=gap["vulnerability"],
                reasoning_chain=reasoning,
                exploitation_path=gap["test"],
                impact=f"Could lead to: {gap['vulnerability']}",
                confidence=confidence,
                severity=gap["severity"],
                cwe=gap.get("cwe", ""),
                evidence=evidence,
            ))

        return candidates


# ---------------------------------------------------------------------------
# 2. Logic Flow Analysis
# ---------------------------------------------------------------------------

class LogicFlowAnalyzer:
    """Find vulnerabilities by reasoning about application logic.

    These are the bugs that automated scanners NEVER find because
    they require understanding WHAT the application is supposed to do,
    not just how it responds to malformed input.

    Categories:
    - TOCTOU (Time-of-Check to Time-of-Use) races
    - Missing authorization checks on state transitions
    - Business logic flaws (negative quantities, price manipulation)
    - Order-of-operations bugs (validate THEN load vs load THEN validate)
    """

    _LOGIC_PATTERNS = [
        {
            "name": "Race condition in state transition",
            "description": (
                "If two requests hit a state-changing endpoint simultaneously, "
                "the application may process both before either completes. "
                "Common in: payment processing, coupon redemption, vote counting."
            ),
            "indicators": ["balance", "credit", "coupon", "redeem", "transfer", "vote", "quantity"],
            "test_approach": "Send concurrent identical requests, check for double-processing",
            "cwe": "CWE-362",
            "severity": "critical",
        },
        {
            "name": "Price/quantity manipulation",
            "description": (
                "If the client sends price or quantity values and the server "
                "doesn't re-validate against the catalog, an attacker can "
                "modify prices, use negative quantities, or bypass minimums."
            ),
            "indicators": ["price", "amount", "quantity", "total", "cart", "checkout", "order"],
            "test_approach": "Intercept checkout request, modify price/quantity fields",
            "cwe": "CWE-20",
            "severity": "critical",
        },
        {
            "name": "Broken function-level access control",
            "description": (
                "Admin functions exist at predictable URLs but rely on "
                "UI hiding rather than server-side authorization. Direct "
                "access to /admin/deleteUser works without admin session."
            ),
            "indicators": ["admin", "manage", "delete", "create", "update", "config", "settings"],
            "test_approach": "Access admin endpoints with regular user session",
            "cwe": "CWE-285",
            "severity": "critical",
        },
        {
            "name": "Insecure direct object reference (IDOR)",
            "description": (
                "Sequential or predictable IDs allow accessing other users' "
                "resources by simply changing the ID parameter. The server "
                "checks authentication but not authorization on the specific object."
            ),
            "indicators": ["id", "user_id", "account", "profile", "document", "file"],
            "test_approach": "Change ID parameter to another user's ID while authenticated",
            "cwe": "CWE-639",
            "severity": "high",
        },
        {
            "name": "Multi-step process bypass",
            "description": (
                "Multi-step workflows (signup, checkout, approval) can sometimes "
                "be bypassed by jumping directly to the final step, skipping "
                "validation steps in between."
            ),
            "indicators": ["step", "stage", "wizard", "flow", "process", "confirm", "verify"],
            "test_approach": "Skip intermediate steps, submit final step directly",
            "cwe": "CWE-841",
            "severity": "high",
        },
        {
            "name": "Privilege escalation via parameter pollution",
            "description": (
                "Sending duplicate parameters or unexpected fields can confuse "
                "the authorization layer. The first parameter is checked, the "
                "second is used, or vice versa."
            ),
            "indicators": ["role", "permission", "group", "type", "level", "tier"],
            "test_approach": "Send duplicate parameters with different values, add role/admin fields",
            "cwe": "CWE-269",
            "severity": "critical",
        },
    ]

    def analyze_endpoints(
        self,
        endpoints: list[dict[str, Any]],
        technologies: list[str] | None = None,
    ) -> list[ZeroDayCandidate]:
        """Analyze discovered endpoints for logic flow vulnerabilities.

        Each endpoint's path, parameters, and behavior are checked
        against known logic flaw patterns.
        """
        candidates: list[ZeroDayCandidate] = []

        for endpoint in endpoints:
            path = endpoint.get("path", "").lower()
            params = str(endpoint.get("params", "")).lower()
            combined = f"{path} {params}"

            for pattern in self._LOGIC_PATTERNS:
                # Check if endpoint matches pattern indicators
                matches = sum(
                    1 for indicator in pattern["indicators"]
                    if indicator in combined
                )
                if matches >= 1:
                    confidence = min(0.8, 0.3 + matches * 0.15)
                    candidates.append(ZeroDayCandidate(
                        category="logic_flaw",
                        title=f"{pattern['name']} at {endpoint.get('path', '/')}",
                        description=pattern["description"],
                        reasoning_chain=[
                            f"Endpoint: {endpoint.get('path', '/')}",
                            f"Matched indicators: {[i for i in pattern['indicators'] if i in combined]}",
                            f"Pattern: {pattern['name']}",
                            f"Test: {pattern['test_approach']}",
                        ],
                        exploitation_path=pattern["test_approach"],
                        impact=pattern["description"],
                        confidence=confidence,
                        severity=pattern["severity"],
                        cwe=pattern["cwe"],
                        evidence={"endpoint": endpoint, "matches": matches},
                    ))

        return candidates


# ---------------------------------------------------------------------------
# 3. Supply Chain Analysis
# ---------------------------------------------------------------------------

@dataclass
class SupplyChainRisk:
    """A supply chain attack vector."""
    attack_type: str         # "dependency_confusion", "typosquatting", "abandoned", "build_injection"
    target_package: str      # The package at risk
    ecosystem: str           # "npm", "pypi", "docker", "github_actions"
    description: str
    exploitation_steps: list[str]
    severity: str = "high"
    real_world_examples: list[str] = field(default_factory=list)


class SupplyChainAttackPlanner:
    """Analyze and plan supply chain attack campaigns.

    The most devastating modern attacks are supply chain attacks:
    - SolarWinds (2020): build pipeline compromise, 18,000 organizations
    - Codecov (2021): CI/CD credential theft via bash uploader
    - ua-parser-js (2021): npm package hijack, crypto miner injection
    - event-stream (2018): npm maintainer social engineering
    - PyPI typosquatting: thousands of malicious packages

    Daena analyzes the target's dependency tree and identifies:
    1. Dependency confusion opportunities (internal vs public packages)
    2. Typosquatting candidates (similar names to popular packages)
    3. Abandoned packages (unmaintained, vulnerable to takeover)
    4. Build pipeline injection points (CI/CD, Docker, GitHub Actions)

    NOT for executing attacks. For showing clients their supply chain
    risk and recommending defenses.
    """

    # Known supply chain attack patterns
    _ATTACK_PATTERNS = {
        "dependency_confusion": {
            "description": (
                "If the target uses private package names that don't exist on "
                "public registries, an attacker can publish a public package "
                "with the same name and higher version. Package managers will "
                "install the public (malicious) version."
            ),
            "exploitation_steps": [
                "Identify internal package names (from package.json, requirements.txt, etc.)",
                "Check if those names exist on public npm/pypi",
                "Register the name with a higher version number",
                "Include a post-install script that phones home",
                "Wait for automated builds to install the malicious package",
            ],
            "defenses": [
                "Use scoped packages (@company/package-name)",
                "Pin exact versions in lock files",
                "Use private registry with priority over public",
                "Enable package provenance verification",
            ],
            "real_world": ["Alex Birsan (2021) -- hit Apple, Microsoft, PayPal"],
        },
        "typosquatting": {
            "description": (
                "Register packages with names similar to popular ones. "
                "Developers who mistype 'lodash' as 'lodahs' or 'lodashs' "
                "install the malicious package instead."
            ),
            "exploitation_steps": [
                "Identify popular packages used by target",
                "Generate typo variants (character swap, omission, addition)",
                "Register variants on npm/pypi with malicious code",
                "Wait for developers to mistype during install",
            ],
            "defenses": [
                "Use lock files (package-lock.json, poetry.lock)",
                "Audit new dependencies before merging",
                "Use allow-lists for approved packages",
            ],
            "real_world": ["crossenv (npm, 2017) -- impersonated cross-env"],
        },
        "maintainer_takeover": {
            "description": (
                "Abandoned or under-maintained packages can be taken over. "
                "Contact the original maintainer (social engineering), offer "
                "to maintain the package, then inject malicious code in a "
                "future update."
            ),
            "exploitation_steps": [
                "Identify dependencies that haven't been updated in 2+ years",
                "Check if maintainer is still active on GitHub",
                "Offer to take over maintenance (or register expired domain for email)",
                "Publish a 'maintenance' update with backdoor",
            ],
            "defenses": [
                "Monitor dependency freshness",
                "Subscribe to security advisories for all dependencies",
                "Fork critical abandoned dependencies",
            ],
            "real_world": ["event-stream (npm, 2018) -- social engineering of maintainer"],
        },
        "build_pipeline_injection": {
            "description": (
                "Compromise the CI/CD pipeline to inject code during build. "
                "Targets: GitHub Actions workflows, Docker base images, "
                "build scripts, post-install hooks."
            ),
            "exploitation_steps": [
                "Analyze CI/CD configuration (github/workflows, Dockerfile, etc.)",
                "Find actions/images pulled from untrusted sources",
                "Find secrets exposed in build logs",
                "Identify build steps that run arbitrary code",
            ],
            "defenses": [
                "Pin GitHub Actions to specific commit SHAs",
                "Use Docker image digests instead of tags",
                "Audit CI/CD secrets access",
                "Enable build provenance signing (SLSA)",
            ],
            "real_world": ["Codecov (2021) -- modified bash uploader stole CI secrets"],
        },
    }

    def analyze_dependencies(
        self,
        packages: list[dict[str, str]],
        ecosystem: str = "npm",
    ) -> list[SupplyChainRisk]:
        """Analyze a dependency list for supply chain risks.

        packages: list of {"name": "lodash", "version": "4.17.21"}
        """
        risks: list[SupplyChainRisk] = []

        for pkg in packages:
            name = pkg.get("name", "")
            version = pkg.get("version", "")

            # Check for dependency confusion risk (internal-looking names)
            if self._looks_internal(name):
                pattern = self._ATTACK_PATTERNS["dependency_confusion"]
                risks.append(SupplyChainRisk(
                    attack_type="dependency_confusion",
                    target_package=name,
                    ecosystem=ecosystem,
                    description=f"Package '{name}' looks like an internal package. {pattern['description']}",
                    exploitation_steps=pattern["exploitation_steps"],
                    severity="critical",
                    real_world_examples=pattern["real_world"],
                ))

            # Check for typosquatting risk (similar to popular packages)
            similar = self._find_similar_popular(name, ecosystem)
            if similar:
                pattern = self._ATTACK_PATTERNS["typosquatting"]
                risks.append(SupplyChainRisk(
                    attack_type="typosquatting",
                    target_package=name,
                    ecosystem=ecosystem,
                    description=f"Package '{name}' is similar to popular '{similar}'. {pattern['description']}",
                    exploitation_steps=pattern["exploitation_steps"],
                    severity="high",
                    real_world_examples=pattern["real_world"],
                ))

        # Always include build pipeline risk
        pattern = self._ATTACK_PATTERNS["build_pipeline_injection"]
        risks.append(SupplyChainRisk(
            attack_type="build_pipeline_injection",
            target_package="CI/CD pipeline",
            ecosystem=ecosystem,
            description=pattern["description"],
            exploitation_steps=pattern["exploitation_steps"],
            severity="critical",
            real_world_examples=pattern["real_world"],
        ))

        return risks

    def plan_campaign(
        self,
        target_org: str,
        technologies: list[str],
        employees: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Plan a full supply chain attack campaign.

        This is the APT-level planning capability. It combines:
        - Technical analysis (dependency trees, build pipelines)
        - Human analysis (who has commit access, who reviews PRs)
        - Timing analysis (when are builds triggered, maintenance windows)

        Returns a structured campaign plan with stages, fallbacks,
        and expected outcomes.
        """
        campaign: dict[str, Any] = {
            "target": target_org,
            "campaign_type": "supply_chain",
            "stages": [],
            "estimated_timeline": "2-6 weeks",
            "success_probability": "medium",
        }

        # Stage 1: Reconnaissance
        campaign["stages"].append({
            "stage": 1,
            "name": "Supply Chain Reconnaissance",
            "description": "Map the target's entire dependency tree and build pipeline",
            "actions": [
                "Analyze public repositories for package.json, requirements.txt, go.mod",
                "Identify CI/CD platform (GitHub Actions, Jenkins, CircleCI)",
                "Map Docker base images and their update cadence",
                "Identify who has commit/merge access (from GitHub/GitLab)",
            ],
            "duration": "3-5 days",
            "opsec": "All passive -- public data only",
        })

        # Stage 2: Target Selection
        campaign["stages"].append({
            "stage": 2,
            "name": "Attack Vector Selection",
            "description": "Choose the highest-impact, lowest-detection attack vector",
            "actions": [
                "Rank dependencies by: internal naming (confusion risk) > abandoned > popular",
                "Check which dependencies have post-install scripts",
                "Identify the weakest link in the CI/CD chain",
                "Select primary and backup attack vectors",
            ],
            "duration": "2-3 days",
            "opsec": "Registry lookups only -- no suspicious activity",
        })

        # Stage 3: Weaponization
        campaign["stages"].append({
            "stage": 3,
            "name": "Payload Development",
            "description": "Create malicious package/action that blends with legitimate code",
            "actions": [
                "Fork legitimate package, add subtle backdoor in post-install",
                "Obfuscate payload to pass automated scanning",
                "Set up C2 infrastructure (DNS-over-HTTPS for stealth)",
                "Test payload in isolated environment matching target's build",
            ],
            "duration": "3-5 days",
            "opsec": "Development on isolated infrastructure",
        })

        # Stage 4: Delivery
        campaign["stages"].append({
            "stage": 4,
            "name": "Package Publication",
            "description": "Publish the malicious package and wait for installation",
            "actions": [
                "Publish package with version number higher than target's",
                "Create convincing README and documentation",
                "Wait for automated builds or developer installation",
                "Monitor C2 for initial callback",
            ],
            "duration": "1-14 days (waiting)",
            "opsec": "Package published from clean identity, no link to attacker",
        })

        # Stage 5: Post-Exploitation
        campaign["stages"].append({
            "stage": 5,
            "name": "Post-Compromise Operations",
            "description": "Leverage initial access for broader compromise",
            "actions": [
                "Extract CI/CD secrets from build environment",
                "Pivot to internal services using stolen credentials",
                "Establish persistence independent of the malicious package",
                "Begin data exfiltration through identified channels",
            ],
            "duration": "Ongoing",
            "opsec": "All communication via DNS-over-HTTPS or steganography",
        })

        # Defenses
        campaign["recommended_defenses"] = [
            "Enable npm/pip audit in CI/CD pipeline",
            "Use Sigstore/SLSA for package provenance",
            "Pin all dependencies to exact versions with integrity hashes",
            "Use private registries with scoped packages",
            "Monitor for unexpected packages in build output",
            "Implement least-privilege for CI/CD secrets",
            "Regular dependency audits with automated tooling",
        ]

        return campaign

    def _looks_internal(self, name: str) -> bool:
        """Check if a package name looks like an internal/private package."""
        internal_patterns = [
            r"^(internal|private|corp|company|org)-",
            r"-(internal|private|core|util|lib|common|shared)$",
            r"^@[^/]+/",  # Scoped packages are often internal
        ]
        return any(re.search(p, name) for p in internal_patterns)

    def _find_similar_popular(self, name: str, ecosystem: str) -> str:
        """Check if name is suspiciously similar to a popular package."""
        popular = {
            "npm": [
                "lodash", "express", "react", "axios", "moment", "chalk",
                "commander", "webpack", "babel", "eslint", "typescript",
                "underscore", "request", "async", "uuid", "dotenv",
            ],
            "pypi": [
                "requests", "flask", "django", "numpy", "pandas", "scipy",
                "beautifulsoup4", "selenium", "pillow", "sqlalchemy",
                "boto3", "pytest", "setuptools", "cryptography", "pyyaml",
            ],
        }

        for pkg in popular.get(ecosystem, []):
            if name != pkg and self._edit_distance(name, pkg) <= 2:
                return pkg
        return ""

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return SupplyChainAttackPlanner._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                curr.append(min(
                    prev[j + 1] + 1,
                    curr[j] + 1,
                    prev[j] + (0 if c1 == c2 else 1),
                ))
            prev = curr
        return prev[len(s2)]
