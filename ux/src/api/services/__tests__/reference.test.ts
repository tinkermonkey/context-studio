/**
 * Unit tests for ReferenceService using MSW to mock HTTP responses.
 * Tests verify reference database search and status operations.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { referenceService } from "../reference";
import {
  createReferenceSearchResponse,
  createReferenceStatusResponse,
} from "./fixtures/reference.fixtures";

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

describe("ReferenceService", () => {
  describe("search", () => {
    it("searches reference databases with default options", async () => {
      const mockResponse = createReferenceSearchResponse({
        term: "machine learning",
        results: [
          {
            uri: "http://en.wikipedia.org/wiki/Machine_learning",
            label: "Machine Learning",
            description: "Algorithms that learn from data",
            source: "wikipedia",
            confidence: 0.92,
          },
        ],
      });

      server.use(
        rest.post("*/api/reference/search", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      const result = await referenceService.search("machine learning");

      expect(result).toEqual(mockResponse);
      expect(result.results).toHaveLength(1);
      expect(result.results![0].label).toBe("Machine Learning");
    });

    it("searches with custom limit option", async () => {
      const mockResponse = createReferenceSearchResponse({
        term: "test",
        results: Array.from({ length: 5 }, (_, i) => ({
          uri: `http://example.com/${i}`,
          label: `Result ${i}`,
          description: `Description ${i}`,
          source: "wikipedia",
          confidence: 0.9 - i * 0.05,
        })),
      });

      server.use(
        rest.post("*/api/reference/search", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      const result = await referenceService.search("test", { limit: 5 });

      expect(result.results).toHaveLength(5);
    });

    it("searches with custom sources option", async () => {
      const mockResponse = createReferenceSearchResponse({
        term: "knowledge",
        results: [
          {
            uri: "http://custom.example.com/kb",
            label: "Knowledge Base",
            description: "Custom knowledge source",
            source: "custom_db",
            confidence: 0.88,
          },
        ],
      });

      server.use(
        rest.post("*/api/reference/search", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      const result = await referenceService.search("knowledge", {
        sources: ["custom_db"],
      });

      expect(result.results![0].source).toBe("custom_db");
    });

    it("throws ApiError on 400 for empty search term", async () => {
      server.use(
        rest.post("*/api/reference/search", (req, res, ctx) =>
          res(
            ctx.status(400),
            ctx.json({
              detail: "Search term cannot be empty",
            }),
          ),
        ),
      );

      await expect(referenceService.search("")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 404 when no results found", async () => {
      server.use(
        rest.post("*/api/reference/search", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "No results found for search term",
            }),
          ),
        ),
      );

      await expect(referenceService.search("nonexistent_term_xyz")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });

    it("throws ApiError on 503 when reference service unavailable", async () => {
      server.use(
        rest.post("*/api/reference/search", (req, res, ctx) =>
          res(
            ctx.status(503),
            ctx.json({
              detail: "Reference service temporarily unavailable",
            }),
          ),
        ),
      );

      await expect(referenceService.search("test")).rejects.toMatchObject({
        name: "ApiError",
        status: 503,
      });
    });
  });

  describe("getStatus", () => {
    it("returns reference service status", async () => {
      const mockStatus = createReferenceStatusResponse({
        sources_available: 2,
      });

      server.use(rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockStatus))));

      const result = await referenceService.getStatus();

      expect(result).toEqual(mockStatus);
      expect(result.sources_available).toBe(2);
    });

    it("returns degraded status when some sources unavailable", async () => {
      const mockStatus = createReferenceStatusResponse({
        sources_available: 1,
      });

      server.use(rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockStatus))));

      const result = await referenceService.getStatus();

      expect(result.sources_available).toBe(1);
    });

    it("returns status with source information", async () => {
      const mockStatus = createReferenceStatusResponse({
        sources: [
          { name: "wikipedia", available: true },
          { name: "dbpedia", available: false },
        ],
        sources_available: 1,
      });

      server.use(rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockStatus))));

      const result = await referenceService.getStatus();

      expect(result.sources).toHaveLength(2);
      expect(result.sources_available).toBe(1);
    });

    it("throws ApiError on 500 from getStatus", async () => {
      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) =>
          res(
            ctx.status(500),
            ctx.json({
              detail: "Failed to retrieve reference service status",
            }),
          ),
        ),
      );

      await expect(referenceService.getStatus()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });

    it("throws ApiError on 503 when service is down", async () => {
      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) =>
          res(
            ctx.status(503),
            ctx.json({
              detail: "Reference service is down",
            }),
          ),
        ),
      );

      await expect(referenceService.getStatus()).rejects.toMatchObject({
        name: "ApiError",
        status: 503,
      });
    });
  });
});
