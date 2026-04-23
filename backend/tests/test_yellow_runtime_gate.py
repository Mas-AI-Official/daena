"""Tests for the YELLOW-tier security-tool runtime gate.

Covers:
- Target parsing (URL, IP, hostname, repo path, invalid).
- Scope matching (exact domain, wildcard subdomain, CIDR, source path).
- Gate decisions: RED runtime block, unknown tool block, GREEN auto,
  YELLOW role + scope matrix, AD-tools FOUNDER-only subset.
"""

from __future__ import annotations

import ipaddress

import pytest

from app.services.security.tool_catalog import SecurityTier
from app.services.security.yellow_runtime_gate import (
    AuthorizedScope,
    GateDecision,
    check_yellow_runtime,
    parse_target,
    target_matches_scope,
)


# ---------------------------------------------------------------------------
# parse_target
# ---------------------------------------------------------------------------


class TestParseTarget:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("example.com", ("domain", "example.com")),
            ("Example.COM", ("domain", "example.com")),
            ("sub.example.com", ("domain", "sub.example.com")),
            ("https://example.com/path?q=1", ("domain", "example.com")),
            ("http://example.com:8080/", ("domain", "example.com")),
            ("192.168.1.5", ("ipv4", "192.168.1.5")),
            ("https://10.0.0.4/api", ("ipv4", "10.0.0.4")),
            ("https://github.com/mas-ai/daena/tree/main", ("path", "github.com/mas-ai/daena/tree/main")),
            ("github.com/mas-ai/daena", ("path", "github.com/mas-ai/daena")),
            ("", ("unknown", "")),
            ("   ", ("unknown", "   ")),
            ("not a target", ("unknown", "not a target")),
        ],
    )
    def test_parse(self, raw: str, expected: tuple[str, str]) -> None:
        assert parse_target(raw) == expected


# ---------------------------------------------------------------------------
# target_matches_scope
# ---------------------------------------------------------------------------


class TestScopeMatching:
    def test_exact_domain(self) -> None:
        scope = AuthorizedScope(exact_domains=frozenset({"example.com"}))
        assert target_matches_scope("example.com", scope)
        assert target_matches_scope("https://example.com/anything", scope)
        assert not target_matches_scope("sub.example.com", scope)  # exact, no wildcard
        assert not target_matches_scope("evil.com", scope)

    def test_wildcard_domain_matches_self_and_subs(self) -> None:
        scope = AuthorizedScope(wildcard_domains=frozenset({"example.com"}))
        assert target_matches_scope("example.com", scope)
        assert target_matches_scope("a.example.com", scope)
        assert target_matches_scope("a.b.example.com", scope)
        assert not target_matches_scope("example.org", scope)
        assert not target_matches_scope("fake-example.com", scope)

    def test_ipv4_cidr(self) -> None:
        scope = AuthorizedScope(
            ipv4_cidrs=(ipaddress.IPv4Network("10.0.0.0/24"),),
        )
        assert target_matches_scope("10.0.0.5", scope)
        assert target_matches_scope("https://10.0.0.254", scope)
        assert not target_matches_scope("10.0.1.5", scope)
        assert not target_matches_scope("192.168.0.1", scope)

    def test_source_path(self) -> None:
        scope = AuthorizedScope(source_paths=frozenset({"github.com/mas-ai/"}))
        assert target_matches_scope("github.com/mas-ai/daena", scope)
        assert target_matches_scope("https://github.com/mas-ai/daena/tree/main", scope)
        assert not target_matches_scope("github.com/someone-else/evil", scope)
        assert not target_matches_scope("github.com/mas-ai-impostor/x", scope)

    def test_empty_scope_matches_nothing(self) -> None:
        scope = AuthorizedScope()
        assert scope.is_empty
        assert not target_matches_scope("example.com", scope)
        assert not target_matches_scope("10.0.0.1", scope)


# ---------------------------------------------------------------------------
# check_yellow_runtime
# ---------------------------------------------------------------------------


_SCOPE_FOR_OWN = AuthorizedScope(
    exact_domains=frozenset({"example.com"}),
    wildcard_domains=frozenset({"mas-ai.co"}),
    ipv4_cidrs=(ipaddress.IPv4Network("10.0.0.0/24"),),
    source_paths=frozenset({"github.com/mas-ai/"}),
)


def _call(
    tool: str,
    target: str = "example.com",
    *,
    role: str = "FOUNDER",
    scope: AuthorizedScope | None = _SCOPE_FOR_OWN,
    first_run: bool = False,
) -> GateDecision:
    return check_yellow_runtime(
        tool,
        target,
        user_role=role,
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        is_first_run_in_project=first_run,
        authorized_scope=scope,
    )


