import { test, expect } from "@playwright/test";

/**
 * Navigation E2E Tests
 *
 * Verifies that sidebar navigation links route to the correct pages and that
 * every primary page loads without a blank or crashed body.
 *
 * These tests use link text and URLs rather than generic `nav` locators so a
 * failure points to a specific broken link, not an ambiguous selector.
 */

const PRIMARY_ROUTES = [
  { path: "/app/taxonomies", label: "Taxonomies" },
  { path: "/app/concept-schemes", label: "Concept Schemes" },
  { path: "/app/classes", label: "Classes" },
  { path: "/app/individuals", label: "Individuals" },
  { path: "/app/relationships", label: "Relationships" },
  { path: "/app/properties", label: "Properties" },
];

test.describe("Navigation", () => {
  test("each primary page renders non-blank content", async ({ page }) => {
    for (const route of PRIMARY_ROUTES) {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      const bodyText = await page.locator("body").textContent();
      expect(
        bodyText?.trim().length,
        `${route.path} rendered a blank page`,
      ).toBeGreaterThan(0);
    }
  });

  test("sidebar links navigate to the correct URLs", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    for (const route of PRIMARY_ROUTES) {
      const link = page.getByRole("link", { name: route.label, exact: true });
      // Hard assertion — a missing link is a failure, not a no-op.
      await expect(link, `Sidebar link "${route.label}" should be visible`).toBeVisible();
      await link.click();
      await page.waitForLoadState("networkidle");
      expect(
        page.url(),
        `Clicking "${route.label}" should navigate to ${route.path}`,
      ).toContain(route.path);
    }
  });

  test("browser Back button restores the previous page", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("/app/classes");

    await page.goBack();
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("/app/taxonomies");

    const bodyText = await page.locator("body").textContent();
    expect(bodyText?.trim().length).toBeGreaterThan(0);
  });

  test("app title is visible on all primary pages", async ({ page }) => {
    for (const route of PRIMARY_ROUTES) {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");

      await expect(page).toHaveTitle(/Context Studio/i, { timeout: 5000 });
    }
  });

  test("navigating between pages does not leave a blank screen", async ({
    page,
  }) => {
    const sequence = [
      "/app/taxonomies",
      "/app/classes",
      "/app/concept-schemes",
      "/app/individuals",
      "/app/taxonomies",
    ];

    for (const path of sequence) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");

      const bodyText = await page.locator("body").textContent();
      expect(
        bodyText?.trim().length,
        `${path} rendered blank after navigation sequence`,
      ).toBeGreaterThan(0);
    }
  });
});
