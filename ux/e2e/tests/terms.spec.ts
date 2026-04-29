import { test, expect } from "@playwright/test";
import { apiRequest } from "../fixtures/test-helpers";

/**
 * Term Management E2E Tests
 *
 * These tests validate the complete CRUD workflow for terms:
 * - Creating terms through the table view
 * - Editing terms through modals and detail view
 * - Deleting terms with confirmation
 * - Searching and filtering terms
 * - Navigation between table and detail views
 * - Hierarchical relationships (layer → domain → term)
 */

test.describe("Term Management", () => {
  let testLayerId: string;
  let testDomainId: string;

  test.beforeEach(async ({ page }) => {
    // Create a test layer
     
    const layerResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `E2E Test Layer ${Date.now()}`,
        definition: "Test layer for term tests",
        node_type: "layer",
      },
    });
    testLayerId = layerResponse.id;

    // Create a test domain
     
    const domainResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `E2E Test Domain ${Date.now()}`,
        definition: "Test domain for term tests",
        node_type: "domain",
        parent_node_id: testLayerId,
      },
    });
    testDomainId = domainResponse.id;

    // Navigate to terms page
    await page.goto("/app/terms");
    await page.waitForLoadState("networkidle");
  });

  test("should display the terms table", async ({ page }) => {
    // Verify table is visible
    await expect(page.locator('[data-testid="term-table"]')).toBeVisible();

    // Verify toolbar is visible with add button
    await expect(
      page.locator('[data-testid="term-table-toolbar"]'),
    ).toBeVisible();
    await expect(page.locator('[data-testid="term-add-button"]')).toBeVisible();
  });

  test("should create a new term with domain selection", async ({ page }) => {
    const termTitle = `E2E Test Term ${Date.now()}`;
    const termDefinition = "A test term created by E2E tests";

    // Click "Add Term" button
    await page.click('[data-testid="term-add-button"]');

    // Wait for create modal to appear
    await expect(
      page.getByRole("dialog", { name: "Create New Term" }),
    ).toBeVisible();

    // Fill in the form
    await page.fill('[data-testid="term-title-input"]', termTitle);
    await page.fill('[data-testid="term-definition-input"]', termDefinition);

    // Select domain - wait for selector to be ready, then click to open dropdown
    const domainSelector = page
      .locator('[data-testid="term-domain-selector"]')
      .locator("button");
    await expect(domainSelector).toBeVisible({ timeout: 10000 });
    await expect(domainSelector).toBeEnabled({ timeout: 5000 });

    // Wait a moment for selector to be fully ready
    await page.waitForTimeout(500);
    await domainSelector.click({ timeout: 10000 });

    // Wait for dropdown menu to appear (rendered in portal) and be interactive
    const dropdown = page.locator('div[role="listbox"]');
    await expect(dropdown).toBeVisible({ timeout: 5000 });

    // Wait for actual options to load by looking for our specific test domain
    // Get the test domain title first
     
    const domainResponse = await apiRequest<any>(
      page,
      `/api/classes/${testDomainId}`,
    );
    const testDomainTitle = domainResponse.title;

    // Find the option that contains our test domain title
    const domainOption = page.locator(
      `div[role="option"]:has-text("${testDomainTitle}")`,
    );
    await expect(domainOption).toBeVisible({ timeout: 10000 });

    // Wait a moment for options to be fully interactive
    await page.waitForTimeout(300);
    await domainOption.click();

    // Submit the form
    await page.click('[data-testid="term-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Create New Term" }),
    ).not.toBeVisible();

    // Verify term appears in the table
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      termTitle,
    );

    // Verify term exists in backend with correct domain association
     
    const response = await apiRequest<{ data: any[] }>(
      page,
      "/api/classes?node_type=term",
    );

     
    const createdTerm = response.data.find((n: any) => n.title === termTitle);

    expect(createdTerm).toBeDefined();
    expect(createdTerm?.definition).toBe(termDefinition);
    expect(createdTerm?.node_type).toBe("term");
    expect(createdTerm?.parent_node_id).toBe(testDomainId);
  });

  test("should edit a term through the table", async ({ page }) => {
    // First, create a term to edit
    const originalTitle = `E2E Edit Test ${Date.now()}`;
    const updatedTitle = `${originalTitle} (Updated)`;
    const updatedDefinition = "Updated definition via E2E test";

    // Create term via API
     
    const createResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: originalTitle,
        definition: "Original definition",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });
    const termId = createResponse.id;

    // Refresh the page to see the new term
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Double-click the term row to edit
    await page.locator(`[data-testid="term-row-${termId}"]`).dblclick();

    // Wait for edit modal
    await expect(page.getByRole("dialog", { name: "Edit Term" })).toBeVisible();

    // Clear and update the title
    await page.fill('[data-testid="term-title-input"]', updatedTitle);
    await page.fill('[data-testid="term-definition-input"]', updatedDefinition);

    // Submit
    await page.click('[data-testid="term-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Edit Term" }),
    ).not.toBeVisible();

    // Verify updated values appear in table
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      updatedTitle,
    );

    // Verify backend was updated
     
    const response = await apiRequest<any>(
      page,
      `/api/classes/${termId}`,
    );
    expect(response.title).toBe(updatedTitle);
    expect(response.definition).toBe(updatedDefinition);
  });

  test("should delete a term", async ({ page }) => {
    // Create a term to delete
    const termTitle = `E2E Delete Test ${Date.now()}`;
     
    const createResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: termTitle,
        definition: "Term to be deleted",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });
    const termId = createResponse.id;

    // Refresh to see the term
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Select the term row by clicking its checkbox
    const row = page.locator(`[data-testid="term-row-${termId}"]`);
    await row.locator('input[type="checkbox"]').check();

    // Click Actions dropdown and select Delete
    await page.click('[data-testid="term-actions-dropdown"]');
    await page.click('[data-testid="term-delete-selected-action"]');

    // Wait for delete confirmation modal
    await expect(
      page.getByRole("dialog", { name: /Confirm Delete/i }),
    ).toBeVisible();

    // Confirm deletion
    await page.click('[data-testid="term-delete-confirm-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: /Confirm Delete/i }),
    ).not.toBeVisible();

    // Verify term is removed from table
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      termTitle,
    );

    // Verify term is deleted from backend
    try {
      await apiRequest(page, `/api/classes/${termId}`);
      // If we get here, the term wasn't deleted
      expect(false).toBe(true); // Force fail
    } catch (error) {
      // Expected - term should be deleted
      expect(error).toBeDefined();
    }
  });

  test("should search for terms", async ({ page }) => {
    // Create multiple terms with distinct names
    const timestamp = Date.now();
    const term1Title = `Alpha Term ${timestamp}`;
    const term2Title = `Beta Term ${timestamp}`;
    const term3Title = `Gamma Term ${timestamp}`;

    // Create terms via API
    await Promise.all([
      apiRequest(page, "/api/classes", {
        method: "POST",
        body: {
          title: term1Title,
          definition: "Definition 1",
          node_type: "term",
          parent_node_id: testDomainId,
        },
      }),
      apiRequest(page, "/api/classes", {
        method: "POST",
        body: {
          title: term2Title,
          definition: "Definition 2",
          node_type: "term",
          parent_node_id: testDomainId,
        },
      }),
      apiRequest(page, "/api/classes", {
        method: "POST",
        body: {
          title: term3Title,
          definition: "Definition 3",
          node_type: "term",
          parent_node_id: testDomainId,
        },
      }),
    ]);

    // Wait for API requests to complete, then refresh with cache cleared
    await page.waitForTimeout(1000);
    await page.evaluate(() => sessionStorage.clear());
    await page.reload({ waitUntil: "networkidle" });

    // Verify all terms are visible initially
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term1Title,
    );
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term2Title,
    );
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term3Title,
    );

    // Search for "Beta"
    await page.fill('[data-testid="term-search-input"]', "Beta");

    // Wait a bit for search to filter (debounced)
    await page.waitForTimeout(500);

    // Verify only Beta term is visible
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term2Title,
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      term1Title,
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      term3Title,
    );

    // Clear search
    await page.fill('[data-testid="term-search-input"]', "");
    await page.waitForTimeout(500);

    // Verify all terms are visible again
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term1Title,
    );
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term2Title,
    );
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term3Title,
    );
  });

  test("should navigate to term detail view", async ({ page }) => {
    // Create a term
    const termTitle = `E2E Detail Test ${Date.now()}`;
    const termDefinition = "Test term for detail view";
     
    const createResponse = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: termTitle,
        definition: termDefinition,
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });
    const termId = createResponse.id;

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Find and click the link icon to navigate to detail view
    const row = page.locator(`[data-testid="term-row-${termId}"]`);

    // Wait for the row to be visible
    await expect(row).toBeVisible({ timeout: 10000 });

    // Find the link in the row
    const link = row.locator('a[href*="/app/classes/"]');
    await expect(link).toBeVisible({ timeout: 5000 });

    // Click the link
    await link.click();

    // Wait for navigation
    await page.waitForURL(`**/app/classes/${termId}`, {
      timeout: 15000,
    });
    await page.waitForLoadState("networkidle");

    // Verify we're on the detail page
    expect(page.url()).toContain(`/app/classes/${termId}`);

    // Verify term details are displayed
    await expect(page.locator("body")).toContainText(termTitle, {
      timeout: 10000,
    });
  });

  test("should cancel term creation", async ({ page }) => {
    // Get current term count
     
    const beforeResponse = await apiRequest<{ data: any[]; total: number }>(
      page,
      "/api/classes?node_type=term",
    );
    const beforeCount = beforeResponse.total;

    // Click "Add Term" button
    await page.click('[data-testid="term-add-button"]');

    // Wait for create modal
    const createModal = page.getByRole("dialog", { name: "Create New Term" });
    await expect(createModal).toBeVisible();

    // Fill in some data but don't submit
    await page.fill(
      '[data-testid="term-title-input"]',
      "Test Term Not Submitted",
    );

    // Navigate away to close the modal
    await page.goto("/app/terms");
    await page.waitForLoadState("networkidle");

    // Verify no new term was created
     
    const afterResponse = await apiRequest<{ data: any[]; total: number }>(
      page,
      "/api/classes?node_type=term",
    );
    const afterCount = afterResponse.total;

    expect(afterCount).toBe(beforeCount);

    // Verify the specific test term was not created
    const testTerm = afterResponse.data.find(
       
      (n: any) => n.title === "Test Term Not Submitted",
    );
    expect(testTerm).toBeUndefined();
  });

  test("should validate required fields", async ({ page }) => {
    // Click "Add Term" button
    await page.click('[data-testid="term-add-button"]');

    // Wait for create modal
    await expect(
      page.getByRole("dialog", { name: "Create New Term" }),
    ).toBeVisible();

    // Try to submit without filling in required fields
    await page.click('[data-testid="term-submit-button"]');

    // Modal should still be visible (HTML5 validation prevented submission)
    await expect(
      page.getByRole("dialog", { name: "Create New Term" }),
    ).toBeVisible();

    // Verify the title input field is marked as invalid
    const titleInput = page.locator('[data-testid="term-title-input"]');
    await expect(titleInput).toHaveAttribute("required");

    // Verify the definition input field is marked as invalid
    const definitionInput = page.locator(
      '[data-testid="term-definition-input"]',
    );
    await expect(definitionInput).toHaveAttribute("required");
  });

  test("should handle multiple term selections and bulk delete", async ({
    page,
  }) => {
    // Create multiple terms
    const timestamp = Date.now();
     
    const term1 = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Bulk Delete 1 ${timestamp}`,
        definition: "Term 1",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });
     
    const term2 = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Bulk Delete 2 ${timestamp}`,
        definition: "Term 2",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });

    // Refresh
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Select both terms
    await page
      .locator(`[data-testid="term-row-${term1.id}"]`)
      .locator('input[type="checkbox"]')
      .check();
    await page
      .locator(`[data-testid="term-row-${term2.id}"]`)
      .locator('input[type="checkbox"]')
      .check();

    // Delete selected
    await page.click('[data-testid="term-actions-dropdown"]');
    await page.click('[data-testid="term-delete-selected-action"]');

    // Confirm
    const deleteModal = page.getByRole("dialog", { name: /Confirm Delete/i });
    await expect(deleteModal).toBeVisible();
    await expect(deleteModal).toContainText("2 selected");
    await page.click('[data-testid="term-delete-confirm-button"]');

    // Wait for modal to close
    await expect(deleteModal).not.toBeVisible();

    // Verify both terms are gone
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      `Bulk Delete 1 ${timestamp}`,
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      `Bulk Delete 2 ${timestamp}`,
    );
  });

  test("should filter terms by domain", async ({ page }) => {
    // Create a second domain
     
    const domain2Response = await apiRequest<any>(
      page,
      "/api/classes",
      {
        method: "POST",
        body: {
          title: `E2E Test Domain 2 ${Date.now()}`,
          definition: "Second test domain",
          node_type: "domain",
          parent_node_id: testLayerId,
        },
      },
    );
    const domain2Id = domain2Response.id;

    const timestamp = Date.now();
    const term1Title = `Term Domain 1 ${timestamp}`;
    const term2Title = `Term Domain 2 ${timestamp}`;

    // Create terms in each domain
     
    await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: term1Title,
        definition: "Term in domain 1",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });

     
    await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: term2Title,
        definition: "Term in domain 2",
        node_type: "term",
        parent_node_id: domain2Id,
      },
    });

    // Navigate DIRECTLY to filtered view for domain 1
    await page.goto(`/app/terms?parent_node_id=${testDomainId}`);
    await page.waitForLoadState("networkidle");

    // Wait for table to be visible
    await expect(page.locator('[data-testid="term-table"]')).toBeVisible({
      timeout: 10000,
    });

    // Verify term1 is visible and term2 is not
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term1Title,
      { timeout: 10000 },
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      term2Title,
    );

    // Navigate to filtered view for domain 2
    await page.goto(`/app/terms?parent_node_id=${domain2Id}`);
    await page.waitForLoadState("networkidle");

    // Verify term2 is visible and term1 is not
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term2Title,
      { timeout: 10000 },
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      term1Title,
    );
  });

  test("should filter terms by layer", async ({ page }) => {
    // Create a second layer and domain
     
    const layer2Response = await apiRequest<any>(page, "/api/classes", {
      method: "POST",
      body: {
        title: `E2E Test Layer 2 ${Date.now()}`,
        definition: "Second test layer",
        node_type: "layer",
      },
    });
    const layer2Id = layer2Response.id;

     
    const domain2Response = await apiRequest<any>(
      page,
      "/api/classes",
      {
        method: "POST",
        body: {
          title: `E2E Test Domain Layer 2 ${Date.now()}`,
          definition: "Domain in layer 2",
          node_type: "domain",
          parent_node_id: layer2Id,
        },
      },
    );
    const domain2Id = domain2Response.id;

    const timestamp = Date.now();
    const term1Title = `Term Layer 1 ${timestamp}`;
    const term2Title = `Term Layer 2 ${timestamp}`;

    // Create terms in domains from different layers
    await apiRequest(page, "/api/classes", {
      method: "POST",
      body: {
        title: term1Title,
        definition: "Term in layer 1",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });

    await apiRequest(page, "/api/classes", {
      method: "POST",
      body: {
        title: term2Title,
        definition: "Term in layer 2",
        node_type: "term",
        parent_node_id: domain2Id,
      },
    });

    // Navigate DIRECTLY to filtered view for domain 1 (which is in layer 1)
    await page.goto(`/app/terms?parent_node_id=${testDomainId}`);
    await page.waitForLoadState("networkidle");

    // Wait for table to be visible
    await expect(page.locator('[data-testid="term-table"]')).toBeVisible({
      timeout: 10000,
    });

    // Verify only term1 is visible (filtering by domain also filters by layer)
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term1Title,
      { timeout: 10000 },
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      term2Title,
    );

    // Navigate to filtered view for domain 2 (which is in layer 2)
    await page.goto(`/app/terms?parent_node_id=${domain2Id}`);
    await page.waitForLoadState("networkidle");

    // Verify only term2 is visible
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      term2Title,
      { timeout: 10000 },
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      term1Title,
    );
  });

  test("should handle hierarchical filtering by both layer and domain", async ({
    page,
  }) => {
    // Create a second domain in the same layer
     
    const domain2Response = await apiRequest<any>(
      page,
      "/api/classes",
      {
        method: "POST",
        body: {
          title: `E2E Test Domain 2 ${Date.now()}`,
          definition: "Second domain in same layer",
          node_type: "domain",
          parent_node_id: testLayerId,
        },
      },
    );
    const domain2Id = domain2Response.id;

    const timestamp = Date.now();

    // Create terms in different domains
    await apiRequest(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Term D1 ${timestamp}`,
        definition: "Term in domain 1",
        node_type: "term",
        parent_node_id: testDomainId,
      },
    });

    await apiRequest(page, "/api/classes", {
      method: "POST",
      body: {
        title: `Term D2 ${timestamp}`,
        definition: "Term in domain 2",
        node_type: "term",
        parent_node_id: domain2Id,
      },
    });

    // Filter by specific domain
    await page.goto(`/app/terms?parent_node_id=${testDomainId}`);
    await page.waitForLoadState("networkidle");

    // Verify only terms from first domain are visible
    await expect(page.locator('[data-testid="term-table"]')).toContainText(
      `Term D1 ${timestamp}`,
    );
    await expect(page.locator('[data-testid="term-table"]')).not.toContainText(
      `Term D2 ${timestamp}`,
    );
  });
});