class TestRedRuntimeBlock:
    @pytest.mark.parametrize("name", ["pyphisher", "ddostool", "pyshell", "vegile", "blackeye"])
    def test_red_blocks_even_at_runtime(self, name: str) -> None:
        d = _call(name, target="example.com")
        assert d.allow is False
        assert d.tier == SecurityTier.RED
        assert "RED denylist" in d.reason


class TestUnknownToolBlock:
    def test_tool_not_in_catalog_is_denied(self) -> None:
        d = _call("completely-made-up-tool-that-does-not-exist-2026")
        assert d.allow is False
        assert d.tier is None
        assert "Unknown" in d.reason


class TestGreenTier:
    def test_green_always_allowed(self) -> None:
        d = _call("volatility", target="example.com", role="OPERATOR", scope=AuthorizedScope())
        assert d.allow is True
        assert d.tier == SecurityTier.GREEN
        # Auto-approved even with empty authorized_scope -- GREEN doesn't care
        assert d.rate_limit_key is not None
        assert d.audit_log.get("tier") == "green"


class TestYellowTierRole:
    def test_founder_allowed_with_in_scope_target(self) -> None:
        d = _call("nmap", target="example.com", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.allow is True
        assert d.tier == SecurityTier.YELLOW

    def test_admin_allowed_for_general_yellow(self) -> None:
        d = _call("nmap", target="example.com", role="ADMIN", scope=_SCOPE_FOR_OWN)
        assert d.allow is True

    def test_admin_denied_for_founder_only_subset(self) -> None:
        # sqlmap is in the FOUNDER-only active-exploitation subset
        d = _call("sqlmap", target="example.com", role="ADMIN", scope=_SCOPE_FOR_OWN)
        assert d.allow is False
        assert "requires role" in d.reason
        assert "FOUNDER" in d.reason

    def test_operator_denied_for_yellow(self) -> None:
        d = _call("nmap", target="example.com", role="OPERATOR", scope=_SCOPE_FOR_OWN)
        assert d.allow is False
        assert "requires role" in d.reason

    def test_founder_allowed_for_ad_tools(self) -> None:
        d = _call("bloodhound", target="example.com", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.allow is True


class TestYellowScope:
    def test_empty_scope_blocks_all_yellow(self) -> None:
        d = _call("nmap", target="example.com", role="FOUNDER", scope=AuthorizedScope())
        assert d.allow is False
        assert "authorized_scope" in d.reason

    def test_off_scope_target_blocked(self) -> None:
        d = _call("nmap", target="evil.com", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.allow is False
        assert "outside the tenant's authorized_scope" in d.reason

    def test_wildcard_subdomain_matches(self) -> None:
        d = _call("nmap", target="app.mas-ai.co", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.allow is True

    def test_ipv4_in_cidr_matches(self) -> None:
        d = _call("nmap", target="10.0.0.42", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.allow is True

    def test_ipv4_outside_cidr_blocked(self) -> None:
        d = _call("nmap", target="10.1.0.42", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.allow is False

    def test_source_path_in_scope(self) -> None:
        d = _call("trivy", target="github.com/mas-ai/daena", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        # trivy is GREEN in our catalog -- it doesn't need scope. This
        # confirms the GREEN path short-circuits before the scope check.
        assert d.allow is True


class TestFirstRunApproval:
    def test_first_run_flags_requires_approval(self) -> None:
        d = _call("nmap", target="example.com", role="FOUNDER", scope=_SCOPE_FOR_OWN, first_run=True)
        assert d.allow is True
        assert d.requires_approval is True
        assert "first-run approval needed" in d.reason

    def test_subsequent_run_no_approval(self) -> None:
        d = _call("nmap", target="example.com", role="FOUNDER", scope=_SCOPE_FOR_OWN, first_run=False)
        assert d.allow is True
        assert d.requires_approval is False


class TestAuditLog:
    def test_green_audit_log_shape(self) -> None:
        d = _call("volatility", target="dump.mem", role="FOUNDER", scope=_SCOPE_FOR_OWN)
        assert d.audit_log["event"] == "security_tool_allowed"
        assert d.audit_log["tier"] == "green"
        assert d.audit_log["tool"] == "volatility"
        assert d.audit_log["user_id"] == "u1"

    def test_yellow_audit_log_shape(self) -> None:
        d = _call("nmap", target="example.com", role="FOUNDER", scope=_SCOPE_FOR_OWN, first_run=True)
        assert d.audit_log["event"] == "security_tool_yellow_allowed"
        assert d.audit_log["tier"] == "yellow"
        assert d.audit_log["scope_matched"] is True
        assert d.audit_log["requires_approval"] is True
