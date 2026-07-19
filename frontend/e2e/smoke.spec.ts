import { test, expect } from "@playwright/test"

// Frontend smoke tests: public pages render and auth gating works. No analysis
// backend required (these never upload data or run a test).

test.describe("public pages", () => {
  test("landing renders and links into the product", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByText("Everything a research assistant should be")).toBeVisible()
    await expect(page.locator('a[href="/login"]').first()).toBeVisible()
    await expect(page.locator('a[href="/signup"]').first()).toBeVisible()
  })

  test("login page shows the sign-in form", async ({ page }) => {
    await page.goto("/login")
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible()
  })

  test("signup page shows the create-account form", async ({ page }) => {
    await page.goto("/signup")
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.getByRole("button", { name: "Create account" })).toBeVisible()
  })

  test("legal pages render", async ({ page }) => {
    await page.goto("/privacy")
    await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible()
    await page.goto("/terms")
    await expect(page.getByRole("heading", { name: "Terms of Service" })).toBeVisible()
  })
})

test.describe("auth gating (unauthenticated)", () => {
  test("/app redirects to login", async ({ page }) => {
    await page.goto("/app")
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible()
  })

  test("/billing redirects to login", async ({ page }) => {
    await page.goto("/billing")
    await expect(page).toHaveURL(/\/login/)
  })
})
