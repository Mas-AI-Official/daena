"""PR-CONN-PHASE2-ARM-ZERO-INPUT-MCPS (Sprint-9, 2026-05-05).

Pins the SSRF guard used by mcp-fetch:fetch_public_url. The check
runs string + IP-literal only -- no DNS, no network -- so the test
suite stays offline + deterministic.
"""

from __future__ import annotations

import pytest

from app.services.connection_v2.url_safety import (
    REASON_BAD_SCHEME,
    REASON_INTERNAL_TLD,
    REASON_INVALID_URL,
    REASON_LINK_LOCAL,
    REASON_LOCALHOST,
    REASON_LOOPBACK,
    REASON_NO_HOST,
    REASON_PRIVATE_IP,
    REASON_RESERVED_IP,
    is_public_url_safe,
)


# ──────────────────────────────────────────────────────────────────
# Public URLs that MUST pass.
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "https://example.com/",
    "http://example.com/path?q=1",
    "https://api.github.com/repos/anthropic/claude-code",
    "https://www.cloudflare.com/learning/",
    "https://huggingface.co/models",
    # IDN / punycode -- pass through to MCP's normalizer.
    "https://xn--mxail5aa.com/",
    # IPv4 public -- 8.8.8.8 (Google DNS).
    "https://8.8.8.8/",
    # IPv6 public -- 2606:4700:4700::1111 (Cloudflare).
    "https://[2606:4700:4700::1111]/",
])
def test_public_urls_pass(url):
    ok, reason = is_public_url_safe(url)
    assert ok, f"{url} should pass; got reason={reason}"
    assert reason == ""


# ──────────────────────────────────────────────────────────────────
# Loopback / localhost names.
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "http://localhost/",
    "https://localhost:8000/",
    "http://LOCALHOST/x",  # case-insensitive
    "http://broadcasthost/",
])
def test_localhost_names_blocked(url):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == REASON_LOCALHOST


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://127.1.2.3/",
    "https://127.0.0.1:8443/",
    "http://[::1]/",
    "http://[::1]:8000/admin",
])
def test_loopback_ips_blocked(url):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == REASON_LOOPBACK


# ──────────────────────────────────────────────────────────────────
# Private RFC1918 / link-local / reserved ranges.
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", [
    "http://10.0.0.1/",
    "http://10.255.255.255/",
    "http://172.16.0.1/",
    "http://172.31.255.254/",
    "http://192.168.1.1/",
    "https://192.168.0.42/admin",
    # IPv6 unique-local fc00::/7
    "http://[fc00::1]/",
    "http://[fd12:3456:789a::1]/",
])
def test_private_ips_blocked(url):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == REASON_PRIVATE_IP


@pytest.mark.parametrize("url", [
    # AWS / GCE / Azure metadata endpoint.
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.0.1/",
    # IPv6 link-local fe80::/10
    "http://[fe80::1]/",
])
def test_link_local_blocked(url):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == REASON_LINK_LOCAL


@pytest.mark.parametrize("url,acceptable_reasons", [
    # 0.0.0.0 -- both unspecified AND in 0/8 (Python's ipaddress flags
    # it as is_private=True before is_unspecified is checked); either
    # private or reserved is correct -- the only invariant that matters
    # is that the URL is REFUSED.
    ("http://0.0.0.0/", {REASON_PRIVATE_IP, REASON_RESERVED_IP}),
    # 224.0.0.1 -- multicast; Python flags as is_multicast.
    ("http://224.0.0.1/", {REASON_RESERVED_IP}),
    # 255.255.255.255 -- broadcast; Python's ipaddress flags it as
    # is_private (it sits inside 240/4 reserved which Python treats
    # as private under the modern table). Either is a refusal; both
    # are acceptable.
    ("http://255.255.255.255/", {REASON_PRIVATE_IP, REASON_RESERVED_IP}),
])
def test_reserved_ips_blocked(url, acceptable_reasons):
    """Blocking is the invariant; the exact reason code follows
    Python's ipaddress classification table, which evolves across
    minor versions for edge cases like 0.0.0.0 and 255.255.255.255."""
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason in acceptable_reasons, (
        f"{url} blocked with unexpected reason {reason!r}"
    )


# ──────────────────────────────────────────────────────────────────
# Internal-DNS suffixes (.local / .internal / .corp / etc.)
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url,expected_reason", [
    ("http://server.local/", REASON_INTERNAL_TLD),
    ("http://printer.local:631/", REASON_INTERNAL_TLD),
    ("http://wiki.internal/", REASON_INTERNAL_TLD),
    ("http://billing.corp/", REASON_INTERNAL_TLD),
    ("http://router.home/", REASON_INTERNAL_TLD),
    ("http://nas.lan/", REASON_INTERNAL_TLD),
    ("http://app.intranet/", REASON_INTERNAL_TLD),
    ("http://host.localdomain/", REASON_INTERNAL_TLD),
])
def test_internal_dns_suffixes_blocked(url, expected_reason):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == expected_reason


# ──────────────────────────────────────────────────────────────────
# Bad / malformed inputs.
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url,expected_reason", [
    ("ftp://example.com/", REASON_BAD_SCHEME),
    ("file:///etc/passwd", REASON_BAD_SCHEME),
    ("javascript:alert(1)", REASON_BAD_SCHEME),
    ("ws://example.com/", REASON_BAD_SCHEME),
    ("data:text/plain,hi", REASON_BAD_SCHEME),
])
def test_non_http_schemes_blocked(url, expected_reason):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == expected_reason


@pytest.mark.parametrize("url", ["", "   ", None])
def test_empty_and_none_rejected(url):
    ok, reason = is_public_url_safe(url)
    assert not ok
    assert reason == REASON_INVALID_URL


def test_url_without_scheme_rejected():
    """Plain hostname without scheme has no host parsed -- urlsplit
    can't tell it from a path. We refuse rather than guess."""
    ok, reason = is_public_url_safe("example.com")
    assert not ok
    # Either NO_HOST or BAD_SCHEME depending on parser; both are correct
    # rejections from the operator's perspective.
    assert reason in (REASON_NO_HOST, REASON_BAD_SCHEME)
