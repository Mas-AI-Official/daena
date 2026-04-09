"""OSINT Engine -- People Intelligence, Supply Chain, Breach Intel.

The gap in every security tool: they test SYSTEMS. Elite researchers
test PEOPLE. The biggest breaches start with finding a real email or
phone number, not with a SQL injection.

Three capabilities:

1. OSINTPeopleIntelligence: Find real contact info from public sources.
   Emails from GitHub commits, domains from WHOIS, socials from
   public profiles, org charts from LinkedIn, phone patterns from
   company directories. All from PUBLICLY AVAILABLE information.

2. SupplyChainAnalyzer: Map every third-party service the target uses.
   CDN from headers, analytics from JS includes, email provider from
   MX records, DNS provider from NS records, hosting from IP ranges.
   Attack the weakest link, not the hardened front door.

3. BreachIntelligenceChecker: Check if the target's domain, emails, or
   patterns appear in known breach databases. Not to exploit -- to
   report that credentials may be compromised.

LEGAL NOTE: All methods use PUBLICLY AVAILABLE information only.
No unauthorized access, no password cracking, no private database access.
This is the same information available via Google, GitHub, WHOIS, DNS,
and public APIs. Authorized penetration testing context required.

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
class PersonIntel:
    """Intelligence gathered about a person."""
    name: str
    emails: list[str] = field(default_factory=list)
    phone_patterns: list[str] = field(default_factory=list)  # Patterns, not verified numbers
    social_profiles: dict[str, str] = field(default_factory=dict)  # platform -> url
    job_title: str = ""
    company: str = ""
    github_username: str = ""
    repositories: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    public_keys: list[str] = field(default_factory=list)  # GPG/SSH public keys from GitHub
    sources: list[str] = field(default_factory=list)  # Where each piece of info came from


@dataclass
class OrgIntel:
    """Intelligence about an organization."""
    name: str
    domain: str
    employees: list[PersonIntel] = field(default_factory=list)
    email_pattern: str = ""  # e.g., "{first}.{last}@domain.com"
    tech_stack: list[str] = field(default_factory=list)
    social_profiles: dict[str, str] = field(default_factory=dict)
    dns_registrar: str = ""
    hosting_provider: str = ""
    ip_ranges: list[str] = field(default_factory=list)


@dataclass
class SupplyChainEntry:
    """A third-party dependency in the target's supply chain."""
    service_name: str
    category: str  # "cdn", "analytics", "email", "dns", "hosting", "auth", "payment", "monitoring"
    detected_via: str  # How we found it: "header", "js_include", "dns", "cookie", "html_meta"
    evidence: str  # The specific header/include/record that revealed it
    risk_notes: str = ""  # Known security issues with this service
    url: str = ""


@dataclass
class BreachHit:
    """A match in breach intelligence."""
    source: str  # Which breach database
    match_type: str  # "domain", "email_pattern", "credential", "paste"
    details: str
    severity: str  # "info", "low", "medium", "high", "critical"
    date: str = ""  # When the breach occurred
    affected_records: int = 0


# ---------------------------------------------------------------------------
# 1. OSINT People Intelligence
# ---------------------------------------------------------------------------

