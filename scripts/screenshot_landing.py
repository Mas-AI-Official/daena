"""
Take a full-page screenshot of the Daena landing page.
Opens the local HTML file directly in Playwright.
"""
import os
from playwright.sync_api import sync_playwright

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANDING_HTML = os.path.join(PROJECT_ROOT, "landing", "index.html")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "Doc", "demo", "landing-preview.png")


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        file_url = f"file:///{LANDING_HTML.replace(os.sep, '/')}"
        page.goto(file_url)
        page.wait_for_load_state("networkidle")

        # Trigger all fade-in animations by scrolling through the page
        page.evaluate("""
            () => {
                document.querySelectorAll('.fade-in').forEach(el => el.classList.add('visible'));
            }
        """)
        page.wait_for_timeout(500)

        page.screenshot(path=OUTPUT_PATH, full_page=True)
        size_kb = os.path.getsize(OUTPUT_PATH) / 1024
        print(f"Landing page screenshot saved: {OUTPUT_PATH}")
        print(f"Size: {size_kb:.0f} KB")
        browser.close()


if __name__ == "__main__":
    main()
