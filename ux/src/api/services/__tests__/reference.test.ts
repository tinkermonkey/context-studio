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
  createGroundingWorkflow,
  createGroundingWorkflowCreate,
  createGroundingWorkflowUpdate,
  createWorkflowRun,
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

  describe("listGroundingWorkflows", () => {
    it("returns list of grounding workflows from GET /api/reference/grounding-workflows", async () => {
      const mockWorkflows = [
        createGroundingWorkflow({ id: "wf-1", title: "Workflow 1" }),
        createGroundingWorkflow({ id: "wf-2", title: "Workflow 2" }),
      ];

      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json(mockWorkflows)),
        ),
      );

      const result = await referenceService.listGroundingWorkflows();

      expect(result).toHaveLength(2);
      expect(result[0].title).toBe("Workflow 1");
    });

    it("throws ApiError on 500 from listGroundingWorkflows", async () => {
      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(
            ctx.status(500),
            ctx.json({
              detail: "Internal server error",
            }),
          ),
        ),
      );

      await expect(referenceService.listGroundingWorkflows()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getGroundingWorkflow", () => {
    it("returns workflow by ID from GET /api/reference/grounding-workflows/:id", async () => {
      const mockWorkflow = createGroundingWorkflow({ id: "wf-123" });

      server.use(
        rest.get("*/api/reference/grounding-workflows/wf-123", (req, res, ctx) =>
          res(ctx.json(mockWorkflow)),
        ),
      );

      const result = await referenceService.getGroundingWorkflow("wf-123");

      expect(result).toEqual(mockWorkflow);
      expect(result.id).toBe("wf-123");
    });

    it("throws ApiError with 404 on getGroundingWorkflow with non-existent ID", async () => {
      server.use(
        rest.get("*/api/reference/grounding-workflows/not-found", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "Workflow not found",
            }),
          ),
        ),
      );

      await expect(referenceService.getGroundingWorkflow("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createGroundingWorkflow", () => {
    it("creates workflow from POST /api/reference/grounding-workflows", async () => {
      const createRequest = createGroundingWorkflowCreate();
      const mockResponse = createGroundingWorkflow({ id: "wf-999" });

      server.use(
        rest.post("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json(mockResponse)),
        ),
      );

      const result = await referenceService.createGroundingWorkflow(createRequest);

      expect(result.id).toBe("wf-999");
      expect(result.source).toBe("dbpedia");
    });

    it("throws ApiError with 400 on createGroundingWorkflow with invalid data", async () => {
      const createRequest = createGroundingWorkflowCreate({ title: "" });

      server.use(
        rest.post("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(
            ctx.status(400),
            ctx.json({
              detail: "Title is required",
            }),
          ),
        ),
      );

      await expect(referenceService.createGroundingWorkflow(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("updateGroundingWorkflow", () => {
    it("updates workflow from PUT /api/reference/grounding-workflows/:id", async () => {
      const updateRequest = createGroundingWorkflowUpdate({ title: "Updated Workflow" });
      const mockResponse = createGroundingWorkflow({
        id: "wf-123",
        title: "Updated Workflow",
      });

      server.use(
        rest.put("*/api/reference/grounding-workflows/wf-123", (req, res, ctx) =>
          res(ctx.json(mockResponse)),
        ),
      );

      const result = await referenceService.updateGroundingWorkflow("wf-123", updateRequest);

      expect(result.title).toBe("Updated Workflow");
    });

    it("throws ApiError with 404 on updateGroundingWorkflow with non-existent ID", async () => {
      const updateRequest = createGroundingWorkflowUpdate();

      server.use(
        rest.put("*/api/reference/grounding-workflows/not-found", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "Workflow not found",
            }),
          ),
        ),
      );

      await expect(referenceService.updateGroundingWorkflow("not-found", updateRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deleteGroundingWorkflow", () => {
    it("deletes workflow via DELETE /api/reference/grounding-workflows/:id", async () => {
      server.use(
        rest.delete("*/api/reference/grounding-workflows/wf-123", (req, res, ctx) =>
          res(ctx.status(204)),
        ),
      );

      await expect(referenceService.deleteGroundingWorkflow("wf-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteGroundingWorkflow with non-existent ID", async () => {
      server.use(
        rest.delete("*/api/reference/grounding-workflows/not-found", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "Workflow not found",
            }),
          ),
        ),
      );

      await expect(referenceService.deleteGroundingWorkflow("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("runGroundingWorkflow", () => {
    it("runs workflow from POST /api/reference/grounding-workflows/:id/run", async () => {
      const mockRun = createWorkflowRun({ workflow_id: "wf-123", status: "success" });

      server.use(
        rest.post("*/api/reference/grounding-workflows/wf-123/run", (req, res, ctx) =>
          res(ctx.json(mockRun)),
        ),
      );

      const result = await referenceService.runGroundingWorkflow("wf-123");

      expect(result.status).toBe("success");
      expect(result.workflow_id).toBe("wf-123");
    });

    it("throws ApiError with 400 on runGroundingWorkflow when workflow is inactive", async () => {
      server.use(
        rest.post("*/api/reference/grounding-workflows/wf-123/run", (req, res, ctx) =>
          res(
            ctx.status(400),
            ctx.json({
              detail: "Cannot run inactive workflow",
            }),
          ),
        ),
      );

      await expect(referenceService.runGroundingWorkflow("wf-123")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("getGroundingWorkflowRuns", () => {
    it("returns workflow runs from GET /api/reference/grounding-workflows/:id/runs", async () => {
      const mockRuns = [
        createWorkflowRun({ id: "run-1", workflow_id: "wf-123" }),
        createWorkflowRun({ id: "run-2", workflow_id: "wf-123" }),
      ];

      server.use(
        rest.get("*/api/reference/grounding-workflows/wf-123/runs", (req, res, ctx) =>
          res(ctx.json(mockRuns)),
        ),
      );

      const result = await referenceService.getGroundingWorkflowRuns("wf-123");

      expect(result).toHaveLength(2);
      expect(result[0].workflow_id).toBe("wf-123");
    });

    it("throws ApiError with 404 on getGroundingWorkflowRuns with non-existent workflow", async () => {
      server.use(
        rest.get("*/api/reference/grounding-workflows/not-found/runs", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "Workflow not found",
            }),
          ),
        ),
      );

      await expect(referenceService.getGroundingWorkflowRuns("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});
