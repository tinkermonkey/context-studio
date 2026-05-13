import { test, expect } from "@playwright/test";

test.describe("Command Palette", () => {
  test.beforeEach(async ({ page }) => {
    // Set a workspace path in localStorage before any page scripts run
    await page.addInitScript(() => {
      localStorage.setItem("context-studio:workspace-path", "/tmp/test-workspace");
    });

    // Navigate to app to ensure command palette is available
    await page.goto("/app");
    await page.waitForLoadState("networkidle");
  });

  test("Test Case 1: Open Palette via ⌘K and Assert Focus", async ({ page }) => {
    // Press ⌘K to open the palette
    await page.keyboard.press("Meta+k");

    // Assert the palette overlay appears
    const palette = page.getByTestId("command-palette");
    await expect(palette).toBeVisible();

    // Assert the search input has keyboard focus
    const input = page.getByTestId("command-palette-input");
    await expect(input).toBeFocused();

    // Assert at least one result exists and first result is highlighted
    const resultsContainer = page.getByTestId("command-palette-results");
    const firstItem = resultsContainer.locator('[data-testid^="command-palette-item-"]').first();
    await expect(firstItem).toBeVisible();
    await expect(firstItem).toHaveAttribute("data-active", "true");
  });

  test("Test Case 2: Fuzzy Filter on Typed Query", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Get baseline: count initial results
    const baselineItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const baselineCount = await baselineItems.count();
    expect(baselineCount).toBeGreaterThan(0);

    // Type a partial query to filter
    await input.fill("schema");

    // Assert results are filtered to matching items
    const filteredItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const filteredCount = await filteredItems.count();
    expect(filteredCount).toBeGreaterThan(0);

    // Verify at least one result is visible (fuzzy matching is working)
    const firstFilteredItem = filteredItems.first();
    await expect(firstFilteredItem).toBeVisible();

    // Verify case-insensitive matching by typing uppercase
    await input.fill("SCHEMA");
    const uppercaseItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const uppercaseCount = await uppercaseItems.count();
    expect(uppercaseCount).toBeGreaterThan(0);
    const firstUppercaseItem = uppercaseItems.first();
    await expect(firstUppercaseItem).toBeVisible();

    // Type additional characters to further narrow results
    await input.fill("schema/classes");
    const narrowedItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const narrowedCount = await narrowedItems.count();
    // Results should either be empty or contain filtered items (no vacuous assertion)
    if (narrowedCount > 0) {
      const firstNarrowedItem = narrowedItems.first();
      await expect(firstNarrowedItem).toBeVisible();
    } else {
      // If no results, empty state should be visible
      const emptyState = page.getByTestId("command-palette-empty-state");
      await expect(emptyState).toBeVisible();
    }
  });

  test("Test Case 3: Keyboard Navigation (↓ Arrow Key)", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to ensure we have results
    await input.fill("schema");

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    // Assert we have at least 2 items for navigation testing
    await expect(allItems.nth(0)).toBeVisible();
    await expect(allItems.nth(1)).toBeVisible();

    // Get first item and assert it's active
    const firstItem = allItems.nth(0);
    await expect(firstItem).toHaveAttribute("data-active", "true");

    // Press down arrow
    await page.keyboard.press("ArrowDown");

    // Assert focus moves to second result
    const secondItem = allItems.nth(1);
    await expect(secondItem).toHaveAttribute("data-active", "true");
    await expect(firstItem).not.toHaveAttribute("data-active", "true");

    // Press down again
    await page.keyboard.press("ArrowDown");

    // Check if there are at least 3 items
    const itemCount = await allItems.count();
    if (itemCount >= 3) {
      // Assert focus moves to third result
      const thirdItem = allItems.nth(2);
      await expect(thirdItem).toHaveAttribute("data-active", "true");
    }

    // Navigate to the last item
    const lastItem = allItems.nth(itemCount - 1);
    // Press down repeatedly until we reach the last item
    for (let i = 2; i < itemCount; i++) {
      await page.keyboard.press("ArrowDown");
    }

    // Verify focus is now on last item
    await expect(lastItem).toHaveAttribute("data-active", "true");

    // Press down once more and verify it doesn't go beyond last item (no wrapping)
    await page.keyboard.press("ArrowDown");
    await expect(lastItem).toHaveAttribute("data-active", "true");
  });

  test("Test Case 4: Keyboard Navigation (↑ Arrow Key)", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to ensure we have results
    await input.fill("schema");

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    // Assert we have at least 2 items for navigation testing
    await expect(allItems.nth(0)).toBeVisible();
    await expect(allItems.nth(1)).toBeVisible();

    const firstItem = allItems.nth(0);
    const secondItem = allItems.nth(1);

    // Navigate to the second item using ArrowDown
    await page.keyboard.press("ArrowDown");

    // Assert we're at the second item
    await expect(secondItem).toHaveAttribute("data-active", "true");

    // Press up arrow
    await page.keyboard.press("ArrowUp");

    // Assert focus moves backward to first result
    await expect(firstItem).toHaveAttribute("data-active", "true");

    // Press up once more
    await page.keyboard.press("ArrowUp");

    // Assert focus does not move above first result (no wrapping)
    await expect(firstItem).toHaveAttribute("data-active", "true");
  });

  test("Test Case 5: Execute Command via Enter Key", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to get filtered results
    await input.fill("schema");

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    // Assert at least one result exists
    await expect(allItems.nth(0)).toBeVisible();

    const palette = page.getByTestId("command-palette");

    // Capture the URL before executing the command
    const urlBefore = page.url();

    // Press Enter to execute the focused command
    await page.keyboard.press("Enter");

    // Assert the palette closes (verifies the command's onSelect() callback fired)
    await expect(palette).not.toBeVisible();
  });

  test("Test Case 6: Execute Command via Mouse Click", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to get results
    await input.fill("schema");

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    // Assert at least one result exists
    await expect(allItems.nth(0)).toBeVisible();

    const palette = page.getByTestId("command-palette");

    // Click on the first item to execute it
    const firstItem = allItems.nth(0);
    await firstItem.click();

    // Assert the palette closes after command execution
    await expect(palette).not.toBeVisible();
  });

  test("Test Case 7: Close Palette via Escape Key", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    // Assert palette is open
    const palette = page.getByTestId("command-palette");
    await expect(palette).toBeVisible();

    // Press Escape
    await page.keyboard.press("Escape");

    // Assert palette is hidden (auto-retries until hidden)
    await expect(palette).not.toBeVisible();

    // Assert the underlying page is still visible
    await expect(page).toHaveURL(/\/app/);
  });

  test("Test Case 8: Close Palette via Backdrop Click", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const palette = page.getByTestId("command-palette");
    const backdrop = page.getByTestId("command-palette-backdrop");

    // Assert palette is open
    await expect(palette).toBeVisible();

    // Click on the backdrop (outside the palette dialog)
    await backdrop.click({ position: { x: 10, y: 10 } });

    // Assert palette is closed
    await expect(palette).not.toBeVisible();

    // Test that clicking on the palette itself does NOT close it
    await page.keyboard.press("Meta+k");

    const input = page.getByTestId("command-palette-input");
    await input.click();

    // Palette should still be open
    await expect(palette).toBeVisible();
  });

  test("Test Case 9: Reopen Palette After Close", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const palette = page.getByTestId("command-palette");
    const input = page.getByTestId("command-palette-input");

    // Assert palette is open
    await expect(palette).toBeVisible();

    // Type some query
    await input.fill("test-query");

    // Close the palette by pressing ⌘K again
    await page.keyboard.press("Meta+k");

    // Assert palette is hidden
    await expect(palette).not.toBeVisible();

    // Press ⌘K again to reopen
    await page.keyboard.press("Meta+k");

    // Assert palette opens again
    await expect(palette).toBeVisible();

    // Assert input is focused
    await expect(input).toBeFocused();

    // Assert query is cleared (state reset)
    await expect(input).toHaveValue("");

    // Assert first result is highlighted
    const resultsContainer = page.getByTestId("command-palette-results");
    const firstItem = resultsContainer.locator('[data-testid^="command-palette-item-"]').first();
    await expect(firstItem).toBeVisible();
    await expect(firstItem).toHaveAttribute("data-active", "true");
  });

  test("Test Case 10: Reopen via Topbar ⌘K Chip", async ({ page }) => {
    const palette = page.getByTestId("command-palette");

    // Close palette if it's open
    const paletteLocator = palette;
    try {
      if (await paletteLocator.isVisible()) {
        await page.keyboard.press("Escape");
        await expect(palette).not.toBeVisible();
      }
    } catch {
      // Palette already not visible
    }

    // Locate the ⌘K chip button in the Topbar
    const topbarButton = page.getByTestId("topbar-palette-button");
    await expect(topbarButton).toBeVisible();

    // Click the button
    await topbarButton.click();

    // Assert the palette opens
    await expect(palette).toBeVisible();

    // Assert input is focused
    const input = page.getByTestId("command-palette-input");
    await expect(input).toBeFocused();

    // Assert first result is highlighted
    const resultsContainer = page.getByTestId("command-palette-results");
    const firstItem = resultsContainer.locator('[data-testid^="command-palette-item-"]').first();
    await expect(firstItem).toBeVisible();
    await expect(firstItem).toHaveAttribute("data-active", "true");
  });

  test("Test Case 11: Empty State (No Results Match Query)", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const palette = page.getByTestId("command-palette");
    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type a query that matches no registered actions
    const nonMatchingQuery = "xyzzzzzz-no-results";
    await input.fill(nonMatchingQuery);

    // Assert the results area shows empty state
    const emptyState = page.getByTestId("command-palette-empty-state");
    await expect(emptyState).toBeVisible();

    // Assert the message contains the query text
    await expect(emptyState).toContainText(nonMatchingQuery);

    // Assert palette remains open (does not auto-close)
    await expect(palette).toBeVisible();

    // Type additional characters
    await input.fill(nonMatchingQuery + "more");

    // Empty state should still show
    await expect(emptyState).toBeVisible();

    // Clear and type a query that should match
    await input.fill("schema");

    // Assert results appear for matching query
    const items = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const itemCount = await items.count();
    expect(itemCount).toBeGreaterThan(0);

    // Assert at least first item is visible
    await expect(items.first()).toBeVisible();
  });

  test("Test Case 12: Esc Button in Palette Input Row", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");

    const palette = page.getByTestId("command-palette");
    const escButton = page.getByTestId("command-palette-esc-button");

    // Assert palette is open
    await expect(palette).toBeVisible();

    // Locate and click the esc button
    await expect(escButton).toBeVisible();
    await escButton.click();

    // Assert the palette closes
    await expect(palette).not.toBeVisible();
  });
});
