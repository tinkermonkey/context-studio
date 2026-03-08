import { defineConfig, devices } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Playwright configuration for Context Studio E2E tests.
 *
 * This configuration manages end-to-end testing of the full application stack,
 * including both the React frontend and FastAPI backend. Servers are started
 * once in global setup and torn down after all tests complete.
 */
export default defineConfig({
  testDir: "./e2e/tests",

  // Test execution settings
  fullyParallel: false, // Run tests sequentially (shared backend server)
  forbidOnly: !!process.env.CI, // Fail CI if test.only is used
  retries: process.env.CI ? 2 : 0, // Retry flaky tests in CI
  workers: 1, // Single worker to avoid backend conflicts

  // Reporting
  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],

  // Test behavior defaults
  use: {
    baseURL: "http://localhost:3888",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",

    // API request context for backend validation
    extraHTTPHeaders: {
      Accept: "application/json",
    },
  },

  // Global setup/teardown for server lifecycle
  globalSetup: path.resolve(__dirname, "./e2e/global-setup.ts"),
  globalTeardown: path.resolve(__dirname, "./e2e/global-teardown.ts"),

  // Browser projects
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Uncomment to test on additional browsers:
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Timeout configurations
  timeout: 30000, // 30 seconds per test
  expect: {
    timeout: 5000, // 5 seconds for assertions
  },

  // Web server config (not used - we use global setup instead for more control)
  // webServer: undefined,
});
