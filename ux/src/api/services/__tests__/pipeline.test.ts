/**
 * Unit tests for PipelineService using MSW to mock HTTP responses.
 * Tests verify pipeline CRUD operations and execution management.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { pipelineService } from "../pipeline";
import {
  createPipelineConfiguration,
  createPipelineConfigurationCreate,
  createPipelineConfigurationUpdate,
  createExecution,
} from "./fixtures/pipeline.fixtures";

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

describe("PipelineService", () => {
  describe("listPipelines", () => {
    it("returns list of pipeline configurations", async () => {
      const mockPipelines = [
        createPipelineConfiguration({ id: "p-1", title: "Pipeline 1", pipeline: "pipeline_1" }),
        createPipelineConfiguration({ id: "p-2", title: "Pipeline 2", pipeline: "pipeline_2" }),
      ];

      server.use(rest.get("*/api/pipelines", (req, res, ctx) => res(ctx.json(mockPipelines))));

      const result = await pipelineService.listPipelines();

      expect(result).toHaveLength(2);
      expect(result[0].title).toBe("Pipeline 1");
    });

    it("throws ApiError on 500 from listPipelines", async () => {
      server.use(
        rest.get("*/api/pipelines", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Failed to list pipelines" })),
        ),
      );

      await expect(pipelineService.listPipelines()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getPipeline", () => {
    it("returns pipeline by ID", async () => {
      const mockPipeline = createPipelineConfiguration({
        id: "p-123",
        title: "Pipeline",
        pipeline: "pipe",
      });

      server.use(rest.get("*/api/pipelines/p-123", (req, res, ctx) => res(ctx.json(mockPipeline))));

      const result = await pipelineService.getPipeline("p-123");

      expect(result.title).toBe("Pipeline");
    });

    it("throws ApiError on 404 for non-existent pipeline", async () => {
      server.use(
        rest.get("*/api/pipelines/not-found", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Pipeline not found" })),
        ),
      );

      await expect(pipelineService.getPipeline("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createPipeline", () => {
    it("creates and returns new pipeline", async () => {
      const mockPipeline = createPipelineConfiguration({
        id: "p-999",
        title: "New",
        pipeline: "new",
      });

      server.use(rest.post("*/api/pipelines", (req, res, ctx) => res(ctx.json(mockPipeline))));

      const createRequest = createPipelineConfigurationCreate({ title: "New", pipeline: "new" });
      const result = await pipelineService.createPipeline(createRequest);

      expect(result.id).toBe("p-999");
    });

    it("throws ApiError on 400 for invalid pipeline data", async () => {
      server.use(
        rest.post("*/api/pipelines", (req, res, ctx) =>
          res(ctx.status(400), ctx.json({ detail: "Invalid data" })),
        ),
      );

      const createRequest = createPipelineConfigurationCreate();
      await expect(pipelineService.createPipeline(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("updatePipeline", () => {
    it("updates and returns pipeline", async () => {
      const mockPipeline = createPipelineConfiguration({
        id: "p-123",
        title: "Updated",
        pipeline: "pipe",
      });

      server.use(rest.put("*/api/pipelines/p-123", (req, res, ctx) => res(ctx.json(mockPipeline))));

      const updateRequest = createPipelineConfigurationUpdate({ title: "Updated" });
      const result = await pipelineService.updatePipeline("p-123", updateRequest);

      expect(result.id).toBe("p-123");
    });

    it("throws ApiError on 404 when updating non-existent pipeline", async () => {
      server.use(
        rest.put("*/api/pipelines/not-found", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Not found" })),
        ),
      );

      const updateRequest = createPipelineConfigurationUpdate();
      await expect(
        pipelineService.updatePipeline("not-found", updateRequest),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deletePipeline", () => {
    it("deletes pipeline successfully", async () => {
      server.use(rest.delete("*/api/pipelines/p-123", (req, res, ctx) => res(ctx.status(204))));

      await expect(pipelineService.deletePipeline("p-123")).resolves.toBeDefined();
    });

    it("throws ApiError on 404 when deleting non-existent pipeline", async () => {
      server.use(
        rest.delete("*/api/pipelines/not-found", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Not found" })),
        ),
      );

      await expect(pipelineService.deletePipeline("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("executePipeline", () => {
    it("executes pipeline and returns execution result", async () => {
      const mockExecution = createExecution({ pipeline_config_id: "p-123", status: "success" });

      server.use(
        rest.post("*/api/pipelines/p-123/execute", (req, res, ctx) => res(ctx.json(mockExecution))),
      );

      const result = await pipelineService.executePipeline("p-123", "input");

      expect(result.status).toBe("success");
    });

    it("throws ApiError on 400 for empty input text", async () => {
      server.use(
        rest.post("*/api/pipelines/p-123/execute", (req, res, ctx) =>
          res(ctx.status(400), ctx.json({ detail: "Empty input" })),
        ),
      );

      await expect(pipelineService.executePipeline("p-123", "")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 504 for pipeline timeout", async () => {
      server.use(
        rest.post("*/api/pipelines/p-123/execute", (req, res, ctx) =>
          res(ctx.status(504), ctx.json({ detail: "Timeout" })),
        ),
      );

      await expect(pipelineService.executePipeline("p-123", "text")).rejects.toMatchObject({
        name: "ApiError",
        status: 504,
      });
    });
  });

  describe("getPipelineExecutions", () => {
    it("returns list of pipeline executions", async () => {
      const mockExecutions = [
        createExecution({ id: "e1", pipeline_config_id: "p-123" }),
        createExecution({ id: "e2", pipeline_config_id: "p-123" }),
      ];

      server.use(
        rest.get("*/api/pipelines/p-123/executions", (req, res, ctx) =>
          res(ctx.json(mockExecutions)),
        ),
      );

      const result = await pipelineService.getPipelineExecutions("p-123");

      expect(result).toHaveLength(2);
    });

    it("throws ApiError on 404 for non-existent pipeline", async () => {
      server.use(
        rest.get("*/api/pipelines/not-found/executions", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Not found" })),
        ),
      );

      await expect(pipelineService.getPipelineExecutions("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});
