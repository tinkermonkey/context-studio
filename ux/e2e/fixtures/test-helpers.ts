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

  if (!response.ok()) {
    const responseText = await response.text();
    console.error(`API request failed: ${method} ${endpoint}`);
    console.error(`Status: ${response.status()} ${response.statusText()}`);
    console.error(`Response: ${responseText}`);
    throw new Error(`API request failed with status ${response.status()}: ${responseText}`);
  }

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

/**
 * Wait for an element to be visible with better error messages
 */
export async function waitForElement(
  page: Page,
  selector: string,
  options?: { timeout?: number; state?: 'visible' | 'hidden' | 'attached' }
): Promise<void> {
  try {
    await page.waitForSelector(selector, {
      state: options?.state || 'visible',
      timeout: options?.timeout || 10000,
    });
  } catch (error) {
    throw new Error(
      `Element "${selector}" not found after ${options?.timeout || 10000}ms. Current URL: ${page.url()}`
    );
  }
}

/**
 * Wait for any of multiple conditions to be true
 */
export async function waitForAnyCondition(
  page: Page,
  conditions: Array<() => Promise<boolean>>,
  timeout: number = 10000
): Promise<number> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    for (let i = 0; i < conditions.length; i++) {
      try {
        const result = await conditions[i]();
        if (result) {
          return i; // Return which condition succeeded
        }
      } catch {
        // Condition not met yet, continue
      }
    }
    await page.waitForTimeout(100);
  }

  throw new Error(`None of the ${conditions.length} conditions were met within ${timeout}ms`);
}

/**
 * Check if a backend endpoint exists
 */
export async function endpointExists(
  page: Page,
  endpoint: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET'
): Promise<boolean> {
  try {
    const response = await page.request.fetch(`http://localhost:8888${endpoint}`, {
      method: method === 'GET' ? 'HEAD' : method,
      headers: { 'Content-Type': 'application/json' },
      failOnStatusCode: false,
    });

    // 404 means endpoint doesn't exist, anything else means it exists
    return response.status() !== 404;
  } catch {
    return false;
  }
}

/**
 * Mock reference search API responses
 * Note: The app calls backend endpoints, not external APIs directly
 * Response format matches MultiSourceSearchResponse from backend
 */
export async function mockReferenceAPIs(page: Page): Promise<void> {
  // Helper to get query from URL
  const getQueryFromUrl = (url: string): string => {
    try {
      const urlObj = new URL(url);
      return urlObj.searchParams.get('query') || 'computer';
    } catch {
      return 'computer';
    }
  };

  // Mock backend's DBpedia search endpoint
  await page.route('**/api/reference/dbpedia/search*', (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: 'http://dbpedia.org/resource/Computer',
            source: 'dbpedia',
            title: 'Computer',
            definition: 'A computer is an electronic device for storing and processing data, typically in binary form.',
            source_url: 'http://dbpedia.org/resource/Computer',
            relevance_score: 0.95,
            attributes: {}
          }
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ['dbpedia'],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 150.5
      })
    });
  });

  // Mock backend's Wikidata search endpoint
  await page.route('**/api/reference/wikidata/search*', (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: 'Q68',
            source: 'wikidata',
            title: 'computer',
            definition: 'general-purpose device for performing arithmetic or logical operations',
            source_url: 'https://www.wikidata.org/wiki/Q68',
            relevance_score: 0.92,
            attributes: {}
          }
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ['wikidata'],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 200.3
      })
    });
  });

  // Mock backend's ConceptNet search endpoint
  await page.route('**/api/reference/conceptnet/search*', (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: '/c/en/computer',
            source: 'conceptnet',
            title: 'computer',
            definition: 'An electronic device that can perform calculations and process information',
            source_url: 'http://conceptnet.io/c/en/computer',
            relevance_score: 0.88,
            attributes: {}
          }
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ['conceptnet'],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 180.7
      })
    });
  });

  // Mock backend's Schema.org search endpoint
  await page.route('**/api/reference/schema-org/search*', (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: 'schema:ComputerLanguage',
            source: 'schema_org',
            title: 'ComputerLanguage',
            definition: 'A computer language is an artificial language designed for humans to communicate with computers',
            source_url: 'https://schema.org/ComputerLanguage',
            relevance_score: 0.85,
            attributes: {}
          }
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ['schema_org'],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 120.2
      })
    });
  });
}
