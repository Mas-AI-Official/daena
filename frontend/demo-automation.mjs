/**
 * Daena Demo Browser Automation
 * Playwright script that drives a 60-second product walkthrough.
 * Run from frontend/ directory: node demo-automation.mjs
 */
import { chromium } from '@playwright/test';

const BASE_URL = 'http://localhost:5173';
const ts = Date.now();
const DEMO_USER = {
  name: 'Masoud Masoori',
  org: 'MAS-AI Technologies',
  email: `demo-${ts}@mas-ai.co`,
  password: 'DemoPass123!@#',
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  console.log('[automation] Launching browser (headed)...');

  const browser = await chromium.launch({
    headless: false,
    args: ['--start-maximized', '--window-position=0,0'],
  });

  const DEMO_DIR = 'D:/Ideas/Daena/Doc/demo';
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: DEMO_DIR,
      size: { width: 1920, height: 1080 },
    },
  });

  const page = await context.newPage();
  page.setDefaultTimeout(30_000);

  try {
    // ── 0-5s: Register ─────────────────────────────────
    console.log('[automation] 0-5s: Register...');
    await page.goto(`${BASE_URL}/register`);
    await page.waitForLoadState('networkidle');
    await sleep(500);

    await page.getByLabel('Display Name', { exact: true }).fill(DEMO_USER.name);
    await sleep(150);
    await page.getByLabel('Organization', { exact: true }).fill(DEMO_USER.org);
    await sleep(150);
    await page.getByLabel('Email', { exact: true }).fill(DEMO_USER.email);
    await sleep(150);

    const pwInputs = page.locator('input[type="password"]');
    await pwInputs.nth(0).fill(DEMO_USER.password);
    await sleep(150);
    await pwInputs.nth(1).fill(DEMO_USER.password);
    await sleep(300);

    await page.locator('button:has-text("Create Workspace")').click();
    await page.waitForURL('**/chat**', { timeout: 15_000 });
    console.log('[automation] Registered. On /chat.');
    await sleep(2000);

    // ── 5-15s: Chat message ────────────────────────────
    console.log('[automation] 5-15s: Chat demo...');
    const chatInput = page
      .locator('textarea[placeholder*="Message"], textarea[placeholder*="Daena"]')
      .first();
    await chatInput.waitFor({ state: 'visible', timeout: 8_000 });
    await chatInput.click();

    // Type slowly for visual effect (40ms per char)
    const msg = "Explain how Daena's governance works";
    for (const ch of msg) {
      await chatInput.type(ch, { delay: 40 });
    }
    await sleep(500);
    await chatInput.press('Enter');

    console.log('[automation] Waiting for LLM response...');
    await sleep(10_000);

    // ── 15-25s: Governance > Audit Trail ───────────────
    console.log('[automation] 15-25s: Governance > Audit Trail...');
    await page.goto(`${BASE_URL}/governance/audit`);
    await page.waitForLoadState('networkidle');
    // Slow scroll down to show content
    await page.mouse.wheel(0, 200);
    await sleep(3000);
    await page.mouse.wheel(0, 200);
    await sleep(5000);

    // ── 25-35s: Founder > Control Panel ────────────────
    console.log('[automation] 25-35s: Founder > Control Panel...');
    await page.goto(`${BASE_URL}/founder`);
    await page.waitForLoadState('networkidle');
    await sleep(3000);
    await page.mouse.wheel(0, 300);
    await sleep(5000);

    // ── 35-45s: Settings > LLM ─────────────────────────
    console.log('[automation] 35-45s: Settings > LLM...');
    await page.goto(`${BASE_URL}/settings/llm`);
    await page.waitForLoadState('networkidle');
    await sleep(3000);
    await page.mouse.wheel(0, 300);
    await sleep(5000);

    // ── 45-55s: Departments (8 departments) ────────────
    console.log('[automation] 45-55s: Departments...');
    await page.goto(`${BASE_URL}/departments`);
    await page.waitForLoadState('networkidle');
    await sleep(3000);
    await page.mouse.wheel(0, 300);
    await sleep(5000);

    // ── 55-60s: Back to chat ───────────────────────────
    console.log('[automation] 55-60s: Back to chat...');
    await page.goto(`${BASE_URL}/chat`);
    await page.waitForLoadState('networkidle');
    await sleep(5000);

    console.log('[automation] Demo flow complete.');
  } catch (err) {
    console.error('[automation] ERROR:', err.message);
    process.exitCode = 1;
  } finally {
    // Get Playwright's viewport-only recording path before closing
    const videoPath = await page.video()?.path();
    await context.close();
    await browser.close();
    if (videoPath) {
      const fs = await import('node:fs');
      const dest = `${DEMO_DIR}/daena-demo-viewport.webm`;
      try {
        fs.default.copyFileSync(videoPath, dest);
        console.log(`[automation] Viewport recording saved: ${dest}`);
      } catch (e) {
        console.log(`[automation] Viewport video at: ${videoPath}`);
      }
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
