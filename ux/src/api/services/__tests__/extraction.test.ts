/**
 * Unit tests for ExtractionService using MSW to mock HTTP responses.
 * Tests verify text extraction, analysis, and reference enrichment.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { extractionService } from "../extraction";
import {
  createExtractionResult,
  createEnrichFromReferencesRequest,
} from "./fixtures/extraction.fixtures";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("ExtractionService", () => {
  describe("extract", () => {
    it("extracts entities and relationships from text", async () => {
      const mockResult = createExtractionResult({
        extracted_entities: [
          {
            id: "entity-1",
            label: "John",
            entity_type: "PERSON",
            source_layer: 1,
            confidence: 0.92,
          },
        ],
      });

      server.use(http.post("*/api/extract", () => HttpResponse.json(mockResult)));

      const result = await extractionService.extract("John works at Google");

      expect(result).toEqual(mockResult);
      expect(result.extracted_entities).toBeDefined();
      expect(result.extracted_entities).toHaveLength(1);
      expect(result.extracted_entities?.[0].entity_type).toBe("PERSON");
    });

    it("throws ApiError on 400 for empty text", async () => {
      server.use(
        http.post("*/api/extract", () =>
          HttpResponse.json({
              detail: "Text cannot be empty",
            }, { status: 400 }),
        ),
      );

      await expect(extractionService.extract("")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 500 from extract", async () => {
      server.use(
        http.post("*/api/extract", () =>
          HttpResponse.json({
              detail: "Extraction service error",
            }, { status: 500 }),
        ),
      );

      await expect(extractionService.extract("Some text")).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("analyzeText", () => {
    it("analyzes text and returns entities and relationships", async () => {
      const mockResult = createExtractionResult({
        total_duration_ms: 320,
      });

      server.use(http.post("*/api/analyze_text", () => HttpResponse.json(mockResult)));

      const result = await extractionService.analyzeText("Sample text");

      expect(result).toEqual(mockResult);
      expect(result.total_duration_ms).toBe(320);
    });

    it("throws ApiError on 413 for text too long", async () => {
      server.use(
        http.post("*/api/analyze_text", () =>
          HttpResponse.json({
              detail: "Text exceeds maximum length",
            }, { status: 413 }),
        ),
      );

      await expect(extractionService.analyzeText("x".repeat(100000))).rejects.toMatchObject({
        name: "ApiError",
        status: 413,
      });
    });

    it("throws ApiError on 500 from analyzeText", async () => {
      server.use(
        http.post("*/api/analyze_text", () =>
          HttpResponse.json({
              detail: "Analysis failed",
            }, { status: 500 }),
        ),
      );

      await expect(extractionService.analyzeText("Text")).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("enrichFromReferences", () => {
    it("enriches entities using reference databases", async () => {
      const request = createEnrichFromReferencesRequest({
        extracted_entities: [
          {
            id: "entity-1",
            label: "Apple",
            entity_type: "ORGANIZATION",
            source_layer: 1,
            confidence: 0.98,
          },
          {
            id: "entity-2",
            label: "Steve Jobs",
            entity_type: "PERSON",
            source_layer: 1,
            confidence: 0.97,
          },
        ],
      });
      const mockResult = createExtractionResult({
        extracted_entities: [
          {
            id: "entity-1",
            label: "Apple",
            entity_type: "ORGANIZATION",
            source_layer: 1,
            confidence: 0.98,
          },
          {
            id: "entity-2",
            label: "Steve Jobs",
            entity_type: "PERSON",
            source_layer: 1,
            confidence: 0.97,
          },
        ],
      });

      server.use(
        http.post("*/api/enrich_from_references", () => HttpResponse.json(mockResult)),
      );

      const result = await extractionService.enrichFromReferences(request);

      expect(result).toEqual(mockResult);
      expect(result.extracted_entities).toHaveLength(2);
    });

    it("throws ApiError on 400 for invalid entity names", async () => {
      server.use(
        http.post("*/api/enrich_from_references", () =>
          HttpResponse.json({
              detail: "Entity names list cannot be empty",
            }, { status: 400 }),
        ),
      );

      await expect(
        extractionService.enrichFromReferences({
          text: "Sample",
          extracted_entities: [],
        }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 503 when reference service unavailable", async () => {
      server.use(
        http.post("*/api/enrich_from_references", () =>
          HttpResponse.json({
              detail: "Reference service temporarily unavailable",
            }, { status: 503 }),
        ),
      );

      await expect(
        extractionService.enrichFromReferences({
          text: "test",
          extracted_entities: [
            {
              id: "e1",
              label: "test",
              entity_type: "OTHER",
              source_layer: 1,
              confidence: 0.5,
            },
          ],
        }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 503,
      });
    });
  });
});
