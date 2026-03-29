"""
Daena Demo Scenario: Playwright-based screenshot capture.
Registers a test user, navigates through all key pages,
and captures a screenshot at each step.

Usage:
    python scripts/demo_scenario.py

Requires: pip install playwright && python -m playwright install chromium
Requires: backend + frontend running (localhost:8000 + localhost:5173)
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
    "email": f"demo-{ts}@mas-ai.co",
    "password": "DemoPass123!@#",
}


def preflight():
    """Check backend and frontend are accessible."""
    checks = [
        ("http://127.0.0.1:8000/api/v1/health", "Backend"),
        ("http://localhost:5173", "Frontend"),
    ]
    for url, name in checks:
        try:
            urllib.request.urlopen(url, timeout=10)
            print(f"[preflight] {name}: OK")
        except Exception:
            # Try alternative addresses
            alt_ok = False
            for alt in ["http://127.0.0.1:5173", "http://[::1]:5173"]:
                if "5173" in url:
                    try:
                        urllib.request.urlopen(alt, timeout=5)
                        print(f"[preflight] {name}: OK ({alt})")
                        alt_ok = True
                        break
                    except Exception:
                        continue
            if not alt_ok:
                print(f"[preflight] {name}: NOT RUNNING")
                print("Start servers first: start-backend.bat + npm run dev")
                sys.exit(1)


def screenshot(page, name: str, wait_ms: int = 2000):
    """Wait for content to load, then take a screenshot."""
    page.wait_for_load_state("networkidle")
    # Wait for skeleton loaders to disappear
    try:
        page.wait_for_selector(".animate-pulse", state="hidden", timeout=3000)
    except Exception:
        pass  # No skeleton loaders present
    time.sleep(wait_ms / 1000)
    path = os.path.join(SCREENSHOT_DIR, name)
    page.screenshot(path=path, full_page=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"  [{name}] {size_kb:.0f} KB")
    return path


def run_demo():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    preflight()

    results = []
    failures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            # ── Register ──
            print("\n[demo] Registering test user...")
            page.goto(f"{BASE_URL}/register")
            page.wait_for_load_state("networkidle")

            page.get_by_label("Display Name", exact=True).fill(DEMO_USER["name"])
            page.get_by_label("Organization", exact=True).fill(DEMO_USER["org"])
            page.get_by_label("Email", exact=True).fill(DEMO_USER["email"])

            pw_inputs = page.locator("input[type='password']")
            pw_inputs.nth(0).fill(DEMO_USER["password"])
            pw_inputs.nth(1).fill(DEMO_USER["password"])

            page.locator('button:has-text("Create Workspace")').click()
            page.wait_for_url("**/chat**", timeout=30000)
            print("[demo] Registered. Starting screenshot sequence.\n")

            # ── a. Chat: send message, wait for response ──
            print("[step a] Chat: send message + wait for response")
            chat_input = page.locator(
                'textarea[placeholder*="Message"], textarea[placeholder*="Daena"]'
            ).first
            chat_input.wait_for(state="visible", timeout=8000)
            chat_input.click()
            chat_input.fill("What can you help me with?")
            chat_input.press("Enter")

            # Wait for streamed response (up to 60s)
            # The orchestrator pipeline has 10 stages before LLM response streams
            try:
                page.wait_for_function(
                    """() => {
                        // Look for any assistant message bubble or streamed content
                        const msgs = document.querySelectorAll('[class*="message"], [class*="Message"]');
                        if (msgs.length >= 2) return true;
                        // Fallback: check for substantial text beyond user input
                        const body = document.body.textContent || '';
                        return body.length > 500;
                    }""",
                    timeout=60000,
                )
            except Exception:
                print("  [warn] LLM response timeout, screenshotting anyway")

            results.append(screenshot(page, "01_chat.png", 1000))

            # ── b. Governance > Audit Log ──
            print("[step b] Governance > Audit Log")
            try:
                page.goto(f"{BASE_URL}/governance/audit")
                results.append(screenshot(page, "02_audit.png"))
            except Exception as e:
                failures.append(("02_audit.png", str(e)))
                print(f"  [FAIL] {e}")

            # ── c. Founder > Control Panel ──
            print("[step c] Founder > Control Panel")
            try:
                page.goto(f"{BASE_URL}/founder")
                results.append(screenshot(page, "03_founder.png"))
            except Exception as e:
                failures.append(("03_founder.png", str(e)))
                print(f"  [FAIL] {e}")

            # ── d. Settings > LLM ──
            print("[step d] Settings > LLM")
            try:
                page.goto(f"{BASE_URL}/settings/llm")
                results.append(screenshot(page, "04_settings_llm.png"))
            except Exception as e:
                failures.append(("04_settings_llm.png", str(e)))
                print(f"  [FAIL] {e}")

            # ── e. Settings > Governance ──
            print("[step e] Settings > Governance")
            try:
                page.goto(f"{BASE_URL}/settings/governance")
                results.append(screenshot(page, "05_governance.png"))
            except Exception as e:
                failures.append(("05_governance.png", str(e)))
                print(f"  [FAIL] {e}")

            # ── f. Skills ──
            print("[step f] Skills")
            try:
                page.goto(f"{BASE_URL}/skills")
                results.append(screenshot(page, "06_skills.png"))
            except Exception as e:
                failures.append(("06_skills.png", str(e)))
                print(f"  [FAIL] {e}")

            # ── g. Departments ──
            print("[step g] Departments")
            try:
                page.goto(f"{BASE_URL}/departments")
                results.append(screenshot(page, "07_departments.png"))
            except Exception as e:
                failures.append(("07_departments.png", str(e)))
                print(f"  [FAIL] {e}")

            # ── h. Back to Chat ──
            print("[step h] Chat (final)")
            try:
                page.goto(f"{BASE_URL}/chat")
                results.append(screenshot(page, "08_chat_final.png"))
            except Exception as e:
                failures.append(("08_chat_final.png", str(e)))
                print(f"  [FAIL] {e}")

        except Exception as e:
            print(f"\n[demo] FATAL: {e}")
            failures.append(("setup", str(e)))
        finally:
            browser.close()

    # Report
    print(f"\n{'=' * 50}")
    print(f"Screenshots: {len(results)} captured, {len(failures)} failed")
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
    run_demo()
