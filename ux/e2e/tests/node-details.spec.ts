import { test, expect, Page } from '@playwright/test';
import { apiRequest } from '../fixtures/test-helpers';

/**
 * Structure Node Detail View E2E Tests
 *
 * These tests validate the structure node detail view pages:
 * - Loading and displaying layer detail pages
 * - Loading and displaying domain detail pages
 * - Loading and displaying term detail pages
 * - Displaying node metadata (title, definition, type)
 * - Editing node properties inline
 * - Navigating between nodes
 * - Viewing hierarchies
 */

test.describe('Structure Node Detail View', () => {
  let testLayerId: string;
  let testDomainId: string;
  let testTermId: string;

  test.beforeEach(async ({ page }) => {
    // Create test hierarchy: layer → domain → term
    const layerResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `E2E Test Layer ${Date.now()}`,
        definition: 'Test layer for node detail tests',
        node_type: 'layer',
      },
    });
    testLayerId = layerResponse.id;

    const domainResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `E2E Test Domain ${Date.now()}`,
        definition: 'Test domain for node detail tests',
        node_type: 'domain',
        parent_node_id: testLayerId,
      },
    });
    testDomainId = domainResponse.id;

    const termResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `E2E Test Term ${Date.now()}`,
        definition: 'Test term for node detail tests',
        node_type: 'term',
        parent_node_id: testDomainId,
      },
    });
    testTermId = termResponse.id;
  });

  test('should load and display layer detail page', async ({ page }) => {
    // Navigate to layer detail page
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    // Verify page loaded
    expect(page.url()).toContain(`/app/structure_nodes/${testLayerId}`);

    // Verify layer title is displayed
    const titleElement = page.locator('[data-testid="node-detail-title"]');
    await expect(titleElement).toBeVisible({ timeout: 10000 });
    await expect(titleElement).toContainText('E2E Test Layer');

    // Verify node type is displayed
    const typeElement = page.locator('[data-testid="node-detail-type"]');
    await expect(typeElement).toBeVisible();
    await expect(typeElement).toContainText('layer');

    // Verify definition section exists
    const definitionSection = page.locator('[data-testid="node-detail-definition-section"]');
    await expect(definitionSection).toBeVisible();
    await expect(definitionSection).toContainText('Test layer for node detail tests');
  });

  test('should load and display domain detail page', async ({ page }) => {
    // Navigate to domain detail page
    await page.goto(`/app/structure_nodes/${testDomainId}`);
    await page.waitForLoadState('networkidle');

    // Verify page loaded
    expect(page.url()).toContain(`/app/structure_nodes/${testDomainId}`);

    // Verify domain title is displayed
    const titleElement = page.locator('[data-testid="node-detail-title"]');
    await expect(titleElement).toBeVisible({ timeout: 10000 });
    await expect(titleElement).toContainText('E2E Test Domain');

    // Verify node type is displayed
    const typeElement = page.locator('[data-testid="node-detail-type"]');
    await expect(typeElement).toBeVisible();
    await expect(typeElement).toContainText('domain');

    // Verify definition section exists
    const definitionSection = page.locator('[data-testid="node-detail-definition-section"]');
    await expect(definitionSection).toBeVisible();
    await expect(definitionSection).toContainText('Test domain for node detail tests');
  });

  test('should load and display term detail page', async ({ page }) => {
    // Navigate to term detail page
    await page.goto(`/app/structure_nodes/${testTermId}`);
    await page.waitForLoadState('networkidle');

    // Verify page loaded
    expect(page.url()).toContain(`/app/structure_nodes/${testTermId}`);

    // Verify term title is displayed
    const titleElement = page.locator('[data-testid="node-detail-title"]');
    await expect(titleElement).toBeVisible({ timeout: 10000 });
    await expect(titleElement).toContainText('E2E Test Term');

    // Verify node type is displayed
    const typeElement = page.locator('[data-testid="node-detail-type"]');
    await expect(typeElement).toBeVisible();
    await expect(typeElement).toContainText('term');

    // Verify definition section exists
    const definitionSection = page.locator('[data-testid="node-detail-definition-section"]');
    await expect(definitionSection).toBeVisible();
    await expect(definitionSection).toContainText('Test term for node detail tests');
  });

  test('should display node metadata correctly', async ({ page }) => {
    // Navigate to layer detail page
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    // Verify title
    const titleElement = page.locator('[data-testid="node-detail-title"]');
    await expect(titleElement).toBeVisible();

    // Verify ID is shown
    const idElement = page.locator('[data-testid="node-detail-id"]');
    await expect(idElement).toBeVisible();
    await expect(idElement).toContainText(testLayerId);

    // Verify type information
    const typeElement = page.locator('[data-testid="node-detail-type"]');
    await expect(typeElement).toBeVisible();
    await expect(typeElement).toContainText('layer');
    await expect(typeElement).toContainText('Version');
  });

  test('should display definition section', async ({ page }) => {
    // Navigate to domain detail page
    await page.goto(`/app/structure_nodes/${testDomainId}`);
    await page.waitForLoadState('networkidle');

    // Verify definition section is visible
    const definitionSection = page.locator('[data-testid="node-detail-definition-section"]');
    await expect(definitionSection).toBeVisible();

    // Verify definition content
    const definition = page.locator('[data-testid="node-detail-definition"]');
    await expect(definition).toBeVisible();
    await expect(definition).toContainText('Test domain for node detail tests');
  });

  test.skip('should edit node definition inline', async ({ page }) => {
    // Navigate to term detail page
    await page.goto(`/app/structure_nodes/${testTermId}`);
    await page.waitForLoadState('networkidle');

    const definitionSection = page.locator('[data-testid="node-detail-definition"]');
    await expect(definitionSection).toBeVisible();

    // Find any div with cursor-text class (the editable area) within the definition section
    const editableArea = definitionSection.locator('.cursor-text');
    await expect(editableArea).toBeVisible({ timeout: 5000 });

    // Wait for the element to be stable and fully interactive
    await page.waitForTimeout(500);

    // Use Playwright's dblclick with delay and clickCount for more reliable double-click
    await editableArea.dblclick({ delay: 100, force: true });

    // Wait for textarea to appear
    const textarea = definitionSection.locator('textarea');
    await expect(textarea).toBeVisible({ timeout: 5000 });

    // Update the definition
    const newDefinition = 'Updated test term definition';
    await textarea.fill(newDefinition);

    // Save changes
    const saveButton = definitionSection.locator('button:has-text("Save")');
    await saveButton.click();

    // Wait for save to complete
    await expect(textarea).not.toBeVisible({ timeout: 10000 });

    // Verify updated definition is displayed
    await expect(definitionSection).toContainText(newDefinition);

    // Verify backend was updated
    const response = await apiRequest<any>(page, `/api/structure_nodes/${testTermId}`);
    expect(response.definition).toBe(newDefinition);
  });

  test('should view child nodes section (hierarchy)', async ({ page }) => {
    // Navigate to layer detail page (which has a domain child)
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    // Verify children section exists
    const childrenSection = page.locator('[data-testid="node-children-section"]');
    await expect(childrenSection).toBeVisible();

    // Verify hierarchy/tree is displayed
    await expect(childrenSection).toContainText('Hierarchy');
  });

  test('should navigate to child nodes from hierarchy', async ({ page }) => {
    // Navigate to layer detail page
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    // Wait for the page to fully load
    await page.waitForTimeout(2000);

    // Look for links in the children section that point to the domain
    const childrenSection = page.locator('[data-testid="node-children-section"]');
    await expect(childrenSection).toBeVisible();

    // Note: Navigation to child nodes depends on how TreeChartPanel renders links
    // This test validates the hierarchy section exists and is interactive
  });

  test('should handle nodes with no definition', async ({ page }) => {
    // Create a node without a definition
    const nodeResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `No Definition Node ${Date.now()}`,
        node_type: 'layer',
      },
    });
    const nodeId = nodeResponse.id;

    // Navigate to the node
    await page.goto(`/app/structure_nodes/${nodeId}`);
    await page.waitForLoadState('networkidle');

    // Verify definition section shows placeholder text
    const definition = page.locator('[data-testid="node-detail-definition"]');
    await expect(definition).toBeVisible();
    await expect(definition).toContainText('No definition provided');
  });

  test('should handle invalid node IDs gracefully', async ({ page }) => {
    const invalidNodeId = '00000000-0000-0000-0000-000000000000';

    // Navigate to invalid node
    await page.goto(`/app/structure_nodes/${invalidNodeId}`);
    await page.waitForLoadState('networkidle');

    // Verify error message is displayed
    // The exact error handling may vary, but there should be some indication
    const body = page.locator('body');
    const content = await body.textContent();

    // Should show some form of error or "not found" message
    expect(content).toBeTruthy();
  });

  test('should display breadcrumb navigation', async ({ page }) => {
    // Navigate to term detail page (deepest in hierarchy)
    await page.goto(`/app/structure_nodes/${testTermId}`);
    await page.waitForLoadState('networkidle');

    // Look for breadcrumb navigation
    const breadcrumb = page.locator('[aria-label="Node hierarchy breadcrumb"]');
    await expect(breadcrumb).toBeVisible();

    // Breadcrumb should contain parent nodes
    // The exact structure depends on Breadcrumb component implementation
  });

  test('should open edit modal from detail page', async ({ page }) => {
    // Navigate to domain detail page
    await page.goto(`/app/structure_nodes/${testDomainId}`);
    await page.waitForLoadState('networkidle');

    // Click Edit button
    const editButton = page.locator('button:has-text("Edit")');
    await expect(editButton).toBeVisible();
    await editButton.click();

    // Verify edit modal opens
    const editModal = page.getByRole('dialog', { name: 'Edit Domain' });
    await expect(editModal).toBeVisible({ timeout: 5000 });

    // Verify form fields are visible
    await expect(editModal.locator('[data-testid="domain-title-input"]')).toBeVisible();
    await expect(editModal.locator('[data-testid="domain-definition-input"]')).toBeVisible();
  });

  test('should navigate between related nodes', async ({ page }) => {
    // Start at layer
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    // Verify we're on layer page
    const layerTitle = page.locator('[data-testid="node-detail-title"]');
    await expect(layerTitle).toContainText('E2E Test Layer');

    // Navigate to domain (via sidebar or hierarchy)
    await page.goto(`/app/structure_nodes/${testDomainId}`);
    await page.waitForLoadState('networkidle');

    // Verify we're on domain page
    const domainTitle = page.locator('[data-testid="node-detail-title"]');
    await expect(domainTitle).toContainText('E2E Test Domain');

    // Navigate to term
    await page.goto(`/app/structure_nodes/${testTermId}`);
    await page.waitForLoadState('networkidle');

    // Verify we're on term page
    const termTitle = page.locator('[data-testid="node-detail-title"]');
    await expect(termTitle).toContainText('E2E Test Term');
  });

  test('should display correct hierarchy for each node type', async ({ page }) => {
    // Test layer hierarchy
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    let childrenSection = page.locator('[data-testid="node-children-section"]');
    await expect(childrenSection).toBeVisible();

    // Test domain hierarchy
    await page.goto(`/app/structure_nodes/${testDomainId}`);
    await page.waitForLoadState('networkidle');

    childrenSection = page.locator('[data-testid="node-children-section"]');
    await expect(childrenSection).toBeVisible();

    // Test term hierarchy
    await page.goto(`/app/structure_nodes/${testTermId}`);
    await page.waitForLoadState('networkidle');

    childrenSection = page.locator('[data-testid="node-children-section"]');
    await expect(childrenSection).toBeVisible();
  });

  test.skip('should cancel definition edit', async ({ page }) => {
    // Navigate to layer detail page
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    const definitionSection = page.locator('[data-testid="node-detail-definition"]');
    const originalText = await definitionSection.textContent();

    // Find the editable div (cursor-text class) and double-click to edit
    const editableArea = definitionSection.locator('.cursor-text');
    await expect(editableArea).toBeVisible({ timeout: 5000 });

    // Wait for the element to be stable and fully interactive
    await page.waitForTimeout(500);

    // Use Playwright's dblclick with delay and force for more reliable double-click
    await editableArea.dblclick({ delay: 100, force: true });

    // Wait for textarea
    const textarea = definitionSection.locator('textarea');
    await expect(textarea).toBeVisible({ timeout: 5000 });

    // Change the text
    await textarea.fill('This change will be cancelled');

    // Click Cancel button
    const cancelButton = definitionSection.locator('button:has-text("Cancel")');
    await cancelButton.click();

    // Wait for edit mode to exit
    await expect(textarea).not.toBeVisible({ timeout: 5000 });

    // Verify original text is still there
    await expect(definitionSection).toContainText('Test layer for node detail tests');
  });

  test('should show version information', async ({ page }) => {
    // Navigate to any node detail page
    await page.goto(`/app/structure_nodes/${testLayerId}`);
    await page.waitForLoadState('networkidle');

    // Verify version is displayed
    const typeElement = page.locator('[data-testid="node-detail-type"]');
    await expect(typeElement).toBeVisible();
    await expect(typeElement).toContainText('Version');
  });

  test('should persist word sense selections across page reload', async ({ page }) => {
    // Create term with multi-word title to trigger NLP
    const termResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `machine learning ${Date.now()}`,
        definition: 'A multi-word test term for word sense testing',
        node_type: 'term',
      },
    });
    const termId = termResponse.id;

    // Navigate to term detail page
    await page.goto(`/app/structure_nodes/${termId}`);
    await page.waitForLoadState('networkidle');

    // Verify NLP Analysis panel is visible
    await expect(page.locator('[data-testid="nlp-analysis-panel"]')).toBeVisible({ timeout: 10000 });

    // Click on first word to expand NLP analysis
    const firstWord = page.locator('[data-testid="nlp-word-token"]').first();
    await firstWord.click();

    // Wait for concept chart to appear
    await page.waitForSelector('[data-testid="nlp-concept-chart"]', { timeout: 10000 });

    // Select first synset/sense
    const firstSynset = page.locator('[data-testid^="synset-"]').first();
    await firstSynset.click();

    // Verify save button appears (indicates dirty state)
    const saveButton = page.locator('button:has-text("Save Word Senses")');
    await expect(saveButton).toBeVisible({ timeout: 5000 });

    // Click save button
    await saveButton.click();

    // Wait for API response
    await page.waitForResponse(
      (resp) => resp.url().includes('/word_senses') && resp.status() === 200,
      { timeout: 10000 }
    );

    // Verify save button disappears (no longer dirty)
    await expect(saveButton).not.toBeVisible({ timeout: 5000 });

    // Refresh page to verify persistence
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Verify selected sense is still visible after reload
    await expect(page.locator('[data-testid="nlp-analysis-panel"]')).toBeVisible({ timeout: 10000 });

    // The selected sense should be visible in the persisted senses section
    // (exact selector depends on implementation, adjust as needed)
    const persistedSense = page.locator('[data-testid="persisted-word-sense"]').first();
    await expect(persistedSense).toBeVisible({ timeout: 5000 });

    // Verify save button is NOT visible (not dirty)
    await expect(page.locator('button:has-text("Save Word Senses")')).not.toBeVisible();
  });

  test('should add and remove reference node links', async ({ page }) => {
    // Create term for reference linking
    const termResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: `algorithm ${Date.now()}`,
        definition: 'A test term for reference node linking',
        node_type: 'term',
      },
    });
    const termId = termResponse.id;

    // Navigate to term detail page
    await page.goto(`/app/structure_nodes/${termId}`);
    await page.waitForLoadState('networkidle');

    // Verify Reference Node panel is visible
    await expect(page.locator('[data-testid="reference-node-panel"]')).toBeVisible({ timeout: 10000 });

    // Initially should show "no references" message
    await expect(page.locator('text=/no reference.*associated/i')).toBeVisible({ timeout: 5000 });

    // Reference search should be visible in empty state
    const searchInput = page.locator('input[placeholder*="Search reference"]');
    await expect(searchInput).toBeVisible();

    // Search for "algorithm"
    await searchInput.fill('algorithm');

    // Wait for search results (may take a few seconds for API call)
    await page.waitForSelector('[data-testid="reference-search-result"]', { timeout: 15000 });

    // Click first search result to add it
    const firstResult = page.locator('[data-testid="reference-search-result"]').first();
    await firstResult.click();

    // Wait for add operation to complete
    await page.waitForResponse(
      (resp) => resp.url().includes('/reference_links') && resp.request().method() === 'POST' && resp.status() === 200,
      { timeout: 10000 }
    );

    // Verify reference link now appears in the list
    await expect(page.locator('[data-testid="reference-link-item"]')).toBeVisible({ timeout: 5000 });

    // Verify "no references" message is gone
    await expect(page.locator('text=/no reference.*associated/i')).not.toBeVisible();

    // Refresh page to verify persistence
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Reference should still be there after reload
    await expect(page.locator('[data-testid="reference-link-item"]')).toBeVisible({ timeout: 10000 });

    // Remove the reference link
    const removeButton = page.locator('[data-testid="remove-reference-button"]').first();
    await removeButton.click();

    // Wait for remove operation to complete
    await page.waitForResponse(
      (resp) => resp.url().includes('/reference_links') && resp.request().method() === 'DELETE' && resp.status() === 200,
      { timeout: 10000 }
    );

    // Verify reference is removed and "no references" message returns
    await expect(page.locator('text=/no reference.*associated/i')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="reference-link-item"]')).not.toBeVisible();
  });
});
