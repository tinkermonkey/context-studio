import { Page } from "@playwright/test";

/**
 * Test helper utilities for E2E tests.
 */

/**
 * Wait for the application to be fully loaded and ready.
 */
export async function waitForAppReady(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
}

/**
 * Re-export apiRequest and APIError from api-client for convenient access
 */
export { apiRequest, APIError } from "./api-client";

/**
 * Export factory functions for convenient access
 */
export {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  clearTestData,
  type Taxonomy,
  type ConceptScheme,
  type OntologyClass,
  type PropertyDefinition,
  type Relationship,
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
      state: (options?.state || "visible") as "visible" | "hidden" | "attached",
      timeout: options?.timeout || 10000,
    });
  } catch (error) {
    throw new Error(
      `Element "${selector}" not found after ${options?.timeout || 10000}ms. Current URL: ${page.url()}`,
    );
  }
}
