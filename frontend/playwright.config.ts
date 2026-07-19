import { defineConfig, devices } from "@playwright/test"

// UI smoke tests for public pages + auth gating. These deliberately DO NOT
// exercise the analysis backend (E2B / LLM) — they cover the frontend rendering
// and routing surface, which was previously untested. The webServer starts the
// Next dev server; no separate backend is needed for these flows.
//
// Run: npm run test:e2e
// Defaults to 3000 to match `next dev`; with a dev server already running,
// Playwright reuses it (Next 16 allows only one dev server per project).
const PORT = Number(process.env.E2E_PORT || 3000)
const baseURL = `http://localhost:${PORT}`

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 45_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    trace: "on-first-retry",
    navigationTimeout: 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx next dev -p ${PORT}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
})
