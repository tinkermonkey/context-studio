import { test, expect } from "../../fixtures/app-test";

/**
 * Contact-sheet behavioral checks: every reference section renders, and the
 * canvas-mode toggle flips the `dark-canvas` body class in both directions.
 *
 * Pixel-level visual regression (screenshots) is intentionally NOT asserted
 * here — it is fragile without a pinned rendering environment and is covered by
 * the dedicated `/frontend-visual-qa` flow. These tests guard structure and
 * behavior, which are deterministic.
 */
const SECTIONS = [
  "contact-sheet-buttons",
  "contact-sheet-chips",
  "contact-sheet-stat-tiles",
  "contact-sheet-tabs",
  "contact-sheet-form-inputs",
  "contact-sheet-panel",
  "contact-sheet-table",
  "contact-sheet-hierarchy-tree",
  "contact-sheet-pipeline-card",
  "contact-sheet-toasts",
  "contact-sheet-modal",
  "contact-sheet-drawer",
  "contact-sheet-schema-components",
  "contact-sheet-intent-states",
];

test.describe("Contact Sheet", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: /contact sheet/i })).toBeVisible();
  });

  test("renders all reference sections", async ({ page }) => {
    for (const section of SECTIONS) {
      await expect(page.getByTestId(section)).toBeVisible({ timeout: 5000 });
    }
  });

  test("the canvas toggle flips dark mode in both directions", async ({ page }) => {
    const body = page.locator("body");
    const toggle = page.getByTestId("contact-sheet-canvas-toggle");
    await expect(toggle).toBeVisible();

    const startedDark = await body.evaluate((el) => el.classList.contains("dark-canvas"));

    // First toggle flips the mode.
    await toggle.click();
    if (startedDark) {
      await expect(body).not.toHaveClass(/dark-canvas/);
    } else {
      await expect(body).toHaveClass(/dark-canvas/);
    }

    // Sections still render after the toggle.
    for (const section of SECTIONS) {
      await expect(page.getByTestId(section)).toBeVisible({ timeout: 5000 });
    }

    // Second toggle restores the original mode.
    await toggle.click();
    if (startedDark) {
      await expect(body).toHaveClass(/dark-canvas/);
    } else {
      await expect(body).not.toHaveClass(/dark-canvas/);
    }
  });
});
