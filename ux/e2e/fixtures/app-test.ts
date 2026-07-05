import { test as base, expect } from "@playwright/test";
import { clearTestData } from "./factories";

/**
 * Shared Playwright test fixture for Context Studio app specs.
 *
 * The app gates every route on a workspace path in localStorage (otherwise it
 * redirects to /welcome). The isolated test backend serves its own data via
 * VITE_API_BASE_URL regardless of this value, so any non-empty path satisfies
 * the gate. Seeding it here (before any page script runs) lets specs navigate
 * straight into /app without going through the workspace switcher.
 *
 * The backend is shared across the whole (serialized) suite, so this fixture
 * also wipes all ontology data before each test. That guarantees every test
 * starts from a clean slate regardless of what any prior test created or left
 * behind (even one that crashed before its own cleanup) — the single source of
 * test isolation. Individual specs must NOT rely on data from other specs.
 *
 * Usage: import { test, expect } from "../../fixtures/app-test";
 */
export const WORKSPACE_PATH = "/e2e/workspace/local.db";

export const test = base.extend({
  page: async ({ page }, use) => {
    await page.addInitScript((path) => {
      try {
        localStorage.setItem("context-studio:workspace-path", path);
      } catch {
        /* ignore */
      }
    }, WORKSPACE_PATH);
    await clearTestData(page);
    await use(page);
  },
});

export { expect };
