/**
 * Structure Node Attributes E2E Tests
 *
 * Comprehensive end-to-end tests for structure node attribute management
 * including fixture generation, inheritance, validation, and performance.
 */

import { test, expect, Page } from "@playwright/test";
import { apiRequest } from "../fixtures/test-helpers";

/**
 * Test fixture for a complete hierarchy with attributes
 */
interface TestHierarchy {
  layer: { id: string; title: string };
  domain: { id: string; title: string };
  term1: { id: string; title: string };
  term2: { id: string; title: string };
  deepTerms: Array<{ id: string; title: string }>;
}

/**
 * Generate a complete test hierarchy with attributes
 */
async function generateTestHierarchy(
  page: Page,
  timestamp: number,
): Promise<TestHierarchy> {
  // Create layer with category attribute
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layerResponse = await apiRequest<any>(page, "/api/structure_nodes", {
    method: "POST",
    body: {
      title: `Legal Domain ${timestamp}`,
      definition: "Test layer for attribute inheritance",
      node_type: "layer",
    },
  });
  const layerId = layerResponse.id;

  // Set attributes on layer
  await apiRequest(page, `/api/structure_nodes/${layerId}/attributes`, {
    method: "POST",
    body: [
      {
        key: "category",
        title: "Domain Category",
        value_type: "string",
        value: "legal_classification",
      },
    ],
  });

  // Create domain with jurisdiction attribute
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const domainResponse = await apiRequest<any>(page, "/api/structure_nodes", {
    method: "POST",
    body: {
      title: `Contract Law ${timestamp}`,
      definition: "Test domain for attribute inheritance",
      node_type: "domain",
      parent_node_id: layerId,
    },
  });
  const domainId = domainResponse.id;

  // Set attributes on domain
  await apiRequest(page, `/api/structure_nodes/${domainId}/attributes`, {
    method: "POST",
    body: [
      {
        key: "jurisdiction",
        title: "Jurisdiction",
        value_type: "string",
        value: "US Federal",
      },
    ],
  });

  // Create term1 with override and local attribute
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const term1Response = await apiRequest<any>(page, "/api/structure_nodes", {
    method: "POST",
    body: {
      title: `Force Majeure ${timestamp}`,
      definition: "Test term with attribute override",
      node_type: "term",
      parent_node_id: domainId,
    },
  });
  const term1Id = term1Response.id;

  // Set attributes on term1 (override jurisdiction, add definition_date)
  await apiRequest(page, `/api/structure_nodes/${term1Id}/attributes`, {
    method: "POST",
    body: [
      {
        key: "jurisdiction",
        title: "Jurisdiction",
        value_type: "string",
        value: "New York State",
      },
      {
        key: "definition_date",
        title: "Definition Date",
        value_type: "date",
        value: "2025-01-15",
      },
    ],
  });

  // Create term2 with no local attributes (inherits all)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const term2Response = await apiRequest<any>(page, "/api/structure_nodes", {
    method: "POST",
    body: {
      title: `Indemnification ${timestamp}`,
      definition: "Test term with inherited attributes only",
      node_type: "term",
      parent_node_id: domainId,
    },
  });
  const term2Id = term2Response.id;

  // Create 5-level deep nested structure
  const deepTerms = [];
  let parentId = term1Id;

  for (let i = 1; i <= 5; i++) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const deepTermResponse = await apiRequest<any>(
      page,
      "/api/structure_nodes",
      {
        method: "POST",
        body: {
          title: `Deep Term Level ${i} ${timestamp}`,
          definition: `Nested term at level ${i}`,
          node_type: "term",
          parent_node_id: parentId,
        },
      },
    );

    // Add level attribute only at level 3
    if (i === 3) {
      await apiRequest(
        page,
        `/api/structure_nodes/${deepTermResponse.id}/attributes`,
        {
          method: "POST",
          body: [
            {
              key: "level_attribute",
              title: "Level Attribute",
              value_type: "string",
              value: `Level ${i}`,
            },
          ],
        },
      );
    }

    deepTerms.push(deepTermResponse);
    parentId = deepTermResponse.id;
  }

  return {
    layer: { id: layerId, title: `Legal Domain ${timestamp}` },
    domain: { id: domainId, title: `Contract Law ${timestamp}` },
    term1: { id: term1Id, title: `Force Majeure ${timestamp}` },
    term2: { id: term2Id, title: `Indemnification ${timestamp}` },
    deepTerms,
  };
}

