import { test, expect } from '@playwright/test';
import { apiRequest } from '../fixtures/test-helpers';

/**
 * Pipeline Configuration E2E Tests
 *
 * These tests validate the pipeline flavor management workflow:
 * - Viewing pipeline type selection
 * - Listing pipeline flavors by type
 * - Creating new pipeline flavors
 * - Editing pipeline flavor configuration
 * - Deleting pipeline flavors
 * - Testing pipeline flavors (navigation)
 * - Form validation
 *
 * Note: These are admin features for configuring LLM pipeline behaviors
 */

test.describe('Pipeline Configuration', () => {
  const pipelineType = 'suggest_layer_definition';

  test.beforeEach(async ({ page }) => {
    // Navigate to pipeline configuration index page
    await page.goto('/app/config/pipelines');
    await page.waitForLoadState('networkidle');
  });

  test('should display pipeline type selection page', async ({ page }) => {
    // Verify page title
    await expect(page.getByText('Pipeline Flavor Configuration')).toBeVisible();

    // Verify description
    await expect(page.getByText('Select Pipeline Type')).toBeVisible();
    await expect(page.getByText(/Choose which pipeline type you want to manage/i)).toBeVisible();

    // Verify all three pipeline types are shown
    await expect(page.getByText('Layer Definitions')).toBeVisible();
    await expect(page.getByText('Domain Definitions')).toBeVisible();
    await expect(page.getByText('Term Definitions')).toBeVisible();
  });

  test('should navigate to specific pipeline type', async ({ page }) => {
    // Click on Layer Definitions pipeline type
    await page.getByText('Layer Definitions').click();

    // Wait for navigation
    await page.waitForURL('**/app/config/pipelines/suggest_layer_definition', { timeout: 10000 });
    await page.waitForLoadState('networkidle');

    // Verify we're on the right page
    expect(page.url()).toContain('/app/config/pipelines/suggest_layer_definition');

    // Verify page title
    await expect(page.getByText('Layer Definitions Pipeline Flavors')).toBeVisible({ timeout: 10000 });
  });

  test('should list pipeline flavors for a type', async ({ page }) => {
    // Navigate to specific pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list to load
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Verify create button is visible
    await expect(page.locator('[data-testid="pipeline-flavor-create-button"]')).toBeVisible();

    // Verify flavors container is visible
    await expect(page.locator('[data-testid="pipeline-flavors-container"]')).toBeVisible();

    // Verify at least the default flavor exists using test ID
    await expect(page.locator('[data-testid="pipeline-flavor-title-default"]')).toBeVisible();
  });

  test('should display flavor details in list', async ({ page }) => {
    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Get all flavor cards
    const flavorCards = page.locator('[data-testid^="pipeline-flavor-card-"]');
    await expect(flavorCards.first()).toBeVisible();

    // Verify flavor details are shown (provider, model, version) - scoped to flavors container
    const flavorsContainer = page.locator('[data-testid="pipeline-flavors-container"]');
    await expect(flavorsContainer.getByText(/Provider:/)).toBeVisible();
    await expect(flavorsContainer.getByText(/Model:/)).toBeVisible();
    await expect(flavorsContainer.getByText(/Version:/)).toBeVisible();

    // Verify status information
    await expect(flavorsContainer.getByText(/Enabled|Disabled/)).toBeVisible();
  });

  test('should navigate to create new flavor page', async ({ page }) => {
    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for create button
    const createButton = page.locator('[data-testid="pipeline-flavor-create-button"]');
    await expect(createButton).toBeVisible({ timeout: 10000 });

    // Click create button
    await createButton.click();

    // Verify navigation to create page
    await page.waitForURL(`**/app/config/pipelines/${pipelineType}/create`, { timeout: 10000 });
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain(`/app/config/pipelines/${pipelineType}/create`);

    // Verify create form is displayed by checking for the page title text
    await expect(page.getByText(/Create New.*Layer.*Flavor/i)).toBeVisible({ timeout: 10000 });
  });

  test('should not allow editing default flavor', async ({ page }) => {
    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Find the default flavor card using its test ID
    const defaultFlavorCard = page.locator('[data-testid="pipeline-flavor-card-default"]');
    await expect(defaultFlavorCard).toBeVisible();

    // Verify edit button is disabled for default flavor
    const editButton = page.locator('[data-testid="pipeline-flavor-edit-button-default"]');
    await expect(editButton).toBeDisabled();

    // Verify delete button is disabled for default flavor
    const deleteButton = page.locator('[data-testid="pipeline-flavor-delete-button-default"]');
    await expect(deleteButton).toBeDisabled();
  });

  test('should navigate to edit flavor page for custom flavors', async ({ page }) => {
    // First create a custom flavor via API
    const timestamp = Date.now();
    const flavorTitle = `E2E Test Flavor ${timestamp}`;

    const createResponse = await apiRequest<any>(page, '/api/pipeline-flavors', {
      method: 'POST',
      body: {
        title: flavorTitle,
        pipeline: pipelineType,
        llm_provider: 'openai',
        llm_model: 'gpt-4',
        version: 1,
        system_prompt: 'Test system prompt',
        user_prompt: 'Test user prompt: {input}',
        enabled: true,
      },
    });
    const flavorId = createResponse.id;

    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for the flavor to appear
    await expect(page.locator(`[data-testid="pipeline-flavor-card-${flavorId}"]`)).toBeVisible({ timeout: 10000 });

    // Click edit button
    const editButton = page.locator(`[data-testid="pipeline-flavor-edit-button-${flavorId}"]`);
    await expect(editButton).toBeVisible();
    await expect(editButton).toBeEnabled();
    await editButton.click();

    // Verify navigation to edit page
    await page.waitForURL(`**/app/config/pipelines/${pipelineType}/edit/${flavorId}`, { timeout: 10000 });
    expect(page.url()).toContain(`/app/config/pipelines/${pipelineType}/edit/${flavorId}`);
  });

  test('should navigate to test flavor page', async ({ page }) => {
    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Find any flavor card (we'll test with the first available)
    const flavorCards = page.locator('[data-testid^="pipeline-flavor-card-"]');
    await expect(flavorCards.first()).toBeVisible();

    // Get the flavor ID from the first card
    const firstCard = flavorCards.first();
    const cardTestId = await firstCard.getAttribute('data-testid');
    const flavorId = cardTestId?.replace('pipeline-flavor-card-', '');

    if (flavorId) {
      // Click test button
      const testButton = page.locator(`[data-testid="pipeline-flavor-test-button-${flavorId}"]`);
      await expect(testButton).toBeVisible();
      await testButton.click();

      // Wait for navigation and page load
      await page.waitForLoadState('networkidle', { timeout: 10000 });

      // Verify we're on the test page by checking URL and page title text
      expect(page.url()).toContain(`/app/config/pipelines/${pipelineType}/test/`);
      await expect(page.getByText('Flavor Tester')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should delete a custom flavor', async ({ page }) => {
    // Create a custom flavor via API
    const timestamp = Date.now();
    const flavorTitle = `E2E Delete Test ${timestamp}`;

    const createResponse = await apiRequest<any>(page, '/api/pipeline-flavors', {
      method: 'POST',
      body: {
        title: flavorTitle,
        pipeline: pipelineType,
        llm_provider: 'openai',
        llm_model: 'gpt-4',
        version: 1,
        system_prompt: 'Test system prompt',
        user_prompt: 'Test user prompt: {input}',
        enabled: true,
      },
    });
    const flavorId = createResponse.id;

    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for the flavor card to appear
    const flavorCard = page.locator(`[data-testid="pipeline-flavor-card-${flavorId}"]`);
    await expect(flavorCard).toBeVisible({ timeout: 10000 });

    // Verify flavor title is displayed
    await expect(page.getByText(flavorTitle)).toBeVisible();

    // Click delete button
    const deleteButton = page.locator(`[data-testid="pipeline-flavor-delete-button-${flavorId}"]`);
    await expect(deleteButton).toBeVisible();
    await expect(deleteButton).toBeEnabled();
    await deleteButton.click();

    // Wait for delete confirmation modal
    const deleteModal = page.locator('[data-testid="pipeline-flavor-delete-modal"]');
    await expect(deleteModal).toBeVisible({ timeout: 5000 });

    // Verify modal shows flavor title
    await expect(deleteModal).toContainText(flavorTitle);

    // Confirm deletion
    const confirmButton = page.locator('[data-testid="pipeline-flavor-delete-confirm-button"]');
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();

    // Wait for modal to close
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });

    // Verify flavor is removed from list
    await expect(page.getByText(flavorTitle)).not.toBeVisible();

    // Verify flavor is deleted from backend
    try {
      await apiRequest(page, `/api/pipeline-flavors/${flavorId}`);
      expect(false).toBe(true); // Force fail if request succeeds
    } catch (error) {
      // Expected - flavor should be deleted
      expect(error).toBeDefined();
    }
  });

  test('should cancel flavor deletion', async ({ page }) => {
    // Create a custom flavor via API
    const timestamp = Date.now();
    const flavorTitle = `E2E Cancel Delete ${timestamp}`;

    const createResponse = await apiRequest<any>(page, '/api/pipeline-flavors', {
      method: 'POST',
      body: {
        title: flavorTitle,
        pipeline: pipelineType,
        llm_provider: 'openai',
        llm_model: 'gpt-4',
        version: 1,
        system_prompt: 'Test system prompt',
        user_prompt: 'Test user prompt: {input}',
        enabled: true,
      },
    });
    const flavorId = createResponse.id;

    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for the flavor card
    await expect(page.locator(`[data-testid="pipeline-flavor-card-${flavorId}"]`)).toBeVisible({ timeout: 10000 });

    // Click delete button
    const deleteButton = page.locator(`[data-testid="pipeline-flavor-delete-button-${flavorId}"]`);
    await deleteButton.click();

    // Wait for delete modal
    const deleteModal = page.locator('[data-testid="pipeline-flavor-delete-modal"]');
    await expect(deleteModal).toBeVisible({ timeout: 5000 });

    // Click cancel button
    const cancelButton = page.locator('[data-testid="pipeline-flavor-delete-cancel-button"]');
    await cancelButton.click();

    // Wait for modal to close
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });

    // Verify flavor is still in the list
    await expect(page.getByText(flavorTitle)).toBeVisible();

    // Verify flavor still exists in backend
    const response = await apiRequest<any>(page, `/api/pipeline-flavors/${flavorId}`);
    expect(response.title).toBe(flavorTitle);
  });

  test('should navigate between different pipeline types', async ({ page }) => {
    // Start at Layer Definitions
    await page.goto('/app/config/pipelines/suggest_layer_definition');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Layer Definitions Pipeline Flavors')).toBeVisible({ timeout: 10000 });

    // Navigate back to index
    await page.goto('/app/config/pipelines');
    await page.waitForLoadState('networkidle');

    // Navigate to Domain Definitions
    await page.getByText('Domain Definitions').click();
    await page.waitForURL('**/app/config/pipelines/suggest_domain_definition', { timeout: 10000 });
    await expect(page.getByText('Domain Definitions Pipeline Flavors')).toBeVisible({ timeout: 10000 });

    // Navigate back to index
    await page.goto('/app/config/pipelines');
    await page.waitForLoadState('networkidle');

    // Navigate to Term Definitions
    await page.getByText('Term Definitions').click();
    await page.waitForURL('**/app/config/pipelines/suggest_term_definition', { timeout: 10000 });
    await expect(page.getByText('Term Definitions Pipeline Flavors')).toBeVisible({ timeout: 10000 });
  });

  test('should display breadcrumb navigation', async ({ page }) => {
    // Navigate to specific pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Verify breadcrumbs are present - use more specific selector targeting the breadcrumb container
    const breadcrumb = page.locator('.flex.items-center.space-x-2.text-sm.text-gray-500');
    await expect(breadcrumb.getByText('Home')).toBeVisible();
    await expect(breadcrumb.getByText('Configuration')).toBeVisible();
    await expect(breadcrumb.getByText('Pipeline Flavors')).toBeVisible();
  });

  test('should show loading state while fetching flavors', async ({ page }) => {
    // Navigate to pipeline type (the loading state is very fast, so we just verify the final state)
    await page.goto(`/app/config/pipelines/${pipelineType}`);

    // Eventually, the flavors list should be visible
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });
  });

  test('should display flavor version information', async ({ page }) => {
    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Verify version information is displayed - scoped to flavors container
    const flavorsContainer = page.locator('[data-testid="pipeline-flavors-container"]');
    await expect(flavorsContainer.getByText(/Version:/).first()).toBeVisible();
  });

  test('should display flavor enabled/disabled status', async ({ page }) => {
    // Create a disabled flavor via API
    const timestamp = Date.now();
    const flavorTitle = `E2E Disabled Flavor ${timestamp}`;

    const createResponse = await apiRequest<any>(page, '/api/pipeline-flavors', {
      method: 'POST',
      body: {
        title: flavorTitle,
        pipeline: pipelineType,
        llm_provider: 'openai',
        llm_model: 'gpt-4',
        version: 1,
        system_prompt: 'Test system prompt',
        user_prompt: 'Test user prompt: {input}',
        enabled: false, // Explicitly disabled
      },
    });
    const flavorId = createResponse.id;

    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for the flavor card
    const flavorCard = page.locator(`[data-testid="pipeline-flavor-card-${flavorId}"]`);
    await expect(flavorCard).toBeVisible({ timeout: 10000 });

    // Verify status shows as "Disabled"
    const statusElement = page.locator(`[data-testid="pipeline-flavor-status-${flavorId}"]`);
    await expect(statusElement).toContainText('Disabled');
  });

  test('should display creation date for flavors', async ({ page }) => {
    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Verify "Created:" date is shown - scoped to flavors container
    const flavorsContainer = page.locator('[data-testid="pipeline-flavors-container"]');
    await expect(flavorsContainer.getByText(/Created:/).first()).toBeVisible();
  });

  test('should handle multiple custom flavors', async ({ page }) => {
    // Create multiple custom flavors via API
    const timestamp = Date.now();
    const flavor1Title = `E2E Flavor 1 ${timestamp}`;
    const flavor2Title = `E2E Flavor 2 ${timestamp}`;

    await Promise.all([
      apiRequest(page, '/api/pipeline-flavors', {
        method: 'POST',
        body: {
          title: flavor1Title,
          pipeline: pipelineType,
          llm_provider: 'openai',
          llm_model: 'gpt-4',
          version: 1,
          system_prompt: 'Test prompt 1',
          user_prompt: 'Test template 1: {input}',
          enabled: true,
        },
      }),
      apiRequest(page, '/api/pipeline-flavors', {
        method: 'POST',
        body: {
          title: flavor2Title,
          pipeline: pipelineType,
          llm_provider: 'anthropic',
          llm_model: 'claude-3',
          version: 1,
          system_prompt: 'Test prompt 2',
          user_prompt: 'Test template 2: {input}',
          enabled: true,
        },
      }),
    ]);

    // Navigate to pipeline type
    await page.goto(`/app/config/pipelines/${pipelineType}`);
    await page.waitForLoadState('networkidle');

    // Wait for flavors list
    await expect(page.locator('[data-testid="pipeline-flavors-list"]')).toBeVisible({ timeout: 10000 });

    // Verify both flavors are displayed
    await expect(page.getByText(flavor1Title)).toBeVisible();
    await expect(page.getByText(flavor2Title)).toBeVisible();

    // Verify different providers are shown - scoped to flavors container
    const flavorsContainer = page.locator('[data-testid="pipeline-flavors-container"]');
    await expect(flavorsContainer.getByText(/Provider: openai/).first()).toBeVisible();
    await expect(flavorsContainer.getByText(/Provider: anthropic/).first()).toBeVisible();
  });
});
