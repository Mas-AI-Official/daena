from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.config.settings import settings
from backend.tools.policies import check_allowed_url


def _require_selenium():
    try:
        import selenium  # noqa: F401
        from selenium import webdriver  # noqa: F401
    except Exception as e:
        raise RuntimeError(f"selenium not installed: {e}")


def _make_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=opts)


def run(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: browser_automation_selenium (optional dependency)

    Safe usage:
    - only acts on allowlisted domains
    - runs a visible logical sequence (navigate + steps)
    - no credential harvesting: caller must provide any credentials in args (redacted in audit)

    Args:
      - url (required)
      - steps: list of { action: click|type|wait, selector: css, text?: str, ms?: int }
      - screenshot: bool (optional)
    """
    if not getattr(settings, "automation_enable_browser", False):
        raise RuntimeError("browser automation disabled (AUTOMATION_ENABLE_BROWSER=0)")

    _require_selenium()

    url = (args or {}).get("url")
    steps: List[Dict[str, Any]] = (args or {}).get("steps") or []
    screenshot = bool((args or {}).get("screenshot", False))

    check_allowed_url(url)

    driver = _make_driver()
    try:
        driver.set_page_load_timeout(int(getattr(settings, "automation_action_timeout_sec", 20.0)))
        driver.get(url)

        from selenium.webdriver.common.by import By
        import time

        for step in steps:
            action = (step.get("action") or "").lower().strip()
            selector = step.get("selector")
            if action == "wait":
                ms = int(step.get("ms", 500))
                time.sleep(max(0, ms) / 1000.0)
                continue

            if not selector:
                raise RuntimeError("step.selector is required for click/type")

            el = driver.find_element(By.CSS_SELECTOR, selector)
            if action == "click":
                el.click()
            elif action == "type":
                text = step.get("text", "")
                el.clear()
                el.send_keys(text)
            else:
                raise RuntimeError(f"unknown action: {action}")

        result: Dict[str, Any] = {"url": url, "steps": len(steps), "final_url": driver.current_url, "title": driver.title}
        if screenshot:
            import base64
            png = driver.get_screenshot_as_png()
            result["png_base64"] = base64.b64encode(png).decode("ascii")
        return result
    finally:
        try:
            driver.quit()
        except Exception:
            pass











