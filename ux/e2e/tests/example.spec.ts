import { test, expect } from "@playwright/test";

/**
 * Example E2E test to verify the test infrastructure is working.
 *
 * This is a simple smoke test that validates:
 * 1. The frontend server is running
 * 2. The backend server is running
 * 3. Basic navigation works
 */

test.describe("Smoke Tests", () => {
  test("should load the application", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for the page to load
    await page.waitForLoadState("networkidle");

    // Verify the page loaded successfully
    await expect(page).toHaveTitle(/Context Studio/i);
  });

  test("should communicate with backend API", async ({ request }) => {
    // Make a direct API request to verify backend is running
    const response = await request.get(
      "http://localhost:8888/api/v1/admin/health",
    );

    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);
  });

  test("should render navigation elements", async ({ page }) => {
    // Navigate to the app
    await page.goto("/");

    // Wait for initial load
    await page.waitForLoadState("networkidle");

    // Verify navbar is visible and contains navigation elements
    const navbar = page.locator("nav");
    await expect(navbar).toBeVisible();

    // Verify the app brand/logo is visible
    const brand = page.locator("nav").getByRole("link").first();
    await expect(brand).toBeVisible();
  });

  test("should load the classes page", async ({ page }) => {
    // Navigate to classes page (replaces /app/layers which no longer exists)
    await page.goto("/app/classes");

    // Wait for page to load
    await page.waitForLoadState("networkidle");

    // Verify we're on the classes page
    expect(page.url()).toContain("/app/classes");

    // Verify the page loaded without errors
    // Just check that the page rendered something
    const bodyText = await page.locator("body").textContent();
    expect(bodyText).toBeTruthy();
    expect(bodyText!.length).toBeGreaterThan(0);
  });
});
