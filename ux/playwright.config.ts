import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/tests",
  // Pipeline run→review→apply specs are deferred: the run wizard is currently
  // unreachable in the UI (no run affordance + missing route <Outlet/>).
  // Tracked in https://github.com/tinkermonkey/context-studio/issues/1108.
  // Re-enable once the product bug is fixed and the specs are rewritten against
  // the current UI (the deterministic E2E LLM-fake infra is described there).
  testIgnore: ["**/pipelines/**"],
  // Boot an isolated test stack (backend :8888 + frontend :3888 with their own
  // DBs) for the run, and tear it down after. Dev servers are never touched.
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["html", { outputFolder: "e2e/reports" }]],
  use: {
    baseURL: "http://localhost:3888",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // No webServer block: e2e/global-setup.ts starts the isolated backend (:8888)
  // and frontend (:3888) and global-teardown stops them.
});
