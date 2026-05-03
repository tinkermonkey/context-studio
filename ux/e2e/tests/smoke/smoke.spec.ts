import { test, expect } from "@playwright/test";
import { apiRequest, clearTestData } from "../../fixtures/test-helpers";

/**
 * Smoke Tests
 *
 * Fast, broad checks that the system is alive and wired together correctly.
 * These must complete in under 30 seconds and run before any other suite.
 *
 * Each test verifies a distinct failure mode that would make all other tests
 * meaningless:
 *   1. Backend is healthy (API responds)
 *   2. Frontend renders actual content (not a blank error page)
 *   3. API calls succeed from inside the browser (catches CORS, wrong port)
 *   4. Taxonomies page loads and displays API data through the UI
 *   5. The add-taxonomy button exists and opens the form
 *
 * If any smoke test fails, subsequent tests are guaranteed to produce false
 * results and should not be trusted.
 */

test.describe("Smoke", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("backend health endpoint responds", async ({ page }) => {
    const health = await apiRequest<{
      status: string;
      database_connected: boolean;
    }>(page, "/api/v1/admin/health");

    expect(health.status).toBeDefined();
    expect(health.database_connected).toBe(true);
  });

  test("frontend renders content", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    const bodyText = await page.textContent("body");
    expect(bodyText).toBeTruthy();
    expect(bodyText!.trim().length).toBeGreaterThan(0);
  });

  test("API calls succeed from inside the browser", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("domcontentloaded");

    // fetch() inside page.evaluate() uses the browser's network stack, so CORS
    // headers and origin restrictions are enforced. A Node-level fetch() bypasses this.
    const result = await page.evaluate(async () => {
      try {
        const res = await fetch("http://localhost:8888/api/v1/admin/health");
        return { ok: res.ok, status: res.status };
      } catch (err) {
        return { ok: false, status: 0, error: String(err) };
      }
    });

    expect(result.ok).toBe(true);
  });

  test("taxonomies page loads and displays data from the API", async ({
    page,
  }) => {
    // Create a taxonomy through the API so we have something to display.
    // Capture the ID so afterEach clearTestData can clean it up by ID.
    await apiRequest(page, "/api/taxonomies", {
      method: "POST",
      body: { title: "Smoke Test Taxonomy", description: "smoke" },
    });

    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // The page must render the taxonomy title we just created — this proves the
    // frontend fetched data from the backend and rendered it.
    await expect(page.getByText("Smoke Test Taxonomy")).toBeVisible({
      timeout: 10000,
    });
  });

  test("add-taxonomy button opens the form", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // taxonomy-add-button is dynamically generated in node_table.tsx via
    // `${typeName.toLowerCase()}-add-button` — it exists at runtime.
    const addButton = page.getByTestId("taxonomy-add-button");
    await expect(addButton).toBeVisible({ timeout: 10000 });
    await addButton.click();

    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible({ timeout: 5000 });
  });
});
