"""Tests for OSINT Engine -- People Intelligence, Supply Chain, Breach Intel."""

import pytest

from app.services.security.osint_engine import (
    BreachHit,
    BreachIntelligenceChecker,
    OSINTPeopleIntelligence,
    OrgIntel,
    PersonIntel,
    SupplyChainAnalyzer,
    SupplyChainEntry,
)


# -----------------------------------------------------------------------
# OSINT People Intelligence
# -----------------------------------------------------------------------

class TestOSINTPeopleIntelligence:
    """Tests for people search and email generation."""

    def setup_method(self):
        self.osint = OSINTPeopleIntelligence()

    def test_generate_email_candidates(self):
        candidates = self.osint.generate_email_candidates("John", "Doe", "example.com")
        assert "john.doe@example.com" in candidates
        assert "johndoe@example.com" in candidates
        assert "jdoe@example.com" in candidates
        assert "john@example.com" in candidates
        assert len(candidates) >= 5

    def test_generate_role_emails(self):
        emails = self.osint.generate_role_emails("example.com")
        assert "admin@example.com" in emails
        assert "security@example.com" in emails
        assert "ceo@example.com" in emails
        assert "cto@example.com" in emails
        assert len(emails) >= 15

    def test_extract_emails_from_text(self):
        text = """
        Contact us at support@example.com or sales@example.com.
        Our CTO john.doe@example.com is available for meetings.
        Image: photo@example.png should be ignored.
        """
        emails = self.osint.extract_emails_from_text(text)
        assert "support@example.com" in emails
        assert "sales@example.com" in emails
        assert "john.doe@example.com" in emails
        # .png should be filtered
        assert not any(e.endswith(".png") for e in emails)

    def test_extract_emails_deduplicates(self):
        text = "Contact test@example.com or TEST@example.com"
        emails = self.osint.extract_emails_from_text(text)
        assert len(emails) == 1

    def test_detect_email_pattern_first_dot_last(self):
        emails = ["john.doe@company.com", "jane.smith@company.com", "bob.jones@company.com"]
        pattern = self.osint.detect_email_pattern(emails, "company.com")
        assert pattern == "first.last"

    def test_detect_email_pattern_flast(self):
        emails = ["j.doe@company.com", "j.smith@company.com"]
        pattern = self.osint.detect_email_pattern(emails, "company.com")
        assert pattern == "f.last"

    def test_detect_pattern_wrong_domain(self):
        emails = ["test@other.com"]
        pattern = self.osint.detect_email_pattern(emails, "company.com")
        assert pattern == ""

    def test_person_intel_dataclass(self):
        person = PersonIntel(
            name="Elon Musk",
            emails=["elon@tesla.com"],
            social_profiles={"twitter": "https://x.com/elonmusk"},
            job_title="CEO",
            company="Tesla",
        )
        assert person.name == "Elon Musk"
        assert person.emails[0] == "elon@tesla.com"

    @pytest.mark.asyncio
    async def test_gather_from_github_graceful_failure(self):
        """Should not crash if GitHub API fails."""
        people = await self.osint.gather_from_github(username="nonexistent_user_12345")
        # May return empty or data depending on network
        assert isinstance(people, list)


# -----------------------------------------------------------------------
# Supply Chain Analyzer
# -----------------------------------------------------------------------

