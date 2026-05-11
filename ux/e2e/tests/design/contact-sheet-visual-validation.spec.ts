import { test, expect } from "@playwright/test";

test.describe("Contact Sheet Visual Validation", () => {
  const sections = [
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

  test("should render all sections in light mode with correct styling", async ({ page }) => {
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /contact sheet/i })).toBeVisible();

    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toBeVisible({
        timeout: 5000,
      });
    }

    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("contact-sheet-full-light.png", {
      fullPage: true,
    });

    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toHaveScreenshot(`${section}-light.png`);
    }
  });

  test("should toggle to dark canvas mode and render all sections correctly", async ({ page }) => {
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /contact sheet/i })).toBeVisible();

    const toggleButton = page.getByTestId("contact-sheet-canvas-toggle");
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    await expect(page.locator("body")).toHaveClass(/dark-canvas/);

    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toBeVisible({
        timeout: 5000,
      });
    }

    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("contact-sheet-full-dark.png", {
      fullPage: true,
    });

    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toHaveScreenshot(`${section}-dark.png`);
    }
  });

  test("should toggle back to light canvas mode and restore original styling", async ({ page }) => {
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");

    const toggleButton = page.getByTestId("contact-sheet-canvas-toggle");
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();
    await expect(page.locator("body")).toHaveClass(/dark-canvas/);

    await toggleButton.click();
    await expect(page.locator("body")).not.toHaveClass(/dark-canvas/);

    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toBeVisible({
        timeout: 5000,
      });
    }

    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveScreenshot("contact-sheet-full-light-restored.png", {
      fullPage: true,
    });
  });
});
