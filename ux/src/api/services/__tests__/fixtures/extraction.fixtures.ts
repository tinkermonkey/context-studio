/**
 * Test fixtures for ExtractionService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createExtractionResult(
  overrides?: Partial<components["schemas"]["ExtractionResultSchema"]>
): components["schemas"]["ExtractionResultSchema"] {
  return {
    entities: [
      {
        text: "Apple",
        type: "ORGANIZATION",
        confidence: 0.95,
        start_char: 0,
        end_char: 5,
      },
    ],
    relationships: [
      {
        source_text: "Apple",
        target_text: "iPhone",
        type: "manufactures",
        confidence: 0.88,
      },
    ],
    extraction_time_ms: 450,
    ...overrides,
  };
}

export function createExtractRequest(
  overrides?: Partial<components["schemas"]["ExtractRequest"]>
): components["schemas"]["ExtractRequest"] {
  return {
    text: "Apple manufactures the iPhone.",
    ...overrides,
  };
}

export function createAnalyzeTextRequest(
  overrides?: Partial<components["schemas"]["AnalyzeTextRequest"]>
): components["schemas"]["AnalyzeTextRequest"] {
  return {
    text: "Sample text for analysis.",
    ...overrides,
  };
}

export function createEnrichFromReferencesRequest(
  overrides?: Partial<components["schemas"]["EnrichFromReferencesRequest"]>
): components["schemas"]["EnrichFromReferencesRequest"] {
  return {
    entity_names: ["Apple", "Google", "Microsoft"],
    ...overrides,
  };
}
