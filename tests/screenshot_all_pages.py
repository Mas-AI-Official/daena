"""Take screenshots of all Daena pages for launch verification."""
import requests
import time
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

BASE_API = "http://localhost:8000/api/v1"
BASE_UI = "http://localhost:5173"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "Doc", "demo", "screenshots", "final")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Get auth token
r = requests.post(f"{BASE_API}/auth/login", json={
    "email": "autotest@daena.ai", "password": "TestPass123456!"
})
token = r.json().get("data", {}).get("access_token", "")
if not token:
    print("FAIL: Could not get auth token")
    sys.exit(1)

print(f"Auth token obtained: {token[:20]}...")

# Install playwright if needed
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    from playwright.sync_api import sync_playwright

PAGES = [
    ("/chat", "01_chat"),
    ("/dashboard", "02_dashboard"),
    ("/governance/approvals", "03_approvals"),
    ("/governance/audit", "04_audit"),
    ("/departments", "05_departments"),
    ("/skills", "06_skills"),
    ("/tasks", "07_tasks"),
    ("/daenabot", "08_daenabot"),
    ("/connections", "09_connections"),
    ("/settings/general", "10_settings_general"),
    ("/settings/appearance", "11_settings_appearance"),
    ("/settings/governance", "12_settings_governance"),
    ("/settings/llm", "13_settings_llm"),
    ("/settings/memory", "14_settings_memory"),
    ("/settings/connections", "15_settings_connections"),
    ("/settings/daenabot", "16_settings_daenabot"),
    ("/settings/developer", "17_settings_developer"),
    ("/settings/about", "18_settings_about"),
    ("/founder", "19_founder"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        color_scheme="dark",
    )
    page = context.new_page()

    # Login via evaluate: fill fields + submit via JS
    page.goto(f"{BASE_UI}/login", wait_until="networkidle")
    time.sleep(2)

    # Fill email
    page.evaluate("""() => {
        const emailInput = document.querySelector('input[type="email"]') || document.querySelectorAll('input')[0];
        if (emailInput) {
            const nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSet.call(emailInput, 'autotest@daena.ai');
            emailInput.dispatchEvent(new Event('input', {bubbles: true}));
            emailInput.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }""")
    time.sleep(0.3)

    # Fill password
    page.evaluate("""() => {
        const pwInput = document.querySelector('input[type="password"]');
        if (pwInput) {
            const nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSet.call(pwInput, 'TestPass123456!');
            pwInput.dispatchEvent(new Event('input', {bubbles: true}));
            pwInput.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }""")
    time.sleep(0.3)

    # Click Sign in
    page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const signIn = btns.find(b => b.textContent.trim() === 'Sign in');
        if (signIn) signIn.click();
    }""")

    # Wait for redirect (poll URL)
    for _ in range(20):
        time.sleep(0.5)
        if "/login" not in page.url and "/register" not in page.url:
            break
    time.sleep(2)
    print(f"Auth complete: {page.title()} at {page.url}")

    results = []
    for path, name in PAGES:
        try:
            # Use SPA navigation to preserve auth state
            page.evaluate(f"window.history.pushState(null, '', '{path}')")
            page.evaluate("window.dispatchEvent(new PopStateEvent('popstate'))")
            time.sleep(2)  # Wait for route + data loading

            # Verify not on login page
            current_title = page.title()
            if "Sign In" in current_title:
                # Auth expired, try full navigation as fallback
                page.goto(f"{BASE_UI}{path}", wait_until="networkidle", timeout=15000)
                time.sleep(1.5)
                current_title = page.title()

            filepath = os.path.join(SCREENSHOT_DIR, f"{name}.png")
            page.screenshot(path=filepath, full_page=False)

            results.append(("PASS", name, current_title))
            print(f"  [PASS] {name}: {current_title}")
        except Exception as e:
            results.append(("FAIL", name, str(e)[:80]))
            print(f"  [FAIL] {name}: {str(e)[:80]}")

    browser.close()

passes = sum(1 for r in results if r[0] == "PASS")
print(f"\nTotal: {passes}/{len(results)} pages screenshotted")
print(f"Screenshots saved to: {SCREENSHOT_DIR}")
