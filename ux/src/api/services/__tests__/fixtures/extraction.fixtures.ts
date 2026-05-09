/**
 * Test fixtures for ExtractionService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createExtractionResult(
  overrides?: Partial<components["schemas"]["ExtractionResultSchema"]>
): components["schemas"]["ExtractionResultSchema"] {
  return {
    id: "extraction-123",
    text: "Sample text",
    extracted_entities: [
      {
        id: "entity-1",
        label: "Apple",
        entity_type: "ORGANIZATION",
        source_layer: 1,
        confidence: 0.95,
      },
    ],
    total_duration_ms: 450,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createEnrichFromReferencesRequest(
  overrides?: Partial<components["schemas"]["EnrichFromReferencesRequest"]>
): components["schemas"]["EnrichFromReferencesRequest"] {
  return {
    text: "Sample text with entities",
    extracted_entities: [
      {
        id: "entity-1",
        label: "Apple",
        entity_type: "ORGANIZATION",
        source_layer: 1,
        confidence: 0.95,
      },
    ],
    ...overrides,
  };
}
