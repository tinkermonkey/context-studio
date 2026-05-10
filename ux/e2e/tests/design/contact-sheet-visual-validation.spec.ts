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

  test("should render all sections in light mode with correct styling", async ({
    page,
  }) => {
    // Test Case 1: Navigate to Contact Sheet and Verify Initial Light Mode Rendering
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");

    // Verify the page title "Contact Sheet" is visible
    await expect(page.getByRole("heading", { name: /contact sheet/i })).toBeVisible();

    // Test Case 2: Verify All Sections Render in Light Mode
    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toBeVisible({
        timeout: 5000,
      });
    }

    // Test Case 3: Take Full-Page Screenshot in Light Mode
    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.waitForTimeout(300);
    await expect(page).toHaveScreenshot("contact-sheet-full-light.png", {
      fullPage: true,
      mask: [],
    });

    // Test Case 4: Capture Section-by-Section Screenshots in Light Mode
    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toHaveScreenshot(`${section}-light.png`, {
        mask: [],
      });
    }
  });

  test("should toggle to dark canvas mode and render all sections correctly", async ({
    page,
  }) => {
    // Setup: Navigate to Contact Sheet in light mode
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");

    // Verify initial light mode state
    await expect(page.getByRole("heading", { name: /contact sheet/i })).toBeVisible();

    // Test Case 5: Toggle to Dark Canvas Mode
    const toggleButton = page.getByTestId("contact-sheet-canvas-toggle");
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();

    // Wait for animations/transitions to complete
    await page.waitForTimeout(500);

    // Test Case 6: Verify All Sections Still Render in Dark Mode
    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toBeVisible({
        timeout: 5000,
      });
    }

    // Test Case 7: Take Full-Page Screenshot in Dark Mode
    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.waitForTimeout(300);
    await expect(page).toHaveScreenshot("contact-sheet-full-dark.png", {
      fullPage: true,
      mask: [],
    });

    // Test Case 8: Capture Section-by-Section Screenshots in Dark Mode
    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toHaveScreenshot(`${section}-dark.png`, {
        mask: [],
      });
    }
  });

  test("should toggle back to light canvas mode and restore original styling", async ({
    page,
  }) => {
    // Setup: Navigate to Contact Sheet
    await page.goto("/app/contact-sheet");
    await page.waitForLoadState("networkidle");

    // Toggle to dark mode
    const toggleButton = page.getByTestId("contact-sheet-canvas-toggle");
    await expect(toggleButton).toBeVisible();
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Test Case 9: Toggle Back to Light Mode and Verify Consistency
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Verify all sections are still visible in light mode
    for (const section of sections) {
      const sectionElement = page.getByTestId(section);
      await expect(sectionElement).toBeVisible({
        timeout: 5000,
      });
    }

    // Verify the page has returned to light mode state
    await page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await page.waitForTimeout(300);
    await expect(page).toHaveScreenshot("contact-sheet-full-light-restored.png", {
      fullPage: true,
      mask: [],
    });
  });
});
