/**
 * Heimdall Design Conformance Tests — Behavioral subset only
 *
 * These tests check a small set of structural facts that are fast, reliable,
 * and cannot be verified by a screenshot alone (e.g. dark-canvas class presence,
 * tab label text, eyebrow casing). They are NOT the primary success criterion —
 * visual review agents comparing /screenshots/audit/ pairs are.
 *
 * Run: npx playwright test design/heimdall-conformance
 * Full visual audit: cd ux && npm run design-audit:capture  (then /heimdall-fix)
 */

import { test, expect, Page } from "@playwright/test";

const SCREENSHOT_DIR = "../../screenshots/audit";

async function setupWorkspace(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("context-studio:workspace-path", "./local.db");
  });
}

async function captureAuditScreenshot(page: Page, name: string) {
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${name}-impl-auto.png`,
    fullPage: true,
  });
}

// ─── Behavioral: dark canvas class (S-3) ─────────────────────────────────────
// This is a class presence check — a screenshot can't distinguish "class set by
// JS" from "dark background by chance." Keep as a real test.

test("S-3: dark canvas is active by default", async ({ page }) => {
  await setupWorkspace(page);
  await page.goto("/app");
  await page.waitForLoadState("networkidle");

  const hasDarkCanvas = await page.evaluate(() => document.body.classList.contains("dark-canvas"));
  expect(hasDarkCanvas).toBe(true);
});

// ─── Behavioral: pipeline tab labels (P-1) ───────────────────────────────────
// Status-based tabs vs state-based tabs — must check text content, not pixels.

test("P-1: pipeline run status filter uses status labels (Running / Completed / Failed)", async ({
  page,
}) => {
  // The status filter only renders on the runs page once at least one run
  // exists (the empty state omits the filter bar), and runs cannot be created
  // because the run wizard is unreachable — tracked in
  // https://github.com/tinkermonkey/context-studio/issues/1108. Re-enable with
  // the deferred pipeline E2E suite once #1108 is fixed.
  test.skip(true, "Blocked by #1108 — status filter needs a run to exist");

  await setupWorkspace(page);
  await page.goto("/app/pipelines/runs");
  await page.waitForLoadState("networkidle");

  await page.getByTestId("filter-status").click();
  await expect(page.getByText("Running", { exact: true })).toBeVisible();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByText("Failed", { exact: true })).toBeVisible();
  await expect(page.getByText("Enabled", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Disabled", { exact: true })).toHaveCount(0);
});

// ─── Behavioral: settings eyebrow casing (ST-4) ──────────────────────────────
// The eyebrow must be lowercase — a visual reviewer cannot reliably distinguish
// "settings" from "SETTINGS" at screenshot resolution.

test("ST-4: settings eyebrow uses lowercase label (not all-caps)", async ({ page }) => {
  await setupWorkspace(page);
  await page.goto("/app/settings");
  await page.waitForLoadState("networkidle");

  const eyebrow = page.locator(
    "[data-testid*='eyebrow'], [class*='eyebrow'], [class*='page-header-eyebrow']",
  );
  await expect(eyebrow.first()).toBeVisible();

  const text = await eyebrow.first().textContent();
  expect(text?.toLowerCase()).toMatch(/settings/);
  expect(text).not.toMatch(/^[A-Z\s]+$/);
});

// ─── Screenshot capture: full-page pairs for visual review ───────────────────
// This is the primary artifact. Visual review agents read these images.

test.describe("Audit screenshots", () => {
  test("capture all pages for design comparison", async ({ page }) => {
    await setupWorkspace(page);

    const pages = [
      { route: "/app", name: "dashboard" },
      { route: "/app/schema/classes", name: "schema-classes" },
      { route: "/app/schema/taxonomies", name: "schema-taxonomies" },
      { route: "/app/pipelines", name: "pipelines" },
      { route: "/app/settings", name: "settings" },
    ];

    for (const { route, name } of pages) {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      await captureAuditScreenshot(page, name);
    }
  });
});
