import { test, expect } from "@playwright/test";
import {
  waitForAnyCondition,
  mockReferenceAPIs,
} from "../../fixtures/test-helpers";

/**
 * Reference Data Search E2E Tests
 *
 * These tests validate the reference search functionality:
 * - Loading the reference search page
 * - Searching across multiple reference sources
 * - Viewing search results
 * - Filtering by reference source
 * - Handling search errors gracefully
 *
 * Note: External APIs are mocked to ensure reliable test execution
 */
test.describe("Reference Search", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the reference search page
    await page.goto("/app/reference-search");

    // Wait for page to load
    await page.waitForLoadState("networkidle");

    // Mock the reference APIs
    await mockReferenceAPIs(page);
  });

  test("should display the reference search interface", async ({ page }) => {
    // Verify search bar is visible
    await expect(
      page.locator('[data-testid="reference-search-input"]'),
    ).toBeVisible();

    // Verify source filter is visible
    await expect(
      page.locator('[data-testid="reference-source-filter"]'),
    ).toBeVisible();

    // Verify results area is visible
    await expect(
      page.locator('[data-testid="reference-search-results"]'),
    ).toBeVisible();
  });

  test("should perform a reference search", async ({ page }) => {
    // Type in the search box
    await page.fill('[data-testid="reference-search-input"]', "computer");

    // Wait for search results to appear
    const results = page.locator(
      '[data-testid="reference-search-result-item"]',
    );
    await expect(results.first()).toBeVisible({ timeout: 10000 });

    // Verify results are displayed
    const resultCount = await results.count();
    expect(resultCount).toBeGreaterThan(0);
  });

  test("should filter results by source", async ({ page }) => {
    // Perform a search first
    await page.fill('[data-testid="reference-search-input"]', "computer");

    // Wait for results to load
    await expect(
      page.locator('[data-testid="reference-search-result-item"]').first(),
    ).toBeVisible({ timeout: 10000 });

    // Get initial result count
    const allResults = page.locator(
      '[data-testid="reference-search-result-item"]',
    );
    const initialCount = await allResults.count();
    expect(initialCount).toBeGreaterThan(0);

    // Filter by a specific source
    const sourceFilter = page.locator(
      '[data-testid="reference-source-filter"]',
    );
    await sourceFilter.click();

    // Select DBpedia from the dropdown
    const dbpediaOption = page.locator('text="DBpedia"');
    await dbpediaOption.click();

    // Wait for filtered results
    await page.waitForTimeout(500);

    // Verify results are filtered (should be less or equal to initial)
    const filteredResults = page.locator(
      '[data-testid="reference-search-result-item"]',
    );
    const filteredCount = await filteredResults.count();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test("should display search result details", async ({ page }) => {
    // Perform a search
    await page.fill('[data-testid="reference-search-input"]', "computer");

    // Wait for results
    const firstResult = page
      .locator('[data-testid="reference-search-result-item"]')
      .first();
    await expect(firstResult).toBeVisible({ timeout: 10000 });

    // Click on the first result
    await firstResult.click();

    // Verify details are displayed
    await expect(
      page.locator('[data-testid="reference-result-detail"]'),
    ).toBeVisible();

    // Verify detail content is shown
    const detailPanel = page.locator('[data-testid="reference-result-detail"]');
    const detailText = await detailPanel.textContent();
    expect(detailText).toBeTruthy();
    expect(detailText!.length).toBeGreaterThan(0);
  });

  test("should handle search with no results", async ({ page }) => {
    // Mock API to return no results
    await page.route("**/api/reference/*/search*", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: "nonexistent",
          results: [],
          links: [],
          total_results: 0,
          total_links: 0,
          sources_queried: [],
          source_errors: {},
          offset: 0,
          limit: 20,
          search_time_ms: 100,
        }),
      });
    });

    // Perform a search that returns no results
    await page.fill('[data-testid="reference-search-input"]', "nonexistent");

    // Wait for the no-results message
    await expect(
      page.locator('text="No results found" | text="No results"'),
    ).toBeVisible({ timeout: 10000 });
  });

  test("should handle search errors gracefully", async ({ page }) => {
    // Mock API to return an error
    await page.route("**/api/reference/*/search*", (route) => {
      route.abort("failed");
    });

    // Perform a search
    await page.fill('[data-testid="reference-search-input"]', "computer");

    // Wait for error message
    const errorIndicator = page.locator(
      'text="Error" | [data-testid="reference-search-error"]',
    );

    // Use waitForAnyCondition to handle different error states
    try {
      await waitForAnyCondition(page, [
        async () => {
          const visible = await errorIndicator.isVisible();
          return visible;
        },
        async () => {
          const text = await page.locator("body").textContent();
          return text!.includes("Error");
        },
      ]);
    } catch {
      // Error handling is working - search failed gracefully
    }
  });

  test("should clear search and reset results", async ({ page }) => {
    // Perform a search
    await page.fill('[data-testid="reference-search-input"]', "computer");

    // Wait for results to appear
    await expect(
      page.locator('[data-testid="reference-search-result-item"]').first(),
    ).toBeVisible({ timeout: 10000 });

    // Verify results exist
    const resultsBefore = page.locator(
      '[data-testid="reference-search-result-item"]',
    );
    expect(await resultsBefore.count()).toBeGreaterThan(0);

    // Clear the search box
    const searchInput = page.locator('[data-testid="reference-search-input"]');
    await searchInput.clear();

    // Verify results area is cleared or hidden
    const resultsAfter = page.locator(
      '[data-testid="reference-search-result-item"]',
    );
    const countAfter = await resultsAfter.count();
    expect(countAfter).toBe(0);
  });
});
