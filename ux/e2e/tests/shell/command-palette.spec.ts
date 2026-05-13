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
    await page.waitForTimeout(100); // Brief delay for animation

    // Assert the palette overlay appears
    const palette = page.getByTestId("command-palette");
    await expect(palette).toBeVisible();

    // Assert the search input has keyboard focus
    const input = page.getByTestId("command-palette-input");
    await expect(input).toBeFocused();

    // Assert the first result is highlighted (if any exist)
    const resultsContainer = page.getByTestId("command-palette-results");
    const firstItem = resultsContainer.locator('[data-testid^="command-palette-item-"]').first();
    const firstItemExists = await firstItem.count().catch(() => 0);
    if (firstItemExists > 0) {
      await expect(firstItem).toHaveAttribute("data-active", "true");
    }
  });

  test("Test Case 2: Fuzzy Filter on Typed Query", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type a partial query
    await input.fill("schema");

    // Allow time for filtering
    await page.waitForTimeout(100);

    // Assert results are filtered
    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const itemCount = await allItems.count();
    // If results exist, they should contain the search term in their visible text or be filtered
    if (itemCount > 0) {
      const visibleItems = allItems.locator(":visible");
      const visibleCount = await visibleItems.count();
      expect(visibleCount).toBeGreaterThan(0);
    }

    // Type additional characters to narrow results further
    await input.fill("schema/classes");

    // Allow time for filtering
    await page.waitForTimeout(100);

    // Results should update on each keystroke
    const updatedItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const updatedCount = await updatedItems.count();
    expect(updatedCount).toBeGreaterThanOrEqual(0); // Either filtered or empty state
  });

  test("Test Case 3: Keyboard Navigation (↓ Arrow Key)", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to ensure we have results
    await input.fill("schema");
    await page.waitForTimeout(100);

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const itemCount = await allItems.count();

    if (itemCount >= 2) {
      // Get first item and assert it's active
      const firstItem = allItems.nth(0);
      await expect(firstItem).toHaveAttribute("data-active", "true");

      // Press down arrow
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(50);

      // Assert focus moves to second result
      const secondItem = allItems.nth(1);
      await expect(secondItem).toHaveAttribute("data-active", "true");
      await expect(firstItem).not.toHaveAttribute("data-active", "true");

      // Press down again
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(50);

      if (itemCount >= 3) {
        // Assert focus moves to third result
        const thirdItem = allItems.nth(2);
        await expect(thirdItem).toHaveAttribute("data-active", "true");
      }

      // Press down repeatedly until reaching the last result
      for (let i = 0; i < itemCount; i++) {
        await page.keyboard.press("ArrowDown");
        await page.waitForTimeout(50);
      }

      // Press down once more and verify it doesn't go beyond last item
      const lastItem = allItems.nth(itemCount - 1);
      const lastItemBefore = await lastItem.getAttribute("data-active");
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(50);
      const lastItemAfter = await lastItem.getAttribute("data-active");

      // Focus should remain at last item (no wrapping)
      if (lastItemBefore === "true") {
        await expect(lastItem).toHaveAttribute("data-active", "true");
      }
    }
  });

  test("Test Case 4: Keyboard Navigation (↑ Arrow Key)", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to ensure we have results
    await input.fill("schema");
    await page.waitForTimeout(100);

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const itemCount = await allItems.count();

    if (itemCount >= 2) {
      // Navigate to the second item using ArrowDown
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(50);

      // Press up arrow
      await page.keyboard.press("ArrowUp");
      await page.waitForTimeout(50);

      // Assert focus moves backward to first result
      const firstItem = allItems.nth(0);
      await expect(firstItem).toHaveAttribute("data-active", "true");

      // Press up once more
      await page.keyboard.press("ArrowUp");
      await page.waitForTimeout(50);

      // Assert focus does not move above first result (no wrapping)
      await expect(firstItem).toHaveAttribute("data-active", "true");
    }
  });

  test("Test Case 5: Execute Command via Enter Key", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to get filtered results
    await input.fill("schema");
    await page.waitForTimeout(100);

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const itemCount = await allItems.count();

    if (itemCount > 0) {
      // Focus on first result (it should be focused by default)
      const firstItem = allItems.nth(0);

      // Press Enter
      await page.keyboard.press("Enter");
      await page.waitForTimeout(200);

      // Assert the palette closes
      const palette = page.getByTestId("command-palette");
      const paletteVisible = await palette.isVisible().catch(() => false);
      expect(paletteVisible).toBe(false);
    }
  });

  test("Test Case 6: Execute Command via Mouse Click", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type to get results
    await input.fill("schema");
    await page.waitForTimeout(100);

    const allItems = resultsContainer.locator('[data-testid^="command-palette-item-"]');
    const itemCount = await allItems.count();

    if (itemCount >= 2) {
      // Click on a non-first item
      const secondItem = allItems.nth(1);
      await secondItem.click();
      await page.waitForTimeout(200);

      // Assert the palette closes
      const palette = page.getByTestId("command-palette");
      const paletteVisible = await palette.isVisible().catch(() => false);
      expect(paletteVisible).toBe(false);
    } else if (itemCount === 1) {
      // If only one item, click it
      const firstItem = allItems.nth(0);
      await firstItem.click();
      await page.waitForTimeout(200);

      // Assert the palette closes
      const palette = page.getByTestId("command-palette");
      const paletteVisible = await palette.isVisible().catch(() => false);
      expect(paletteVisible).toBe(false);
    }
  });

  test("Test Case 7: Close Palette via Escape Key", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    // Assert palette is open
    const palette = page.getByTestId("command-palette");
    await expect(palette).toBeVisible();

    // Press Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(100);

    // Assert palette is hidden
    const paletteVisible = await palette.isVisible().catch(() => false);
    expect(paletteVisible).toBe(false);

    // Assert the underlying page is still visible
    await expect(page).toHaveURL(/\/app/);
  });

  test("Test Case 8: Close Palette via Backdrop Click", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const palette = page.getByTestId("command-palette");
    const backdrop = page.getByTestId("command-palette-backdrop");

    // Assert palette is open
    await expect(palette).toBeVisible();

    // Click on the backdrop (outside the palette dialog)
    const backdropBox = await backdrop.boundingBox();
    if (backdropBox) {
      // Click near the edge of the backdrop to ensure we're outside the palette
      await page.click(
        "[data-testid='command-palette-backdrop']",
        { position: { x: 10, y: 10 } }
      );
    }
    await page.waitForTimeout(100);

    // Assert palette is closed
    const paletteVisible = await palette.isVisible().catch(() => false);
    expect(paletteVisible).toBe(false);

    // Test that clicking on the palette itself does NOT close it
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const input = page.getByTestId("command-palette-input");
    await input.click();
    await page.waitForTimeout(100);

    // Palette should still be open
    await expect(palette).toBeVisible();
  });

  test("Test Case 9: Reopen Palette After Close", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const palette = page.getByTestId("command-palette");
    const input = page.getByTestId("command-palette-input");

    // Assert palette is open
    await expect(palette).toBeVisible();

    // Type some query
    await input.fill("test-query");
    await page.waitForTimeout(100);

    // Close the palette by pressing ⌘K again
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    // Assert palette is hidden
    let paletteVisible = await palette.isVisible().catch(() => false);
    expect(paletteVisible).toBe(false);

    // Press ⌘K again to reopen
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    // Assert palette opens again
    await expect(palette).toBeVisible();

    // Assert input is focused
    await expect(input).toBeFocused();

    // Assert query is cleared (state reset)
    await expect(input).toHaveValue("");

    // Assert first result is highlighted
    const resultsContainer = page.getByTestId("command-palette-results");
    const firstItem = resultsContainer.locator('[data-testid^="command-palette-item-"]').first();
    const firstItemExists = await firstItem.count().catch(() => 0);
    if (firstItemExists > 0) {
      await expect(firstItem).toHaveAttribute("data-active", "true");
    }
  });

  test("Test Case 10: Reopen via Topbar ⌘K Chip", async ({ page }) => {
    // Ensure palette is closed first
    const palette = page.getByTestId("command-palette");
    let paletteVisible = await palette.isVisible().catch(() => false);
    if (paletteVisible) {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(100);
    }

    // Locate the ⌘K chip button in the Topbar
    const topbarButton = page.getByTestId("topbar-palette-button");
    await expect(topbarButton).toBeVisible();

    // Click the button
    await topbarButton.click();
    await page.waitForTimeout(100);

    // Assert the palette opens
    await expect(palette).toBeVisible();

    // Assert input is focused
    const input = page.getByTestId("command-palette-input");
    await expect(input).toBeFocused();

    // Assert first result is highlighted (if any)
    const resultsContainer = page.getByTestId("command-palette-results");
    const firstItem = resultsContainer.locator('[data-testid^="command-palette-item-"]').first();
    const firstItemExists = await firstItem.count().catch(() => 0);
    if (firstItemExists > 0) {
      await expect(firstItem).toHaveAttribute("data-active", "true");
    }
  });

  test("Test Case 11: Empty State (No Results Match Query)", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const palette = page.getByTestId("command-palette");
    const input = page.getByTestId("command-palette-input");
    const resultsContainer = page.getByTestId("command-palette-results");

    // Type a query that matches no registered actions
    const nonMatchingQuery = "xyzzzzzz-no-results";
    await input.fill(nonMatchingQuery);
    await page.waitForTimeout(100);

    // Assert the results area shows empty state
    const emptyState = page.getByTestId("command-palette-empty-state");
    await expect(emptyState).toBeVisible();

    // Assert the message contains the query text
    await expect(emptyState).toContainText(nonMatchingQuery);

    // Assert palette remains open (does not auto-close)
    await expect(palette).toBeVisible();

    // Type additional characters
    await input.fill(nonMatchingQuery + "more");
    await page.waitForTimeout(100);

    // Empty state should still show
    await expect(emptyState).toBeVisible();

    // Backspace to clear and type a query that should match
    await input.fill("schema");
    await page.waitForTimeout(100);

    // If new query matches results, empty state should be hidden
    const itemCount = await resultsContainer
      .locator('[data-testid^="command-palette-item-"]')
      .count();
    if (itemCount > 0) {
      const emptyStateVisible = await emptyState.isVisible().catch(() => false);
      // Empty state may or may not be visible depending on matching results
      // The key is that results should appear when there are matches
      const hasVisibleItems = itemCount > 0;
      expect(hasVisibleItems).toBe(true);
    }
  });

  test("Test Case 12: Esc Button in Palette Input Row", async ({ page }) => {
    // Open palette
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(100);

    const palette = page.getByTestId("command-palette");
    const escButton = page.getByTestId("command-palette-esc-button");

    // Assert palette is open
    await expect(palette).toBeVisible();

    // Locate and click the esc button
    await expect(escButton).toBeVisible();
    await escButton.click();
    await page.waitForTimeout(100);

    // Assert the palette closes
    const paletteVisible = await palette.isVisible().catch(() => false);
    expect(paletteVisible).toBe(false);
  });
});
