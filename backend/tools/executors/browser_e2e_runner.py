"""
Browser E2E Runner - Playwright-based user flow simulation for testing/validation.
Allowlisted URLs only; produces a report (no exfiltration). Defensive/local only.
"""

from __future__ import annotations

import json
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

# Allowlisted URL prefixes (local and controlled only)
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


async def run_browser_e2e(
    *,
    base_url: str,
    steps: Optional[List[Dict[str, Any]]] = None,
    timeout_ms: int = 30000,
    headless: bool = True,
    allowlist: Optional[List[str]] = None,
    report_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run E2E flow: navigate to base_url, execute steps (click, fill, etc.), capture result.
    Only allowlisted URLs. Produces report (markdown + JSON summary).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "status": "error",
            "error": "Playwright not installed. pip install playwright && playwright install",
            "report": None,
        }
    if not _allowed_url(base_url, allowlist):
        return {
            "status": "error",
            "error": "URL not in allowlist (use localhost/127.0.0.1 or configure allowlist)",
            "report": None,
        }

    steps = steps or [{"action": "navigate", "url": base_url}]
    report_entries: List[Dict[str, Any]] = []
    screenshots: List[str] = []
    err = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 720})
            page = await context.new_page()

            for i, step in enumerate(steps):
                action = (step.get("action") or "navigate").lower()
                try:
                    if action == "navigate":
                        url = step.get("url") or base_url
                        if not _allowed_url(url, allowlist):
                            report_entries.append({"step": i + 1, "action": action, "status": "denied", "reason": "url_not_allowlisted"})
                            continue
                        await page.goto(url, timeout=timeout_ms)
                        report_entries.append({"step": i + 1, "action": action, "url": url, "status": "ok"})
                    elif action == "screenshot":
                        path = step.get("path") or f"e2e_step_{i+1}.png"
                        await page.screenshot(path=path)
                        screenshots.append(path)
                        report_entries.append({"step": i + 1, "action": action, "path": path, "status": "ok"})
                    elif action == "click":
                        selector = step.get("selector") or step.get("selector")
                        if selector:
                            await page.click(selector, timeout=5000)
                            report_entries.append({"step": i + 1, "action": action, "selector": selector, "status": "ok"})
                    elif action == "fill":
                        selector = step.get("selector")
                        value = step.get("value") or ""
                        if selector:
                            await page.fill(selector, value, timeout=5000)
                            report_entries.append({"step": i + 1, "action": action, "selector": selector, "status": "ok"})
                    else:
                        report_entries.append({"step": i + 1, "action": action, "status": "skip", "reason": "unknown_action"})
                except PlaywrightTimeout as e:
                    report_entries.append({"step": i + 1, "action": action, "status": "timeout", "error": str(e)})
                    err = str(e)
                    break
                except Exception as e:
                    report_entries.append({"step": i + 1, "action": action, "status": "error", "error": str(e)})
                    err = str(e)
                    break

            await context.close()
            await browser.close()
    except Exception as e:
        err = str(e)
        report_entries.append({"status": "error", "error": str(e)})

    # Build report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "base_url": base_url,
        "steps_run": len(report_entries),
        "steps": report_entries,
        "screenshots": screenshots,
        "success": err is None and all(r.get("status") == "ok" for r in report_entries if "step" in r),
    }
    if report_path:
        try:
            p = Path(report_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(report, indent=2), encoding="utf-8")
            md = p.with_suffix(".md")
            md.write_text(
                f"# E2E Report\n\nBase URL: {base_url}\n\nSteps: {len(report_entries)}\n\n"
                + "\n".join(f"- Step {r.get('step', '?')}: {r.get('action', '')} -> {r.get('status', '')}" for r in report_entries),
                encoding="utf-8",
            )
            report["report_path"] = str(p)
            report["report_md_path"] = str(md)
        except Exception as e:
            report["report_write_error"] = str(e)

    return {
        "status": "ok" if err is None else "error",
        "error": err,
        "report": report,
    }