class TestSupplyChainAnalyzer:
    """Tests for third-party dependency detection."""

    def setup_method(self):
        self.analyzer = SupplyChainAnalyzer()

    def test_detect_cloudflare_from_headers(self):
        entries = self.analyzer.analyze_headers({
            "cf-ray": "abc123-IAD",
            "Server": "cloudflare",
        })
        services = [e.service_name for e in entries]
        assert "Cloudflare" in services

    def test_detect_vercel_from_headers(self):
        entries = self.analyzer.analyze_headers({
            "x-vercel-id": "iad1::12345",
        })
        assert any(e.service_name == "Vercel" for e in entries)

    def test_detect_server_header(self):
        entries = self.analyzer.analyze_headers({
            "Server": "nginx/1.21.6",
        })
        assert any(e.category == "server" for e in entries)

    def test_detect_framework_from_powered_by(self):
        entries = self.analyzer.analyze_headers({
            "X-Powered-By": "Express",
        })
        assert any(e.service_name == "Express" and e.category == "framework" for e in entries)

    def test_detect_google_analytics_from_html(self):
        html = '<script src="https://www.google-analytics.com/analytics.js"></script>'
        entries = self.analyzer.analyze_html(html)
        assert any(e.service_name == "Google Analytics" for e in entries)

    def test_detect_stripe_from_html(self):
        html = '<script src="https://js.stripe.com/v3/"></script>'
        entries = self.analyzer.analyze_html(html)
        assert any(e.service_name == "Stripe" for e in entries)

    def test_detect_sentry_from_html(self):
        html = '<script src="https://browser.sentry-cdn.com/7.0/bundle.min.js"></script>'
        entries = self.analyzer.analyze_html(html)
        assert any(e.service_name == "Sentry" for e in entries)

    def test_detect_cms_from_meta(self):
        html = '<meta name="generator" content="WordPress 6.4">'
        entries = self.analyzer.analyze_html(html)
        assert any(e.service_name == "WordPress 6.4" and e.category == "cms" for e in entries)

    def test_detect_cookies(self):
        entries = self.analyzer.analyze_cookies({
            "_ga": "GA1.2.123456",
            "_fbp": "fb.1.123456",
        })
        services = [e.service_name for e in entries]
        assert "Google Analytics" in services
        assert "Facebook Pixel" in services

    def test_full_analysis_deduplicates(self):
        entries = self.analyzer.full_analysis(
            headers={"cf-ray": "abc"},
            html='<script src="https://www.google-analytics.com/analytics.js"></script>',
            cookies={"_ga": "test"},
        )
        # Google Analytics should appear only once despite being in both HTML and cookies
        ga_count = sum(1 for e in entries if e.service_name == "Google Analytics")
        assert ga_count == 1

    def test_risk_notes_included(self):
        entries = self.analyzer.analyze_headers({"cf-ray": "abc"})
        cf = [e for e in entries if e.service_name == "Cloudflare"]
        assert cf
        assert cf[0].risk_notes  # Should have known risks

    def test_empty_inputs(self):
        entries = self.analyzer.full_analysis(headers={})
        assert entries == []

    def test_supply_chain_entry_dataclass(self):
        entry = SupplyChainEntry(
            service_name="Stripe",
            category="payment",
            detected_via="js_include",
            evidence="stripe.com/v3",
            risk_notes="Client-side key exposure",
        )
        assert entry.service_name == "Stripe"
        assert entry.risk_notes


# -----------------------------------------------------------------------
# Breach Intelligence Checker
# -----------------------------------------------------------------------

class TestBreachIntelligenceChecker:
    """Tests for breach intelligence checking."""

    def setup_method(self):
        self.checker = BreachIntelligenceChecker()

    def test_domain_exposure_check(self):
        hits = self.checker.check_domain_exposure("bigcorp.com")
        assert len(hits) >= 1
        assert any("LinkedIn" in h.details or "password reuse" in h.details for h in hits)

    def test_generate_credential_report(self):
        hits = [
            BreachHit(
                source="hibp",
                match_type="email",
                details="LinkedIn breach",
                severity="high",
                date="2012-06-05",
                affected_records=164000000,
            ),
            BreachHit(
                source="hibp",
                match_type="email",
                details="Adobe breach",
                severity="medium",
                date="2013-10-04",
            ),
        ]
        report = self.checker.generate_credential_report(
            domain="example.com",
            hibp_results=hits,
            known_emails=["admin@example.com", "cto@example.com"],
        )
        assert report["domain"] == "example.com"
        assert report["emails_checked"] == 2
        assert report["breaches_found"] == 2
        assert report["severity_summary"]["high"] == 1
        assert report["severity_summary"]["medium"] == 1
        assert "multi-factor" in report["recommendation"].lower()

    def test_known_breaches_list(self):
        assert len(self.checker._KNOWN_BREACHES) >= 10
        # Yahoo should be the largest
        yahoo = [b for b in self.checker._KNOWN_BREACHES if "Yahoo" in b["name"]]
        assert yahoo
        assert yahoo[0]["records"] >= 3_000_000_000

    @pytest.mark.asyncio
    async def test_hibp_graceful_failure(self):
        """Should not crash if HIBP is unreachable."""
        hits = await self.checker.check_hibp("test@example.com")
        # May return results, rate limit, or empty -- should not crash
        assert isinstance(hits, list)

    def test_breach_hit_dataclass(self):
        hit = BreachHit(
            source="test",
            match_type="email",
            details="Test breach",
            severity="high",
            date="2024-01-01",
            affected_records=1000000,
        )
        assert hit.severity == "high"
        assert hit.affected_records == 1000000
