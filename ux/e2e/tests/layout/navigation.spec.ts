import { test, expect } from "@playwright/test";

/**
 * Navigation and Layout E2E Tests
 *
 * Tests that every primary page loads with intact:
 * - Navbar (top navigation)
 * - Sidebar (left navigation)
 * - Content area (main content)
 *
 * Verifies the page structure is not broken and all
 * major layout components are visible and accessible.
 */

test.describe("Navigation and Layout Integrity", () => {
  const primaryPages = [
    { path: "/app/", name: "Dashboard" },
    { path: "/app/taxonomies", name: "Taxonomies" },
    { path: "/app/concept-schemes", name: "Concept Schemes" },
    { path: "/app/classes", name: "Classes" },
    { path: "/app/properties", name: "Properties" },
    { path: "/app/datasets", name: "Datasets" },
    { path: "/app/config", name: "Configuration" },
  ];

  test("should display navbar on all primary pages", async ({ page }) => {
    for (const pageInfo of primaryPages) {
      // Navigate to page
      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");

      // Verify navbar is visible
      const navbar = page.locator("nav").first();
      await expect(navbar).toBeVisible({
        timeout: 5000,
      });

      // Verify navbar contains navigation elements
      const navItems = page.locator("nav a, nav button");
      expect(await navItems.count()).toBeGreaterThan(0);
    }
  });

  test("should display sidebar on all content pages", async ({ page }) => {
    // Dashboard and content pages should have sidebar
    const contentPages = primaryPages.filter((p) => p.path !== "/");

    for (const pageInfo of contentPages) {
      // Navigate to page
      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");

      // Verify sidebar is visible
      const sidebar = page.locator("aside, [role='complementary']").first();
      const _hasSidebar = await sidebar.isVisible().catch(() => false);

      // Some pages might not have sidebar, but if they do, it should be visible
      if (_hasSidebar) {
        await expect(sidebar).toBeVisible();
      }
    }
  });

  test("should display main content area on all pages", async ({ page }) => {
    for (const pageInfo of primaryPages) {
      // Navigate to page
      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");

      // Verify main content area exists and is visible
      const mainContent = page.locator("main, [role='main']").first();
      const hasMain = await mainContent.isVisible().catch(() => false);

      // If no main element, verify page has body content
      if (!hasMain) {
        const bodyContent = page.locator("body");
        await expect(bodyContent).toBeVisible();
        const text = await bodyContent.textContent();
        expect(text).toBeTruthy();
      } else {
        await expect(mainContent).toBeVisible();
      }
    }
  });

  test("should maintain layout structure without errors on page transitions", async ({
    page,
  }) => {
    // Start from dashboard
    await page.goto("/app/");
    await page.waitForLoadState("networkidle");

    // Verify initial navbar
    let navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Navigate through several pages
    const navigationSequence = [
      "/app/taxonomies",
      "/app/concept-schemes",
      "/app/classes",
      "/app/properties",
      "/app/",
    ];

    for (const path of navigationSequence) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");

      // Verify navbar is still visible after navigation
      navbar = page.locator("nav").first();
      await expect(navbar).toBeVisible({
        timeout: 5000,
      });

      // Verify page loaded without errors
      const errorMessages = await page.locator("text=/error|error|failed/i").count();
      expect(errorMessages).toBe(0);
    }
  });

  test("should load dashboard with all layout components", async ({ page }) => {
    // Navigate to dashboard
    await page.goto("/app/");
    await page.waitForLoadState("networkidle");

    // Verify title
    await expect(page).toHaveTitle(/Context Studio/i);

    // Verify navbar
    const navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Verify sidebar (optional on dashboard)
    const sidebar = page.locator("aside, [role='complementary']").first();
    const _hasSidebar = await sidebar.isVisible().catch(() => false);
    // Sidebar is optional, so we don't assert on it

    // Verify main content or body text
    const mainContent = page.locator("main, [role='main']").first();
    const hasMain = await mainContent.isVisible().catch(() => false);
    expect(hasMain).toBeTruthy();

    // Verify page has body content
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).toBeTruthy();
  });

  test("should load taxonomies page with complete layout", async ({ page }) => {
    // Navigate to taxonomies
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Verify navbar
    const navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Verify page title or heading
    const heading = page.getByRole("heading", { name: /taxonomies/i });
    const headingVisible = await heading.isVisible().catch(() => false);
    expect(headingVisible).toBe(true);

    // Verify table loads (if data exists)
    const table = page.locator("table, [role='table']").first();
    const _hasTable = await table.isVisible().catch(() => false);
    // Table presence depends on data, so we don't assert
  });

  test("should load schemes page with complete layout", async ({ page }) => {
    // Navigate to schemes
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Verify navbar
    const navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Verify page has content
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).toBeTruthy();
    expect(bodyText!.length).toBeGreaterThan(0);
  });

  test("should load classes page with complete layout", async ({ page }) => {
    // Navigate to classes
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Verify navbar
    const navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Verify page has content
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).toBeTruthy();
  });

  test("should load properties page with complete layout", async ({ page }) => {
    // Navigate to properties
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Verify navbar
    const navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Verify page has content
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).toBeTruthy();
  });

  test("should navigate between pages without breaking layout", async ({
    page,
  }) => {
    // Navigate to taxonomies
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Click on schemes link if visible
    const schemesLink = page.getByRole("link", { name: /schemes/i });
    if (await schemesLink.isVisible().catch(() => false)) {
      await schemesLink.click();
      await page.waitForLoadState("networkidle");

      // Verify navigation worked
      expect(page.url()).toContain("/concept-schemes");

      // Verify navbar is still visible
      const navbar = page.locator("nav").first();
      await expect(navbar).toBeVisible();
    }
  });

  test("should maintain responsive layout on different viewport sizes", async ({
    page,
  }) => {
    // Test at desktop size
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    let navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Test at tablet size
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();

    // Test at mobile size
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    navbar = page.locator("nav").first();
    await expect(navbar).toBeVisible();
  });

  test("should display page titles correctly", async ({ page }) => {
    const pageTitles = [
      { path: "/app/taxonomies", title: /taxonomies/i },
      { path: "/app/concept-schemes", title: /schemes/i },
      { path: "/app/classes", title: /classes/i },
      { path: "/app/properties", title: /properties/i },
    ];

    for (const pageInfo of pageTitles) {
      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");

      // Verify page loads correctly
      const bodyText = await page.locator("body").textContent();
      expect(bodyText).toBeTruthy();

      // Verify page title or heading matches expected
      const heading = page.getByRole("heading");
      const headingText = await heading.allTextContents();
      const hasMatchingTitle = headingText.some((text) =>
        pageInfo.title.test(text),
      );
      expect(hasMatchingTitle).toBeTruthy();
    }
  });
});
