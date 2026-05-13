import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Promote a draft taxonomy", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("golden path: publish a draft taxonomy with changes", async ({ page }) => {
    // Preconditions: Create a draft taxonomy with a concept scheme containing classes
    const taxonomy = await createTaxonomy(page, {
      title: "Biology Taxonomy",
      description: "Taxonomy for biological organisms",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Organisms",
      description: "Classification of organisms",
    });

    await createClass(page, scheme.id, {
      title: "Animal",
      description: "Living creatures with mobility",
    });

    await createClass(page, scheme.id, {
      title: "Plant",
      description: "Photosynthetic organisms",
    });

    // Navigate to taxonomies page
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    // Step 1: Click on the taxonomy name in the taxonomies table to select it
    await page.getByTestId(`taxonomy-name-${taxonomy.id}`).click();
    await page.waitForLoadState("networkidle");

    // Step 2: Drawer opens on the right showing taxonomy details
    const drawer = page.getByTestId("taxonomy-drawer");
    await expect(drawer).toBeVisible();

    // Step 3: Verify the drawer displays the status chip showing "draft"
    await expect(drawer).toContainText("draft");

    // Step 4: Click the "Publish…" button in the drawer header
    await page.getByTestId("taxonomy-drawer-publish-button").click();
    await page.waitForLoadState("networkidle");

    // Step 5: Publish dialog opens
    const publishDialog = page.getByTestId("taxonomy-publish-dialog");
    await expect(publishDialog).toBeVisible();

    // Step 6: Wait for the diff summary to load (contains diff text)
    await expect(publishDialog).toContainText(/added|modified|removed/i);

    // Step 7: Locate the publication message textarea and fill it
    const messageInput = page.getByTestId("taxonomy-publish-message-input");
    await expect(messageInput).toBeVisible();
    await messageInput.fill("Add organism hierarchy to taxonomy");

    // Step 8: Verify the "Publish" button is now enabled
    const publishButton = page.getByTestId("taxonomy-publish-confirm-button");
    await expect(publishButton).toBeEnabled();

    // Step 9: Click the "Publish" button to submit
    await publishButton.click();
    await page.waitForLoadState("networkidle");

    // Step 10: Dialog closes automatically
    await expect(publishDialog).not.toBeVisible();

    // Step 11: Drawer remains open; status text updates to "published"
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("published");

    // Step 12: Toast appears with success message
    await expect(page.locator(".toast")).toContainText(/taxonomy published/i);

    // Step 13: Publish button is no longer available on a published taxonomy
    await expect(page.getByTestId("taxonomy-drawer-publish-button")).not.toBeVisible();
  });

  test("edge case: cancel publish dialog leaves taxonomy in draft state", async ({ page }) => {
    // Preconditions: Create a draft taxonomy with a concept scheme and classes
    const taxonomy = await createTaxonomy(page, {
      title: "Draft Taxonomy",
      description: "Test draft taxonomy",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
      description: "Test scheme",
    });

    await createClass(page, scheme.id, {
      title: "TestClass",
      description: "Test class",
    });

    // Navigate to taxonomies page and select the taxonomy
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    await page.getByTestId(`taxonomy-name-${taxonomy.id}`).click();
    await page.waitForLoadState("networkidle");

    // Verify drawer is open and shows draft status
    const drawer = page.getByTestId("taxonomy-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("draft");

    // Step 1: Click "Publish…" button in drawer header
    await page.getByTestId("taxonomy-drawer-publish-button").click();
    await page.waitForLoadState("networkidle");

    // Step 2: Publish dialog opens
    const publishDialog = page.getByTestId("taxonomy-publish-dialog");
    await expect(publishDialog).toBeVisible();

    // Step 3: Optionally fill in the message field
    const messageInput = page.getByTestId("taxonomy-publish-message-input");
    await messageInput.fill("This will be cancelled");

    // Step 4: Click the "Cancel" button
    await page.getByTestId("taxonomy-publish-cancel-button").click();
    await page.waitForLoadState("networkidle");

    // Step 5: Dialog closes
    await expect(publishDialog).not.toBeVisible();

    // Expected Result: Drawer remains open and displays original taxonomy (unchanged)
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("draft");

    // Verify no toast is displayed
    const toasts = page.locator(".toast");
    await expect(toasts).not.toContainText(/taxonomy published/i);

    // Verify taxonomy in the table continues to show "draft" status
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("draft");
  });

  test("edge case: publish succeeds for empty taxonomy (no concept schemes)", async ({ page }) => {
    // Preconditions: Create a draft taxonomy with no concept schemes
    const emptyTaxonomy = await createTaxonomy(page, {
      title: "Empty Taxonomy",
      description: "Taxonomy with no concept schemes",
    });

    // Navigate to taxonomies page
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    // Step 1: Click on the empty taxonomy name in the table to select it
    await page.getByTestId(`taxonomy-name-${emptyTaxonomy.id}`).click();
    await page.waitForLoadState("networkidle");

    // Step 2: Drawer opens showing taxonomy with no classes listed
    const drawer = page.getByTestId("taxonomy-drawer");
    await expect(drawer).toBeVisible();

    // Step 3: Click the "Publish…" button
    await page.getByTestId("taxonomy-drawer-publish-button").click();
    await page.waitForLoadState("networkidle");

    // Step 4: Publish dialog opens
    const publishDialog = page.getByTestId("taxonomy-publish-dialog");
    await expect(publishDialog).toBeVisible();

    // Step 5: Diff summary area displays "No changes to publish"
    await expect(publishDialog).toContainText(/no changes to publish/i);

    // Step 6: Enter a message in the textarea
    const messageInput = page.getByTestId("taxonomy-publish-message-input");
    await messageInput.fill("Publishing empty taxonomy");

    // Step 7: Click "Publish" button — publish succeeds even with no changes
    const publishButton = page.getByTestId("taxonomy-publish-confirm-button");
    await expect(publishButton).toBeEnabled();
    await publishButton.click();
    await page.waitForLoadState("networkidle");

    // Step 8: Dialog closes automatically
    await expect(publishDialog).not.toBeVisible();

    // Step 9: Success toast appears
    await expect(page.locator(".toast")).toContainText(/taxonomy published/i);

    // Step 10: Drawer remains open; status text updates to "published"
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("published");

    // Step 11: Publish button is no longer available on the published taxonomy
    await expect(page.getByTestId("taxonomy-drawer-publish-button")).not.toBeVisible();
  });
});
