import { Page } from "@playwright/test";

/**
 * Test helper utilities for E2E tests.
 */

/**
 * Wait for the application to be fully loaded and ready.
 */
export async function waitForAppReady(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");

  // Add additional app-specific ready checks here
  // For example, wait for a specific element that indicates the app is ready
  // await expect(page.locator('[data-testid="app-ready"]')).toBeVisible();
}

/**
 * Re-export apiRequest and APIError from api-client for convenient access
 */
export { apiRequest, APIError } from "./api-client";

/**
 * Export factory functions for convenient access
 * See fixtures/factories.ts for implementation
 */
export {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  createIndividual,
  createTestHierarchy,
  seedTestData,
  clearTestData,
} from "./factories";

/**
 * Wait for an element to be visible with better error messages
 */
export async function waitForElement(
  page: Page,
  selector: string,
  options?: { timeout?: number; state?: "visible" | "hidden" | "attached" },
): Promise<void> {
  try {
    await page.waitForSelector(selector, {
      state: options?.state || "visible",
      timeout: options?.timeout || 10000,
    });
  } catch (error) {
    throw new Error(
      `Element "${selector}" not found after ${options?.timeout || 10000}ms. Current URL: ${page.url()}`,
      { cause: error },
    );
  }
}

/**
 * Check if a backend endpoint exists
 * @throws {Error} If the backend is unreachable (network error)
 * @returns true if endpoint exists (status != 404), false if 404
 */
export async function endpointExists(
  page: Page,
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
): Promise<boolean> {
  try {
    // Use HEAD for GET, OPTIONS for all other methods to safely probe endpoint existence
    const probeMethod = method === "GET" ? "HEAD" : "OPTIONS";
    const response = await page.request.fetch(
      `http://localhost:8888${endpoint}`,
      {
        method: probeMethod,
        headers: { "Content-Type": "application/json" },
        failOnStatusCode: false,
      },
    );

    // 404 means endpoint doesn't exist, anything else means it exists
    return response.status() !== 404;
  } catch (error) {
    // Network error: backend unreachable
    throw new Error(
      `Could not reach backend at http://localhost:8888${endpoint}: ${
        error instanceof Error ? error.message : String(error)
      }`,
      { cause: error },
    );
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
      return urlObj.searchParams.get("query") || "computer";
    } catch {
      return "computer";
    }
  };

  // Mock backend's DBpedia search endpoint
  await page.route("**/api/reference/dbpedia/search*", (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: "http://dbpedia.org/resource/Computer",
            source: "dbpedia",
            title: "Computer",
            definition:
              "A computer is an electronic device for storing and processing data, typically in binary form.",
            source_url: "http://dbpedia.org/resource/Computer",
            relevance_score: 0.95,
            attributes: {},
          },
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ["dbpedia"],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 150.5,
      }),
    });
  });

  // Mock backend's Wikidata search endpoint
  await page.route("**/api/reference/wikidata/search*", (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: "Q68",
            source: "wikidata",
            title: "computer",
            definition:
              "general-purpose device for performing arithmetic or logical operations",
            source_url: "https://www.wikidata.org/wiki/Q68",
            relevance_score: 0.92,
            attributes: {},
          },
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ["wikidata"],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 200.3,
      }),
    });
  });

  // Mock backend's ConceptNet search endpoint
  await page.route("**/api/reference/conceptnet/search*", (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: "/c/en/computer",
            source: "conceptnet",
            title: "computer",
            definition:
              "An electronic device that can perform calculations and process information",
            source_url: "http://conceptnet.io/c/en/computer",
            relevance_score: 0.88,
            attributes: {},
          },
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ["conceptnet"],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 180.7,
      }),
    });
  });

  // Mock backend's Schema.org search endpoint
  await page.route("**/api/reference/schema-org/search*", (route) => {
    const query = getQueryFromUrl(route.request().url());
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query: query,
        results: [
          {
            id: "schema:ComputerLanguage",
            source: "schema_org",
            title: "ComputerLanguage",
            definition:
              "A computer language is an artificial language designed for humans to communicate with computers",
            source_url: "https://schema.org/ComputerLanguage",
            relevance_score: 0.85,
            attributes: {},
          },
        ],
        links: [],
        total_results: 1,
        total_links: 0,
        sources_queried: ["schema_org"],
        source_errors: {},
        offset: 0,
        limit: 20,
        search_time_ms: 120.2,
      }),
    });
  });
}
