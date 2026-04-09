"""ProxyManager -- Rotating proxy management for IP protection.

Tor is slow and many targets block Tor exit nodes. Residential proxy
rotation gives you a different real IP per request from millions of
IPs worldwide. To the target, every request comes from a different
real person's home internet.

Priority chain:
    1. Rotating residential proxy (Bright Data, Oxylabs, SmartProxy)
    2. Tor SOCKS5 (slower, blocked by some targets)
    3. Direct connection (WARNING: exposes operator IP)

In /3vilbob offensive mode, proxy is MANDATORY. The engine refuses
to scan without it. The shield is always on.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProxyConfig:
    """Proxy configuration with health tracking."""
    url: str = ""
    proxy_type: str = ""          # "rotating", "tor", "direct", "custom"
    provider: str = ""            # "brightdata", "oxylabs", "smartproxy", "tor", ""
    healthy: bool = True
    last_check: float = 0.0
    requests_sent: int = 0
    failures: int = 0
    avg_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "proxy_type": self.proxy_type,
            "provider": self.provider,
            "healthy": self.healthy,
            "requests_sent": self.requests_sent,
            "failures": self.failures,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


class ProxyManager:
    """Manages proxy rotation for scan IP protection.

    The soldier needs a shield. Every outbound request during a scan
    goes through a proxy so the operator's real IP is never exposed
    to the target. This prevents:
    - IP correlation across scan sessions
    - Retaliatory scanning of the operator's infrastructure
    - Ban evasion detection (same IP = same scanner)
    - Legal exposure (IP in target's logs)

    Usage::

        pm = ProxyManager(offensive_mode=True)
        proxy_url = pm.get_proxy()

        # In offensive mode, this raises if no proxy is available:
        pm.require_proxy()  # Raises ProxyRequired if no proxy

        # Track proxy health:
        pm.record_success(latency_ms=150)
        pm.record_failure()

        # Get status:
        status = pm.get_status()
    """

    def __init__(self, *, offensive_mode: bool = False) -> None:
        self.offensive_mode = offensive_mode
        self._proxies: list[ProxyConfig] = []
        self._active_proxy: ProxyConfig | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Load proxy configuration from environment.

        Environment variables:
            SCAN_PROXY: Primary rotating proxy URL
                        (e.g., http://user:pass@proxy.brightdata.com:22225)
            SCAN_PROXY_PROVIDER: Provider name (brightdata, oxylabs, smartproxy)
            USE_TOR: Enable Tor SOCKS5 as fallback (1/true/yes)
            TOR_SOCKS_PORT: Tor SOCKS port (default: 9050)
        """
        self._proxies = []

        # 1. Rotating residential proxy (highest priority)
        scan_proxy = os.environ.get("SCAN_PROXY", "").strip()
        if scan_proxy:
            provider = os.environ.get("SCAN_PROXY_PROVIDER", "").strip()
            if not provider:
                # Auto-detect provider from URL
                provider = self._detect_provider(scan_proxy)
            self._proxies.append(ProxyConfig(
                url=scan_proxy,
                proxy_type="rotating",
                provider=provider,
            ))
            logger.info("proxy.rotating_configured", provider=provider)

        # 2. Tor SOCKS5 (fallback)
        use_tor = os.environ.get("USE_TOR", "").lower() in ("1", "true", "yes")
        if use_tor:
            tor_port = int(os.environ.get("TOR_SOCKS_PORT", "9050"))
            self._proxies.append(ProxyConfig(
                url=f"socks5://127.0.0.1:{tor_port}",
                proxy_type="tor",
                provider="tor",
            ))
            logger.info("proxy.tor_configured", port=tor_port)

        # 3. Direct connection (always available, but warned)
        self._proxies.append(ProxyConfig(
            url="",
            proxy_type="direct",
            provider="",
        ))

        # Select the best available
        self._active_proxy = self._select_best()
        self._initialized = True

        logger.info(
            "proxy.initialized",
            total_proxies=len(self._proxies),
            active_type=self._active_proxy.proxy_type if self._active_proxy else "none",
            offensive_mode=self.offensive_mode,
        )

    def get_proxy(self) -> str:
        """Get the current proxy URL.

        Returns empty string for direct connection.
        In offensive mode, raises ProxyRequired if only direct is available.
        """
        if not self._initialized:
            self.initialize()

        if self.offensive_mode:
            self.require_proxy()

        if self._active_proxy:
            return self._active_proxy.url
        return ""

    def require_proxy(self) -> None:
        """Enforce proxy requirement. Raises if no proxy available.

        In /3vilbob mode, scanning without a proxy is not allowed.
        The shield is always on.
        """
        if not self._initialized:
            self.initialize()

        if not self._active_proxy or self._active_proxy.proxy_type == "direct":
            raise ProxyRequired(
                "Offensive mode requires a proxy. Set SCAN_PROXY env var "
                "with a rotating proxy URL (e.g., Bright Data, Oxylabs) "
                "or enable Tor with USE_TOR=1. "
                "Direct scanning exposes your IP to the target."
            )

    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record a successful request through the proxy."""
        if self._active_proxy:
            self._active_proxy.requests_sent += 1
            if latency_ms > 0:
                # Running average
                n = self._active_proxy.requests_sent
                self._active_proxy.avg_latency_ms = (
                    (self._active_proxy.avg_latency_ms * (n - 1) + latency_ms) / n
                )

    def record_failure(self) -> None:
        """Record a failed request. Auto-failover if too many failures."""
        if self._active_proxy:
            self._active_proxy.failures += 1

            # After 5 consecutive failures, mark unhealthy and try next
            if self._active_proxy.failures >= 5:
                logger.warning(
                    "proxy.unhealthy",
                    type=self._active_proxy.proxy_type,
                    failures=self._active_proxy.failures,
                )
                self._active_proxy.healthy = False
                self._active_proxy = self._select_best()

                if self._active_proxy:
                    logger.info(
                        "proxy.failover",
                        new_type=self._active_proxy.proxy_type,
                    )

    def get_status(self) -> dict[str, Any]:
        """Get proxy manager status for reporting."""
        return {
            "offensive_mode": self.offensive_mode,
            "active": self._active_proxy.to_dict() if self._active_proxy else None,
            "available": [p.to_dict() for p in self._proxies],
            "proxy_enforced": self.offensive_mode,
        }

    # ------------------------------------------------------------------
    # User-Agent rotation (legitimacy mimicry)
    # ------------------------------------------------------------------

    _USER_AGENTS = [
        # Chrome on Windows (most common)
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        # Chrome on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        # Safari on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        # Chrome on Android
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        # Safari on iPhone
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    ]

    def get_user_agent(self) -> str:
        """Get a realistic User-Agent string for legitimacy mimicry.

        In offensive mode, we rotate User-Agents to look like a
        real user, not a scanner. The defender's paradox: they MUST
        let real users through.
        """
        import random
        return random.choice(self._USER_AGENTS)

    def get_request_headers(self) -> dict[str, str]:
        """Get a complete set of realistic browser headers.

        A real browser sends Accept, Accept-Language, Accept-Encoding,
        Connection headers. A scanner typically only sends User-Agent.
        The more you look like a real browser, the harder it is to
        distinguish from legitimate traffic.
        """
        return {
            "User-Agent": self.get_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_best(self) -> ProxyConfig | None:
        """Select the best available proxy."""
        for proxy in self._proxies:
            if proxy.healthy and proxy.proxy_type != "direct":
                return proxy

        # Fall back to direct (with warning)
        for proxy in self._proxies:
            if proxy.proxy_type == "direct":
                if self.offensive_mode:
                    logger.error("proxy.no_proxy_available_in_offensive_mode")
                else:
                    logger.warning("proxy.falling_back_to_direct")
                return proxy

        return None

    @staticmethod
    def _detect_provider(url: str) -> str:
        """Auto-detect proxy provider from URL."""
        url_lower = url.lower()
        if "brightdata" in url_lower or "luminati" in url_lower:
            return "brightdata"
        if "oxylabs" in url_lower:
            return "oxylabs"
        if "smartproxy" in url_lower:
            return "smartproxy"
        if "iproyal" in url_lower:
            return "iproyal"
        if "webshare" in url_lower:
            return "webshare"
        return "custom"


class ProxyRequired(Exception):
    """Raised when offensive mode requires a proxy but none is available."""
    pass
