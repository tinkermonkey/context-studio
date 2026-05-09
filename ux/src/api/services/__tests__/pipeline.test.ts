/**
 * Unit tests for PipelineService using MSW to mock HTTP responses.
 * Tests verify pipeline CRUD operations and execution management.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { pipelineService } from "../pipeline";

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
      const mockPipelines: any = [
        { id: "p-1", title: "Pipeline 1", pipeline: "pipeline_1", provider: "openai", model: "gpt-4", system_prompt: "You are helpful", user_prompt: "Analyze", version: 1, enabled: true, created_at: "2025-05-09T12:00:00Z", last_updated: "2025-05-09T12:00:00Z" },
        { id: "p-2", title: "Pipeline 2", pipeline: "pipeline_2", provider: "openai", model: "gpt-4", system_prompt: "You are helpful", user_prompt: "Analyze", version: 1, enabled: true, created_at: "2025-05-09T12:00:00Z", last_updated: "2025-05-09T12:00:00Z" },
      ];

      server.use(
        rest.get("*/api/pipelines", (req, res, ctx) => res(ctx.json(mockPipelines)))
      );

      const result = await pipelineService.listPipelines();

      expect(result).toHaveLength(2);
      expect(result[0].title).toBe("Pipeline 1");
    });

    it("throws ApiError on 500 from listPipelines", async () => {
      server.use(
        rest.get("*/api/pipelines", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Failed to list pipelines" }))
        )
      );

      await expect(pipelineService.listPipelines()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getPipeline", () => {
    it("returns pipeline by ID", async () => {
      const mockPipeline: any = { id: "p-123", title: "Pipeline", pipeline: "pipe", provider: "openai", model: "gpt-4", system_prompt: "You are helpful", user_prompt: "Analyze", version: 1, enabled: true, created_at: "2025-05-09T12:00:00Z", last_updated: "2025-05-09T12:00:00Z" };

      server.use(
        rest.get("*/api/pipelines/p-123", (req, res, ctx) =>
          res(ctx.json(mockPipeline))
        )
      );

      const result = await pipelineService.getPipeline("p-123");

      expect(result.title).toBe("Pipeline");
    });

    it("throws ApiError on 404 for non-existent pipeline", async () => {
      server.use(
        rest.get("*/api/pipelines/not-found", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Pipeline not found" }))
        )
      );

      await expect(
        pipelineService.getPipeline("not-found")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createPipeline", () => {
    it("creates and returns new pipeline", async () => {
      const mockPipeline: any = { id: "p-999", title: "New", pipeline: "new", provider: "openai", model: "gpt-4", system_prompt: "help", user_prompt: "analyze", version: 1, enabled: true, created_at: "2025-05-09T12:00:00Z", last_updated: "2025-05-09T12:00:00Z" };

      server.use(
        rest.post("*/api/pipelines", (req, res, ctx) =>
          res(ctx.json(mockPipeline))
        )
      );

      const result = await pipelineService.createPipeline({
        pipeline: "new",
        title: "New",
        provider: "openai",
        model: "gpt-4",
        system_prompt: "help",
        user_prompt: "analyze",
        enabled: true,
      } as any);

      expect(result.id).toBe("p-999");
    });

    it("throws ApiError on 400 for invalid pipeline data", async () => {
      server.use(
        rest.post("*/api/pipelines", (req, res, ctx) =>
          res(ctx.status(400), ctx.json({ detail: "Invalid data" }))
        )
      );

      await expect(
        pipelineService.createPipeline({} as any)
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("updatePipeline", () => {
    it("updates and returns pipeline", async () => {
      const mockPipeline: any = { id: "p-123", title: "Updated", pipeline: "pipe", provider: "openai", model: "gpt-4", system_prompt: "help", user_prompt: "analyze", version: 1, enabled: true, created_at: "2025-05-09T12:00:00Z", last_updated: "2025-05-09T12:00:00Z" };

      server.use(
        rest.put("*/api/pipelines/p-123", (req, res, ctx) =>
          res(ctx.json(mockPipeline))
        )
      );

      const result = await pipelineService.updatePipeline("p-123", {} as any);

      expect(result.id).toBe("p-123");
    });

    it("throws ApiError on 404 when updating non-existent pipeline", async () => {
      server.use(
        rest.put("*/api/pipelines/not-found", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Not found" }))
        )
      );

      await expect(
        pipelineService.updatePipeline("not-found", {} as any)
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deletePipeline", () => {
    it("deletes pipeline successfully", async () => {
      server.use(
        rest.delete("*/api/pipelines/p-123", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        pipelineService.deletePipeline("p-123")
      ).resolves.toBeDefined();
    });

    it("throws ApiError on 404 when deleting non-existent pipeline", async () => {
      server.use(
        rest.delete("*/api/pipelines/not-found", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Not found" }))
        )
      );

      await expect(
        pipelineService.deletePipeline("not-found")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("executePipeline", () => {
    it("executes pipeline and returns execution result", async () => {
      const mockExecution: any = { id: "exec-1", pipeline_config_id: "p-123", output_text: "result", provider: "openai", model: "gpt-4", tokens_in: 100, tokens_out: 50, duration_ms: 500, status: "success", timestamp: "2025-05-09T12:00:00Z" };

      server.use(
        rest.post("*/api/pipelines/p-123/execute", (req, res, ctx) =>
          res(ctx.json(mockExecution))
        )
      );

      const result = await pipelineService.executePipeline("p-123", "input");

      expect(result.status).toBe("success");
    });

    it("throws ApiError on 400 for empty input text", async () => {
      server.use(
        rest.post("*/api/pipelines/p-123/execute", (req, res, ctx) =>
          res(ctx.status(400), ctx.json({ detail: "Empty input" }))
        )
      );

      await expect(
        pipelineService.executePipeline("p-123", "")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 504 for pipeline timeout", async () => {
      server.use(
        rest.post("*/api/pipelines/p-123/execute", (req, res, ctx) =>
          res(ctx.status(504), ctx.json({ detail: "Timeout" }))
        )
      );

      await expect(
        pipelineService.executePipeline("p-123", "text")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 504,
      });
    });
  });

  describe("getPipelineExecutions", () => {
    it("returns list of pipeline executions", async () => {
      const mockExecutions: any = [
        { id: "e1", pipeline_config_id: "p-123", output_text: "r", provider: "openai", model: "gpt-4", tokens_in: 100, tokens_out: 50, duration_ms: 500, status: "success", timestamp: "2025-05-09T12:00:00Z" },
        { id: "e2", pipeline_config_id: "p-123", output_text: "r", provider: "openai", model: "gpt-4", tokens_in: 100, tokens_out: 50, duration_ms: 500, status: "success", timestamp: "2025-05-09T12:00:00Z" },
      ];

      server.use(
        rest.get("*/api/pipelines/p-123/executions", (req, res, ctx) =>
          res(ctx.json(mockExecutions))
        )
      );

      const result = await pipelineService.getPipelineExecutions("p-123");

      expect(result).toHaveLength(2);
    });

    it("throws ApiError on 404 for non-existent pipeline", async () => {
      server.use(
        rest.get("*/api/pipelines/not-found/executions", (req, res, ctx) =>
          res(ctx.status(404), ctx.json({ detail: "Not found" }))
        )
      );

      await expect(
        pipelineService.getPipelineExecutions("not-found")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});
