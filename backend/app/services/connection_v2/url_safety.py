"""Defensive URL classifier for the mcp-fetch read-only skill.

PR-CONN-PHASE2-ARM-ZERO-INPUT-MCPS (Sprint-9, 2026-05-05).

The Phase 2 read-only ``fetch_public_url`` skill calls the reference
``mcp-fetch`` server, which performs an HTTP GET against the supplied
URL. Without a pre-call guard, the operator (or a chat-driven flow)
could trick the MCP into hitting:

  * loopback (127.0.0.1, ::1, localhost)
  * link-local (169.254.0.0/16, fe80::/10) -- includes EC2/GCE metadata
  * RFC1918 private ranges (10/8, 172.16/12, 192.168/16)
  * unique local IPv6 (fc00::/7)
  * multicast / reserved / unspecified ranges
  * common internal hostnames (.local / .internal / .corp / .home / .lan)

These are classic SSRF reach-through targets. The mcp-fetch server
itself does NOT enforce egress policy -- "Daena governance gates
external HTTP egress" was always the catalog's stated invariant.
This module is that gate at the executor boundary.

Defense-in-depth, not crypto:
  * The check is string + IP-literal only. We deliberately do NOT
    resolve hostnames here -- DNS introduces TOCTOU risk + flaky
    tests + a network dependency. Operators with internal DNS that
    resolves a public-looking hostname to a private IP would slip
    through this guard, but the MCP server's own socket layer would
    still hit a private IP. A future PR can add a cached resolver
    + post-resolution recheck.
  * Scheme is restricted to http/https only.
  * IDN (xn--*) hostnames are accepted as-is; the MCP server
    handles punycode normalization.

Returns ``(ok: bool, reason: str)``. The reason is machine-stable
(snake_case prefix) so tests + audit rows can pin it without
matching free text.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

# Stable reason prefixes (machine-readable, audit-stable).
REASON_OK = ""
REASON_INVALID_URL = "url_invalid"
REASON_BAD_SCHEME = "url_scheme_not_http"
REASON_NO_HOST = "url_missing_host"
REASON_PRIVATE_IP = "url_private_ip"
REASON_LOOPBACK = "url_loopback_host"
REASON_LINK_LOCAL = "url_link_local"
REASON_RESERVED_IP = "url_reserved_ip"
REASON_INTERNAL_TLD = "url_internal_tld"
REASON_LOCALHOST = "url_localhost_host"


# Hostnames + suffixes that almost always resolve inside a private
# network. Block at string layer so we never even attempt the call.
_INTERNAL_TLD_SUFFIXES: tuple[str, ...] = (
    ".local",
    ".internal",
    ".corp",
    ".home",
    ".lan",
    ".intranet",
    ".localdomain",
)

_LOCALHOST_NAMES: frozenset[str] = frozenset({
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
})


def is_public_url_safe(url: str) -> tuple[bool, str]:
    """Return (True, "") for a URL safe to fetch from the public internet.

    Returns (False, reason) for any URL that points at a private,
    loopback, link-local, reserved, or internal-DNS-shaped target.

    The check is purely string + IP-literal based -- no DNS lookup.
    The MCP server is the second line of defense for hostname-based
    redirects to private IPs.
    """
    if not isinstance(url, str) or not url.strip():
        return False, REASON_INVALID_URL

    try:
        parts = urlsplit(url.strip())
    except Exception:
        return False, REASON_INVALID_URL

    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, REASON_BAD_SCHEME

    # urlsplit puts everything into netloc/path for malformed inputs;
    # require an explicit host.
    host = (parts.hostname or "").strip().lower()
    if not host:
        return False, REASON_NO_HOST

    # 1. Bare-name loopback / broadcast.
    if host in _LOCALHOST_NAMES:
        return False, REASON_LOCALHOST

    # 2. Internal-DNS suffixes (.local / .internal / etc.).
    for suffix in _INTERNAL_TLD_SUFFIXES:
        if host.endswith(suffix):
            return False, REASON_INTERNAL_TLD

    # 3. IP literal -- run the full ipaddress classification.
    ip_obj = _try_parse_ip(host)
    if ip_obj is not None:
        if ip_obj.is_loopback:
            return False, REASON_LOOPBACK
        if ip_obj.is_link_local:
            return False, REASON_LINK_LOCAL
        if ip_obj.is_private:
            return False, REASON_PRIVATE_IP
        if (
            ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        ):
            return False, REASON_RESERVED_IP

    return True, REASON_OK


def _try_parse_ip(host: str) -> ipaddress._BaseAddress | None:
    """Parse the host as an IPv4 or IPv6 literal. Strips IPv6 brackets."""
    candidate = host
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


__all__ = [
    "REASON_BAD_SCHEME",
    "REASON_INTERNAL_TLD",
    "REASON_INVALID_URL",
    "REASON_LINK_LOCAL",
    "REASON_LOCALHOST",
    "REASON_LOOPBACK",
    "REASON_NO_HOST",
    "REASON_OK",
    "REASON_PRIVATE_IP",
    "REASON_RESERVED_IP",
    "is_public_url_safe",
]
