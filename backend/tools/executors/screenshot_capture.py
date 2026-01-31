"""
Screenshot capture for UI validation. Allowlisted URLs only (local app URLs).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

DEFAULT_ALLOWED_PREFIXES = (
    "http://127.0.0.1",
    "http://localhost",
    "https://127.0.0.1",
    "https://localhost",
)


def _allowed_url(url: str, allowlist: Optional[List[str]] = None) -> bool:
    if not url or not url.strip():
        return False
    allowed = list(allowlist) if allowlist else list(DEFAULT_ALLOWED_PREFIXES)
    return any(url.strip().lower().startswith(p.lower()) for p in allowed)


async def capture_screenshot(
    *,
    url: str,
    path: Optional[str] = None,
    timeout_ms: int = 15000,
    headless: bool = True,
    allowlist: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Capture a screenshot of an allowlisted URL. Local/defensive only."""
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "status": "error",
            "error": "Playwright not installed. pip install playwright && playwright install",
            "path": None,
        }
    if not _allowed_url(url, allowlist):
        return {
            "status": "error",
            "error": "URL not in allowlist (use localhost/127.0.0.1)",
            "path": None,
        }

    path = path or f"screenshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page(viewport={"width": 1280, "height": 720})
            await page.goto(url, timeout=timeout_ms)
            await page.screenshot(path=path)
            await browser.close()
        return {"status": "ok", "path": path, "url": url}
    except PlaywrightTimeout as e:
        return {"status": "timeout", "error": str(e), "path": None}
    except Exception as e:
        return {"status": "error", "error": str(e), "path": None}
