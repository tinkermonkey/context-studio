/**
 * Unit tests for ExtractionService using MSW to mock HTTP responses.
 * Tests verify text extraction, analysis, and reference enrichment.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { extractionService } from "../extraction";
import {
  createExtractionResult,
  createExtractRequest,
  createAnalyzeTextRequest,
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
        entities: [
          {
            text: "John",
            type: "PERSON",
            confidence: 0.92,
            start_char: 0,
            end_char: 4,
          },
        ],
      });

      server.use(
        rest.post("*/api/extract", (req, res, ctx) => res(ctx.json(mockResult)))
      );

      const result = await extractionService.extract("John works at Google");

      expect(result).toEqual(mockResult);
      expect(result.entities).toHaveLength(1);
      expect(result.entities[0].type).toBe("PERSON");
    });

    it("throws ApiError on 400 for empty text", async () => {
      server.use(
        rest.post("*/api/extract", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
              detail: "Text cannot be empty",
            })
      )
        )
      );

      await expect(extractionService.extract("")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 500 from extract", async () => {
      server.use(
        rest.post("*/api/extract", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
              detail: "Extraction service error",
            })
      )
        )
      );

      await expect(
        extractionService.extract("Some text")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("analyzeText", () => {
    it("analyzes text and returns entities and relationships", async () => {
      const mockResult = createExtractionResult({
        extraction_time_ms: 320,
      });

      server.use(
        rest.post("*/api/analyze_text", (req, res, ctx) =>
          res(ctx.json(mockResult))
        )
      );

      const result = await extractionService.analyzeText("Sample text");

      expect(result).toEqual(mockResult);
      expect(result.extraction_time_ms).toBe(320);
    });

    it("throws ApiError on 413 for text too long", async () => {
      server.use(
        rest.post("*/api/analyze_text", (req, res, ctx) =>
          res(
        ctx.status(413),
        ctx.json({
              detail: "Text exceeds maximum length",
            })
      )
        )
      );

      await expect(
        extractionService.analyzeText("x".repeat(100000))
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 413,
      });
    });

    it("throws ApiError on 500 from analyzeText", async () => {
      server.use(
        rest.post("*/api/analyze_text", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
              detail: "Analysis failed",
            })
      )
        )
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
        entity_names: ["Apple", "Steve Jobs"],
      });
      const mockResult = createExtractionResult({
        entities: [
          {
            text: "Apple",
            type: "ORGANIZATION",
            confidence: 0.98,
            start_char: 0,
            end_char: 5,
          },
          {
            text: "Steve Jobs",
            type: "PERSON",
            confidence: 0.97,
            start_char: 7,
            end_char: 17,
          },
        ],
      });

      server.use(
        rest.post("*/api/enrich_from_references", (req, res, ctx) =>
          res(ctx.json(mockResult))
        )
      );

      const result = await extractionService.enrichFromReferences(request);

      expect(result).toEqual(mockResult);
      expect(result.entities).toHaveLength(2);
    });

    it("throws ApiError on 400 for invalid entity names", async () => {
      server.use(
        rest.post("*/api/enrich_from_references", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
              detail: "Entity names list cannot be empty",
            })
      )
        )
      );

      await expect(
        extractionService.enrichFromReferences({ entity_names: [] })
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 503 when reference service unavailable", async () => {
      server.use(
        rest.post("*/api/enrich_from_references", (req, res, ctx) =>
          res(
        ctx.status(503),
        ctx.json({
              detail: "Reference service temporarily unavailable",
            })
      )
        )
      );

      await expect(
        extractionService.enrichFromReferences({
          entity_names: ["test"],
        })
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 503,
      });
    });
  });
});
