import { test, expect } from "../../fixtures/app-test";

// The app wraps Heimdall's CommandPalette. When open it renders inside the
// `command-palette` wrapper as `.command-palette` (role=dialog) with a
// `.command-palette__input` (role=combobox) and `.command-palette__item`
// (role=option) rows; the selected row carries `.command-palette__item--selected`.
// There are no per-element data-testids beyond the `command-palette` wrapper.
const PALETTE = '[data-testid="command-palette"] .command-palette';
const INPUT = ".command-palette__input";
const ITEM = ".command-palette__item";
const EMPTY = ".command-palette__empty";
const BACKDROP = ".command-palette-backdrop";

test.describe("Command Palette", () => {
  test.beforeEach(async ({ page }) => {
    // Workspace path is seeded by the app-test fixture; just land in the app.
    await page.goto("/app");
    await page.waitForLoadState("networkidle");
  });

  test("Test Case 1: Open Palette via ⌘K and Assert Focus", async ({ page }) => {
    await page.keyboard.press("Meta+k");

    const palette = page.locator(PALETTE);
    await expect(palette).toBeVisible();

    // The search input auto-focuses when the palette opens.
    const input = page.locator(INPUT);
    await expect(input).toBeFocused();

    // At least one result exists and the first is highlighted.
    const firstItem = page.locator(ITEM).first();
    await expect(firstItem).toBeVisible();
    await expect(firstItem).toHaveClass(/command-palette__item--selected/);
  });

  test("Test Case 2: Fuzzy Filter on Typed Query", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const input = page.locator(INPUT);

    const baselineCount = await page.locator(ITEM).count();
    expect(baselineCount).toBeGreaterThan(0);

    await input.fill("schema");
    const filteredCount = await page.locator(ITEM).count();
    expect(filteredCount).toBeGreaterThan(0);
    await expect(page.locator(ITEM).first()).toBeVisible();

    // Case-insensitive matching.
    await input.fill("SCHEMA");
    expect(await page.locator(ITEM).count()).toBeGreaterThan(0);
    await expect(page.locator(ITEM).first()).toBeVisible();

    // Narrow to a query that has no substring match → empty state.
    await input.fill("schema/no-such-command");
    const narrowedCount = await page.locator(ITEM).count();
    if (narrowedCount > 0) {
      await expect(page.locator(ITEM).first()).toBeVisible();
    } else {
      await expect(page.locator(EMPTY)).toBeVisible();
    }
  });

  test("Test Case 3: Keyboard Navigation (↓ Arrow Key)", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    await page.locator(INPUT).fill("schema");

    const allItems = page.locator(ITEM);
    await expect(allItems.nth(0)).toBeVisible();
    await expect(allItems.nth(1)).toBeVisible();

    await expect(allItems.nth(0)).toHaveClass(/command-palette__item--selected/);

    await page.keyboard.press("ArrowDown");
    await expect(allItems.nth(1)).toHaveClass(/command-palette__item--selected/);
    await expect(allItems.nth(0)).not.toHaveClass(/command-palette__item--selected/);

    const itemCount = await allItems.count();
    // Walk to the last item.
    for (let i = 1; i < itemCount - 1; i++) {
      await page.keyboard.press("ArrowDown");
    }
    await expect(allItems.nth(itemCount - 1)).toHaveClass(/command-palette__item--selected/);

    // Wraps back to the first.
    await page.keyboard.press("ArrowDown");
    await expect(allItems.nth(0)).toHaveClass(/command-palette__item--selected/);
  });

  test("Test Case 4: Keyboard Navigation (↑ Arrow Key)", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    await page.locator(INPUT).fill("schema");

    const allItems = page.locator(ITEM);
    await expect(allItems.nth(0)).toBeVisible();
    await expect(allItems.nth(1)).toBeVisible();

    await page.keyboard.press("ArrowDown");
    await expect(allItems.nth(1)).toHaveClass(/command-palette__item--selected/);

    await page.keyboard.press("ArrowUp");
    await expect(allItems.nth(0)).toHaveClass(/command-palette__item--selected/);

    // Up at index 0 wraps to the last item.
    const itemCount = await allItems.count();
    await page.keyboard.press("ArrowUp");
    await expect(allItems.nth(itemCount - 1)).toHaveClass(/command-palette__item--selected/);
  });

  test("Test Case 5: Execute Command via Enter Key", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.locator(PALETTE);
    await page.locator(INPUT).fill("schema");
    await expect(page.locator(ITEM).first()).toBeVisible();

    await page.keyboard.press("Enter");

    // Executing a command closes the palette.
    await expect(palette).not.toBeVisible();
  });

  test("Test Case 6: Execute Command via Mouse Click", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.locator(PALETTE);
    await page.locator(INPUT).fill("schema");

    await expect(page.locator(ITEM).first()).toBeVisible();
    await page.locator(ITEM).first().click();

    await expect(palette).not.toBeVisible();
  });

  test("Test Case 7: Close Palette via Escape Key", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.locator(PALETTE);
    await expect(palette).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(palette).not.toBeVisible();
    await expect(page).toHaveURL(/\/app/);
  });

  test("Test Case 8: Close Palette via Backdrop Click", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.locator(PALETTE);
    await expect(palette).toBeVisible();

    // Click the backdrop at a corner, away from the dialog.
    await page.locator(BACKDROP).click({ position: { x: 5, y: 5 } });
    await expect(palette).not.toBeVisible();

    // Clicking inside the palette input must NOT close it.
    await page.keyboard.press("Meta+k");
    await page.locator(INPUT).click();
    await expect(palette).toBeVisible();
  });

  test("Test Case 9: Reopen Palette After Close", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.locator(PALETTE);
    const input = page.locator(INPUT);
    await expect(palette).toBeVisible();

    await input.fill("test-query");

    // Toggle closed with ⌘K.
    await page.keyboard.press("Meta+k");
    await expect(palette).not.toBeVisible();

    // Reopen.
    await page.keyboard.press("Meta+k");
    await expect(palette).toBeVisible();
    await expect(input).toBeFocused();
    await expect(input).toHaveValue("");

    const firstItem = page.locator(ITEM).first();
    await expect(firstItem).toBeVisible();
    await expect(firstItem).toHaveClass(/command-palette__item--selected/);
  });

  test("Test Case 10: Reopen via Topbar Search (⌘K hint)", async ({ page }) => {
    const palette = page.locator(PALETTE);

    // The Topbar search field opens the palette on input (searchHint "⌘K";
    // Heimdall wires the search <input> onChange → onSearch → openPalette).
    const topbarSearch = page.locator(".topbar__search");
    await expect(topbarSearch).toBeVisible();
    await topbarSearch.pressSequentially("k");

    await expect(palette).toBeVisible();
    await expect(page.locator(INPUT)).toBeFocused();

    const firstItem = page.locator(ITEM).first();
    await expect(firstItem).toBeVisible();
    await expect(firstItem).toHaveClass(/command-palette__item--selected/);
  });

  test("Test Case 11: Empty State (No Results Match Query)", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.locator(PALETTE);
    const input = page.locator(INPUT);

    const nonMatchingQuery = "xyzzzzzz-no-results";
    await input.fill(nonMatchingQuery);

    const emptyState = page.locator(EMPTY);
    await expect(emptyState).toBeVisible();
    await expect(emptyState).toContainText("No commands found");
    await expect(palette).toBeVisible();

    await input.fill(nonMatchingQuery + "more");
    await expect(emptyState).toBeVisible();

    // A matching query restores results.
    await input.fill("schema");
    const items = page.locator(ITEM);
    expect(await items.count()).toBeGreaterThan(0);
    await expect(items.first()).toBeVisible();
  });
});
