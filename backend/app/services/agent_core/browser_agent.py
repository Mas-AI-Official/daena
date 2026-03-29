"""BrowserAgent -- Playwright-based web interaction.

Direct browser automation without MCP overhead.
Handles navigation, form filling, screenshots, data extraction.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class BrowserAgent:
    """Daena's browser. Navigate, fill forms, extract data, take screenshots.

    Integrates with InteractivePromptManager for:
    - Credential prompts when login forms are detected
    - Verification prompts when email confirmation is needed
    - CAPTCHA prompts when anti-bot challenges appear
    """

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self, headless: bool = True) -> None:
        """Launch browser."""
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=headless)
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        self._page = await self._context.new_page()
        logger.info("browser_agent.started", headless=headless)

    async def stop(self) -> None:
        """Close browser."""
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = None
        self._pw = None
        self._page = None
        logger.info("browser_agent.stopped")

    async def navigate(self, url: str, wait_ms: int = 3000) -> dict[str, Any]:
        """Navigate to URL and wait for content."""
        if not self._page:
            await self.start()
        assert self._page is not None

        await self._page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await self._page.wait_for_timeout(wait_ms)
        title = await self._page.title()
        return {"url": url, "title": title}

    async def screenshot(self, path: str, full_page: bool = False) -> str:
        """Take a screenshot of the current page."""
        assert self._page is not None
        await self._page.screenshot(path=path, full_page=full_page)
        return path

    async def fill_form(self, fields: dict[str, str]) -> dict[str, Any]:
        """Fill form fields by selector -> value mapping."""
        assert self._page is not None
        filled = []
        failed = []

        for selector, value in fields.items():
            try:
                el = self._page.locator(selector)
                if await el.count() > 0:
                    await el.first.fill(value)
                    filled.append(selector)
                else:
                    failed.append({"selector": selector, "error": "Not found"})
            except Exception as exc:
                failed.append({"selector": selector, "error": str(exc)[:100]})

        return {"filled": filled, "failed": failed}

    async def click(self, selector: str) -> bool:
        """Click an element."""
        assert self._page is not None
        try:
            await self._page.click(selector, timeout=5000)
            return True
        except Exception:
            return False

    async def extract_text(self, selector: str | None = None) -> str:
        """Extract text from page or specific element."""
        assert self._page is not None
        if selector:
            el = self._page.locator(selector)
            if await el.count() > 0:
                return await el.first.text_content() or ""
            return ""
        return await self._page.inner_text("body")

    async def extract_links(self) -> list[dict[str, str]]:
        """Extract all links from the current page."""
        assert self._page is not None
        links = await self._page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: e.textContent?.trim() || ''}))",
        )
        return links

    async def get_form_fields(self) -> list[dict[str, str]]:
        """Get all form fields on the page."""
        assert self._page is not None
        fields = await self._page.eval_on_selector_all(
            "input, textarea, select",
            """els => els.map(e => ({
                tag: e.tagName.toLowerCase(),
                type: e.type || '',
                name: e.name || '',
                id: e.id || '',
                placeholder: e.placeholder || '',
                required: e.required || false,
                value: e.value || '',
            }))""",
        )
        return fields

    async def submit_form(self, submit_selector: str = "button[type='submit']") -> bool:
        """Click the submit button."""
        return await self.click(submit_selector)

    async def wait_for(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for an element to appear."""
        assert self._page is not None
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    # -- Interactive prompt integration --

    async def detect_login_and_prompt(self, url: str) -> dict[str, str] | None:
        """Detect login form on page and ask user for credentials.

        Returns credential dict if provided, None if skipped.
        """
        assert self._page is not None
        fields = await self.get_form_fields()

        # Check for login-like fields
        has_password = any(f["type"] == "password" for f in fields)
        has_email = any(
            f["type"] in ("email", "text") and any(
                kw in (f["name"] + f["placeholder"]).lower()
                for kw in ("email", "user", "login", "username")
            )
            for f in fields
        )

        if not has_password:
            return None

        logger.info("browser_agent.login_detected", url=url)

        from app.services.agent_core.interactive_prompts import InteractivePromptManager

        pm = InteractivePromptManager.get_instance()

        prompt_fields = []
        if has_email:
            prompt_fields.append({
                "name": "email",
                "label": "Email / Username",
                "type": "email",
                "prefill": "",
            })
        prompt_fields.append({
            "name": "password",
            "label": "Password",
            "type": "password",
        })

        creds = await pm.ask_credential(
            title="Login Required",
            message=f"The site {url} requires authentication.",
            fields=prompt_fields,
            context={"url": url},
        )

        if not creds or creds.get("password") == "":
            return None
        return creds

    async def prompt_verification(self, site_name: str, email: str) -> str:
        """Ask user to verify email after account creation."""
        from app.services.agent_core.interactive_prompts import InteractivePromptManager

        pm = InteractivePromptManager.get_instance()
        return await pm.ask_verification(
            title="Email Verification Needed",
            message=f"Account created on {site_name}. Check {email} for verification link.",
            context={"site": site_name, "email": email},
        )

    async def prompt_captcha(self) -> str:
        """Ask user to solve a CAPTCHA visible on screen."""
        from app.services.agent_core.interactive_prompts import InteractivePromptManager

        pm = InteractivePromptManager.get_instance()
        return await pm.ask_verification(
            title="CAPTCHA Detected",
            message="A CAPTCHA challenge is visible on screen. Please solve it in the browser window, then click 'I've Verified'.",
            context={"type": "captcha"},
        )