class OSINTPeopleIntelligence:
    """Find real contact information from public sources.

    This is what separates a $50K penetration test from a $500 scan.
    The scan finds technical vulnerabilities. The pentest finds the
    PERSON who will click the phishing email.

    ALL information comes from PUBLICLY AVAILABLE sources:
    - GitHub: commits contain emails, profiles contain bios
    - DNS: WHOIS records (if not privacy-protected)
    - Company websites: team pages, about pages
    - Social media: public profiles
    - Job postings: reveal tech stack and team structure
    - SEC filings: executive names and compensation
    - Conference talks: reveal expertise and projects
    - Academic papers: author contact info
    """

    # Email pattern templates for common companies
    _EMAIL_PATTERNS: dict[str, list[str]] = {
        "default": [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}_{last}@{domain}",
            "{first}@{domain}",
            "{last}@{domain}",
        ],
    }

    # Common role-based emails that exist at most organizations
    _ROLE_EMAILS: list[str] = [
        "admin@{domain}",
        "info@{domain}",
        "support@{domain}",
        "security@{domain}",
        "abuse@{domain}",
        "webmaster@{domain}",
        "contact@{domain}",
        "hr@{domain}",
        "sales@{domain}",
        "dev@{domain}",
        "engineering@{domain}",
        "press@{domain}",
        "legal@{domain}",
        "privacy@{domain}",
        "compliance@{domain}",
        "ceo@{domain}",
        "cto@{domain}",
        "ciso@{domain}",
    ]

    def generate_email_candidates(
        self,
        first_name: str,
        last_name: str,
        domain: str,
    ) -> list[str]:
        """Generate likely email addresses for a person at a domain.

        Uses common corporate email patterns. These are CANDIDATES
        to be verified, not confirmed addresses.
        """
        candidates = []
        first = first_name.lower().strip()
        last = last_name.lower().strip()
        f = first[0] if first else ""

        for pattern in self._EMAIL_PATTERNS["default"]:
            email = pattern.format(
                first=first, last=last, f=f, domain=domain,
            )
            candidates.append(email)

        return candidates

    def generate_role_emails(self, domain: str) -> list[str]:
        """Generate common role-based email addresses for a domain."""
        return [e.format(domain=domain) for e in self._ROLE_EMAILS]

    async def gather_from_github(
        self,
        username: str = "",
        domain: str = "",
    ) -> list[PersonIntel]:
        """Gather intelligence from GitHub (public API, no auth needed).

        GitHub commits contain real email addresses. Public profiles
        contain bios, company info, and links. Repositories reveal
        tech stack and sometimes credentials in old commits.
        """
        people: list[PersonIntel] = []

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                if username:
                    # Get user profile
                    resp = await client.get(
                        f"https://api.github.com/users/{username}",
                        headers={"Accept": "application/vnd.github.v3+json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        person = PersonIntel(
                            name=data.get("name", username),
                            company=data.get("company", ""),
                            job_title=data.get("bio", "")[:100],
                            github_username=username,
                            social_profiles={"github": f"https://github.com/{username}"},
                            sources=["github_api"],
                        )
                        if data.get("email"):
                            person.emails.append(data["email"])
                        if data.get("blog"):
                            person.social_profiles["website"] = data["blog"]
                        if data.get("twitter_username"):
                            person.social_profiles["twitter"] = f"https://x.com/{data['twitter_username']}"

                        # Get repos for tech stack
                        repos_resp = await client.get(
                            f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10",
                            headers={"Accept": "application/vnd.github.v3+json"},
                        )
                        if repos_resp.status_code == 200:
                            repos = repos_resp.json()
                            person.repositories = [r["full_name"] for r in repos[:10]]
                            for repo in repos:
                                lang = repo.get("language", "")
                                if lang and lang not in person.technologies:
                                    person.technologies.append(lang)

                        people.append(person)

                elif domain:
                    # Search for users/commits associated with domain
                    # GitHub search: find commits with emails from this domain
                    resp = await client.get(
                        f"https://api.github.com/search/users?q={domain}+in:email&per_page=10",
                        headers={"Accept": "application/vnd.github.v3+json"},
                    )
                    if resp.status_code == 200:
                        users = resp.json().get("items", [])
                        for user_data in users[:10]:
                            person = PersonIntel(
                                name=user_data.get("login", ""),
                                github_username=user_data.get("login", ""),
                                social_profiles={"github": user_data.get("html_url", "")},
                                sources=["github_search"],
                            )
                            people.append(person)

        except ImportError:
            logger.debug("osint.github_requires_httpx")
        except Exception as exc:
            logger.debug("osint.github_failed", error=str(exc)[:200])

        return people

    async def gather_from_dns(self, domain: str) -> OrgIntel:
        """Gather organizational intelligence from DNS records.

        MX records reveal email provider. NS records reveal DNS provider.
        TXT records often contain verification tokens for services
        (Google Workspace, Microsoft 365, Salesforce, etc.).
        SOA records reveal admin email.
        """
        import asyncio

        org = OrgIntel(name=domain, domain=domain)

        try:
            # SOA record (admin email)
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=SOA", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            soa_output = stdout.decode("utf-8", errors="ignore")
            # Extract admin email from SOA
            email_match = re.search(r"responsible mail addr\s*=\s*(\S+)", soa_output, re.IGNORECASE)
            if not email_match:
                email_match = re.search(r"(\S+\.\S+)\s+hostmaster", soa_output, re.IGNORECASE)
            if email_match:
                # SOA email uses dots instead of @
                admin_email = email_match.group(1).replace(".", "@", 1)
                org.employees.append(PersonIntel(
                    name="DNS Admin",
                    emails=[admin_email],
                    job_title="DNS Administrator",
                    sources=["soa_record"],
                ))

            # TXT records (reveal services used)
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=TXT", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            txt_output = stdout.decode("utf-8", errors="ignore")

            # Detect services from TXT records
            service_indicators = {
                "google-site-verification": "Google Workspace",
                "ms=": "Microsoft 365",
                "v=spf1": "SPF configured",
                "salesforce": "Salesforce",
                "docusign": "DocuSign",
                "atlassian": "Atlassian",
                "slack": "Slack",
                "zoom": "Zoom",
                "hubspot": "HubSpot",
                "zendesk": "Zendesk",
                "stripe": "Stripe",
                "facebook": "Facebook Business",
            }
            for indicator, service in service_indicators.items():
                if indicator.lower() in txt_output.lower():
                    org.tech_stack.append(service)

            # MX records (email provider)
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=MX", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            mx_output = stdout.decode("utf-8", errors="ignore")

            if "google" in mx_output.lower() or "gmail" in mx_output.lower():
                org.tech_stack.append("Google Workspace (email)")
            elif "outlook" in mx_output.lower() or "microsoft" in mx_output.lower():
                org.tech_stack.append("Microsoft 365 (email)")
            elif "protonmail" in mx_output.lower():
                org.tech_stack.append("ProtonMail")

            # NS records (DNS provider)
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=NS", domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            ns_output = stdout.decode("utf-8", errors="ignore")

            if "cloudflare" in ns_output.lower():
                org.dns_registrar = "Cloudflare"
            elif "awsdns" in ns_output.lower():
                org.dns_registrar = "AWS Route 53"
            elif "google" in ns_output.lower():
                org.dns_registrar = "Google Cloud DNS"

        except Exception as exc:
            logger.debug("osint.dns_failed", error=str(exc)[:200])

        return org

    def extract_emails_from_text(self, text: str) -> list[str]:
        """Extract email addresses from any text (webpage, response body, etc.)."""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, text)
        # Deduplicate and filter obvious false positives
        seen: set[str] = set()
        emails = []
        for email in matches:
            email_lower = email.lower()
            if email_lower not in seen and not email_lower.endswith(".png") and not email_lower.endswith(".jpg"):
                seen.add(email_lower)
                emails.append(email_lower)
        return emails

    def detect_email_pattern(self, emails: list[str], domain: str) -> str:
        """Detect the email naming pattern used by an organization.

        Given a list of known emails for a domain, figure out the pattern:
        john.doe@domain.com -> {first}.{last}@domain
        jdoe@domain.com -> {f}{last}@domain
        """
        domain_emails = [e for e in emails if e.endswith(f"@{domain}")]
        if not domain_emails:
            return ""

        # Count pattern types
        patterns: dict[str, int] = {
            "first.last": 0,
            "firstlast": 0,
            "f.last": 0,
            "flast": 0,
            "first": 0,
        }

        for email in domain_emails:
            local = email.split("@")[0]
            if "." in local:
                parts = local.split(".")
                if len(parts) == 2:
                    if len(parts[0]) == 1:
                        patterns["f.last"] += 1
                    elif len(parts[0]) > 1:
                        patterns["first.last"] += 1
            elif len(local) > 3:
                patterns["firstlast"] += 1

        if patterns:
            best = max(patterns, key=lambda k: patterns[k])
            if patterns[best] > 0:
                return best
        return ""


