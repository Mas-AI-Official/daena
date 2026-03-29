"""BrowserAgent — governed web interaction via Playwright.

Supports navigation, text extraction, screenshots, form filling,
clicking, and form submission.  Playwright is lazy-imported so the
module works even when Playwright is not installed (tests mock it).

Governance tiers:
    - Reading (navigate, extract, screenshot): T0-T1
    - Interaction (fill, click): T2
    - External submission: T3 (Hard Law #5)
"""

from __future__ import annotations

import base64
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)

_ALLOWED_SCHEMES = ("http://", "https://")


class BrowserAgent(BaseAgent):
    """Governed browser-automation agent for Daena's EXE mode."""

    agent_name = "browser"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "navigate": "READ",
        "extract_text": "READ",
        "screenshot": "READ",
        "fill_form": "WRITE_FILE",
        "click_element": "EXECUTE",
        "submit_form": "POST_PUBLIC",
    }

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    # ── dispatch ───────────────────────────────────────────────

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        ops = {
            "navigate": self.navigate,
            "extract_text": self.extract_text,
            "screenshot": self.screenshot,
            "fill_form": self.fill_form,
            "click_element": self.click_element,
            "submit_form": self.submit_form,
        }
        fn = ops.get(operation)
        if fn is None:
            raise ValueError(
                f"BrowserAgent: unknown operation '{operation}'. "
                f"Supported: {list(ops)}"
            )
        return await fn(**params)

    # ── browser lifecycle ──────────────────────────────────────

    async def _ensure_browser(self) -> None:
        """Lazy-init Playwright browser.  Mocked in tests."""
        if self._page is not None:
            return

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is not installed. "
                "Run: pip install playwright && playwright install"
            ) from exc

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
        )
        self._page = await self._browser.new_page()

    async def close(self) -> None:
        """Release browser resources."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    # ── operations ─────────────────────────────────────────────

    async def navigate(
        self, url: str, wait_until: str = "domcontentloaded",
    ) -> dict[str, Any]:
        """Navigate to a URL."""
        self._validate_url(url)
        await self._ensure_browser()

        response = await self._page.goto(url, wait_until=wait_until)
        title = await self._page.title()
        status = response.status if response else 0

        logger.info("browser_agent.navigate", url=url, status=status)
        return self._result("navigate", {
            "url": self._page.url,
            "title": title,
            "status": status,
        })

    async def extract_text(
        self, selector: str | None = None,
    ) -> dict[str, Any]:
        """Extract text from page or a specific element."""
        await self._ensure_browser()

        target = selector or "body"
        text = await self._page.inner_text(target)

        logger.info(
            "browser_agent.extract_text",
            selector=target, length=len(text),
        )
        return self._result("extract_text", {
            "selector": target,
            "text": text,
            "length": len(text),
        })

    async def screenshot(
        self,
        path: str | None = None,
        full_page: bool = False,
    ) -> dict[str, Any]:
        """Take a screenshot, returning file path or base64."""
        await self._ensure_browser()

        if path:
            await self._page.screenshot(path=path, full_page=full_page)
            import os
            size = os.path.getsize(path)
            logger.info("browser_agent.screenshot", path=path, size=size)
            return self._result("screenshot", {
                "path": path,
                "size_bytes": size,
            })
        else:
            data = await self._page.screenshot(full_page=full_page)
            b64 = base64.b64encode(data).decode("ascii")
            logger.info("browser_agent.screenshot", base64_len=len(b64))
            return self._result("screenshot", {
                "base64": b64,
                "size_bytes": len(data),
            })

    async def fill_form(
        self, selector: str, value: str,
    ) -> dict[str, Any]:
        """Fill a form field."""
        await self._ensure_browser()

        await self._page.fill(selector, value)
        logger.info("browser_agent.fill_form", selector=selector)
        return self._result("fill_form", {
            "selector": selector,
            "filled": True,
        })

    async def click_element(self, selector: str) -> dict[str, Any]:
        """Click an element."""
        await self._ensure_browser()

        await self._page.click(selector)
        logger.info("browser_agent.click_element", selector=selector)
        return self._result("click_element", {
            "selector": selector,
            "clicked": True,
        })

    async def submit_form(
        self, selector: str | None = None,
    ) -> dict[str, Any]:
        """Submit a form (press Enter or click submit button)."""
        await self._ensure_browser()

        if selector:
            await self._page.click(selector)
        else:
            await self._page.keyboard.press("Enter")

        # Wait briefly for navigation
        try:  # noqa: SIM105
            await self._page.wait_for_load_state(
                "domcontentloaded", timeout=10000,
            )
        except Exception:
            pass  # page may not navigate

        url_after = self._page.url
        logger.info("browser_agent.submit_form", url_after=url_after)
        return self._result("submit_form", {
            "submitted": True,
            "url_after": url_after,
        })

    # ── validation ─────────────────────────────────────────────

    @staticmethod
    def _validate_url(url: str) -> None:
        """Reject non-HTTP(S) URLs to prevent file:// or javascript: access."""
        lower = url.lower().strip()
        if not any(lower.startswith(scheme) for scheme in _ALLOWED_SCHEMES):
            raise ValueError(
                f"URL scheme not allowed: '{url}'. "
                f"Only {_ALLOWED_SCHEMES} are permitted."
            )
