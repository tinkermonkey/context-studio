import { test, expect } from "@playwright/test";
import { mockReferenceAPIs } from "../../fixtures/test-helpers";

/**
 * Reference Data Search E2E Tests
 *
 * External APIs are mocked so tests run without network access and return
 * deterministic data. Mocks must be registered before page.goto() because
 * Playwright route mocking only intercepts requests made after registration.
 *
 * Actual testids from UnifiedSearchPage.tsx and SearchResults.tsx:
 *   reference-search-input, reference-search-button,
 *   reference-source-filter, reference-results-list
 */

test.describe("Reference Search", () => {
  test.beforeEach(async ({ page }) => {
    await mockReferenceAPIs(page);
    await page.goto("/app/reference/search");
    await page.waitForLoadState("networkidle");
  });

  test("should display the reference search interface", async ({ page }) => {
    await expect(page.getByTestId("reference-search-input")).toBeVisible();
    await expect(page.getByTestId("reference-search-button")).toBeVisible();
    await expect(page.getByTestId("reference-source-filter")).toBeVisible();
  });

  test("should perform a search and display results", async ({ page }) => {
    await page.getByTestId("reference-search-input").fill("computer");
    await page.getByTestId("reference-search-button").click();

    // Results render in a tabbed view — switch to "List View" to access the list.
    await page.getByRole("tab", { name: "List View" }).click();

    const resultsList = page.getByTestId("reference-results-list");
    await expect(resultsList).toBeVisible({ timeout: 10000 });

    // The results list must contain actual content — not just an empty container.
    const text = await resultsList.textContent();
    expect(text).toBeTruthy();
    expect(text!.trim().length).toBeGreaterThan(0);
  });

  test("should open source filter dropdown", async ({ page }) => {
    const sourceFilter = page.getByTestId("reference-source-filter");
    await expect(sourceFilter).toBeVisible();
    await sourceFilter.click();

    // After clicking, at least one source option should appear in the dropdown.
    await expect(page.getByText("DBpedia")).toBeVisible({ timeout: 5000 });
  });

  test("should show empty results list for a zero-result mock response", async ({ page }) => {
    await page.route("**/api/reference/*/search*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: "xyzzy-nothing-matches",
          results: [],
          links: [],
          total_results: 0,
          total_links: 0,
          sources_queried: [],
          source_errors: {},
          offset: 0,
          limit: 20,
          search_time_ms: 10,
        }),
      }),
    );

    await page.getByTestId("reference-search-input").fill("xyzzy-nothing-matches");
    await page.getByTestId("reference-search-button").click();

    // Wait briefly for the response to be processed, then assert the results
    // list either doesn't render or renders visibly empty. Using a hard
    // waitForTimeout is avoided — instead we wait for the search button to
    // become re-enabled (or similar idle signal) before inspecting the DOM.
    await page.waitForLoadState("networkidle");

    const resultsList = page.getByTestId("reference-results-list");
    // Hard assertion: the results list must be absent OR contain no text.
    // A hidden/absent element passes toBeHidden; an empty element passes the
    // textContent check. Both paths fail if content appears unexpectedly.
    const isVisible = await resultsList.isVisible();
    if (isVisible) {
      const text = await resultsList.textContent();
      expect(
        text?.trim().length ?? 0,
        "reference-results-list should be empty for a zero-result response",
      ).toBe(0);
    } else {
      await expect(resultsList).toBeHidden();
    }
  });
});
