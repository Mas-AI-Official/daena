/**
 * Screenshot all pages: navigates to every Daena page and captures a screenshot.
 * Results saved to Doc/demo/screenshots/final/.
 */
import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const SCREENSHOT_DIR = path.resolve(__dirname, '../../Doc/demo/screenshots/final')

const ts = Date.now()
const TEST_USER = {
  name: `Screenshot Bot ${ts}`,
  org: `ScreenOrg-${ts}`,
  email: `screen-${ts}@example.com`,
  password: 'TestPass123!@#',
}

async function fillInput(page: Page, label: string, value: string) {
  await page.getByLabel(label, { exact: true }).fill(value)
}

test.describe('Screenshot All Pages', () => {
  test.describe.configure({ mode: 'serial' })

  let page: Page
  const results: { name: string; loadTime: number; errors: string[] }[] = []

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    page = await context.newPage()

    // Register + login
    await page.goto('/register')
    await fillInput(page, 'Display Name', TEST_USER.name)
    await fillInput(page, 'Organization', TEST_USER.org)
    await fillInput(page, 'Email', TEST_USER.email)
    const passwordInputs = page.locator('input[type="password"]')
    await passwordInputs.nth(0).fill(TEST_USER.password)
    await passwordInputs.nth(1).fill(TEST_USER.password)
    await page.locator('button:has-text("Create Workspace")').click()
    await page.waitForURL('**/chat', { timeout: 10000 })
  })

  test.afterAll(async () => {
    // Print results table
    console.log('\n=== Screenshot Results ===')
    for (const r of results) {
      const status = r.errors.length ? `ERRORS: ${r.errors.join(', ')}` : 'OK'
      console.log(`  ${r.name.padEnd(28)} ${String(r.loadTime).padStart(5)}ms  ${status}`)
    }
    console.log('=========================\n')
    await page.context().close()
  })

  const pages = [
    { name: 'chat', path: '/chat' },
    { name: 'dashboard', path: '/dashboard' },
    { name: 'governance-approvals', path: '/governance/approvals' },
    { name: 'governance-audit', path: '/governance/audit' },
    { name: 'founder', path: '/founder' },
    { name: 'departments', path: '/departments' },
    { name: 'skills', path: '/skills' },
    { name: 'daenabot', path: '/daenabot' },
    { name: 'tasks', path: '/tasks' },
    { name: 'connections', path: '/connections' },
    { name: 'settings-general', path: '/settings/general' },
    { name: 'settings-appearance', path: '/settings/appearance' },
    { name: 'settings-governance', path: '/settings/governance' },
    { name: 'settings-llm', path: '/settings/llm' },
    { name: 'settings-memory', path: '/settings/memory' },
    { name: 'settings-connections', path: '/settings/connections' },
    { name: 'settings-daenabot', path: '/settings/daenabot' },
    { name: 'settings-developer', path: '/settings/developer' },
    { name: 'settings-about', path: '/settings/about' },
  ]

  for (const p of pages) {
    test(`screenshot: ${p.name}`, async () => {
      const consoleErrors: string[] = []
      const errorHandler = (msg: import('@playwright/test').ConsoleMessage) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text())
      }
      page.on('console', errorHandler)

      const start = Date.now()
      await page.goto(p.path)
      await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {})
      await page.waitForTimeout(800)
      const loadTime = Date.now() - start

      await page.screenshot({
        path: path.join(SCREENSHOT_DIR, `${p.name}.png`),
        fullPage: false,
      })

      page.off('console', errorHandler)
      results.push({ name: p.name, loadTime, errors: consoleErrors })
      console.log(`${p.name}: ${loadTime}ms${consoleErrors.length ? ` (${consoleErrors.length} errors)` : ''}`)

      const title = await page.title()
      expect(title).toContain('Daena')
    })
  }

  test('chat: send message and verify response', async () => {
    test.setTimeout(120000)
    await page.goto('/chat')
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {})

    // Type and send a message
    const input = page.locator('textarea[aria-label="Message input"]')
    await input.fill('What is 2+2?')
    await page.locator('button[aria-label="Send message"]').click()

    // Wait for streaming response to appear (up to 60s for Ollama cold start)
    const aiResponse = page.locator('[class*="glass-card"]').last()
    await expect(aiResponse).toBeVisible({ timeout: 60000 })

    // Wait for streaming to finish (send button reappears, stop button disappears)
    await expect(page.locator('button[aria-label="Send message"]')).toBeVisible({ timeout: 60000 })

    await page.waitForTimeout(1000)
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, 'chat-with-response.png'),
      fullPage: false,
    })

    console.log('chat-with-response: captured')
  })
})