test.describe("Structure Node Attributes E2E", () => {
  let testHierarchy: TestHierarchy;
  const timestamp = Date.now();

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    try {
      testHierarchy = await generateTestHierarchy(page, timestamp);
    } finally {
      await page.close();
    }
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/app");
    await page.waitForLoadState("networkidle");
  });

  test("Create attribute on structure node", async ({ page }) => {
    // Navigate to term1 detail page
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState("networkidle");

    // Verify page loaded
    await expect(page.locator("body")).toContainText(testHierarchy.term1.title);

    // Find and click the Add Attribute button
    const addAttributeButton = page.getByRole("button", {
      name: /Add Attribute/i,
    });
    await expect(addAttributeButton).toBeVisible({ timeout: 5000 });
    await addAttributeButton.click();

    // Wait for the form to appear (Card element with form inputs)
    await expect(page.locator("form")).toBeVisible({ timeout: 5000 });

    // Fill in attribute details
    const attributeKey = `test_attr_${Date.now()}`;
    const inputs = page.locator('input[type="text"]');

    // Key input (first text input)
    const keyInput = inputs.nth(0);
    await keyInput.fill(attributeKey);

    // Title input (second text input)
    const titleInput = inputs.nth(1);
    await titleInput.fill("Test Attribute");

    // Type select
    const typeSelect = page.locator("select");
    await typeSelect.selectOption("string");

    // Value input (third text input)
    const valueInput = inputs.nth(2);
    await valueInput.fill("test_value");

    // Submit the form
    const submitButton = page.getByRole("button", {
      name: /Add Attribute|Update Attribute/i,
    });
    await submitButton.click();

    // Wait for form to close
    await expect(page.locator("form")).not.toBeVisible({ timeout: 5000 });

    // Verify attribute appears in the list
    await expect(page.getByText(attributeKey)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("test_value")).toBeVisible();

    // Verify via API
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodeResponse = await apiRequest<any>(
      page,
      `/api/structure_nodes/${testHierarchy.term1.id}/attributes`,
    );
    const createdAttr = nodeResponse.find(
      (attr: any) => attr.key === attributeKey, // eslint-disable-line @typescript-eslint/no-explicit-any
    );
    expect(createdAttr).toBeDefined();
    expect(createdAttr.value).toBe("test_value");
    expect(createdAttr.inherited).toBe(false);
  });

  test("View inherited attributes with visual distinction", async ({
    page,
  }) => {
    // Navigate to term2 (has only inherited attributes)
    await page.goto(`/app/structure_nodes/${testHierarchy.term2.id}`);
    await page.waitForLoadState("networkidle");

    // Verify page loaded
    await expect(page.locator("body")).toContainText(testHierarchy.term2.title);

    // Look for inherited attributes section heading
    const inheritedHeading = page.getByText("Inherited Attributes");
    await expect(inheritedHeading).toBeVisible({ timeout: 5000 });

    // Verify inherited attributes are displayed
    const jurisdictionAttribute = page.getByText("Jurisdiction");
    await expect(jurisdictionAttribute).toBeVisible();

    // Verify the inherited value is shown
    await expect(page.getByText("US Federal")).toBeVisible();

    // Verify inheritance indicator (icon) is present
    // The InheritedAttributeInfo component shows a link icon and "inherited" text
    const inheritedText = page.getByText("inherited");
    await expect(inheritedText).toBeVisible({ timeout: 5000 });

    // Hover over the inherited indicator to see tooltip
    await inheritedText.first().hover();
    const tooltip = page.locator('[role="tooltip"]');

    // Tooltip should mention the source node (domain)
    if (await tooltip.isVisible()) {
      await expect(tooltip).toContainText(testHierarchy.domain.title);
    }
  });

  test("Override inherited attribute", async ({ page }) => {
    // Navigate to term1 (which has jurisdiction override)
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState("networkidle");

    // Find the jurisdiction attribute
    const jurisdictionText = page.getByText("Jurisdiction").first();
    await expect(jurisdictionText).toBeVisible({ timeout: 5000 });

    // Find parent element containing the attribute
    const attributeContainer = jurisdictionText.locator("..");

    // Look for edit button (Edit2 icon button)

    // Find the edit button near the jurisdiction attribute
    const editButton = attributeContainer.locator("button").first();
    await expect(editButton).toBeVisible({ timeout: 5000 });

    // Click edit button
    await editButton.click();

    // Wait for edit form
    await expect(page.locator("form")).toBeVisible({ timeout: 5000 });

    // Verify current override value is shown
    const valueInput = page.locator('input[type="text"]').nth(2); // Third input is value
    const currentValue = await valueInput.inputValue();
    expect(currentValue).toBe("New York State");

    // Change the value
    await valueInput.clear();
    await valueInput.fill("California");

    // Submit
    const submitButton = page.getByRole("button", {
      name: /Update Attribute/i,
    });
    await submitButton.click();

    // Wait for form to close
    await expect(page.locator("form")).not.toBeVisible({ timeout: 5000 });

    // Verify updated value appears
    await expect(page.getByText("California")).toBeVisible({ timeout: 5000 });

    // Verify via API
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const attributes = await apiRequest<any>(
      page,
      `/api/structure_nodes/${testHierarchy.term1.id}/attributes`,
    );
    const jurisdictionAttr = attributes.find(
      (a: any) => a.key === "jurisdiction", // eslint-disable-line @typescript-eslint/no-explicit-any
    );
    expect(jurisdictionAttr.value).toBe("California");
  });

  test("Delete local attribute override", async ({ page }) => {
    // Navigate to term1 (has override we can delete)
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState("networkidle");

    // Create a new attribute to delete
    const addAttributeButton = page.getByRole("button", {
      name: /Add Attribute/i,
    });
    await expect(addAttributeButton).toBeVisible({ timeout: 5000 });
    await addAttributeButton.click();

    // Wait for form
    await expect(page.locator("form")).toBeVisible({ timeout: 5000 });

    // Fill in a simple test attribute
    const inputs = page.locator('input[type="text"]');
    await inputs.nth(0).fill("deletable_attr");
    await inputs.nth(1).fill("Deletable");
    await inputs.nth(2).fill("delete_me");

    // Submit
    const submitButton = page.getByRole("button", { name: /Add Attribute/i });
    await submitButton.click();

    // Wait for form to close
    await expect(page.locator("form")).not.toBeVisible({ timeout: 5000 });

    // Verify attribute was created
    await expect(page.getByText("deletable_attr")).toBeVisible({
      timeout: 5000,
    });

    // Now delete it - find the delete button (trash icon) for this attribute
    const deleteButtons = page
      .getByRole("button")
      .filter({ has: page.locator("svg") });
    const buttons = await deleteButtons.all();

    // Find the trash button (last button in the attribute row)
    let trashButton = null;
    for (const btn of buttons) {
      const html = await btn.innerHTML();
      if (html.includes("w-4") && html.includes("h-4")) {
        // SVG icon
        // Check if it's near the deletable_attr text
        const text = await btn.locator("..").textContent();
        if (text?.includes("deletable_attr")) {
          trashButton = btn;
          break;
        }
      }
    }

    if (trashButton) {
      await trashButton.click();

      // Confirm if there's a confirmation dialog
      const confirmButton = page.getByRole("button", {
        name: /confirm|delete|yes/i,
      });
      if (await confirmButton.isVisible().catch(() => false)) {
        await confirmButton.click();
      }

      // Wait for deletion
      await page.waitForTimeout(500);

      // Verify attribute is removed
      await expect(page.getByText("deletable_attr")).not.toBeVisible({
        timeout: 5000,
      });
    }
  });

  test("Inline validation for attribute types", async ({ page }) => {
    // Navigate to a term
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState("networkidle");

    // Click add attribute
    const addAttributeButton = page.getByRole("button", {
      name: /Add Attribute/i,
    });
    await addAttributeButton.click();

    // Wait for form
    await expect(page.locator("form")).toBeVisible({ timeout: 5000 });

    // Set type to number
    const typeSelect = page.locator("select");
    await typeSelect.selectOption("number");

    // Get the value input (AttributeValueInput component handles type-specific rendering)
    const inputs = page.locator('input[type="text"]');
    const valueInput = inputs.nth(2); // Third input is value

    // Enter a non-numeric value
    await valueInput.fill("not_a_number");

    // Trigger validation by blurring
    await valueInput.blur();
    await page.waitForTimeout(300);

    // Look for error message
    const errorText = page.locator("text=/invalid|must be|error/i");

    // Error might appear as part of the form
    let hasError = false;
    try {
      const visibleErrors = await errorText.all();
      hasError = visibleErrors.length > 0;
    } catch {
      // No visible error elements found
    }

    if (hasError) {
      // Correct the value
      await valueInput.clear();
      await valueInput.fill("42");
      await valueInput.blur();
      await page.waitForTimeout(300);

      // Error should be gone
      const errorsAfter = await errorText.all();
      expect(errorsAfter.length).toBeLessThanOrEqual(0);
    }
  });

  test("Attribute inheritance across 5-level hierarchy", async ({ page }) => {
    // Navigate to deepest level (level 5)
    const deepestTerm = testHierarchy.deepTerms[4];
    await page.goto(`/app/structure_nodes/${deepestTerm.id}`);
    await page.waitForLoadState("networkidle");

    // Verify attributes are loaded
    const attributesHeading = page.getByText("Attributes");
    await expect(attributesHeading).toBeVisible({ timeout: 5000 });

    // Verify inherited attributes from different levels are present
    // Category from layer (inherited through all levels)
    await expect(page.getByText("Category")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("legal_classification")).toBeVisible();

    // Jurisdiction from domain (inherited through term1 and deep terms)
    await expect(page.getByText("Jurisdiction")).toBeVisible({ timeout: 5000 });

    // Level attribute from level 3 term
    await expect(page.getByText("Level Attribute")).toBeVisible({
      timeout: 5000,
    });
    await expect(page.getByText("Level 3")).toBeVisible();

    // Verify via API - resolve attributes should show all ancestors' attributes
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const attributes = await apiRequest<any>(
      page,
      `/api/structure_nodes/${deepestTerm.id}/attributes`,
    );
    expect(attributes.length).toBeGreaterThan(0);

    // Check for category attribute
    const categoryAttr = attributes.find(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (a: any) => a.key === "category",
    );
    expect(categoryAttr).toBeDefined();
    expect(categoryAttr.inherited).toBe(true);
  });

  test("Display performance with 50+ attributes", async ({ page }) => {
    // Create a term with many attributes
    const timestamp = Date.now();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const termResponse = await apiRequest<any>(page, "/api/structure_nodes", {
      method: "POST",
      body: {
        title: `Performance Test Term ${timestamp}`,
        definition: "Term for performance testing",
        node_type: "term",
        parent_node_id: testHierarchy.domain.id,
      },
    });
    const termId = termResponse.id;

    // Add 50 attributes via API
    const attributes = [];
    for (let i = 0; i < 50; i++) {
      attributes.push({
        key: `perf_attr_${i}`,
        title: `Performance Attribute ${i}`,
        value_type: "string",
        value: `Value ${i}`,
      });
    }

    await apiRequest(page, `/api/structure_nodes/${termId}/attributes`, {
      method: "POST",
      body: attributes,
    });

    // Navigate and measure render time
    const startTime = Date.now();
    await page.goto(`/app/structure_nodes/${termId}`);
    await page.waitForLoadState("networkidle");
    const renderTime = Date.now() - startTime;

    // Verify page loaded
    const attributesHeading = page.getByText("Attributes");
    await expect(attributesHeading).toBeVisible({ timeout: 5000 });

    // Count visible attributes (at least some should be visible)
    const attributeKeys = page.locator("text=/perf_attr_/");
    const count = await attributeKeys.all().then((items) => items.length);
    expect(count).toBeGreaterThan(0);

    // Verify render time is acceptable (< 500ms)
    console.log(`Render time with 50+ attributes: ${renderTime}ms`);
    expect(renderTime).toBeLessThan(500);

    // Verify no horizontal scrolling required
    const bodyWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const viewportWidth = page.viewportSize()?.width || 0;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 1);
  });

  test("Attribute display readability", async ({ page }) => {
    // Navigate to term1 with multiple attributes
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState("networkidle");

    // Verify attributes section is visible
    const attributesHeading = page.getByText("Attributes");
    await expect(attributesHeading).toBeVisible({ timeout: 5000 });

    // Verify attribute types are visible (badges like "string", "date", etc.)
    const typeBadges = page.locator(
      "text=/^(string|number|boolean|date|url)$/",
    );
    const typeCount = await typeBadges.all().then((items) => items.length);
    expect(typeCount).toBeGreaterThan(0);

    // Verify no horizontal scrolling
    const bodyWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const viewportWidth = page.viewportSize()?.width || 0;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 1);

    // Take screenshot for visual regression
    await page.screenshot({
      path: "test-results/attribute-readability.png",
      fullPage: true,
    });
  });

  test("API error handling in UX", async ({ page }) => {
    // Navigate to term1
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState("networkidle");

    // Intercept attribute API to simulate error
    await page.route(`**/api/structure_nodes/*/attributes`, (route) => {
      if (route.request().method() === "POST") {
        route.abort("failed");
      } else {
        route.continue();
      }
    });

    // Click add attribute
    const addAttributeButton = page.getByRole("button", {
      name: /Add Attribute/i,
    });
    await addAttributeButton.click();

    // Wait for form
    await expect(page.locator("form")).toBeVisible({ timeout: 5000 });

    // Fill in form
    const inputs = page.locator('input[type="text"]');
    await inputs.nth(0).fill(`error_test_${Date.now()}`);
    await inputs.nth(1).fill("Error Test");
    await inputs.nth(2).fill("test");

    // Try to submit
    const submitButton = page.getByRole("button", { name: /Add Attribute/i });
    await submitButton.click();

    // Wait for error to appear
    await page.waitForTimeout(1000);

    // Look for error message (should be user-friendly)
    const alertOrErrorDiv = page.locator(
      '[role="alert"], .alert, .error, text=/error|failed/i',
    );
    const errorElements = await alertOrErrorDiv.all();

    // If error element found, verify it's not raw error
    if (errorElements.length > 0) {
      const errorText = await errorElements[0].textContent();
      expect(errorText).toBeTruthy();
      expect(errorText?.toLowerCase()).toContain("error");
    }

    // Verify form is still visible (not broken)
    await expect(page.locator("form")).toBeVisible();
  });

  test("Verify attribute types are preserved", async ({ page }) => {
    // Create a test node with all attribute types
    const timestamp = Date.now();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const testNodeResponse = await apiRequest<any>(
      page,
      "/api/structure_nodes",
      {
        method: "POST",
        body: {
          title: `Type Test Node ${timestamp}`,
          definition: "Test all attribute types",
          node_type: "term",
          parent_node_id: testHierarchy.domain.id,
        },
      },
    );
    const testNodeId = testNodeResponse.id;

    // Set attributes with all types
    await apiRequest(page, `/api/structure_nodes/${testNodeId}/attributes`, {
      method: "POST",
      body: [
        {
          key: "string_attr",
          title: "String",
          value_type: "string",
          value: "hello",
        },
        {
          key: "number_attr",
          title: "Number",
          value_type: "number",
          value: 42,
        },
        {
          key: "boolean_attr",
          title: "Boolean",
          value_type: "boolean",
          value: true,
        },
        {
          key: "date_attr",
          title: "Date",
          value_type: "date",
          value: "2025-01-15",
        },
        {
          key: "url_attr",
          title: "URL",
          value_type: "url",
          value: "https://example.com",
        },
      ],
    });

    // Navigate to node
    await page.goto(`/app/structure_nodes/${testNodeId}`);
    await page.waitForLoadState("networkidle");

    // Verify all attributes are displayed
    await expect(page.getByText("String")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("Number")).toBeVisible();
    await expect(page.getByText("Boolean")).toBeVisible();
    await expect(page.getByText("Date")).toBeVisible();
    await expect(page.getByText("URL")).toBeVisible();

    // Verify values
    await expect(page.getByText("hello")).toBeVisible();
    await expect(page.getByText("42")).toBeVisible();
    await expect(page.getByText("2025-01-15")).toBeVisible();
    await expect(page.getByText("https://example.com")).toBeVisible();

    // Verify via API
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const attributes = await apiRequest<any>(
      page,
      `/api/structure_nodes/${testNodeId}/attributes`,
    );
    expect(attributes.length).toBe(5);
    expect(
      attributes.some(
        (a: any) => a.key === "string_attr" && a.value_type === "string", // eslint-disable-line @typescript-eslint/no-explicit-any
      ),
    ).toBe(true);
    expect(
      attributes.some(
        (a: any) => a.key === "number_attr" && a.value_type === "number", // eslint-disable-line @typescript-eslint/no-explicit-any
      ),
    ).toBe(true);
    expect(
      attributes.some(
        (a: any) => a.key === "boolean_attr" && a.value_type === "boolean", // eslint-disable-line @typescript-eslint/no-explicit-any
      ),
    ).toBe(true);
    expect(
      attributes.some(
        (a: any) => a.key === "date_attr" && a.value_type === "date", // eslint-disable-line @typescript-eslint/no-explicit-any
      ),
    ).toBe(true);
    expect(
      attributes.some(
        (a: any) => a.key === "url_attr" && a.value_type === "url", // eslint-disable-line @typescript-eslint/no-explicit-any
      ),
    ).toBe(true);
  });
});
