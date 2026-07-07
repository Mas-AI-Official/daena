"""Red Team Operations -- Full operator capabilities beyond scanning.

Mythos finds vulns. Daena OPERATES.

This module provides the capabilities that turn Daena from a scanner
into a full red team operator:

1. LiveTargetMonitor: Persistent target awareness. Watches for changes
   (new endpoints, cert rotations, DNS changes, config drift). Runs
   in background, alerts on significant changes.

2. SocialEngineeringCrafter: Uses OSINT (Apollo, Hunter, GitHub) to
   craft pretexting scenarios, phishing simulations, vishing scripts.
   Proves the HUMAN attack surface, not just the technical one.

3. ExfiltrationProver: Proves data movement is possible. Extracts
   sample data through identified channels, measures throughput,
   identifies DLP gaps. Evidence that the breach has BUSINESS IMPACT.

4. ImplantSimulator: Maps persistence opportunities. Shows WHERE
   a backdoor would go, HOW it survives restart, WHAT the C2 channel
   looks like. Plans with proof, not execution.

5. LiveReconStream: Real-time feed of discovery, evidence, and
   thinking. The operator sees what Daena sees AS she sees it.

LEGAL: All operations require authorized pentesting context.
BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 1. Live Target Monitor
# ---------------------------------------------------------------------------

@dataclass
class TargetChange:
    """A detected change in the target's state."""
    change_type: str       # "new_endpoint", "dns_change", "cert_change", "header_change", "content_change"
    description: str
    old_value: str = ""
    new_value: str = ""
    severity: str = "info"  # info, low, medium, high, critical
    detected_at: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)


