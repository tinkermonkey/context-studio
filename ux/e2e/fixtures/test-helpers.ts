import { Page, expect } from '@playwright/test';

/**
 * Test helper utilities for E2E tests.
 */

/**
 * Wait for the application to be fully loaded and ready.
 */
export async function waitForAppReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');

  // Add additional app-specific ready checks here
  // For example, wait for a specific element that indicates the app is ready
  // await expect(page.locator('[data-testid="app-ready"]')).toBeVisible();
}

/**
 * Make an API request to the backend and return the response.
 */
export async function apiRequest<T = any>(
  page: Page,
  endpoint: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
    body?: any;
    headers?: Record<string, string>;
  }
): Promise<T> {
  const { method = 'GET', body, headers = {} } = options || {};

  const response = await page.request.fetch(`http://localhost:8888${endpoint}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    data: body ? JSON.stringify(body) : undefined,
  });

  expect(response.ok()).toBeTruthy();
  return await response.json();
}

/**
 * Clear all test data from the backend.
 * Useful for resetting state between tests.
 */
export async function clearTestData(page: Page): Promise<void> {
  // Implement based on your API's data clearing endpoint
  // For example:
  // await apiRequest(page, '/api/test/clear', { method: 'POST' });
}

/**
 * Create test data in the backend.
 */
export async function seedTestData(
  page: Page,
  data: {
    layers?: any[];
    domains?: any[];
    terms?: any[];
    predicates?: any[];
  }
): Promise<void> {
  // Implement based on your API's structure
  // For example:
  // if (data.layers) {
  //   for (const layer of data.layers) {
  //     await apiRequest(page, '/api/structure-nodes', {
  //       method: 'POST',
  //       body: layer,
  //     });
  //   }
  // }
}