# ---------------------------------------------------------------------------
# 2. Supply Chain Analyzer
# ---------------------------------------------------------------------------

class SupplyChainAnalyzer:
    """Map every third-party service the target depends on.

    The target's front door may be hardened. But their CDN provider,
    analytics service, email gateway, or payment processor might not be.
    Every third-party dependency is a potential attack vector.

    Detection methods:
    - HTTP response headers reveal CDN, framework, server software
    - JavaScript includes reveal analytics, tracking, A/B testing
    - DNS records reveal email, DNS, and hosting providers
    - Cookies reveal session management and analytics platforms
    - HTML meta tags reveal CMS and framework
    - Certificate details reveal CA and organization
    """

    # Header-based service detection
    _HEADER_SERVICES: dict[str, dict[str, str]] = {
        "cf-ray": {"service": "Cloudflare", "category": "cdn"},
        "x-amz-cf-id": {"service": "AWS CloudFront", "category": "cdn"},
        "x-vercel-id": {"service": "Vercel", "category": "hosting"},
        "x-netlify-request-id": {"service": "Netlify", "category": "hosting"},
        "x-heroku-request-id": {"service": "Heroku", "category": "hosting"},
        "x-github-request-id": {"service": "GitHub Pages", "category": "hosting"},
        "x-shopify-stage": {"service": "Shopify", "category": "ecommerce"},
        "x-powered-by-plesk": {"service": "Plesk", "category": "hosting"},
        "x-fastly-request-id": {"service": "Fastly", "category": "cdn"},
        "x-cache": {"service": "CDN (generic)", "category": "cdn"},
        "x-drupal-cache": {"service": "Drupal", "category": "cms"},
        "x-wordpress": {"service": "WordPress", "category": "cms"},
    }

    # JavaScript include patterns
    _JS_SERVICES: dict[str, dict[str, str]] = {
        r"google-analytics\.com|gtag": {"service": "Google Analytics", "category": "analytics"},
        r"googletagmanager\.com": {"service": "Google Tag Manager", "category": "analytics"},
        r"facebook\.net/en_US/fbevents": {"service": "Facebook Pixel", "category": "analytics"},
        r"hotjar\.com": {"service": "Hotjar", "category": "analytics"},
        r"mixpanel\.com": {"service": "Mixpanel", "category": "analytics"},
        r"segment\.com|segment\.io": {"service": "Segment", "category": "analytics"},
        r"sentry\.io|sentry-cdn": {"service": "Sentry", "category": "monitoring"},
        r"stripe\.com/v3": {"service": "Stripe", "category": "payment"},
        r"js\.intercom\.io": {"service": "Intercom", "category": "support"},
        r"zendesk\.com": {"service": "Zendesk", "category": "support"},
        r"crisp\.chat": {"service": "Crisp", "category": "support"},
        r"cdn\.auth0\.com": {"service": "Auth0", "category": "auth"},
        r"recaptcha": {"service": "Google reCAPTCHA", "category": "security"},
        r"hcaptcha\.com": {"service": "hCaptcha", "category": "security"},
        r"cloudflare\.com/turnstile": {"service": "Cloudflare Turnstile", "category": "security"},
        r"amplitude\.com": {"service": "Amplitude", "category": "analytics"},
        r"posthog\.com": {"service": "PostHog", "category": "analytics"},
        r"datadog": {"service": "Datadog", "category": "monitoring"},
        r"newrelic": {"service": "New Relic", "category": "monitoring"},
        r"pendo\.io": {"service": "Pendo", "category": "analytics"},
        r"launchdarkly": {"service": "LaunchDarkly", "category": "feature_flags"},
    }

    # Cookie-based detection
    _COOKIE_SERVICES: dict[str, dict[str, str]] = {
        "_ga": {"service": "Google Analytics", "category": "analytics"},
        "_fbp": {"service": "Facebook Pixel", "category": "analytics"},
        "__cf_bm": {"service": "Cloudflare Bot Management", "category": "security"},
        "hubspotutk": {"service": "HubSpot", "category": "marketing"},
        "intercom-session": {"service": "Intercom", "category": "support"},
        "_shopify_s": {"service": "Shopify", "category": "ecommerce"},
    }

    # Known security issues with services
    _SERVICE_RISKS: dict[str, str] = {
        "Cloudflare": "CDN cache poisoning if misconfigured; bypass via origin IP",
        "AWS CloudFront": "S3 bucket misconfiguration; origin access identity bypass",
        "Stripe": "Client-side key exposure; webhook signature bypass",
        "Auth0": "JWT algorithm confusion; tenant misconfiguration",
        "Google Analytics": "Data exfiltration via measurement protocol",
        "Sentry": "DSN exposure reveals project structure; PII in error reports",
        "WordPress": "Plugin vulnerabilities; XML-RPC abuse; wp-config exposure",
        "Shopify": "Checkout manipulation; gift card brute force",
        "Heroku": "Subdomain takeover if app deleted; environment variable exposure",
        "Vercel": "Deployment URL enumeration; serverless function timeout abuse",
        "Netlify": "Deploy preview access to unpublished content; redirect abuse",
    }

    def analyze_headers(self, headers: dict[str, str]) -> list[SupplyChainEntry]:
        """Detect third-party services from HTTP response headers."""
        entries = []
        headers_lower = {k.lower(): v for k, v in headers.items()}

        for header_key, service_info in self._HEADER_SERVICES.items():
            if header_key.lower() in headers_lower:
                service_name = service_info["service"]
                entry = SupplyChainEntry(
                    service_name=service_name,
                    category=service_info["category"],
                    detected_via="header",
                    evidence=f"{header_key}: {headers_lower[header_key.lower()][:100]}",
                    risk_notes=self._SERVICE_RISKS.get(service_name, ""),
                )
                entries.append(entry)

        # Server header
        server = headers_lower.get("server", "")
        if server:
            entries.append(SupplyChainEntry(
                service_name=server.split("/")[0],
                category="server",
                detected_via="header",
                evidence=f"Server: {server}",
            ))

        # X-Powered-By
        powered = headers_lower.get("x-powered-by", "")
        if powered:
            entries.append(SupplyChainEntry(
                service_name=powered,
                category="framework",
                detected_via="header",
                evidence=f"X-Powered-By: {powered}",
            ))

        return entries

    def analyze_html(self, html: str, base_url: str = "") -> list[SupplyChainEntry]:
        """Detect third-party services from HTML content (JS includes, meta tags)."""
        entries = []

        for pattern, service_info in self._JS_SERVICES.items():
            if re.search(pattern, html, re.IGNORECASE):
                service_name = service_info["service"]
                # Find the actual script tag for evidence
                match = re.search(
                    rf'<script[^>]*src=["\']([^"\']*{pattern}[^"\']*)["\']',
                    html, re.IGNORECASE,
                )
                evidence = match.group(1)[:200] if match else f"Pattern: {pattern}"
                entries.append(SupplyChainEntry(
                    service_name=service_name,
                    category=service_info["category"],
                    detected_via="js_include",
                    evidence=evidence,
                    risk_notes=self._SERVICE_RISKS.get(service_name, ""),
                    url=match.group(1) if match else "",
                ))

        # Meta tags
        meta_generators = re.findall(
            r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        for gen in meta_generators:
            entries.append(SupplyChainEntry(
                service_name=gen,
                category="cms",
                detected_via="html_meta",
                evidence=f'<meta name="generator" content="{gen}">',
                risk_notes=self._SERVICE_RISKS.get(gen.split("/")[0], ""),
            ))

        return entries

    def analyze_cookies(self, cookies: dict[str, str]) -> list[SupplyChainEntry]:
        """Detect third-party services from cookies."""
        entries = []
        for cookie_name, service_info in self._COOKIE_SERVICES.items():
            if cookie_name in cookies:
                entries.append(SupplyChainEntry(
                    service_name=service_info["service"],
                    category=service_info["category"],
                    detected_via="cookie",
                    evidence=f"Cookie: {cookie_name}",
                    risk_notes=self._SERVICE_RISKS.get(service_info["service"], ""),
                ))
        return entries

    def full_analysis(
        self,
        headers: dict[str, str],
        html: str = "",
        cookies: dict[str, str] | None = None,
    ) -> list[SupplyChainEntry]:
        """Run full supply chain analysis from all available sources."""
        entries = []
        entries.extend(self.analyze_headers(headers))
        if html:
            entries.extend(self.analyze_html(html))
        if cookies:
            entries.extend(self.analyze_cookies(cookies))

        # Deduplicate by service name
        seen: set[str] = set()
        unique: list[SupplyChainEntry] = []
        for entry in entries:
            if entry.service_name not in seen:
                seen.add(entry.service_name)
                unique.append(entry)

        return unique


# ---------------------------------------------------------------------------
# 3. Breach Intelligence Checker
# ---------------------------------------------------------------------------

class BreachIntelligenceChecker:
    """Check if target appears in known breach databases.

    NOT password cracking. NOT unauthorized access.
    This checks PUBLICLY AVAILABLE breach intelligence:
    - Have I Been Pwned API (public, free tier)
    - Dehashed patterns (domain search)
    - Paste sites (public pastes containing domain emails)
    - Known breach lists (public knowledge)

    Finding that target credentials were in a breach is a FINDING
    in a penetration test report. It means: "Your employees' passwords
    may be compromised. Credential stuffing attacks are likely."
    """

    # Known major breaches (public knowledge, reported by media)
    _KNOWN_BREACHES: list[dict[str, Any]] = [
        {"name": "LinkedIn 2012", "year": 2012, "records": 164_000_000, "type": "password_hash"},
        {"name": "Adobe 2013", "year": 2013, "records": 153_000_000, "type": "email_password"},
        {"name": "Yahoo 2013-2014", "year": 2014, "records": 3_000_000_000, "type": "email_password"},
        {"name": "Dropbox 2012", "year": 2012, "records": 68_000_000, "type": "email_password_hash"},
        {"name": "MySpace 2013", "year": 2013, "records": 360_000_000, "type": "email_password"},
        {"name": "Collection #1 2019", "year": 2019, "records": 773_000_000, "type": "email_password"},
        {"name": "Facebook 2019", "year": 2019, "records": 533_000_000, "type": "phone_email"},
        {"name": "Twitter 2022", "year": 2022, "records": 200_000_000, "type": "email"},
        {"name": "MOVEit 2023", "year": 2023, "records": 77_000_000, "type": "mixed"},
        {"name": "National Public Data 2024", "year": 2024, "records": 2_700_000_000, "type": "ssn_email_phone"},
    ]

    async def check_hibp(self, email: str) -> list[BreachHit]:
        """Check Have I Been Pwned for an email (public API).

        Note: HIBP rate-limits and requires API key for search.
        This method uses the free breach-check endpoint.
        """
        hits = []
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                    headers={
                        "User-Agent": "Daena-Security-Assessment",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    breaches = resp.json()
                    for breach in breaches:
                        hits.append(BreachHit(
                            source="haveibeenpwned",
                            match_type="email",
                            details=f"{breach.get('Name', 'Unknown')}: {breach.get('Description', '')[:200]}",
                            severity="high" if breach.get("IsVerified") else "medium",
                            date=breach.get("BreachDate", ""),
                            affected_records=breach.get("PwnCount", 0),
                        ))
                elif resp.status_code == 404:
                    pass  # Email not found in breaches -- good
                elif resp.status_code == 429:
                    hits.append(BreachHit(
                        source="haveibeenpwned",
                        match_type="rate_limited",
                        details="HIBP rate limited. Retry later or use API key.",
                        severity="info",
                    ))
        except ImportError:
            logger.debug("breach.hibp_requires_httpx")
        except Exception as exc:
            logger.debug("breach.hibp_failed", error=str(exc)[:200])

        return hits

    def check_domain_exposure(self, domain: str) -> list[BreachHit]:
        """Check if a domain is likely affected by known major breaches.

        Uses heuristics: if the target is a large organization,
        their employees almost certainly have personal accounts
        on breached platforms (LinkedIn, Adobe, etc.).
        """
        hits = []

        # Any organization with employees likely has LinkedIn accounts
        hits.append(BreachHit(
            source="known_breach_analysis",
            match_type="domain",
            details=(
                f"Employees of {domain} likely have accounts on breached platforms "
                f"(LinkedIn 2012: 164M, Collection #1: 773M, etc.). "
                f"Password reuse from these breaches may affect corporate accounts. "
                f"Recommend: enforce MFA, check credential stuffing attempts in logs."
            ),
            severity="medium",
            affected_records=0,
        ))

        return hits

    def generate_credential_report(
        self,
        domain: str,
        hibp_results: list[BreachHit],
        known_emails: list[str],
    ) -> dict[str, Any]:
        """Generate a credential exposure report for a domain."""
        report = {
            "domain": domain,
            "emails_checked": len(known_emails),
            "breaches_found": len([h for h in hibp_results if h.match_type == "email"]),
            "total_hits": len(hibp_results),
            "severity_summary": {
                "critical": len([h for h in hibp_results if h.severity == "critical"]),
                "high": len([h for h in hibp_results if h.severity == "high"]),
                "medium": len([h for h in hibp_results if h.severity == "medium"]),
                "low": len([h for h in hibp_results if h.severity == "low"]),
                "info": len([h for h in hibp_results if h.severity == "info"]),
            },
            "recommendation": (
                "Enforce multi-factor authentication on all accounts. "
                "Monitor authentication logs for credential stuffing patterns. "
                "Implement password rotation policy for accounts associated with breached emails."
            ),
            "hits": [
                {
                    "source": h.source,
                    "type": h.match_type,
                    "details": h.details,
                    "severity": h.severity,
                    "date": h.date,
                }
                for h in hibp_results
            ],
        }
        return report


# ---------------------------------------------------------------------------
# 4. Apollo.io Integration (Free tier: 50 credits/month)
# ---------------------------------------------------------------------------

class ApolloIntelligence:
    """Find real business contact info via Apollo.io API.

    Apollo has 275+ million contacts with verified emails and
    direct phone numbers. Free tier gives 50 credits/month.

    What Apollo finds that DNS/GitHub cannot:
    - Verified personal business email (not guessed -- confirmed deliverable)
    - Direct dial phone numbers (office lines, not cell)
    - Mobile phone numbers (for some contacts)
    - Job title, seniority, department
    - Company details (revenue, headcount, industry)
    - LinkedIn URL
    - Tech stack used by the company

    API key goes in .env as APOLLO_API_KEY
    Sign up free: https://app.apollo.io/
    """

    BASE_URL = "https://api.apollo.io/v1"

    def __init__(self) -> None:
        import os
        self._api_key = os.environ.get("APOLLO_API_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search_person(
        self,
        first_name: str = "",
        last_name: str = "",
        domain: str = "",
        title: str = "",
    ) -> list[PersonIntel]:
        """Search for a person in Apollo's database.

        Returns verified contact info including email and phone.
        """
        if not self._api_key:
            return [PersonIntel(
                name=f"{first_name} {last_name}".strip(),
                sources=["apollo_not_configured"],
            )]

        try:
            import httpx

            payload: dict[str, Any] = {
                "api_key": self._api_key,
                "per_page": 5,
            }
            if first_name:
                payload["person_titles"] = [title] if title else []
                # Use people/search endpoint
                search_payload = {
                    "api_key": self._api_key,
                    "q_person_name": f"{first_name} {last_name}".strip(),
                    "per_page": 5,
                }
                if domain:
                    search_payload["q_organization_domains"] = domain

                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{self.BASE_URL}/mixed_people/search",
                        json=search_payload,
                        headers={"Content-Type": "application/json"},
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        people = []
                        for person_data in data.get("people", []):
                            person = self._parse_person(person_data)
                            people.append(person)
                        return people
                    else:
                        logger.debug(
                            "apollo.search_failed",
                            status=resp.status_code,
                            body=resp.text[:200],
                        )
                        return []

        except ImportError:
            logger.debug("apollo.requires_httpx")
        except Exception as exc:
            logger.debug("apollo.search_error", error=str(exc)[:200])

        return []

    async def enrich_email(self, email: str) -> PersonIntel | None:
        """Enrich a known email with full contact details from Apollo."""
        if not self._api_key:
            return None

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/people/match",
                    json={
                        "api_key": self._api_key,
                        "email": email,
                    },
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    person_data = data.get("person")
                    if person_data:
                        return self._parse_person(person_data)

        except Exception as exc:
            logger.debug("apollo.enrich_error", error=str(exc)[:200])

        return None

    async def search_company(self, domain: str) -> dict[str, Any]:
        """Get company intelligence from Apollo."""
        if not self._api_key:
            return {"domain": domain, "source": "apollo_not_configured"}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/organizations/enrich",
                    json={
                        "api_key": self._api_key,
                        "domain": domain,
                    },
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    org = data.get("organization", {})
                    return {
                        "name": org.get("name", ""),
                        "domain": domain,
                        "industry": org.get("industry", ""),
                        "headcount": org.get("estimated_num_employees", 0),
                        "revenue": org.get("annual_revenue_printed", ""),
                        "description": org.get("short_description", ""),
                        "linkedin": org.get("linkedin_url", ""),
                        "twitter": org.get("twitter_url", ""),
                        "phone": org.get("phone", ""),
                        "address": org.get("raw_address", ""),
                        "tech_stack": org.get("current_technologies", []),
                        "funding": org.get("total_funding_printed", ""),
                        "source": "apollo",
                    }

        except Exception as exc:
            logger.debug("apollo.company_error", error=str(exc)[:200])

        return {"domain": domain, "source": "apollo_error"}

    def _parse_person(self, data: dict[str, Any]) -> PersonIntel:
        """Parse Apollo person response into PersonIntel."""
        emails = []
        if data.get("email"):
            emails.append(data["email"])
        # Apollo sometimes has personal email too
        for email_obj in data.get("email_addresses", []):
            if isinstance(email_obj, dict) and email_obj.get("email"):
                emails.append(email_obj["email"])
            elif isinstance(email_obj, str):
                emails.append(email_obj)

        phone_patterns = []
        if data.get("phone_number"):
            phone_patterns.append(data["phone_number"])
        if data.get("sanitized_phone"):
            phone_patterns.append(data["sanitized_phone"])
        for phone_obj in data.get("phone_numbers", []):
            if isinstance(phone_obj, dict):
                num = phone_obj.get("sanitized_number", phone_obj.get("number", ""))
                if num:
                    phone_patterns.append(num)
            elif isinstance(phone_obj, str):
                phone_patterns.append(phone_obj)
        # Direct dial
        if data.get("organization", {}).get("phone"):
            phone_patterns.append(f"company: {data['organization']['phone']}")

        socials: dict[str, str] = {}
        if data.get("linkedin_url"):
            socials["linkedin"] = data["linkedin_url"]
        if data.get("twitter_url"):
            socials["twitter"] = data["twitter_url"]
        if data.get("facebook_url"):
            socials["facebook"] = data["facebook_url"]
        if data.get("github_url"):
            socials["github"] = data["github_url"]

        return PersonIntel(
            name=data.get("name", f"{data.get('first_name', '')} {data.get('last_name', '')}").strip(),
            emails=list(set(emails)),
            phone_patterns=list(set(phone_patterns)),
            social_profiles=socials,
            job_title=data.get("title", ""),
            company=data.get("organization", {}).get("name", ""),
            sources=["apollo"],
        )


# ---------------------------------------------------------------------------
# 5. Hunter.io Integration (Free tier: 25 searches/month)
# ---------------------------------------------------------------------------

class HunterIntelligence:
    """Verify emails and find contacts via Hunter.io API.

    Hunter.io specializes in email finding and verification.
    It tells you which of your generated email candidates are
    REAL deliverable addresses vs. guesses.

    Free tier: 25 searches + 50 verifications per month.
    API key goes in .env as HUNTER_API_KEY
    Sign up free: https://hunter.io/
    """

    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self) -> None:
        import os
        self._api_key = os.environ.get("HUNTER_API_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def domain_search(self, domain: str) -> dict[str, Any]:
        """Find all email addresses associated with a domain.

        Returns verified emails, email pattern, and employee names.
        This is the most powerful Hunter.io feature -- it finds
        emails that exist at a company, not just guesses.
        """
        if not self._api_key:
            return {"domain": domain, "source": "hunter_not_configured", "emails": []}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/domain-search",
                    params={
                        "domain": domain,
                        "api_key": self._api_key,
                        "limit": 20,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    emails_data = data.get("emails", [])
                    emails = []
                    people = []
                    for email_entry in emails_data:
                        email = email_entry.get("value", "")
                        if email:
                            emails.append(email)
                            people.append({
                                "email": email,
                                "first_name": email_entry.get("first_name", ""),
                                "last_name": email_entry.get("last_name", ""),
                                "position": email_entry.get("position", ""),
                                "department": email_entry.get("department", ""),
                                "confidence": email_entry.get("confidence", 0),
                                "sources": email_entry.get("sources", []),
                            })

                    return {
                        "domain": domain,
                        "organization": data.get("organization", ""),
                        "pattern": data.get("pattern", ""),
                        "total_emails": data.get("total", 0),
                        "emails": emails,
                        "people": people,
                        "source": "hunter",
                    }
                else:
                    return {
                        "domain": domain,
                        "source": "hunter_error",
                        "error": resp.text[:200],
                    }

        except Exception as exc:
            logger.debug("hunter.domain_search_error", error=str(exc)[:200])
            return {"domain": domain, "source": "hunter_error"}

    async def verify_email(self, email: str) -> dict[str, Any]:
        """Verify if an email address is real and deliverable.

        Returns: deliverable, undeliverable, risky, or unknown.
        This confirms whether our generated candidates are REAL.
        """
        if not self._api_key:
            return {"email": email, "status": "not_configured"}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/email-verifier",
                    params={
                        "email": email,
                        "api_key": self._api_key,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {
                        "email": email,
                        "status": data.get("status", "unknown"),
                        "result": data.get("result", "unknown"),
                        "score": data.get("score", 0),
                        "disposable": data.get("disposable", False),
                        "webmail": data.get("webmail", False),
                        "mx_records": data.get("mx_records", False),
                        "smtp_server": data.get("smtp_server", False),
                        "smtp_check": data.get("smtp_check", False),
                        "source": "hunter",
                    }

        except Exception as exc:
            logger.debug("hunter.verify_error", error=str(exc)[:200])

        return {"email": email, "status": "error"}

    async def find_email(
        self,
        domain: str,
        first_name: str,
        last_name: str,
    ) -> dict[str, Any]:
        """Find a specific person's email at a company.

        Uses Hunter.io's email finder which checks multiple sources
        and returns the most likely email with confidence score.
        """
        if not self._api_key:
            return {"status": "not_configured"}

        try:
            import httpx

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first_name,
                        "last_name": last_name,
                        "api_key": self._api_key,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return {
                        "email": data.get("email", ""),
                        "confidence": data.get("confidence", 0),
                        "first_name": data.get("first_name", first_name),
                        "last_name": data.get("last_name", last_name),
                        "domain": domain,
                        "position": data.get("position", ""),
                        "twitter": data.get("twitter", ""),
                        "linkedin": data.get("linkedin_url", ""),
                        "phone_number": data.get("phone_number", ""),
                        "company": data.get("company", ""),
                        "sources": [s.get("uri", "") for s in data.get("sources", [])],
                        "source": "hunter",
                    }

        except Exception as exc:
            logger.debug("hunter.find_error", error=str(exc)[:200])

        return {"status": "error"}


# ---------------------------------------------------------------------------
# 6. Full OSINT Pipeline
# ---------------------------------------------------------------------------

class OSINTRecon:
    """Full OSINT pipeline -- runs all intelligence sources in parallel.

    Usage::

        recon = OSINTRecon()
        report = await recon.full_recon_person("Elon", "Musk", "tesla.com")
        report = await recon.full_recon_domain("tesla.com")
    """

    def __init__(self) -> None:
        self.people = OSINTPeopleIntelligence()
        self.apollo = ApolloIntelligence()
        self.hunter = HunterIntelligence()
        self.supply_chain = SupplyChainAnalyzer()
        self.breach = BreachIntelligenceChecker()

    async def full_recon_person(
        self,
        first_name: str,
        last_name: str,
        domain: str,
        title: str = "",
    ) -> dict[str, Any]:
        """Run full OSINT reconnaissance on a person.

        Runs all sources in parallel and merges results.
        """
        import asyncio

        # Generate email candidates (instant)
        email_candidates = self.people.generate_email_candidates(first_name, last_name, domain)

        # Run all async sources in parallel
        tasks = {
            "apollo": self.apollo.search_person(first_name, last_name, domain, title),
            "hunter_find": self.hunter.find_email(domain, first_name, last_name),
            "github": self.people.gather_from_github(domain=domain),
            "dns": self.people.gather_from_dns(domain),
        }

        results = {}
        for name, coro in tasks.items():
            try:
                results[name] = await asyncio.wait_for(coro, timeout=20.0)
            except asyncio.TimeoutError:
                results[name] = {"error": "timeout"}
            except Exception as exc:
                results[name] = {"error": str(exc)[:200]}

        # Merge into unified report
        report: dict[str, Any] = {
            "target": f"{first_name} {last_name}",
            "domain": domain,
            "email_candidates": email_candidates,
            "verified_emails": [],
            "phone_numbers": [],
            "social_profiles": {},
            "job_info": {},
            "organization": {},
            "sources_used": [],
        }

        # Merge Apollo results
        apollo_people = results.get("apollo", [])
        if isinstance(apollo_people, list):
            for person in apollo_people:
                if isinstance(person, PersonIntel):
                    report["verified_emails"].extend(person.emails)
                    report["phone_numbers"].extend(person.phone_patterns)
                    report["social_profiles"].update(person.social_profiles)
                    if person.job_title:
                        report["job_info"]["title"] = person.job_title
                    if person.company:
                        report["job_info"]["company"] = person.company
                    report["sources_used"].append("apollo")

        # Merge Hunter results
        hunter_result = results.get("hunter_find", {})
        if isinstance(hunter_result, dict):
            if hunter_result.get("email"):
                report["verified_emails"].append(hunter_result["email"])
                report["sources_used"].append("hunter")
            if hunter_result.get("phone_number"):
                report["phone_numbers"].append(hunter_result["phone_number"])
            if hunter_result.get("linkedin"):
                report["social_profiles"]["linkedin"] = hunter_result["linkedin"]
            if hunter_result.get("twitter"):
                report["social_profiles"]["twitter"] = hunter_result["twitter"]

        # Merge DNS results
        dns_result = results.get("dns")
        if isinstance(dns_result, OrgIntel):
            report["organization"] = {
                "dns_registrar": dns_result.dns_registrar,
                "tech_stack": dns_result.tech_stack,
                "admin_emails": [
                    e for emp in dns_result.employees for e in emp.emails
                ],
            }
            report["sources_used"].append("dns")

        # Merge GitHub results
        gh_people = results.get("github", [])
        if isinstance(gh_people, list):
            for person in gh_people:
                if isinstance(person, PersonIntel):
                    report["verified_emails"].extend(person.emails)
                    report["social_profiles"].update(person.social_profiles)
                    report["sources_used"].append("github")

        # Deduplicate
        report["verified_emails"] = list(set(report["verified_emails"]))
        report["phone_numbers"] = list(set(report["phone_numbers"]))
        report["sources_used"] = list(set(report["sources_used"]))

        return report

    async def full_recon_domain(self, domain: str) -> dict[str, Any]:
        """Run full OSINT reconnaissance on a domain/organization."""
        import asyncio

        role_emails = self.people.generate_role_emails(domain)

        tasks = {
            "hunter_domain": self.hunter.domain_search(domain),
            "apollo_company": self.apollo.search_company(domain),
            "dns": self.people.gather_from_dns(domain),
            "breach": asyncio.coroutine(lambda: self.breach.check_domain_exposure(domain))()
            if False else asyncio.sleep(0),  # breach check is sync
        }

        results = {}
        for name, coro in tasks.items():
            try:
                results[name] = await asyncio.wait_for(coro, timeout=20.0)
            except Exception as exc:
                results[name] = {"error": str(exc)[:200]}

        # Run sync breach check
        breach_hits = self.breach.check_domain_exposure(domain)

        report: dict[str, Any] = {
            "domain": domain,
            "role_emails": role_emails,
            "hunter_results": results.get("hunter_domain", {}),
            "apollo_company": results.get("apollo_company", {}),
            "dns_intel": {},
            "breach_intelligence": [
                {"source": h.source, "details": h.details, "severity": h.severity}
                for h in breach_hits
            ],
            "sources_used": [],
        }

        dns_result = results.get("dns")
        if isinstance(dns_result, OrgIntel):
            report["dns_intel"] = {
                "registrar": dns_result.dns_registrar,
                "tech_stack": dns_result.tech_stack,
                "admin_emails": [e for emp in dns_result.employees for e in emp.emails],
            }

        return report
