/**
 * Daena E2E Flow — full user journey test.
 *
 * Prerequisites: frontend (localhost:5173) and backend (localhost:8000) must be running.
 *
 * Flow:
 *   1. Register a new user
 *   2. Login with that user
 *   3. Send a chat message and verify streaming response
 *   4. Navigate to Departments and verify 10 render
 *   5. Navigate to Settings and toggle a setting
 *   6. Navigate to Dashboard (Control Room) and verify hex hive
 */
import { test, expect, type Page } from '@playwright/test'

// Unique test user per run to avoid collisions
const ts = Date.now()
const TEST_USER = {
  name: `E2E Tester ${ts}`,
  org: `TestOrg-${ts}`,
  email: `e2e-${ts}@example.com`,
  password: 'TestPass123!@#',
}

// ── Helpers ──────────────────────────────────────────

async function fillInput(page: Page, label: string, value: string) {
  // Input component uses <label htmlFor={id}> + <input id={id}> — getByLabel handles this
  await page.getByLabel(label, { exact: true }).fill(value)
}

// ── Test Suite ───────────────────────────────────────

test.describe('Daena Full E2E Flow', () => {
  test.describe.configure({ mode: 'serial' })

  let page: Page

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext()
    page = await context.newPage()
    page.setDefaultTimeout(15_000)
  })

  test.afterAll(async () => {
    await page.close()
  })

  // ── Step 1: Register ──

  test('1. Register a new user', async () => {
    await page.goto('/register')
    await expect(page.locator('h2:has-text("Register")')).toBeVisible()

    // Fill form fields
    await fillInput(page, 'Display Name', TEST_USER.name)
    await fillInput(page, 'Organization', TEST_USER.org)
    await fillInput(page, 'Email', TEST_USER.email)

    // Password fields — use specific locators since there are two password inputs
    const passwordInputs = page.locator('input[type="password"]')
    await passwordInputs.nth(0).fill(TEST_USER.password)
    await passwordInputs.nth(1).fill(TEST_USER.password)

    // Intercept the register API call to capture any error
    const responsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/auth/register'),
      { timeout: 15_000 },
    )

    // Submit
    await page.locator('button:has-text("Create Workspace")').click()

    // Check the API response
    const response = await responsePromise
    if (!response.ok()) {
      const body = await response.json().catch(() => null)
      console.error('Register API failed:', response.status(), JSON.stringify(body, null, 2))
    }
    expect(response.ok(), `Register API returned ${response.status()}`).toBeTruthy()

    // Should redirect to /chat on success
    await expect(page).toHaveURL(/\/chat/, { timeout: 10_000 })
  })

  // ── Step 2: Logout then Login ──

  test('2. Login with registered user', async () => {
    // Logout first (click avatar or go to login directly)
    const logoutBtn = page.locator('button:has-text("Logout"), a:has-text("Logout"), text="Logout"')
    if (await logoutBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await logoutBtn.click()
      await page.waitForURL(/\/login/, { timeout: 5000 })
    } else {
      // Force navigate to login
      await page.goto('/login')
    }

    await expect(page.locator('h2:has-text("Sign in")')).toBeVisible()

    // Fill login form
    await fillInput(page, 'Email', TEST_USER.email)
    const passwordInput = page.locator('input[type="password"]').first()
    await passwordInput.fill(TEST_USER.password)

    await page.locator('button:has-text("Sign in")').click()

    // Should land on /chat
    await expect(page).toHaveURL(/\/chat/, { timeout: 10_000 })
  })

  // ── Step 3: Send chat message + verify streaming ──

  test('3. Send a chat message and verify response', async () => {
    // We're already on /chat from step 2 — don't reload (avoids auth hydration race).
    if (!page.url().includes('/chat')) {
      await page.goto('/chat')
    }
    await page.waitForLoadState('networkidle')

    // The chat input should be visible
    const input = page.locator('textarea[placeholder*="Message"], textarea[placeholder*="Daena"]').first()
    await expect(input).toBeVisible({ timeout: 8_000 })

    await input.fill('Hello Daena, what can you do?')
    await input.press('Enter')

    // Wait for the user message to appear
    await expect(page.locator('text="Hello Daena, what can you do?"')).toBeVisible({ timeout: 10_000 })

    // Wait for an assistant response — the SYSTEM role message bubble or streaming content.
    // The message container is the first .max-w-4xl (the scrollable list, not the input bar).
    // Give the LLM up to 45s to produce visible content beyond the user's own message.
    await page.waitForFunction(
      (userMsg: string) => {
        const container = document.querySelector('.overflow-y-auto .max-w-4xl')
        if (!container) return false
        const text = container.textContent || ''
        // Strip out the user message and check remaining text length
        const remaining = text.replace(userMsg, '').replace(/Edit/g, '').trim()
        return remaining.length > 20
      },
      'Hello Daena, what can you do?',
      { timeout: 45_000 },
    )
  })

  // ── Step 4: Navigate to Departments, verify 10 render ──

  test('4. Navigate to Departments and verify 10 departments', async () => {
    // Click Departments in sidebar
    await page.getByRole('link', { name: 'Departments' }).first().click()
    await expect(page).toHaveURL(/\/departments/, { timeout: 5000 })

    // Wait for department cards to load
    await page.waitForLoadState('networkidle')

    // Each department shows as a card. Verify all 10 names are visible.
    const deptNames = [
      'Engineering', 'Product', 'Marketing', 'Sales', 'Finance',
      'Operations', 'Research', 'Legal & Compliance', 'Skill Governance', 'Security Operations',
    ]

    for (const name of deptNames) {
      await expect(
        page.getByText(name, { exact: true }).first()
      ).toBeVisible({ timeout: 8_000 })
    }

    // Count department cards — should be at least 10
    const cards = page.locator('[class*="card"], [class*="Card"]').filter({
      hasText: /Engineering|Product|Marketing|Sales|Finance|Operations|Research|Legal|Skill|Security/,
    })
    const count = await cards.count()
    expect(count).toBeGreaterThanOrEqual(10)
  })

  // ── Step 5: Navigate to Settings, toggle a setting ──

  test('5. Navigate to Settings and toggle a setting', async () => {
    await page.getByRole('link', { name: 'Settings' }).first().click()
    await expect(page).toHaveURL(/\/settings/, { timeout: 5000 })

    // The General tab has a CMD/EXE toggle. Let's toggle it.
    await expect(page.getByText('Session Defaults')).toBeVisible({ timeout: 5000 })

    // Find the CMD/EXE toggle buttons
    const exeButton = page.locator('button:has-text("EXE")').last()
    const cmdButton = page.locator('button:has-text("CMD")').last()

    // Get current state — check which one has the active styling
    const exeClasses = await exeButton.getAttribute('class') || ''
    const isExeActive = exeClasses.includes('primary-500') || exeClasses.includes('primary-400')

    if (isExeActive) {
      // Currently EXE, toggle to CMD
      await cmdButton.click()
      await expect(cmdButton).toHaveClass(/primary/, { timeout: 3000 })
    } else {
      // Currently CMD, toggle to EXE
      await exeButton.click()
      await expect(exeButton).toHaveClass(/primary/, { timeout: 3000 })
    }

    // Toggle back to verify bidirectional
    if (isExeActive) {
      await exeButton.click()
      await expect(exeButton).toHaveClass(/primary/, { timeout: 3000 })
    } else {
      await cmdButton.click()
      await expect(cmdButton).toHaveClass(/primary/, { timeout: 3000 })
    }
  })

  // ── Step 6: Navigate to Dashboard (Control Room), verify hex hive ──

  test('6. Navigate to Dashboard and verify it renders', async () => {
    await page.getByRole('link', { name: 'Dashboard' }).first().click()
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5000 })

    await page.waitForLoadState('networkidle')

    // Dashboard shows stat cards: Chat Sessions, Pending Approvals, Memories
    await expect(page.getByText('Chat Sessions')).toBeVisible({ timeout: 8000 })
    await expect(page.getByText('Pending Approvals')).toBeVisible({ timeout: 5000 })
    await expect(page.getByText('Memories')).toBeVisible({ timeout: 5000 })
  })
})
