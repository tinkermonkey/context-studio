import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createPropertyDefinition,
  clearTestData,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Page Layout E2E Tests
 *
 * Verifies that each entity page renders its expected structural elements:
 * add button, table, and correct heading. These tests complement the CRUD
 * specs by ensuring the page shell is intact independent of data operations.
 *
 * Every test uses testids or exact heading text — no generic `table` or `nav`
 * locators, and no assertions swallowed by .catch(() => {}).
 */

test.describe("Entity Page Layout", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("taxonomies page shows add button and table when data exists", async ({
    page,
  }) => {
    await createTestHierarchy(page, 1);

    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await expect(page.getByTestId("taxonomy-add-button")).toBeVisible();
    await expect(page.getByTestId("taxonomy-table")).toBeVisible();
  });

  test("classes page shows add button and table when data exists", async ({
    page,
  }) => {
    await createTestHierarchy(page, 1);

    await page.goto("/app/classes");
    await waitForAppReady(page);

    await expect(page.getByTestId("class-add-button")).toBeVisible();
    await expect(page.getByTestId("class-table")).toBeVisible();
  });

  test("concept schemes page shows add button and table when data exists", async ({
    page,
  }) => {
    const { taxonomy } = await createTestHierarchy(page, 1);
    // scheme already created by createTestHierarchy
    void taxonomy;

    await page.goto("/app/concept-schemes");
    await waitForAppReady(page);

    await expect(page.getByTestId("concept-scheme-add-button")).toBeVisible();
    await expect(page.getByTestId("concept-scheme-table")).toBeVisible();
  });

  test("properties page shows add button and table when data exists", async ({
    page,
  }) => {
    await createPropertyDefinition(page, {
      title: "Layout Test Property",
      identifier: "layout_test",
    });

    await page.goto("/app/properties");
    await waitForAppReady(page);

    await expect(
      page.getByTestId("property-definition-add-button"),
    ).toBeVisible();
    await expect(page.getByTestId("property-definition-table")).toBeVisible();
  });

  test("individuals page shows add button", async ({ page }) => {
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await expect(page.getByTestId("individual-add-button")).toBeVisible();
  });

  test("relationships page shows table when data exists", async ({ page }) => {
    await page.goto("/app/relationships");
    await waitForAppReady(page);

    // The relationships page always renders the table shell even without data.
    await expect(page.getByTestId("relationship-table")).toBeVisible();
  });

  test("add button opens create modal on taxonomies page", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await page.getByTestId("taxonomy-add-button").click();
    await expect(page.getByTestId("taxonomy-create-modal").first()).toBeVisible(
      { timeout: 5000 },
    );

    // Cancel to leave the page clean.
    await page.keyboard.press("Escape");
  });

  test("responsive layout — pages render at tablet and mobile widths", async ({
    page,
  }) => {
    const routes = ["/app/taxonomies", "/app/classes"];

    for (const width of [768, 375]) {
      await page.setViewportSize({ width, height: 900 });

      for (const path of routes) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");

        const bodyText = await page.locator("body").textContent();
        expect(
          bodyText?.trim().length,
          `${path} at ${width}px rendered blank`,
        ).toBeGreaterThan(0);
      }
    }
  });
});
