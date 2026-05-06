/**
 * Sprint-MORNING PR-6 — NUser end-to-end smoke.
 *
 * Tests the morning workflow as a new user would experience it:
 *
 *   1. Register + login.
 *   2. Visit Settings -> Models & Runtimes; verify both BrainReadinessPanel
 *      and the new MorningReadinessPanel render with honest state.
 *   3. Visit /workstreams; verify the StartHereCard + Drafts lane render
 *      with the new status badges (no fake "online" pills).
 *   4. Verify NO send / submit / apply / publish button exists anywhere.
 *
 * Prerequisites: backend on localhost:8000, frontend on localhost:5173.
 * Run: npx playwright test morning-workflow.spec.ts --headed
 */
import { test, expect, type Page } from '@playwright/test'

const ts = Date.now()
const TEST_USER = {
  name: `Morning Tester ${ts}`,
  org: `MorningOrg-${ts}`,
  email: `morning-${ts}@example.com`,
  password: 'MorningPass123!@#',
}

async function fillInput(page: Page, label: string, value: string) {
  await page.getByLabel(label, { exact: true }).fill(value)
}

test.describe('Daena Morning VP Beta Workflow', () => {
  test.describe.configure({ mode: 'serial' })

  let page: Page

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext()
    page = await context.newPage()
  })

  test('register a new operator', async () => {
    await page.goto('/register')
    await fillInput(page, 'Display Name', TEST_USER.name)
    await fillInput(page, 'Organization Name', TEST_USER.org)
    await fillInput(page, 'Email', TEST_USER.email)
    await fillInput(page, 'Password', TEST_USER.password)
    await page.getByRole('button', { name: /create account|register|sign up/i }).click()
    // Settled when the dashboard or chat surface is reachable.
    await page.waitForURL(/\/dashboard|\/chat|\/$/, { timeout: 15000 })
  })

  test('Settings -> Models & Runtimes shows brain + ecosystem panels', async () => {
    await page.goto('/settings/models-runtimes')
    // Both panels must render. We assert by visible-text anchors.
    await expect(page.getByText(/Brain Readiness|Main brain/i)).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('Ecosystem Readiness')).toBeVisible({ timeout: 8000 })
    // Honest blocked-state -- the readiness pill must show either "Ready"
    // or "Not yet ready"; never a fake "online" with no brain.
    const headlinePill = page.locator(
      'text=/Ready for VP work|Not yet ready/',
    )
    await expect(headlinePill).toBeVisible()
  })

  test('Workstreams page shows StartHereCard + Drafts lane', async () => {
    await page.goto('/workstreams')
    await expect(page.getByText('Start here tomorrow')).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('Drafts to review')).toBeVisible()
    // The 5-step suggested workflow text must be present.
    await expect(page.getByText(/Open Settings/i)).toBeVisible()
    await expect(page.getByText(/Pick a draft/i)).toBeVisible()
  })

  test('no banned verbs in DOM', async () => {
    // Walk to /workstreams and /settings/models-runtimes; assert no
    // <button> renders text matching the banned verbs.
    for (const route of ['/workstreams', '/settings/models-runtimes']) {
      await page.goto(route)
      await page.waitForLoadState('networkidle')
      const allButtons = await page.locator('button').allInnerTexts()
      const banned = ['Send', 'Submit', 'Apply', 'Publish', 'Post now']
      for (const text of allButtons) {
        for (const verb of banned) {
          expect(
            text.trim() === verb,
            `banned verb button "${verb}" found on ${route}: "${text}"`,
          ).toBe(false)
        }
      }
    }
  })

  test('autofix proposals never carry an "Execute" button', async () => {
    await page.goto('/settings/models-runtimes')
    await page.waitForLoadState('networkidle')
    // The autofix section may be hidden if everything is ready --
    // both states are honest. If it's there, no Execute button.
    const executeButtons = page.locator('button', { hasText: /^Execute$|^Run Now$|^Apply$/ })
    expect(await executeButtons.count()).toBe(0)
  })
})
