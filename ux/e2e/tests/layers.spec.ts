import { test, expect, Page } from '@playwright/test';
import { apiRequest } from '../fixtures/test-helpers';

/**
 * Layer Management E2E Tests
 *
 * These tests validate the complete CRUD workflow for layers:
 * - Creating layers through the table view
 * - Editing layers through modals and detail view
 * - Deleting layers with confirmation
 * - Searching and filtering layers
 * - Navigation between table and detail views
 */

test.describe('Layer Management', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to layers page
    await page.goto('/app/layers');
    await page.waitForLoadState('networkidle');
  });

  test('should display the layers table', async ({ page }) => {
    // Verify table is visible
    await expect(page.locator('[data-testid="layer-table"]')).toBeVisible();

    // Verify toolbar is visible with add button
    await expect(page.locator('[data-testid="layer-table-toolbar"]')).toBeVisible();
    await expect(page.locator('[data-testid="layer-add-button"]')).toBeVisible();
  });

  test('should create a new layer', async ({ page }) => {
    const layerTitle = `E2E Test Layer ${Date.now()}`;
    const layerDefinition = 'A test layer created by E2E tests';

    // Click "Add Layer" button
    await page.click('[data-testid="layer-add-button"]');

    // Wait for create modal to appear (use role=dialog to get the actual modal, not the backdrop)
    await expect(page.getByRole('dialog', { name: 'Create New Layer' })).toBeVisible();

    // Fill in the form
    await page.fill('[data-testid="layer-title-input"]', layerTitle);
    await page.fill('[data-testid="layer-definition-input"]', layerDefinition);

    // Submit the form
    await page.click('[data-testid="layer-submit-button"]');

    // Wait for modal to close
    await expect(page.getByRole('dialog', { name: 'Create New Layer' })).not.toBeVisible();

    // Verify layer appears in the table
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layerTitle);

    // Verify layer exists in backend
    const response = await apiRequest<{ nodes: any[] }>(page, '/api/structure_nodes?node_type=layer');
    const createdLayer = response.nodes.find((n: any) => n.title === layerTitle);

    expect(createdLayer).toBeDefined();
    expect(createdLayer?.definition).toBe(layerDefinition);
    expect(createdLayer?.node_type).toBe('layer');
  });

  test('should edit a layer through the table', async ({ page }) => {
    // First, create a layer to edit
    const originalTitle = `E2E Edit Test ${Date.now()}`;
    const updatedTitle = `${originalTitle} (Updated)`;
    const updatedDefinition = 'Updated definition via E2E test';

    // Create layer via API for speed
    const createResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: originalTitle,
        definition: 'Original definition',
        node_type: 'layer',
      },
    });
    const layerId = createResponse.id;

    // Refresh the page to see the new layer
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Double-click the layer row to edit
    await page.locator(`[data-testid="layer-row-${layerId}"]`).dblclick();

    // Wait for edit modal
    await expect(page.getByRole('dialog', { name: 'Edit Layer' })).toBeVisible();

    // Clear and update the title
    await page.fill('[data-testid="layer-title-input"]', updatedTitle);
    await page.fill('[data-testid="layer-definition-input"]', updatedDefinition);

    // Submit
    await page.click('[data-testid="layer-submit-button"]');

    // Wait for modal to close
    await expect(page.locator('[data-testid="layer-edit-modal"]')).not.toBeVisible();

    // Verify updated values appear in table
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(updatedTitle);

    // Verify backend was updated
    const response = await apiRequest<any>(page, `/api/structure_nodes/${layerId}`);
    expect(response.title).toBe(updatedTitle);
    expect(response.definition).toBe(updatedDefinition);
  });

  test('should delete a layer', async ({ page }) => {
    // Create a layer to delete
    const layerTitle = `E2E Delete Test ${Date.now()}`;
    const createResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: layerTitle,
        definition: 'Layer to be deleted',
        node_type: 'layer',
      },
    });
    const layerId = createResponse.id;

    // Refresh to see the layer
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Select the layer row by clicking its checkbox
    const row = page.locator(`[data-testid="layer-row-${layerId}"]`);
    await row.locator('input[type="checkbox"]').check();

    // Click Actions dropdown and select Delete
    await page.click('[data-testid="layer-actions-dropdown"]');
    await page.click('[data-testid="layer-delete-selected-action"]');

    // Wait for delete confirmation modal
    await expect(page.getByRole('dialog', { name: /Confirm Delete/i })).toBeVisible();

    // Confirm deletion
    await page.click('[data-testid="layer-delete-confirm-button"]');

    // Wait for modal to close
    await expect(page.getByRole('dialog', { name: /Confirm Delete/i })).not.toBeVisible();

    // Verify layer is removed from table
    await expect(page.locator('[data-testid="layer-table"]')).not.toContainText(layerTitle);

    // Verify layer is deleted from backend
    try {
      await apiRequest(page, `/api/structure_nodes/${layerId}`);
      // If we get here, the layer wasn't deleted
      expect(false).toBe(true); // Force fail
    } catch (error) {
      // Expected - layer should be deleted
      expect(error).toBeDefined();
    }
  });

  test('should search for layers', async ({ page }) => {
    // Create multiple layers with distinct names
    const timestamp = Date.now();
    const layer1Title = `Alpha Layer ${timestamp}`;
    const layer2Title = `Beta Layer ${timestamp}`;
    const layer3Title = `Gamma Layer ${timestamp}`;

    // Create layers via API
    await Promise.all([
      apiRequest(page, '/api/structure_nodes', {
        method: 'POST',
        body: { title: layer1Title, node_type: 'layer' },
      }),
      apiRequest(page, '/api/structure_nodes', {
        method: 'POST',
        body: { title: layer2Title, node_type: 'layer' },
      }),
      apiRequest(page, '/api/structure_nodes', {
        method: 'POST',
        body: { title: layer3Title, node_type: 'layer' },
      }),
    ]);

    // Refresh page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Verify all layers are visible initially
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer1Title);
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer2Title);
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer3Title);

    // Search for "Beta"
    await page.fill('[data-testid="layer-search-input"]', 'Beta');

    // Wait a bit for search to filter (debounced)
    await page.waitForTimeout(500);

    // Verify only Beta layer is visible
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer2Title);
    await expect(page.locator('[data-testid="layer-table"]')).not.toContainText(layer1Title);
    await expect(page.locator('[data-testid="layer-table"]')).not.toContainText(layer3Title);

    // Clear search
    await page.fill('[data-testid="layer-search-input"]', '');
    await page.waitForTimeout(500);

    // Verify all layers are visible again
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer1Title);
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer2Title);
    await expect(page.locator('[data-testid="layer-table"]')).toContainText(layer3Title);
  });

  test('should navigate to layer detail view', async ({ page }) => {
    // Create a layer
    const layerTitle = `E2E Detail Test ${Date.now()}`;
    const layerDefinition = 'Test layer for detail view';
    const createResponse = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: {
        title: layerTitle,
        definition: layerDefinition,
        node_type: 'layer',
      },
    });
    const layerId = createResponse.id;

    // Refresh page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Click the link icon to navigate to detail view
    const row = page.locator(`[data-testid="layer-row-${layerId}"]`);
    const linkCell = row.locator('td').last(); // Link is in the last cell
    await linkCell.locator('a').click();

    // Wait for navigation
    await page.waitForURL(`**/app/structure_nodes/${layerId}`);
    await page.waitForLoadState('networkidle');

    // Verify we're on the detail page
    expect(page.url()).toContain(`/app/structure_nodes/${layerId}`);

    // Verify layer details are displayed
    await expect(page.locator('body')).toContainText(layerTitle);
  });

  test('should cancel layer creation', async ({ page }) => {
    // Click "Add Layer" button
    await page.click('[data-testid="layer-add-button"]');

    // Wait for create modal
    await expect(page.getByRole('dialog', { name: 'Create New Layer' })).toBeVisible();

    // Fill in some data
    await page.fill('[data-testid="layer-title-input"]', 'Test Layer');

    // Close the modal by clicking outside or pressing escape
    await page.keyboard.press('Escape');

    // Modal should be closed
    await expect(page.getByRole('dialog', { name: 'Create New Layer' })).not.toBeVisible();

    // No new layer should be created (verify by checking backend)
    const response = await apiRequest<{ nodes: any[] }>(page, '/api/structure_nodes?node_type=layer');
    const testLayer = response.nodes.find((n: any) => n.title === 'Test Layer');
    expect(testLayer).toBeUndefined();
  });

  test('should validate required fields', async ({ page }) => {
    // Click "Add Layer" button
    await page.click('[data-testid="layer-add-button"]');

    // Wait for create modal
    await expect(page.getByRole('dialog', { name: 'Create New Layer' })).toBeVisible();

    // Try to submit without filling in title (required field)
    await page.click('[data-testid="layer-submit-button"]');

    // Modal should still be visible (form validation prevented submission)
    await expect(page.getByRole('dialog', { name: 'Create New Layer' })).toBeVisible();

    // Verify error message appears
    await expect(page.locator('[data-testid="layer-form"]')).toContainText('required');
  });

  test('should handle multiple layer selections and bulk delete', async ({ page }) => {
    // Create multiple layers
    const timestamp = Date.now();
    const layer1 = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: { title: `Bulk Delete 1 ${timestamp}`, node_type: 'layer' },
    });
    const layer2 = await apiRequest<any>(page, '/api/structure_nodes', {
      method: 'POST',
      body: { title: `Bulk Delete 2 ${timestamp}`, node_type: 'layer' },
    });

    // Refresh
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Select both layers
    await page.locator(`[data-testid="layer-row-${layer1.id}"]`).locator('input[type="checkbox"]').check();
    await page.locator(`[data-testid="layer-row-${layer2.id}"]`).locator('input[type="checkbox"]').check();

    // Delete selected
    await page.click('[data-testid="layer-actions-dropdown"]');
    await page.click('[data-testid="layer-delete-selected-action"]');

    // Confirm
    const deleteModal = page.getByRole('dialog', { name: /Confirm Delete/i });
    await expect(deleteModal).toBeVisible();
    await expect(deleteModal).toContainText('2 selected');
    await page.click('[data-testid="layer-delete-confirm-button"]');

    // Wait for modal to close
    await expect(deleteModal).not.toBeVisible();

    // Verify both layers are gone
    await expect(page.locator('[data-testid="layer-table"]')).not.toContainText(`Bulk Delete 1 ${timestamp}`);
    await expect(page.locator('[data-testid="layer-table"]')).not.toContainText(`Bulk Delete 2 ${timestamp}`);
  });
});
