/**
 * Trust Ladder deterministic gate -- BUILD-NOW #1.
 *
 * Regression bar: GovernanceTrustPage.tsx used to pass `/api/v1/trust/*`
 * on top of `api` axios client baseURL `/api/v1`, producing
 * `/api/v1/api/v1/trust/*` 404s. Fix strips the leading `/api/v1` from
 * the three axios call sites. This spec locks the fix.
 *
 * Assertions:
 *   1. GET /trust/policies fires exactly at `/api/v1/trust/policies`
 *      (single prefix).
 *   2. GET /trust/eligible-tools fires exactly at
 *      `/api/v1/trust/eligible-tools` (single prefix).
 *   3. Zero requests contain `/api/v1/api/v1/`.
 *   4. The mocked policy row renders in the Trust Ladder tab.
 */
import { test, expect, type Page, type Route } from '@playwright/test'

const ts = Date.now()
const TEST_USER = {
  name: `Trust E2E ${ts}`,
  org: `TrustOrg-${ts}`,
  email: `trust-e2e-${ts}@example.com`,
  password: 'TestPass123!@#',
}

const FIXTURE_TOOL_ID = 'workstream.draft.compose'
const FIXTURE_TEMPLATE = 'workstream_low_risk_v1'

const POLICIES_FIXTURE = [
  {
    tool_id: FIXTURE_TOOL_ID,
    template_class: FIXTURE_TEMPLATE,
    max_auto_tier: 'suggest_only',
    locked_reason: null,
    approvals_count: 3,
    rejection_count: 0,
    last_approved_at: '2026-07-08T12:00:00Z',
    last_rejected_at: null,
    eligible: true,
    forbidden: false,
  },
]

const ELIGIBILITY_FIXTURE = {
  eligible_tools: [FIXTURE_TOOL_ID],
  forbidden_tools: ['broker.order.execute'],
  available_tiers: ['none', 'suggest_only', 'auto_approve_low_risk'],
  min_approvals_to_graduate: 3,
}

async function fillInput(page: Page, label: string, value: string) {
  await page.getByLabel(label, { exact: true }).fill(value)
}

async function registerAndLogin(page: Page) {
  await page.goto('/register')
  await fillInput(page, 'Display Name', TEST_USER.name)
  await fillInput(page, 'Organization', TEST_USER.org)
  await fillInput(page, 'Email', TEST_USER.email)
  const passwordInputs = page.locator('input[type="password"]')
  await passwordInputs.nth(0).fill(TEST_USER.password)
  await passwordInputs.nth(1).fill(TEST_USER.password)
  await page.locator('input[type="checkbox"]').first().check()
  await page.locator('button:has-text("Create Workspace")').click()
  await page.waitForURL(/\/(chat|dashboard)/, { timeout: 15_000 })
}

test.describe('Trust Ladder axios baseURL fix (BUILD-NOW #1)', () => {
  test.describe.configure({ mode: 'serial' })
  let page: Page
  const trustRequestUrls: string[] = []

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext()
    page = await context.newPage()
    page.setDefaultTimeout(15_000)

    page.on('request', (req) => {
      const url = req.url()
      if (url.includes('/trust/')) {
        trustRequestUrls.push(new URL(url).pathname)
      }
    })
  })

  test.afterAll(async () => {
    await page.close()
  })

  test('policies + eligible-tools fire on single /api/v1 prefix and render', async () => {
    await page.route('**/trust/policies', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(POLICIES_FIXTURE),
      })
    })
    await page.route('**/trust/eligible-tools', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ELIGIBILITY_FIXTURE),
      })
    })

    await registerAndLogin(page)
    await page.goto('/governance/trust')

    await expect(
      page.locator('h1', { hasText: 'Trust Ladder' })
    ).toBeVisible({ timeout: 10_000 })

    await expect(
      page.locator('text=' + FIXTURE_TOOL_ID).first()
    ).toBeVisible({ timeout: 10_000 })

    await expect(
      page.locator('text=' + FIXTURE_TEMPLATE).first()
    ).toBeVisible()

    await expect(page.getByText('Suggest only').first()).toBeVisible()

    await expect(page.getByText('Eligibility (locked)')).toBeVisible()

    const doubled = trustRequestUrls.filter((u) => u.includes('/api/v1/api/v1/'))
    expect(
      doubled,
      `Doubled-prefix regression: ${JSON.stringify(doubled)}`
    ).toEqual([])

    expect(trustRequestUrls).toContain('/api/v1/trust/policies')
    expect(trustRequestUrls).toContain('/api/v1/trust/eligible-tools')

    await page.unroute('**/trust/policies')
    await page.unroute('**/trust/eligible-tools')
  })
})
