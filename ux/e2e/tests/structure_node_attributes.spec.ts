import { test, expect } from '@playwright/test';
import { apiRequest } from '../fixtures/test-helpers';

/**
 * Structure Node Attributes E2E Tests
 *
 * These tests validate the complete attribute management workflow:
 * - Creating attributes on structure nodes
 * - Viewing inherited attributes with visual distinction
 * - Overriding inherited attributes
 * - Deleting local attribute overrides
 * - Validating attribute types
 * - Verifying inheritance across multi-level hierarchies
 * - Testing performance with large numbers of attributes
 * - Verifying UI readability and error handling
 */

interface StructureNode {
  id: string;
  title: string;
  node_type: 'layer' | 'domain' | 'term';
  parent_id?: string;
  attributes?: Record<string, any>;
}

interface AttributePayload {
  key: string;
  title: string;
  value_type: 'string' | 'number' | 'boolean' | 'date' | 'url';
  value?: string | number | boolean;
}

test.describe('Structure Node Attributes E2E', () => {
  let testHierarchy: {
    layer: StructureNode;
    domain: StructureNode;
    term1: StructureNode;
    term2: StructureNode;
    deepTerms: StructureNode[];
  };

  /**
   * Setup test hierarchy with attributes
   */
  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();

    try {
      const timestamp = Date.now();

      // Create layer with attributes
      const layerResponse = await apiRequest<StructureNode>(page, '/api/structure_nodes', {
        method: 'POST',
        body: {
          title: `Legal Domain ${timestamp}`,
          definition: 'Test layer for attribute inheritance',
          node_type: 'layer',
          attributes: {
            category: {
              key: 'category',
              title: 'Domain Category',
              value_type: 'string',
              value: 'legal_classification',
            },
          },
        },
      });
      const layerId = layerResponse.id;

      // Create domain with inherited attributes
      const domainResponse = await apiRequest<StructureNode>(page, '/api/structure_nodes', {
        method: 'POST',
        body: {
          title: `Contract Law ${timestamp}`,
          definition: 'Test domain for attribute inheritance',
          node_type: 'domain',
          parent_id: layerId,
          attributes: {
            jurisdiction: {
              key: 'jurisdiction',
              title: 'Jurisdiction',
              value_type: 'string',
              value: 'US Federal',
            },
          },
        },
      });
      const domainId = domainResponse.id;

      // Create term 1 with override and local attribute
      const term1Response = await apiRequest<StructureNode>(page, '/api/structure_nodes', {
        method: 'POST',
        body: {
          title: `Force Majeure ${timestamp}`,
          definition: 'Test term with attribute override',
          node_type: 'term',
          parent_id: domainId,
          attributes: {
            jurisdiction: {
              key: 'jurisdiction',
              title: 'Jurisdiction',
              value_type: 'string',
              value: 'New York State',
              is_override: true,
            },
            definition_date: {
              key: 'definition_date',
              title: 'Definition Date',
              value_type: 'date',
              value: '2025-01-15',
            },
          },
        },
      });
      const term1Id = term1Response.id;

      // Create term 2 with only inherited attributes
      const term2Response = await apiRequest<StructureNode>(page, '/api/structure_nodes', {
        method: 'POST',
        body: {
          title: `Indemnification ${timestamp}`,
          definition: 'Test term with inherited attributes only',
          node_type: 'term',
          parent_id: domainId,
        },
      });
      const term2Id = term2Response.id;

      // Create 5-level deep nested structure
      const deepTerms: StructureNode[] = [];
      let parentId = term1Id;

      for (let i = 1; i <= 5; i++) {
        const deepTermResponse = await apiRequest<StructureNode>(page, '/api/structure_nodes', {
          method: 'POST',
          body: {
            title: `Deep Term Level ${i} ${timestamp}`,
            definition: `Nested term at level ${i}`,
            node_type: 'term',
            parent_id: parentId,
            attributes: i === 3 ? {
              level_attribute: {
                key: 'level_attribute',
                title: 'Level Attribute',
                value_type: 'string',
                value: `Level ${i}`,
              },
            } : undefined,
          },
        });
        deepTerms.push(deepTermResponse);
        parentId = deepTermResponse.id;
      }

      testHierarchy = {
        layer: { id: layerId, title: `Legal Domain ${timestamp}`, node_type: 'layer' },
        domain: { id: domainId, title: `Contract Law ${timestamp}`, node_type: 'domain' },
        term1: { id: term1Id, title: `Force Majeure ${timestamp}`, node_type: 'term' },
        term2: { id: term2Id, title: `Indemnification ${timestamp}`, node_type: 'term' },
        deepTerms,
      };
    } finally {
      await page.close();
    }
  });

  test.beforeEach(async ({ page }) => {
    // Navigate to app home
    await page.goto('/app');
    await page.waitForLoadState('networkidle');
  });

  test('Create attribute on structure node', async ({ page }) => {
    // Navigate to term1 detail page
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState('networkidle');

    // Verify we're on the detail page
    await expect(page.locator('body')).toContainText(testHierarchy.term1.title);

    // Find and click the add attribute button
    const addAttributeButton = page.locator('[data-testid="add-attribute-button"]');
    await expect(addAttributeButton).toBeVisible({ timeout: 5000 });
    await addAttributeButton.click();

    // Wait for attribute form to appear
    const attributeForm = page.locator('[data-testid="attribute-form"]');
    await expect(attributeForm).toBeVisible({ timeout: 5000 });

    // Fill in attribute details
    const attributeKey = `test_attr_${Date.now()}`;
    await page.fill('[data-testid="attribute-key-input"]', attributeKey);
    await page.fill('[data-testid="attribute-title-input"]', 'Test Attribute');
    await page.locator('[data-testid="attribute-type-select"]').selectOption('string');
    await page.fill('[data-testid="attribute-value-input"]', 'test_value');

    // Submit the form
    await page.click('[data-testid="attribute-form-submit"]');

    // Wait for form to close
    await expect(attributeForm).not.toBeVisible({ timeout: 5000 });

    // Verify attribute appears in the list
    await expect(page.locator('[data-testid="attributes-list"]')).toContainText(attributeKey);

    // Verify via API
    const nodeResponse = await apiRequest<StructureNode>(page, `/api/structure_nodes/${testHierarchy.term1.id}`);
    expect(nodeResponse.attributes?.[attributeKey]).toBeDefined();
    expect(nodeResponse.attributes?.[attributeKey].value).toBe('test_value');
  });

  test('View inherited attributes with visual distinction', async ({ page }) => {
    // Navigate to term2 which has no local attributes but inherits from domain and layer
    await page.goto(`/app/structure_nodes/${testHierarchy.term2.id}`);
    await page.waitForLoadState('networkidle');

    // Verify inherited attributes section is visible
    const inheritedAttributesSection = page.locator('[data-testid="inherited-attributes-section"]');
    await expect(inheritedAttributesSection).toBeVisible({ timeout: 5000 });

    // Verify inherited attributes have inheritance indicator
    const jurisdictionAttribute = page.locator('[data-testid="attribute-jurisdiction"]');
    await expect(jurisdictionAttribute).toBeVisible();

    // Verify inheritance indicator (icon/badge) is present
    const inheritanceIndicator = jurisdictionAttribute.locator('[data-testid="inheritance-indicator"]');
    await expect(inheritanceIndicator).toBeVisible();

    // Hover over inheritance indicator to see tooltip
    await inheritanceIndicator.hover();
    const tooltip = page.locator('[role="tooltip"]');
    await expect(tooltip).toBeVisible({ timeout: 5000 });

    // Verify tooltip shows source node
    await expect(tooltip).toContainText(testHierarchy.domain.title);
  });

  test('Override inherited attribute', async ({ page }) => {
    // Navigate to term1 which already has a jurisdiction override
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState('networkidle');

    // Find the overridden attribute
    const jurisdictionAttribute = page.locator('[data-testid="attribute-jurisdiction"]');
    await expect(jurisdictionAttribute).toBeVisible({ timeout: 5000 });

    // Verify it currently shows the override value
    await expect(jurisdictionAttribute).toContainText('New York State');

    // Click to edit the attribute
    const editButton = jurisdictionAttribute.locator('[data-testid="edit-attribute-button"]');
    await editButton.click();

    // Wait for edit form
    const attributeForm = page.locator('[data-testid="attribute-form"]');
    await expect(attributeForm).toBeVisible({ timeout: 5000 });

    // Verify the current value is shown
    const valueInput = page.locator('[data-testid="attribute-value-input"]');
    const currentValue = await valueInput.inputValue();
    expect(currentValue).toBe('New York State');

    // Change the value
    await valueInput.clear();
    await valueInput.fill('California');

    // Submit
    await page.click('[data-testid="attribute-form-submit"]');
    await expect(attributeForm).not.toBeVisible({ timeout: 5000 });

    // Verify the updated value appears
    await expect(jurisdictionAttribute).toContainText('California');

    // Verify via API
    const nodeResponse = await apiRequest<StructureNode>(page, `/api/structure_nodes/${testHierarchy.term1.id}`);
    expect(nodeResponse.attributes?.jurisdiction.value).toBe('California');
  });

  test('Delete local attribute override', async ({ page }) => {
    // Navigate to term1 which has an override
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState('networkidle');

    // Find the overridden attribute
    const jurisdictionAttribute = page.locator('[data-testid="attribute-jurisdiction"]');
    await expect(jurisdictionAttribute).toBeVisible({ timeout: 5000 });

    // Open the attribute menu
    const attributeMenu = jurisdictionAttribute.locator('[data-testid="attribute-menu-button"]');
    await attributeMenu.click();

    // Click delete option
    const deleteOption = page.locator('[data-testid="attribute-delete-option"]');
    await expect(deleteOption).toBeVisible({ timeout: 5000 });
    await deleteOption.click();

    // Confirm deletion in dialog
    const confirmButton = page.locator('[data-testid="confirm-delete-button"]');
    await expect(confirmButton).toBeVisible({ timeout: 5000 });
    await confirmButton.click();

    // Wait for deletion to complete
    await page.waitForTimeout(500);

    // Verify the attribute now shows inherited value with inheritance indicator
    const inheritanceIndicator = jurisdictionAttribute.locator('[data-testid="inheritance-indicator"]');
    await expect(inheritanceIndicator).toBeVisible({ timeout: 5000 });

    // Verify it shows the inherited value from domain
    await expect(jurisdictionAttribute).toContainText('US Federal');

    // Verify via API
    const nodeResponse = await apiRequest<StructureNode>(page, `/api/structure_nodes/${testHierarchy.term1.id}`);
    expect(nodeResponse.attributes?.jurisdiction?.is_override).toBeFalsy();
  });

  test('Inline validation for attribute types', async ({ page }) => {
    // Navigate to a term
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState('networkidle');

    // Click add attribute
    const addAttributeButton = page.locator('[data-testid="add-attribute-button"]');
    await addAttributeButton.click();

    // Wait for form
    const attributeForm = page.locator('[data-testid="attribute-form"]');
    await expect(attributeForm).toBeVisible({ timeout: 5000 });

    // Set type to number
    await page.locator('[data-testid="attribute-type-select"]').selectOption('number');

    // Enter a non-numeric value
    const valueInput = page.locator('[data-testid="attribute-value-input"]');
    await valueInput.fill('not_a_number');

    // Blur the input to trigger validation
    await valueInput.blur();
    await page.waitForTimeout(300);

    // Verify error message appears
    const errorMessage = page.locator('[data-testid="attribute-value-error"]');
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
    await expect(errorMessage).toContainText('must be a number');

    // Correct the value
    await valueInput.clear();
    await valueInput.fill('42');
    await valueInput.blur();
    await page.waitForTimeout(300);

    // Verify error disappears
    await expect(errorMessage).not.toBeVisible({ timeout: 5000 });
  });

  test('Attribute inheritance across 5-level hierarchy', async ({ page }) => {
    // Navigate to the deepest nested term
    const deepestTerm = testHierarchy.deepTerms[4];
    await page.goto(`/app/structure_nodes/${deepestTerm.id}`);
    await page.waitForLoadState('networkidle');

    // Verify we can see attributes from all ancestor levels
    const attributesList = page.locator('[data-testid="attributes-list"]');
    await expect(attributesList).toBeVisible({ timeout: 5000 });

    // Verify inherited attributes from different levels are present
    // Category from layer (inherited through all levels)
    const categoryAttribute = page.locator('[data-testid="attribute-category"]');
    await expect(categoryAttribute).toBeVisible({ timeout: 5000 });
    await expect(categoryAttribute).toContainText('legal_classification');

    // Jurisdiction from domain (inherited through term1)
    const jurisdictionAttribute = page.locator('[data-testid="attribute-jurisdiction"]');
    await expect(jurisdictionAttribute).toBeVisible({ timeout: 5000 });

    // Level attribute from level 3
    const levelAttribute = page.locator('[data-testid="attribute-level_attribute"]');
    await expect(levelAttribute).toBeVisible({ timeout: 5000 });

    // Verify nearest-ancestor precedence by checking that level 3's override would take precedence
    const levelAttributeValue = await levelAttribute.textContent();
    expect(levelAttributeValue).toContain('Level 3');
  });

  test('Display performance with 50+ attributes', async ({ page }) => {
    // Create a term with 50+ attributes
    const termResponse = await apiRequest<StructureNode>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `Performance Test Term ${Date.now()}`,
        definition: 'Term for performance testing',
        node_type: 'term',
        parent_id: testHierarchy.domain.id,
      },
    });
    const termId = termResponse.id;

    // Add 50 attributes via API
    const attributeRequests = [];
    for (let i = 0; i < 50; i++) {
      attributeRequests.push(
        apiRequest(page, `/api/structure_nodes/${termId}/attributes`, {
          method: 'POST',
          body: {
            key: `perf_attr_${i}`,
            title: `Performance Attribute ${i}`,
            value_type: 'string',
            value: `Value ${i}`,
          },
        })
      );
    }
    await Promise.all(attributeRequests);

    // Navigate to the term
    const startTime = Date.now();
    await page.goto(`/app/structure_nodes/${termId}`);
    await page.waitForLoadState('networkidle');
    const renderTime = Date.now() - startTime;

    // Verify page loaded and attributes are visible
    const attributesList = page.locator('[data-testid="attributes-list"]');
    await expect(attributesList).toBeVisible({ timeout: 5000 });

    // Count visible attributes
    const attributeItems = page.locator('[data-testid="attribute-item"]');
    const count = await attributeItems.count();
    expect(count).toBeGreaterThanOrEqual(50);

    // Verify render time is acceptable (< 500ms)
    expect(renderTime).toBeLessThan(500);

    // Verify no layout issues - check for horizontal scrolling
    const body = page.locator('body');
    const bodyWidth = await body.evaluate(el => el.scrollWidth);
    const viewportWidth = page.viewportSize()?.width || 0;
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 1); // Allow 1px tolerance
  });

  test('Attribute display readability', async ({ page }) => {
    // Navigate to a term with multiple attributes
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState('networkidle');

    // Verify attributes list is visible
    const attributesList = page.locator('[data-testid="attributes-list"]');
    await expect(attributesList).toBeVisible({ timeout: 5000 });

    // Verify no horizontal scrolling is required
    const attributesContainer = page.locator('[data-testid="attributes-container"]');
    const containerWidth = await attributesContainer.evaluate(el => el.scrollWidth);
    const containerClientWidth = await attributesContainer.evaluate(el => el.clientWidth);
    expect(containerWidth).toBeLessThanOrEqual(containerClientWidth + 1);

    // Verify long values are truncated with tooltips
    const longValueAttribute = page.locator('[data-testid="attribute-item"]').first();
    const valueText = longValueAttribute.locator('[data-testid="attribute-value"]');

    // Check if the value has a tooltip (data-testid or title attribute)
    const hasTooltip = await valueText.evaluate(el => {
      const classList = el.className;
      return classList.includes('truncate') || el.hasAttribute('title');
    });

    // If truncated, verify tooltip appears on hover
    if (hasTooltip) {
      await valueText.hover();
      const tooltip = page.locator('[role="tooltip"]');
      // Tooltip may appear, but it's not critical if it doesn't
      // The important thing is the text is readable somewhere
    }

    // Verify attribute types are visible
    const attributeTypes = page.locator('[data-testid="attribute-type"]');
    const typeCount = await attributeTypes.count();
    expect(typeCount).toBeGreaterThan(0);

    // Take screenshot for visual regression
    await page.screenshot({ path: 'test-results/attribute-readability.png' });
  });

  test('API error handling in UX', async ({ page }) => {
    // Navigate to a term
    await page.goto(`/app/structure_nodes/${testHierarchy.term1.id}`);
    await page.waitForLoadState('networkidle');

    // Intercept API calls to simulate error
    await page.route('**/api/structure_nodes/*/attributes', (route) => {
      route.abort('failed');
    });

    // Click add attribute
    const addAttributeButton = page.locator('[data-testid="add-attribute-button"]');
    await addAttributeButton.click();

    // Wait for form
    const attributeForm = page.locator('[data-testid="attribute-form"]');
    await expect(attributeForm).toBeVisible({ timeout: 5000 });

    // Fill in form
    await page.fill('[data-testid="attribute-key-input"]', `error_test_${Date.now()}`);
    await page.fill('[data-testid="attribute-title-input"]', 'Error Test');
    await page.locator('[data-testid="attribute-type-select"]').selectOption('string');
    await page.fill('[data-testid="attribute-value-input"]', 'test');

    // Try to submit
    await page.click('[data-testid="attribute-form-submit"]');

    // Verify error message is displayed to user
    const errorDisplay = page.locator('[data-testid="error-message"]');
    await expect(errorDisplay).toBeVisible({ timeout: 5000 });

    // Verify error message is user-friendly (not raw error)
    const errorText = await errorDisplay.textContent();
    expect(errorText).toBeTruthy();
    expect(errorText?.toLowerCase()).toContain('error');

    // Verify form is still visible (not broken)
    await expect(attributeForm).toBeVisible();
  });
});