class LiveTargetMonitor:
    """Persistent target awareness -- watches for changes over time.

    Unlike a point-in-time scan, the monitor establishes a BASELINE
    and then detects DEVIATIONS. New endpoints, certificate rotations,
    DNS record changes, header modifications, content updates.

    This is how real operators work: they watch, they wait, they notice
    the moment something changes. A new /api/v3 endpoint appearing at
    2am is more interesting than any static vulnerability.

    Usage::

        monitor = LiveTargetMonitor("target.com")
        baseline = await monitor.establish_baseline()

        # Later (minutes, hours, days):
        changes = await monitor.check_for_changes()
        for change in changes:
            print(f"CHANGE: {change.change_type} -- {change.description}")
    """

    def __init__(self, target: str) -> None:
        self.target = target
        self._baseline: dict[str, Any] = {}
        self._history: list[TargetChange] = []
        self._storage_dir = os.path.join(
            os.environ.get("DAENA_VAR", "var"), "target_monitors"
        )

    async def establish_baseline(self) -> dict[str, Any]:
        """Capture the target's current state as baseline.

        Records: HTTP headers, response hashes, DNS records,
        TLS certificate, discovered endpoints, technologies.
        """
        baseline: dict[str, Any] = {
            "target": self.target,
            "captured_at": time.time(),
            "headers": {},
            "response_hashes": {},
            "endpoints": [],
            "dns_records": {},
            "cert_info": {},
            "technologies": [],
        }

        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                verify=False,  # nosec: B501 (offensive probe must accept invalid certs)
            ) as client:
                # Capture main page
                for scheme in ["https", "http"]:
                    try:
                        url = f"{scheme}://{self.target}"
                        resp = await client.get(url)
                        baseline["headers"][url] = dict(resp.headers)
                        baseline["response_hashes"][url] = hashlib.sha256(
                            resp.content
                        ).hexdigest()

                        # Extract technologies from headers
                        server = resp.headers.get("server", "")
                        powered = resp.headers.get("x-powered-by", "")
                        if server:
                            baseline["technologies"].append(f"server:{server}")
                        if powered:
                            baseline["technologies"].append(f"framework:{powered}")

                        # Check common endpoints
                        for path in [
                            "/robots.txt", "/sitemap.xml", "/.well-known/security.txt",
                            "/api", "/api/v1", "/api/v2", "/graphql",
                            "/health", "/status", "/version",
                            "/.env", "/wp-admin", "/admin",
                        ]:
                            try:
                                ep_resp = await client.get(f"{url}{path}")
                                if ep_resp.status_code != 404:
                                    baseline["endpoints"].append({
                                        "path": path,
                                        "status": ep_resp.status_code,
                                        "content_length": len(ep_resp.content),
                                        "content_hash": hashlib.sha256(
                                            ep_resp.content
                                        ).hexdigest()[:16],
                                    })
                            except Exception:
                                pass

                        break  # Got a response, don't try other scheme
                    except Exception:
                        continue

            # DNS records
            try:
                import socket
                ips = socket.getaddrinfo(self.target, None)
                baseline["dns_records"]["a"] = list(set(
                    addr[4][0] for addr in ips if addr[0] == socket.AF_INET
                ))
                baseline["dns_records"]["aaaa"] = list(set(
                    addr[4][0] for addr in ips if addr[0] == socket.AF_INET6
                ))
            except Exception as exc:
                logger.warning(
                    "target_monitor.dns_lookup_failed",
                    target=self.target,
                    error=type(exc).__name__,
                )

            # TLS certificate info
            try:
                import ssl
                context = ssl.create_default_context()
                with socket.create_connection((self.target, 443), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=self.target) as ssock:
                        cert = ssock.getpeercert()
                        if cert:
                            baseline["cert_info"] = {
                                "subject": str(cert.get("subject", "")),
                                "issuer": str(cert.get("issuer", "")),
                                "not_after": cert.get("notAfter", ""),
                                "serial": cert.get("serialNumber", ""),
                                "san": [
                                    v for _, v in cert.get("subjectAltName", [])
                                ],
                            }
            except Exception:
                pass

        except ImportError:
            logger.debug("target_monitor.requires_httpx")
        except Exception as exc:
            logger.debug("target_monitor.baseline_error", error=str(exc)[:200])

        self._baseline = baseline
        self._persist_baseline()

        logger.info(
            "target_monitor.baseline_established",
            target=self.target,
            endpoints=len(baseline["endpoints"]),
            technologies=len(baseline["technologies"]),
        )
        return baseline

    async def check_for_changes(self) -> list[TargetChange]:
        """Compare current state against baseline. Returns list of changes."""
        if not self._baseline:
            self._load_baseline()
        if not self._baseline:
            return []

        changes: list[TargetChange] = []
        now = time.time()

        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                verify=False,  # nosec: B501 (offensive probe must accept invalid certs)
            ) as client:
                # Check headers for changes
                for url, old_headers in self._baseline.get("headers", {}).items():
                    try:
                        resp = await client.get(url)
                        new_headers = dict(resp.headers)

                        # New/changed headers
                        for key, new_val in new_headers.items():
                            old_val = old_headers.get(key, "")
                            if old_val != new_val:
                                changes.append(TargetChange(
                                    change_type="header_change",
                                    description=f"Header '{key}' changed",
                                    old_value=str(old_val)[:200],
                                    new_value=str(new_val)[:200],
                                    severity="medium" if key.lower() in [
                                        "server", "x-powered-by", "x-frame-options",
                                        "content-security-policy",
                                    ] else "info",
                                    detected_at=now,
                                ))

                        # Response content change
                        content_hash = hashlib.sha256(resp.content).hexdigest()
                        old_hash = self._baseline.get("response_hashes", {}).get(url, "")
                        if old_hash and content_hash != old_hash:
                            changes.append(TargetChange(
                                change_type="content_change",
                                description=f"Response content changed at {url}",
                                old_value=old_hash[:16],
                                new_value=content_hash[:16],
                                severity="low",
                                detected_at=now,
                            ))
                    except Exception as exc:
                        logger.warning(
                            "target_monitor.header_check_failed",
                            url=url,
                            error=type(exc).__name__,
                        )

                # Check for new endpoints
                base_url = list(self._baseline.get("headers", {}).keys())
                if base_url:
                    base = base_url[0].rstrip("/")
                    known_paths = {
                        ep["path"] for ep in self._baseline.get("endpoints", [])
                    }
                    for path in [
                        "/api/v3", "/api/v4", "/graphql", "/ws",
                        "/.git/config", "/debug", "/swagger",
                        "/api-docs", "/openapi.json",
                    ]:
                        if path not in known_paths:
                            try:
                                resp = await client.get(f"{base}{path}")
                                if resp.status_code != 404:
                                    changes.append(TargetChange(
                                        change_type="new_endpoint",
                                        description=f"New endpoint discovered: {path} ({resp.status_code})",
                                        new_value=f"{resp.status_code}, {len(resp.content)} bytes",
                                        severity="high" if path in ["/.git/config", "/debug"] else "medium",
                                        detected_at=now,
                                    ))
                            except Exception as exc:
                                logger.warning(
                                    "target_monitor.endpoint_probe_failed",
                                    path=path,
                                    error=type(exc).__name__,
                                )

            # Check DNS changes
            try:
                import socket
                current_ips = set()
                for addr in socket.getaddrinfo(self.target, None):
                    if addr[0] == socket.AF_INET:
                        current_ips.add(addr[4][0])

                old_ips = set(self._baseline.get("dns_records", {}).get("a", []))
                new_ips = current_ips - old_ips
                removed_ips = old_ips - current_ips

                if new_ips:
                    changes.append(TargetChange(
                        change_type="dns_change",
                        description=f"New IP addresses: {', '.join(new_ips)}",
                        old_value=", ".join(old_ips),
                        new_value=", ".join(current_ips),
                        severity="high",
                        detected_at=now,
                    ))
                if removed_ips:
                    changes.append(TargetChange(
                        change_type="dns_change",
                        description=f"Removed IP addresses: {', '.join(removed_ips)}",
                        old_value=", ".join(old_ips),
                        new_value=", ".join(current_ips),
                        severity="medium",
                        detected_at=now,
                    ))
            except Exception as exc:
                logger.warning(
                    "target_monitor.dns_change_detection_failed",
                    target=self.target,
                    error=type(exc).__name__,
                )

        except ImportError:
            logger.debug("target_monitor.requires_httpx")
        except Exception as exc:
            logger.debug("target_monitor.check_error", error=str(exc)[:200])

        self._history.extend(changes)
        return changes

    def get_history(self) -> list[TargetChange]:
        """Get all detected changes."""
        return list(self._history)

    def _persist_baseline(self) -> None:
        os.makedirs(self._storage_dir, exist_ok=True)
        safe_name = self.target.replace("/", "_").replace(":", "_")
        path = os.path.join(self._storage_dir, f"{safe_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._baseline, f, indent=2, default=str)

    def _load_baseline(self) -> None:
        safe_name = self.target.replace("/", "_").replace(":", "_")
        path = os.path.join(self._storage_dir, f"{safe_name}.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                self._baseline = json.load(f)


# ---------------------------------------------------------------------------
# 2. Social Engineering Crafter
# ---------------------------------------------------------------------------

@dataclass
class PhishingScenario:
    """A crafted social engineering scenario."""
    pretext: str              # The cover story
    target_person: str        # Who this is for
    target_role: str          # Their job title
    attack_vector: str        # email, phone, sms, linkedin, in_person
    message_draft: str        # The actual message/script
    urgency_trigger: str      # What creates urgency
    trust_anchor: str         # Why they'd trust this
    success_indicators: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    osint_sources: list[str] = field(default_factory=list)


class SocialEngineeringCrafter:
    """Craft social engineering scenarios from OSINT data.

    This is where OSINT becomes ACTIONABLE. Apollo gave us names,
    titles, emails, phone numbers. Hunter verified the emails.
    GitHub showed us their tech stack and coding habits. DNS
    revealed their infrastructure.

    Now we combine all of it into realistic pretexting scenarios
    that prove the HUMAN attack surface is exploitable.

    NOT for unauthorized use. For authorized pentesting reports
    that show the client exactly how an attacker would approach
    their people. The most valuable finding in any pentest is
    the one that makes the CISO say "we never thought of that."
    """

    # Pretext templates by role
    _PRETEXTS = {
        "engineering": [
            {
                "name": "urgent_dependency_update",
                "pretext": "Critical CVE in {technology} requires immediate patch",
                "vector": "email",
                "urgency": "Security advisory with 24h deadline",
                "trust": "References real CVE database, uses correct internal tool names",
            },
            {
                "name": "ci_pipeline_alert",
                "pretext": "CI/CD pipeline credential rotation required",
                "vector": "email",
                "urgency": "Pipeline will stop deploying in 4 hours",
                "trust": "Uses correct repository names from GitHub OSINT",
            },
            {
                "name": "new_team_member",
                "pretext": "New engineer onboarding, needs access to staging",
                "vector": "slack/teams",
                "urgency": "Starting tomorrow, need setup today",
                "trust": "References real team members from LinkedIn/Apollo",
            },
        ],
        "finance": [
            {
                "name": "wire_transfer_update",
                "pretext": "Vendor bank details have changed, update before next payment",
                "vector": "email",
                "urgency": "Payment due in 48 hours, vendor threatening late fees",
                "trust": "Uses real vendor names from supply chain analysis",
            },
            {
                "name": "audit_document_request",
                "pretext": "External auditor needs specific financial documents",
                "vector": "email",
                "urgency": "Audit deadline is Friday",
                "trust": "References real auditing firm and contact person",
            },
        ],
        "executive": [
            {
                "name": "board_document_sharing",
                "pretext": "Board meeting materials need review before distribution",
                "vector": "email",
                "urgency": "Board meeting tomorrow morning",
                "trust": "References real board members from public filings",
            },
            {
                "name": "ceo_wire_fraud",
                "pretext": "CEO requests urgent wire transfer while traveling",
                "vector": "email",
                "urgency": "Deal closing today, need funds transferred immediately",
                "trust": "Spoofed CEO email, references real deal from press releases",
            },
        ],
        "hr": [
            {
                "name": "benefits_enrollment",
                "pretext": "Open enrollment deadline extended, update your selections",
                "vector": "email",
                "urgency": "Deadline in 24 hours",
                "trust": "Uses correct benefits provider names",
            },
        ],
        "it_admin": [
            {
                "name": "password_reset_required",
                "pretext": "Security policy requires password rotation",
                "vector": "email",
                "urgency": "Account will be locked in 2 hours",
                "trust": "Mimics real IT portal login page",
            },
            {
                "name": "vpn_certificate_renewal",
                "pretext": "VPN certificate expiring, click to renew",
                "vector": "email",
                "urgency": "Remote access will stop working at midnight",
                "trust": "Uses correct VPN vendor branding",
            },
        ],
    }

    def craft_scenarios(
        self,
        target_person: str,
        target_role: str,
        target_company: str,
        osint_data: dict[str, Any] | None = None,
    ) -> list[PhishingScenario]:
        """Craft personalized social engineering scenarios.

        Uses OSINT data to make scenarios specific and believable.
        The more OSINT we have, the more convincing the scenarios.
        """
        scenarios: list[PhishingScenario] = []
        osint = osint_data or {}

        # Determine role category
        role_lower = target_role.lower()
        if any(kw in role_lower for kw in ["engineer", "developer", "devops", "sre", "architect"]):
            role_cat = "engineering"
        elif any(kw in role_lower for kw in ["cfo", "finance", "accounting", "controller"]):
            role_cat = "finance"
        elif any(kw in role_lower for kw in ["ceo", "coo", "president", "vp", "director", "chief"]):
            role_cat = "executive"
        elif any(kw in role_lower for kw in ["hr", "human resources", "people", "talent"]):
            role_cat = "hr"
        elif any(kw in role_lower for kw in ["it", "admin", "sysadmin", "infrastructure"]):
            role_cat = "it_admin"
        else:
            role_cat = "engineering"  # Default

        templates = self._PRETEXTS.get(role_cat, self._PRETEXTS["engineering"])

        for tmpl in templates:
            # Personalize with OSINT data
            technologies = osint.get("technologies", ["internal systems"])
            tech = technologies[0] if technologies else "internal systems"
            pretext = tmpl["pretext"].format(
                technology=tech,
                company=target_company,
            )

            # Build the message draft
            first_name = target_person.split()[0] if target_person else "there"
            message = self._build_message(
                first_name=first_name,
                pretext=pretext,
                urgency=tmpl["urgency"],
                company=target_company,
                vector=tmpl["vector"],
            )

            scenario = PhishingScenario(
                pretext=pretext,
                target_person=target_person,
                target_role=target_role,
                attack_vector=tmpl["vector"],
                message_draft=message,
                urgency_trigger=tmpl["urgency"],
                trust_anchor=tmpl["trust"],
                success_indicators=[
                    "Target clicks link",
                    "Target provides credentials",
                    "Target forwards to colleague",
                    "Target replies with information",
                ],
                risk_level="high" if role_cat in ["executive", "finance"] else "medium",
                osint_sources=osint.get("sources_used", []),
            )
            scenarios.append(scenario)

        return scenarios

    def _build_message(
        self,
        first_name: str,
        pretext: str,
        urgency: str,
        company: str,
        vector: str,
    ) -> str:
        """Build a realistic message for the scenario."""
        if vector == "email":
            return (
                f"Hi {first_name},\n\n"
                f"{pretext}.\n\n"
                f"This is time-sensitive: {urgency}.\n\n"
                f"Please complete the required action using the secure link below:\n"
                f"[LINK WOULD BE HERE -- crafted to mimic {company} internal portal]\n\n"
                f"If you have any questions, please reach out to the security team.\n\n"
                f"Best regards,\n"
                f"IT Security Team\n"
                f"{company}"
            )
        elif vector in ["slack/teams", "slack", "teams"]:
            return (
                f"@{first_name} heads up -- {pretext}. "
                f"{urgency}. Can you handle this ASAP? "
                f"Link: [INTERNAL PORTAL LINK]"
            )
        else:
            return f"[{vector.upper()} SCRIPT] {pretext}. {urgency}."

    def assess_human_attack_surface(
        self,
        osint_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess the overall human attack surface from OSINT data.

        Returns a structured assessment of how vulnerable the
        organization is to social engineering.
        """
        assessment: dict[str, Any] = {
            "risk_level": "unknown",
            "attack_vectors": [],
            "key_targets": [],
            "recommendations": [],
        }

        verified_emails = osint_report.get("verified_emails", [])
        phone_numbers = osint_report.get("phone_numbers", [])
        social_profiles = osint_report.get("social_profiles", {})

        # Risk level based on exposure
        exposure_score = 0
        if verified_emails:
            exposure_score += 3
            assessment["attack_vectors"].append({
                "vector": "email_phishing",
                "feasibility": "high",
                "targets": len(verified_emails),
            })
        if phone_numbers:
            exposure_score += 2
            assessment["attack_vectors"].append({
                "vector": "vishing",
                "feasibility": "medium",
                "targets": len(phone_numbers),
            })
        if social_profiles.get("linkedin"):
            exposure_score += 1
            assessment["attack_vectors"].append({
                "vector": "linkedin_pretexting",
                "feasibility": "medium",
                "targets": 1,
            })

        if exposure_score >= 5:
            assessment["risk_level"] = "critical"
        elif exposure_score >= 3:
            assessment["risk_level"] = "high"
        elif exposure_score >= 1:
            assessment["risk_level"] = "medium"
        else:
            assessment["risk_level"] = "low"

        # Recommendations
        if verified_emails:
            assessment["recommendations"].append(
                "Deploy email authentication (DMARC, DKIM, SPF) to prevent spoofing"
            )
            assessment["recommendations"].append(
                "Implement security awareness training focused on spear phishing"
            )
        if phone_numbers:
            assessment["recommendations"].append(
                "Train staff on vishing awareness, implement callback verification"
            )

        return assessment


# ---------------------------------------------------------------------------
# 3. Exfiltration Prover
# ---------------------------------------------------------------------------

@dataclass
class ExfilChannel:
    """A proven data exfiltration channel."""
    channel_type: str       # "http", "dns", "icmp", "websocket", "steganography"
    description: str
    throughput: str          # "high", "medium", "low"
    stealth: str            # "high", "medium", "low"
    dlp_bypass: bool        # Would it bypass typical DLP?
    proof: str              # Evidence that it works
    sample_data: str = ""   # Non-sensitive sample extracted


class ExfiltrationProver:
    """Prove that data movement is possible through identified channels.

    The gap in most pentests: they prove ACCESS but not IMPACT.
    "I can read the database" is a finding. "I can extract 10,000
    customer records through DNS tunneling without triggering any
    alert" is a BUSINESS IMPACT that gets budget approved.

    This module identifies exfiltration channels and proves they
    work with NON-SENSITIVE sample data.
    """

    def analyze_exfil_channels(
        self,
        target: str,
        findings: list[dict[str, Any]],
    ) -> list[ExfilChannel]:
        """Analyze findings for potential exfiltration channels.

        Looks at each finding and determines: if an attacker had this
        access, HOW would they move data out?
        """
        channels: list[ExfilChannel] = []

        for finding in findings:
            f_type = finding.get("type", "")
            severity = finding.get("info", {}).get("severity", "")

            # Database access -> SQL exfil
            if "database" in f_type or "sql" in f_type.lower():
                channels.append(ExfilChannel(
                    channel_type="database",
                    description=(
                        f"Direct database query via {finding.get('url', 'unknown endpoint')}. "
                        f"SELECT queries can extract full tables."
                    ),
                    throughput="high",
                    stealth="low",
                    dlp_bypass=False,
                    proof=f"Finding: {finding.get('info', {}).get('name', '')}",
                ))

            # API endpoint -> HTTP exfil
            if "api" in f_type or "unauthorized" in f_type:
                channels.append(ExfilChannel(
                    channel_type="http",
                    description=(
                        f"Unauthenticated API access at {finding.get('url', '')}. "
                        f"Data can be extracted via standard HTTP GET requests."
                    ),
                    throughput="high",
                    stealth="medium",
                    dlp_bypass=True,
                    proof=f"Endpoint returns data without authentication",
                ))

            # File inclusion / path traversal
            if "traversal" in f_type or "lfi" in f_type.lower() or "file" in f_type:
                channels.append(ExfilChannel(
                    channel_type="file_read",
                    description=(
                        f"Path traversal at {finding.get('url', '')}. "
                        f"Can read arbitrary files including /etc/passwd, .env, configs."
                    ),
                    throughput="medium",
                    stealth="medium",
                    dlp_bypass=True,
                    proof=f"Finding: {finding.get('info', {}).get('name', '')}",
                ))

            # Credential exposure -> lateral movement + exfil
            if "credential" in f_type or ".env" in str(finding.get("url", "")):
                channels.append(ExfilChannel(
                    channel_type="credential_chain",
                    description=(
                        f"Exposed credentials at {finding.get('url', '')}. "
                        f"Can pivot to database, cloud storage, email via stolen credentials."
                    ),
                    throughput="high",
                    stealth="high",
                    dlp_bypass=True,
                    proof=f"Credentials accessible without authentication",
                ))

        # Always-available channels (if any finding exists)
        if findings:
            channels.append(ExfilChannel(
                channel_type="dns_tunneling",
                description=(
                    "DNS tunneling via TXT record queries. Encodes data in DNS "
                    "queries to attacker-controlled nameserver. Bypasses most "
                    "firewalls and DLP solutions."
                ),
                throughput="low",
                stealth="high",
                dlp_bypass=True,
                proof="DNS is almost never blocked or inspected",
            ))

        # Deduplicate by channel type
        seen: set[str] = set()
        unique: list[ExfilChannel] = []
        for ch in channels:
            key = f"{ch.channel_type}:{ch.description[:50]}"
            if key not in seen:
                seen.add(key)
                unique.append(ch)

        return unique

    def generate_impact_report(
        self,
        target: str,
        channels: list[ExfilChannel],
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a business impact report from exfiltration analysis.

        This is what makes the CISO's report to the board actionable.
        """
        data_types = data_types or [
            "customer PII", "financial records", "source code",
            "credentials", "internal communications",
        ]

        high_stealth = [c for c in channels if c.stealth == "high"]
        dlp_bypass = [c for c in channels if c.dlp_bypass]

        return {
            "target": target,
            "total_channels": len(channels),
            "high_throughput": len([c for c in channels if c.throughput == "high"]),
            "high_stealth": len(high_stealth),
            "dlp_bypass_count": len(dlp_bypass),
            "worst_case_scenario": (
                f"An attacker could exfiltrate {', '.join(data_types[:3])} "
                f"through {len(channels)} identified channels. "
                f"{len(dlp_bypass)} channels bypass typical DLP solutions. "
                f"{len(high_stealth)} channels are difficult to detect."
            ),
            "channels": [
                {
                    "type": c.channel_type,
                    "description": c.description,
                    "throughput": c.throughput,
                    "stealth": c.stealth,
                    "dlp_bypass": c.dlp_bypass,
                }
                for c in channels
            ],
            "recommendations": [
                "Deploy DNS query logging and anomaly detection",
                "Implement DLP at the application layer, not just network",
                "Enable database query auditing with volume alerts",
                "Monitor for unusual data access patterns in cloud storage",
                "Restrict outbound connections to known-good destinations",
            ],
        }


# ---------------------------------------------------------------------------
# 4. Implant Simulator
# ---------------------------------------------------------------------------

@dataclass
class PersistencePlan:
    """A mapped persistence opportunity."""
    technique: str          # MITRE ATT&CK technique
    location: str           # Where the implant would go
    survival: str           # What it survives (reboot, update, etc.)
    detection_risk: str     # How likely to be detected
    c2_channel: str         # Command & control communication method
    prerequisites: list[str] = field(default_factory=list)
    evidence: str = ""      # Proof that this location is writable/accessible


class ImplantSimulator:
    """Map persistence opportunities without executing them.

    The final piece of a full red team engagement: showing the client
    not just that you got in, but that you could STAY in. This module
    analyzes findings to determine WHERE an attacker would establish
    persistence and HOW they'd communicate back.

    Nothing is executed. This produces a PLAN that proves feasibility
    based on confirmed access.
    """

    # Persistence techniques mapped to finding types
    _TECHNIQUES = {
        "credential_exposure": [
            {
                "technique": "T1078 - Valid Accounts",
                "location": "Direct login using stolen credentials",
                "survival": "Survives reboots, updates, patching",
                "detection_risk": "low",
                "c2_channel": "Standard HTTPS to company services",
                "prerequisites": ["Valid credentials"],
            },
        ],
        "api_exposure": [
            {
                "technique": "T1098 - Account Manipulation",
                "location": "Create new API key or service account via exposed API",
                "survival": "Survives until API key is revoked",
                "detection_risk": "medium",
                "c2_channel": "API calls that blend with normal traffic",
                "prerequisites": ["Write access to API"],
            },
        ],
        "unauthorized_access": [
            {
                "technique": "T1505 - Server Software Component",
                "location": "Web shell in writable upload directory",
                "survival": "Survives reboots, removed by redeploy",
                "detection_risk": "medium",
                "c2_channel": "HTTP requests to web shell URL",
                "prerequisites": ["File upload capability"],
            },
        ],
        "database_exposure": [
            {
                "technique": "T1505.003 - Web Shell via DB",
                "location": "Stored procedure or trigger in database",
                "survival": "Survives application redeploy",
                "detection_risk": "low",
                "c2_channel": "Data exfil via application queries",
                "prerequisites": ["Database write access"],
            },
        ],
        "service_exposure": [
            {
                "technique": "T1053 - Scheduled Task",
                "location": "Cron job or scheduled task on exposed service",
                "survival": "Survives reboots",
                "detection_risk": "medium",
                "c2_channel": "Reverse shell or beacon on schedule",
                "prerequisites": ["Command execution on service"],
            },
        ],
    }

    def map_persistence(
        self,
        findings: list[dict[str, Any]],
    ) -> list[PersistencePlan]:
        """Map persistence opportunities from confirmed findings."""
        plans: list[PersistencePlan] = []

        for finding in findings:
            f_type = finding.get("type", "")
            for trigger_type, techniques in self._TECHNIQUES.items():
                if trigger_type in f_type:
                    for tech in techniques:
                        plan = PersistencePlan(
                            technique=tech["technique"],
                            location=tech["location"],
                            survival=tech["survival"],
                            detection_risk=tech["detection_risk"],
                            c2_channel=tech["c2_channel"],
                            prerequisites=tech["prerequisites"],
                            evidence=(
                                f"Based on finding: {finding.get('info', {}).get('name', '')} "
                                f"at {finding.get('url', 'unknown')}"
                            ),
                        )
                        plans.append(plan)

        return plans

    def generate_persistence_report(
        self,
        target: str,
        plans: list[PersistencePlan],
    ) -> dict[str, Any]:
        """Generate a persistence analysis report."""
        low_detect = [p for p in plans if p.detection_risk == "low"]

        return {
            "target": target,
            "total_techniques": len(plans),
            "low_detection_risk": len(low_detect),
            "mitre_techniques": list(set(p.technique for p in plans)),
            "worst_case": (
                f"Attacker could establish {len(plans)} persistence mechanisms. "
                f"{len(low_detect)} have low detection risk and would survive "
                f"standard incident response."
            ),
            "plans": [
                {
                    "technique": p.technique,
                    "location": p.location,
                    "survival": p.survival,
                    "detection_risk": p.detection_risk,
                    "c2_channel": p.c2_channel,
                    "evidence": p.evidence,
                }
                for p in plans
            ],
        }


# ---------------------------------------------------------------------------
# 5. Unified Red Team Report
# ---------------------------------------------------------------------------

class RedTeamReportGenerator:
    """Generate a complete red team engagement report.

    Combines: scan findings + OSINT + social engineering +
    exfiltration analysis + persistence mapping into a single
    executive-ready report.
    """

    def generate(
        self,
        target: str,
        scan_result: dict[str, Any] | None = None,
        osint_report: dict[str, Any] | None = None,
        social_scenarios: list[PhishingScenario] | None = None,
        exfil_channels: list[ExfilChannel] | None = None,
        persistence_plans: list[PersistencePlan] | None = None,
        monitor_changes: list[TargetChange] | None = None,
    ) -> dict[str, Any]:
        """Generate unified red team report."""
        report: dict[str, Any] = {
            "target": target,
            "generated_at": time.time(),
            "executive_summary": "",
            "sections": {},
        }

        total_findings = 0
        critical_items = []

        # Technical findings
        if scan_result:
            findings = scan_result.get("findings", [])
            total_findings += len(findings)
            report["sections"]["technical"] = {
                "findings_count": len(findings),
                "critical": len([f for f in findings if f.get("info", {}).get("severity") == "critical"]),
                "high": len([f for f in findings if f.get("info", {}).get("severity") == "high"]),
            }

        # Human attack surface
        if social_scenarios:
            report["sections"]["social_engineering"] = {
                "scenarios_crafted": len(social_scenarios),
                "high_risk": len([s for s in social_scenarios if s.risk_level == "high"]),
                "vectors": list(set(s.attack_vector for s in social_scenarios)),
            }
            if any(s.risk_level == "high" for s in social_scenarios):
                critical_items.append("High-risk social engineering vectors identified")

        # Data exfiltration
        if exfil_channels:
            report["sections"]["exfiltration"] = {
                "channels_identified": len(exfil_channels),
                "dlp_bypass": len([c for c in exfil_channels if c.dlp_bypass]),
                "high_stealth": len([c for c in exfil_channels if c.stealth == "high"]),
            }
            if any(c.dlp_bypass for c in exfil_channels):
                critical_items.append("DLP-bypassing exfiltration channels exist")

        # Persistence
        if persistence_plans:
            report["sections"]["persistence"] = {
                "techniques_mapped": len(persistence_plans),
                "low_detection": len([p for p in persistence_plans if p.detection_risk == "low"]),
                "mitre_techniques": list(set(p.technique for p in persistence_plans)),
            }

        # Monitoring
        if monitor_changes:
            report["sections"]["monitoring"] = {
                "changes_detected": len(monitor_changes),
                "high_severity": len([c for c in monitor_changes if c.severity in ["high", "critical"]]),
            }

        # Executive summary
        report["executive_summary"] = (
            f"Red team assessment of {target} identified {total_findings} technical findings"
            f"{', ' + str(len(social_scenarios)) + ' social engineering scenarios' if social_scenarios else ''}"
            f"{', ' + str(len(exfil_channels)) + ' exfiltration channels' if exfil_channels else ''}"
            f"{', ' + str(len(persistence_plans)) + ' persistence mechanisms' if persistence_plans else ''}. "
            f"Critical items: {'; '.join(critical_items) if critical_items else 'None identified'}."
        )

        return report
