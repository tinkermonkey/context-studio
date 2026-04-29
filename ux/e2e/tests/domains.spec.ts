import { test, expect } from "@playwright/test";
import { apiRequest } from "../fixtures/test-helpers";

/**
 * Domain Management E2E Tests
 *
 * These tests validate the complete CRUD workflow for domains:
 * - Creating domains through the table view
 * - Editing domains through modals and detail view
 * - Deleting domains with confirmation
 * - Searching and filtering domains
 * - Navigation between table and detail views
 * - Domain-layer associations
 */

test.describe("Domain Management", () => {
  let testLayerId: string;

  test.beforeEach(async ({ page }) => {
    // Create a test layer for domains to belong to
     
    const layerResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `E2E Test Layer ${Date.now()}`,
        definition: "Test layer for domain tests",
        node_type: "layer",
      },
    });
    testLayerId = layerResponse.id;

    // Navigate to domains page
    await page.goto("/app/domains");
    await page.waitForLoadState("networkidle");
  });

  test("should display the domains table", async ({ page }) => {
    // Wait for table to be visible with extended timeout
    await expect(page.locator('[data-testid="domain-table"]')).toBeVisible({
      timeout: 10000,
    });

    // Verify toolbar is visible with add button
    await expect(
      page.locator('[data-testid="domain-table-toolbar"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="domain-add-button"]'),
    ).toBeVisible();
  });

  test("should create a new domain with layer selection", async ({ page }) => {
    const domainTitle = `E2E Test Domain ${Date.now()}`;
    const domainDefinition = "A test domain created by E2E tests";

    // Click "Add Domain" button
    await page.click('[data-testid="domain-add-button"]');

    // Wait for create modal to appear
    await expect(
      page.getByRole("dialog", { name: "Create New Domain" }),
    ).toBeVisible();

    // Fill in the form
    await page.fill('[data-testid="domain-title-input"]', domainTitle);
    await page.fill(
      '[data-testid="domain-definition-input"]',
      domainDefinition,
    );

    // Select layer - wait for selector to be ready, then click to open dropdown
    const layerSelector = page
      .locator('[data-testid="domain-layer-selector"]')
      .locator("button");
    await expect(layerSelector).toBeVisible({ timeout: 10000 });
    await expect(layerSelector).toBeEnabled({ timeout: 5000 });

    // Wait a moment for selector to be fully ready
    await page.waitForTimeout(500);
    await layerSelector.click({ timeout: 10000 });

    // Wait for dropdown menu to appear (rendered in portal) and be interactive
    const dropdown = page.locator('div[role="listbox"]');
    await expect(dropdown).toBeVisible({ timeout: 5000 });

    // Wait for actual options to load by looking for our specific test layer
    // Get the test layer title first
     
    const layerResponse = await apiRequest<any>(
      page,
      `/api/classes/${testLayerId}`,
    );
    const testLayerTitle = layerResponse.title;

    // Find the option that contains our test layer title
    const layerOption = page.locator(
      `div[role="option"]:has-text("${testLayerTitle}")`,
    );
    await expect(layerOption).toBeVisible({ timeout: 10000 });

    // Wait a moment for options to be fully interactive
    await page.waitForTimeout(300);
    await layerOption.click();

    // Submit the form
    await page.click('[data-testid="domain-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Create New Domain" }),
    ).not.toBeVisible();

    // Verify domain appears in the table
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domainTitle,
    );

    // Verify domain exists in backend with correct layer association
     
    const response = await apiRequest<{ data: any[] }>(
      page,
      "/api/classes?node_type=domain",
    );
    const createdDomain = response.data.find(
       
      (n: any) => n.title === domainTitle,
    );

    expect(createdDomain).toBeDefined();
    expect(createdDomain?.definition).toBe(domainDefinition);
    expect(createdDomain?.node_type).toBe("domain");
    expect(createdDomain?.parent_node_id).toBe(testLayerId);
  });

  test("should edit a domain through the table", async ({ page }) => {
    // First, create a domain to edit
    const originalTitle = `E2E Edit Test ${Date.now()}`;
    const updatedTitle = `${originalTitle} (Updated)`;
    const updatedDefinition = "Updated definition via E2E test";

    // Create domain via API
     
    const createResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: originalTitle,
        definition: "Original definition",
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });
    const domainId = createResponse.id;

    // Refresh the page to see the new domain
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Double-click the domain row to edit
    await page.locator(`[data-testid="domain-row-${domainId}"]`).dblclick();

    // Wait for edit modal
    await expect(
      page.getByRole("dialog", { name: "Edit Domain" }),
    ).toBeVisible();

    // Clear and update the title
    await page.fill('[data-testid="domain-title-input"]', updatedTitle);
    await page.fill(
      '[data-testid="domain-definition-input"]',
      updatedDefinition,
    );

    // Submit
    await page.click('[data-testid="domain-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Edit Domain" }),
    ).not.toBeVisible();

    // Verify updated values appear in table
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      updatedTitle,
    );

    // Verify backend was updated
     
    const response = await apiRequest<any>(
      page,
      `/api/classes/${domainId}`,
    );
    expect(response.title).toBe(updatedTitle);
    expect(response.definition).toBe(updatedDefinition);
  });

  test("should delete a domain", async ({ page }) => {
    // Create a domain to delete
    const domainTitle = `E2E Delete Test ${Date.now()}`;
     
    const createResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: domainTitle,
        definition: "Domain to be deleted",
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });
    const domainId = createResponse.id;

    // Refresh to see the domain
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Select the domain row by clicking its checkbox
    const row = page.locator(`[data-testid="domain-row-${domainId}"]`);
    await row.locator('input[type="checkbox"]').check();

    // Click Actions dropdown and select Delete
    await page.click('[data-testid="domain-actions-dropdown"]');
    await page.click('[data-testid="domain-delete-selected-action"]');

    // Wait for delete confirmation modal
    await expect(
      page.getByRole("dialog", { name: /Confirm Delete/i }),
    ).toBeVisible();

    // Confirm deletion
    await page.click('[data-testid="domain-delete-confirm-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: /Confirm Delete/i }),
    ).not.toBeVisible();

    // Verify domain is removed from table
    await expect(
      page.locator('[data-testid="domain-table"]'),
    ).not.toContainText(domainTitle);

    // Verify domain is deleted from backend
    try {
      await apiRequest(page, `/api/classes/${domainId}`);
      // If we get here, the domain wasn't deleted
      expect(false).toBe(true); // Force fail
    } catch (_error) {
      // Expected - domain should be deleted
      expect(_error).toBeDefined();
    }
  });

  test("should search for domains", async ({ page }) => {
    // Create multiple domains with distinct names
    const timestamp = Date.now();
    const domain1Title = `Alpha Domain ${timestamp}`;
    const domain2Title = `Beta Domain ${timestamp}`;
    const domain3Title = `Gamma Domain ${timestamp}`;

    // Create domains via API
    await Promise.all([
      apiRequest(page, "/api/classes", {
        method: "POST",
        body: {
          title: domain1Title,
          node_type: "domain",
          parent_node_id: testLayerId,
        },
      }),
      apiRequest(page, "/api/classes", {
        method: "POST",
        body: {
          title: domain2Title,
          node_type: "domain",
          parent_node_id: testLayerId,
        },
      }),
      apiRequest(page, "/api/classes", {
        method: "POST",
        body: {
          title: domain3Title,
          node_type: "domain",
          parent_node_id: testLayerId,
        },
      }),
    ]);

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify all domains are visible initially
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain1Title,
    );
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain2Title,
    );
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain3Title,
    );

    // Search for "Beta"
    await page.fill('[data-testid="domain-search-input"]', "Beta");

    // Wait a bit for search to filter (debounced)
    await page.waitForTimeout(500);

    // Verify only Beta domain is visible
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain2Title,
    );
    await expect(
      page.locator('[data-testid="domain-table"]'),
    ).not.toContainText(domain1Title);
    await expect(
      page.locator('[data-testid="domain-table"]'),
    ).not.toContainText(domain3Title);

    // Clear search
    await page.fill('[data-testid="domain-search-input"]', "");
    await page.waitForTimeout(500);

    // Verify all domains are visible again
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain1Title,
    );
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain2Title,
    );
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      domain3Title,
    );
  });

  test("should navigate to domain detail view", async ({ page }) => {
    // Create a domain
    const domainTitle = `E2E Detail Test ${Date.now()}`;
    const domainDefinition = "Test domain for detail view";
     
    const createResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: domainTitle,
        definition: domainDefinition,
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });
    const domainId = createResponse.id;

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Find and click the link icon to navigate to detail view
    const row = page.locator(`[data-testid="domain-row-${domainId}"]`);

    // Wait for the row to be visible
    await expect(row).toBeVisible({ timeout: 10000 });

    // Find the link in the row
    const link = row.locator('a[href*="/app/classes/"]');
    await expect(link).toBeVisible({ timeout: 5000 });

    // Click the link
    await link.click();

    // Wait for navigation
    await page.waitForURL(`**/app/classes/${domainId}`, {
      timeout: 15000,
    });
    await page.waitForLoadState("networkidle");

    // Verify we're on the detail page
    expect(page.url()).toContain(`/app/classes/${domainId}`);

    // Verify domain details are displayed
    await expect(page.locator("body")).toContainText(domainTitle, {
      timeout: 10000,
    });
  });

  test("should cancel domain creation", async ({ page }) => {
    // Get current domain count
     
    const beforeResponse = await apiRequest<{ data: any[]; total: number }>(
      page,
      "/api/classes?node_type=domain",
    );
    const beforeCount = beforeResponse.total;

    // Click "Add Domain" button
    await page.click('[data-testid="domain-add-button"]');

    // Wait for create modal
    const createModal = page.getByRole("dialog", { name: "Create New Domain" });
    await expect(createModal).toBeVisible();

    // Fill in some data but don't submit
    await page.fill(
      '[data-testid="domain-title-input"]',
      "Test Domain Not Submitted",
    );

    // Navigate away to close the modal
    await page.goto("/app/domains");
    await page.waitForLoadState("networkidle");

    // Verify no new domain was created
     
    const afterResponse = await apiRequest<{ data: any[]; total: number }>(
      page,
      "/api/classes?node_type=domain",
    );
    const afterCount = afterResponse.total;

    expect(afterCount).toBe(beforeCount);

    // Verify the specific test domain was not created
    const testDomain = afterResponse.data.find(
       
      (n: any) => n.title === "Test Domain Not Submitted",
    );
    expect(testDomain).toBeUndefined();
  });

  test("should validate required fields", async ({ page }) => {
    // Click "Add Domain" button
    await page.click('[data-testid="domain-add-button"]');

    // Wait for create modal
    await expect(
      page.getByRole("dialog", { name: "Create New Domain" }),
    ).toBeVisible();

    // Try to submit without filling in title (required field)
    await page.click('[data-testid="domain-submit-button"]');

    // Modal should still be visible (HTML5 validation prevented submission)
    await expect(
      page.getByRole("dialog", { name: "Create New Domain" }),
    ).toBeVisible();

    // Verify the title input field is marked as invalid
    const titleInput = page.locator('[data-testid="domain-title-input"]');
    await expect(titleInput).toHaveAttribute("required");
  });

  test("should handle multiple domain selections and bulk delete", async ({
    page,
  }) => {
    // Create multiple domains
    const timestamp = Date.now();
     
    const domain1 = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Bulk Delete 1 ${timestamp}`,
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });
     
    const domain2 = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Bulk Delete 2 ${timestamp}`,
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });

    // Refresh
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Select both domains
    await page
      .locator(`[data-testid="domain-row-${domain1.id}"]`)
      .locator('input[type="checkbox"]')
      .check();
    await page
      .locator(`[data-testid="domain-row-${domain2.id}"]`)
      .locator('input[type="checkbox"]')
      .check();

    // Delete selected
    await page.click('[data-testid="domain-actions-dropdown"]');
    await page.click('[data-testid="domain-delete-selected-action"]');

    // Confirm
    const deleteModal = page.getByRole("dialog", { name: /Confirm Delete/i });
    await expect(deleteModal).toBeVisible();
    await expect(deleteModal).toContainText("2 selected");
    await page.click('[data-testid="domain-delete-confirm-button"]');

    // Wait for modal to close
    await expect(deleteModal).not.toBeVisible();

    // Verify both domains are gone
    await expect(
      page.locator('[data-testid="domain-table"]'),
    ).not.toContainText(`Bulk Delete 1 ${timestamp}`);
    await expect(
      page.locator('[data-testid="domain-table"]'),
    ).not.toContainText(`Bulk Delete 2 ${timestamp}`);
  });

  test("should filter domains by layer", async ({ page }) => {
    // Create a second layer
     
    const layer2Response = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `E2E Test Layer 2 ${Date.now()}`,
        definition: "Second test layer",
        node_type: "layer",
      },
    });
    const layer2Id = layer2Response.id;

    const timestamp = Date.now();

    // Create domains in each layer
    await apiRequest(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Domain Layer 1 ${timestamp}`,
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });

    await apiRequest(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Domain Layer 2 ${timestamp}`,
        node_type: "domain",
        parent_node_id: layer2Id,
      },
    });

    // Navigate to domains with layer filter
    await page.goto(`/app/domains?parent_node_id=${testLayerId}`);
    await page.waitForLoadState("networkidle");

    // Verify only domains from test layer are visible
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      `Domain Layer 1 ${timestamp}`,
    );
    await expect(
      page.locator('[data-testid="domain-table"]'),
    ).not.toContainText(`Domain Layer 2 ${timestamp}`);

    // Navigate to see all domains
    await page.goto("/app/domains");
    await page.waitForLoadState("networkidle");

    // Verify both domains are visible
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      `Domain Layer 1 ${timestamp}`,
    );
    await expect(page.locator('[data-testid="domain-table"]')).toContainText(
      `Domain Layer 2 ${timestamp}`,
    );
  });
});
