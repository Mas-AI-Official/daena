"""
web_eyes.py — Tiered browser engine selector for Daena's EYES capability.

This is the only canonical entry point for Daena agents that need to fetch
web content. It routes to one of three engines based on the site's
bot-detection posture:

  Tier 1: vanilla Playwright + Chromium (trusted/internal sites, dev preview)
  Tier 2: patchright (stealth Playwright fork already in venv) for light bot detection
  Tier 3: Obscura over CDP at ws://127.0.0.1:9222 (hard-blocked sites)

Tier 3 is opt-in only (allow_tier_3=True). It is gated by SecurityGate at the
caller's pipeline stage and emits a WARNING-level audit event so operators
can see exactly when stealth was used.

Browser stack lives at D:\\Ideas\\browser-stack\\. See
D:\\Ideas\\browser-stack\\docs\\daena-integration.md for the architectural
context behind this file.

Per CLAUDE.md Rule 2 (one canonical file per concern): never bypass this
file. Add new tiers here, do not create web_eyes_v2.py.

Per CLAUDE.md Rule 10: this is a hot-path-safe module. It does not import
background-only modules and does not block on the long Obscura cold-start.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

OBSCURA_BIN = Path("D:/Ideas/browser-stack/obscura/bin/obscura.exe")
OBSCURA_PORT = 9222
OBSCURA_CDP_URL = f"http://127.0.0.1:{OBSCURA_PORT}/json/version"
OBSCURA_WS_URL = f"ws://127.0.0.1:{OBSCURA_PORT}"

Tier = Literal[1, 2, 3]
Engine = Literal["playwright_chromium", "patchright_stealth", "obscura_cdp"]

BLOCK_SIGNALS = (
    "access denied",
    "request blocked",
    "verify you are human",
    "checking your browser",
    "cf-chl-",
    "captcha",
)


@dataclass
class FetchResult:
    url: str
    tier: Tier
    engine: Engine
    status: int
    body: str
    title: str
    bytes: int
    latency_ms: int
    blocked_by_detection: bool = False


class WebEyesError(RuntimeError):
    pass


def fetch(
    url: str,
    *,
    tier: Tier | None = None,
    allow_tier_3: bool = False,
    timeout_s: float = 30.0,
) -> FetchResult:
    """Fetch a URL using the lowest tier that works.

    If `tier` is given, that tier is forced (no auto-escalation).
    If `tier` is None, starts at tier 1 and escalates on bot-detection signals.
    Tier 3 is reached only if the caller explicitly passes allow_tier_3=True.
    """
    if tier is not None:
        if tier == 3 and not allow_tier_3:
            raise WebEyesError("tier 3 (Obscura) requires allow_tier_3=True")
        return _fetch_at_tier(url, tier, timeout_s)

    result = _fetch_at_tier(url, 1, timeout_s)
    if not _looks_blocked(result):
        return result

    logger.info("web_eyes: tier 1 blocked on %s, escalating to tier 2", url)
    result = _fetch_at_tier(url, 2, timeout_s)
    if not _looks_blocked(result):
        return result

    if not allow_tier_3:
        logger.warning(
            "web_eyes: tier 2 still blocked on %s; tier 3 not authorized "
            "(pass allow_tier_3=True from a SecurityGate-approved caller)",
            url,
        )
        result.blocked_by_detection = True
        return result

    logger.warning("web_eyes: escalating to tier 3 (Obscura) for %s", url)
    return _fetch_at_tier(url, 3, timeout_s)


def _fetch_at_tier(url: str, tier: Tier, timeout_s: float) -> FetchResult:
    start = time.monotonic()
    if tier == 1:
        body, status, title = _fetch_playwright(url, timeout_s, stealth=False)
        engine: Engine = "playwright_chromium"
    elif tier == 2:
        body, status, title = _fetch_playwright(url, timeout_s, stealth=True)
        engine = "patchright_stealth"
    elif tier == 3:
        body, status, title = _fetch_obscura(url, timeout_s)
        engine = "obscura_cdp"
    else:
        raise WebEyesError(f"unknown tier: {tier}")

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return FetchResult(
        url=url,
        tier=tier,
        engine=engine,
        status=status,
        body=body,
        title=title,
        bytes=len(body.encode("utf-8")),
        latency_ms=elapsed_ms,
    )


def _fetch_playwright(url: str, timeout_s: float, *, stealth: bool) -> tuple[str, int, str]:
    if stealth:
        from patchright.sync_api import sync_playwright
    else:
        from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            response = page.goto(url, timeout=int(timeout_s * 1000))
            status = response.status if response else 0
            body = page.content()
            title = page.title() or ""
            return body, status, title
        finally:
            browser.close()


def _fetch_obscura(url: str, timeout_s: float) -> tuple[str, int, str]:
    if not OBSCURA_BIN.exists():
        raise WebEyesError(f"Obscura binary not found at {OBSCURA_BIN}")
    _ensure_obscura_running(timeout_s=10.0)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(OBSCURA_WS_URL)
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            response = page.goto(url, timeout=int(timeout_s * 1000))
            status = response.status if response else 0
            body = page.content()
            title = page.title() or ""
            return body, status, title
        finally:
            browser.close()


def _ensure_obscura_running(timeout_s: float) -> None:
    """Spawn the Obscura serve process if it isn't already listening."""
    if _obscura_alive():
        return
    logger.info("web_eyes: launching Obscura serve on port %d", OBSCURA_PORT)
    subprocess.Popen(
        [str(OBSCURA_BIN), "serve", "--port", str(OBSCURA_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
    )
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _obscura_alive():
            return
        time.sleep(0.25)
    raise WebEyesError(f"Obscura did not become reachable within {timeout_s}s")


def _obscura_alive() -> bool:
    try:
        r = httpx.get(OBSCURA_CDP_URL, timeout=1.0)
        return r.status_code == 200
    except httpx.RequestError:
        return False


def _looks_blocked(result: FetchResult) -> bool:
    if result.status in (401, 403, 429):
        return True
    if result.status >= 400:
        return True
    body_lc = result.body.lower()
    return any(sig in body_lc for sig in BLOCK_SIGNALS)
