"""
Daena Extra Demo Screenshots: captures additional pages not in the main demo.

Navigates to DaenaBot, Founder Policy Editor, and Skill Refinery pages.
Reuses the same auth session approach as demo_scenario.py.

Usage:
    python scripts/demo_extra_screenshots.py

Requires: playwright, backend + frontend running
"""
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:5173"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_DIR = os.path.join(PROJECT_ROOT, "Doc", "demo", "screenshots")

ts = int(time.time())
DEMO_USER = {
    "name": "Masoud Masoori",
    "org": "MAS-AI Technologies",
    "email": f"extra-{ts}@mas-ai.co",
    "password": "DemoPass123!@#",
}

EXTRA_PAGES = [
    {
        "name": "09_daenabot.png",
        "url": "/daenabot",
        "label": "DaenaBot (Tool Execution)",
        "wait_ms": 2000,
    },
    {
        "name": "10_founder_policy.png",
        "url": "/founder",
        "label": "Founder Policy Editor",
        "wait_ms": 2000,
        "scroll": True,
    },
    {
        "name": "11_skill_refinery.png",
        "url": "/skills",
        "label": "Skill Refinery",
        "wait_ms": 2000,
    },
]


def preflight():
    """Check backend and frontend are accessible."""
    for url, name in [
        ("http://127.0.0.1:8000/api/v1/health", "Backend"),
        ("http://localhost:5173", "Frontend"),
    ]:
        try:
            urllib.request.urlopen(url, timeout=10)
            print(f"[preflight] {name}: OK")
        except Exception:
            print(f"[preflight] {name}: NOT RUNNING")
            sys.exit(1)


def screenshot(page, name: str, wait_ms: int = 2000):
    """Wait for content to load, then take a screenshot."""
    page.wait_for_load_state("networkidle")
    try:
        page.wait_for_selector(".animate-pulse", state="hidden", timeout=3000)
    except Exception:
        pass
    time.sleep(wait_ms / 1000)
    path = os.path.join(SCREENSHOT_DIR, name)
    page.screenshot(path=path, full_page=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"  [{name}] {size_kb:.0f} KB")
    return path


def run_extra_screenshots():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    preflight()

    results = []
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            # Register a fresh user
            print("\n[extra] Registering test user...")
            page.goto(f"{BASE_URL}/register")
            page.wait_for_load_state("networkidle")

            page.get_by_label("Display Name", exact=True).fill(DEMO_USER["name"])
            page.get_by_label("Organization", exact=True).fill(DEMO_USER["org"])
            page.get_by_label("Email", exact=True).fill(DEMO_USER["email"])

            pw_inputs = page.locator("input[type='password']")
            pw_inputs.nth(0).fill(DEMO_USER["password"])
            pw_inputs.nth(1).fill(DEMO_USER["password"])

            page.locator('button:has-text("Create Workspace")').click()
            page.wait_for_url("**/chat**", timeout=15000)
            print("[extra] Registered. Capturing extra pages.\n")

            for pg_info in EXTRA_PAGES:
                label = pg_info["label"]
                print(f"[extra] {label}")
                try:
                    page.goto(f"{BASE_URL}{pg_info['url']}")
                    if pg_info.get("scroll"):
                        page.wait_for_load_state("networkidle")
                        page.evaluate("window.scrollTo(0, 400)")
                        time.sleep(0.5)
                    results.append(
                        screenshot(page, pg_info["name"], pg_info["wait_ms"])
                    )
                except Exception as e:
                    failures.append((pg_info["name"], str(e)))
                    print(f"  [FAIL] {e}")

        except Exception as e:
            print(f"\n[extra] FATAL: {e}")
            failures.append(("setup", str(e)))
        finally:
            browser.close()

    print(f"\n{'=' * 50}")
    print(f"Extra screenshots: {len(results)} captured, {len(failures)} failed")
    print(f"Location: {SCREENSHOT_DIR}")
    for path in results:
        name = os.path.basename(path)
        size_kb = os.path.getsize(path) / 1024
        print(f"  {name}: {size_kb:.0f} KB")
    if failures:
        print("\nFailures:")
        for name, err in failures:
            print(f"  {name}: {err}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    run_extra_screenshots()
