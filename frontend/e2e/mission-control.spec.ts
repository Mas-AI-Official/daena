import { test, expect } from '@playwright/test'

// PR-1 Mission Control smoke.
//
// playwright.config.ts has no webServer block and /mission-control is an
// auth-gated route, so this spec needs a live stack to execute: a Vite dev
// server on :5173, a seeded backend reachable through the vite proxy, and a
// valid founder JWT exported as E2E_DAENA_TOKEN. Without the token we skip
// rather than report a false pass or a false failure (Rule 17 honesty).
const TOKEN = process.env.E2E_DAENA_TOKEN

test('mission control renders the org graph', async ({ page }) => {
  test.skip(!TOKEN, 'set E2E_DAENA_TOKEN and run the dev stack to execute this smoke')

  await page.addInitScript((token) => {
    window.localStorage.setItem('daena_token', token as string)
  }, TOKEN)

  await page.goto('/mission-control')
  await expect(page.getByText(/entities/i)).toBeVisible()
  await expect(page.locator('canvas')).toBeVisible()
  const ribbon = await page.getByText(/entities/i).textContent()
  expect(ribbon).toMatch(/[1-9]/)
})
