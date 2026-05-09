/**
 * Test fixtures for ReferenceService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createReferenceSearchRequest(
  overrides?: Partial<components["schemas"]["ReferenceSearchRequest"]>,
): components["schemas"]["ReferenceSearchRequest"] {
  return {
    term: "artificial intelligence",
    limit: 10,
    sources: ["wikipedia", "dbpedia"],
    ...overrides,
  };
}

export function createReferenceSearchResponse(
  overrides?: Partial<components["schemas"]["ReferenceSearchResponseSchema"]>,
): components["schemas"]["ReferenceSearchResponseSchema"] {
  return {
    term: "artificial intelligence",
    results: [
      {
        uri: "https://en.wikipedia.org/wiki/Artificial_intelligence",
        label: "Artificial Intelligence",
        description: "The simulation of human intelligence",
        confidence: 1.0,
        source: "wikipedia",
      },
    ],
    sources_searched: ["wikipedia", "dbpedia"],
    total_results: 1,
    ...overrides,
  };
}

export function createReferenceStatusResponse(
  overrides?: Partial<components["schemas"]["ReferenceStatusResponseSchema"]>,
): components["schemas"]["ReferenceStatusResponseSchema"] {
  return {
    sources: [
      {
        name: "wikipedia",
        available: true,
      },
      {
        name: "dbpedia",
        available: true,
      },
    ],
    sources_available: 2,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}
