/**
 * Unit tests for AdminService using MSW to mock HTTP responses.
 * Tests verify health checks, configuration management, and background tasks.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { adminService } from "../admin";
import {
  createSystemHealth,
  createDatabaseHealth,
  createServiceMetrics,
  createBackgroundTaskSummary,
  createAppConfiguration,
  createConfigSectionUpdateRequest,
  createBackgroundTask,
  createBackgroundTaskArray,
} from "./fixtures/admin.fixtures";

// Initialize MSW server for all tests
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

// ============================================================================
// Health & Metrics Tests
// ============================================================================

describe("AdminService - Health & Metrics", () => {
  describe("getHealth", () => {
    it("returns system health from GET /api/v1/admin/health", async () => {
      const mockHealth = createSystemHealth({
        status: "healthy",
      });

      server.use(http.get("*/api/v1/admin/health", () => HttpResponse.json(mockHealth)));

      const result = await adminService.getHealth();

      expect(result).toEqual(mockHealth);
      expect(result.status).toBe("healthy");
    });

    it("returns degraded status when services are unhealthy", async () => {
      const mockHealth = createSystemHealth({
        status: "degraded",
      });

      server.use(http.get("*/api/v1/admin/health", () => HttpResponse.json(mockHealth)));

      const result = await adminService.getHealth();

      expect(result.status).toBe("degraded");
    });

    it("throws ApiError on 500 from getHealth", async () => {
      server.use(
        http.get("*/api/v1/admin/health", () =>
          HttpResponse.json({
              detail: "Health check failed",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getHealth()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getDatabaseHealth", () => {
    it("returns database health from GET /api/v1/admin/health/database", async () => {
      const mockDbHealth = createDatabaseHealth({
        connected: true,
      });

      server.use(
        http.get("*/api/v1/admin/health/database", () => HttpResponse.json(mockDbHealth)),
      );

      const result = await adminService.getDatabaseHealth();

      expect(result).toEqual(mockDbHealth);
      expect(result.connected).toBe(true);
    });

    it("returns database disconnected when connection fails", async () => {
      const mockDbHealth = createDatabaseHealth({
        connected: false,
        issues: ["Connection timeout"],
      });

      server.use(
        http.get("*/api/v1/admin/health/database", () => HttpResponse.json(mockDbHealth)),
      );

      const result = await adminService.getDatabaseHealth();

      expect(result.connected).toBe(false);
      expect(result.issues).toBeDefined();
    });

    it("throws ApiError on 500 from getDatabaseHealth", async () => {
      server.use(
        http.get("*/api/v1/admin/health/database", () =>
          HttpResponse.json({
              detail: "Database health check failed",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getDatabaseHealth()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getServiceMetrics", () => {
    it("returns service metrics from GET /api/v1/admin/health/services", async () => {
      const mockMetrics = createServiceMetrics();

      server.use(
        http.get("*/api/v1/admin/health/services", () => HttpResponse.json(mockMetrics)),
      );

      const result = await adminService.getServiceMetrics();

      expect(result).toEqual(mockMetrics);
      expect(result.uptime_seconds).toBeGreaterThan(0);
    });

    it("includes available LLM providers", async () => {
      const mockMetrics = createServiceMetrics({
        llm_providers_available: ["openai", "anthropic"],
      });

      server.use(
        http.get("*/api/v1/admin/health/services", () => HttpResponse.json(mockMetrics)),
      );

      const result = await adminService.getServiceMetrics();

      expect(result.llm_providers_available).toBeDefined();
    });

    it("throws ApiError on 500 from getServiceMetrics", async () => {
      server.use(
        http.get("*/api/v1/admin/health/services", () =>
          HttpResponse.json({
              detail: "Could not retrieve service metrics",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getServiceMetrics()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getTaskSummary", () => {
    it("returns background task summary from GET /api/v1/admin/health/tasks", async () => {
      const mockSummary = createBackgroundTaskSummary({
        total: 15,
        by_status: {
          running: 3,
          completed: 12,
          failed: 0,
        },
      });

      server.use(
        http.get("*/api/v1/admin/health/tasks", () => HttpResponse.json(mockSummary)),
      );

      const result = await adminService.getTaskSummary();

      expect(result).toEqual(mockSummary);
      expect(result.total).toBe(15);
      expect(result.by_status?.running).toBe(3);
    });

    it("throws ApiError on 500 from getTaskSummary", async () => {
      server.use(
        http.get("*/api/v1/admin/health/tasks", () =>
          HttpResponse.json({
              detail: "Could not retrieve task summary",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getTaskSummary()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });
});

// ============================================================================
// Configuration Management Tests
// ============================================================================

describe("AdminService - Configuration Management", () => {
  describe("getConfig", () => {
    it("returns application configuration from GET /api/v1/admin/configuration", async () => {
      const mockConfig = createAppConfiguration();

      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(mockConfig)),
      );

      const result = await adminService.getConfig();

      expect(result).toEqual(mockConfig);
      expect(result.sections).toBeDefined();
    });

    it("includes all configuration sections", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          embeddings: {
            model: "sentence-transformers/all-MiniLM-L6-v2",
            dim: 384,
          },
          llm: {
            provider: "anthropic",
            model: "claude-3-sonnet",
            max_tokens: 4096,
          },
          vector_store: {
            type: "sqlite",
            path: "local.db",
          },
        },
      });

      server.use(
        http.get("*/api/v1/admin/configuration", () => HttpResponse.json(mockConfig)),
      );

      const result = await adminService.getConfig();

      expect(result.sections?.embeddings?.model).toContain("MiniLM");
      expect(result.sections?.llm?.provider).toBe("anthropic");
      expect(result.sections?.llm?.max_tokens).toBe(4096);
    });

    it("throws ApiError on 500 from getConfig", async () => {
      server.use(
        http.get("*/api/v1/admin/configuration", () =>
          HttpResponse.json({
              detail: "Could not load configuration",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getConfig()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("updateConfigSection", () => {
    it("updates configuration section from PATCH /api/v1/admin/configuration/:section", async () => {
      const updateRequest = createConfigSectionUpdateRequest({
        updates: {
          model: "gpt-4-turbo",
        },
      });
      const mockResponse = createAppConfiguration({
        sections: {
          llm: {
            provider: "openai",
            model: "gpt-4-turbo",
            max_tokens: 4096,
          },
        },
      });

      server.use(
        http.patch("*/api/v1/admin/configuration/llm", () =>
          HttpResponse.json(mockResponse),
        ),
      );

      const result = await adminService.updateConfigSection("llm", updateRequest);

      expect(result.sections?.llm?.model).toBe("gpt-4-turbo");
    });

    it("throws ApiError with 400 on updateConfigSection with invalid config", async () => {
      const updateRequest = createConfigSectionUpdateRequest({
        updates: {
          model: "invalid-model-that-does-not-exist",
        },
      });

      server.use(
        http.patch("*/api/v1/admin/configuration/llm", () =>
          HttpResponse.json({
              detail: "Invalid model specified",
            }, { status: 400 }),
        ),
      );

      await expect(adminService.updateConfigSection("llm", updateRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
        detail: expect.stringContaining("Invalid model"),
      });
    });

    it("throws ApiError with 404 on updateConfigSection with non-existent section", async () => {
      const updateRequest = createConfigSectionUpdateRequest();

      server.use(
        http.patch("*/api/v1/admin/configuration/non_existent_section", () =>
          HttpResponse.json({
              detail: "Configuration section not found",
            }, { status: 404 }),
        ),
      );

      await expect(
        adminService.updateConfigSection("non_existent_section", updateRequest),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("resetConfig", () => {
    it("resets configuration to defaults from POST /api/v1/admin/configuration/reset", async () => {
      const mockConfig = createAppConfiguration({
        sections: {
          embeddings: {
            model: "sentence-transformers/all-MiniLM-L6-v2",
            dim: 384,
          },
          llm: {
            provider: "openai",
            model: "gpt-4",
            max_tokens: 2048,
          },
        },
      });

      server.use(
        http.post("*/api/v1/admin/configuration/reset", () =>
          HttpResponse.json(mockConfig),
        ),
      );

      const result = await adminService.resetConfig();

      expect(result).toEqual(mockConfig);
    });

    it("throws ApiError on 500 from resetConfig", async () => {
      server.use(
        http.post("*/api/v1/admin/configuration/reset", () =>
          HttpResponse.json({
              detail: "Failed to reset configuration",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.resetConfig()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });
});

// ============================================================================
// Background Task Tests
// ============================================================================

describe("AdminService - Background Tasks", () => {
  describe("getBackgroundTasks", () => {
    it("returns array of background tasks from GET /api/v1/admin/tasks", async () => {
      const mockTasks = createBackgroundTaskArray(3);

      server.use(http.get("*/api/v1/admin/tasks", () => HttpResponse.json(mockTasks)));

      const result = await adminService.getBackgroundTasks();

      expect(Array.isArray(result)).toBe(true);
      expect(result).toHaveLength(3);
      expect(result[0].id).toBe("task-1");
    });

    it("returns empty array when no tasks exist", async () => {
      server.use(http.get("*/api/v1/admin/tasks", () => HttpResponse.json([])));

      const result = await adminService.getBackgroundTasks();

      expect(result).toHaveLength(0);
    });

    it("includes task details: id, name, status, timestamps", async () => {
      const mockTasks = [
        createBackgroundTask({
          id: "task-123",
          name: "import_reference_data",
          status: "running",
          started_at: new Date().toISOString(),
        }),
      ];

      server.use(http.get("*/api/v1/admin/tasks", () => HttpResponse.json(mockTasks)));

      const result = await adminService.getBackgroundTasks();

      expect(result[0].id).toBe("task-123");
      expect(result[0].name).toBe("import_reference_data");
      expect(result[0].status).toBe("running");
      expect(result[0].started_at).toBeDefined();
    });

    it("throws ApiError on 500 from getBackgroundTasks", async () => {
      server.use(
        http.get("*/api/v1/admin/tasks", () =>
          HttpResponse.json({
              detail: "Failed to retrieve tasks",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getBackgroundTasks()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getBackgroundTask", () => {
    it("returns single background task by ID from GET /api/v1/admin/tasks/:taskId", async () => {
      const mockTask = createBackgroundTask({
        id: "task-123",
        status: "running",
      });

      server.use(
        http.get("*/api/v1/admin/tasks/task-123", () => HttpResponse.json(mockTask)),
      );

      const result = await adminService.getBackgroundTask("task-123");

      expect(result).toEqual(mockTask);
      expect(result.id).toBe("task-123");
    });

    it("includes error message when task fails", async () => {
      const mockTask = createBackgroundTask({
        id: "task-fail",
        status: "failed",
        error: "Connection timeout",
      });

      server.use(
        http.get("*/api/v1/admin/tasks/task-fail", () => HttpResponse.json(mockTask)),
      );

      const result = await adminService.getBackgroundTask("task-fail");

      expect(result.status).toBe("failed");
      expect(result.error).toBe("Connection timeout");
    });

    it("throws ApiError with 404 on getBackgroundTask with non-existent ID", async () => {
      server.use(
        http.get("*/api/v1/admin/tasks/not-found", () =>
          HttpResponse.json({
              detail: "Task not found",
            }, { status: 404 }),
        ),
      );

      await expect(adminService.getBackgroundTask("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
        detail: expect.stringContaining("Task not found"),
      });
    });

    it("throws ApiError on 500 from getBackgroundTask", async () => {
      server.use(
        http.get("*/api/v1/admin/tasks/task-123", () =>
          HttpResponse.json({
              detail: "Failed to retrieve task",
            }, { status: 500 }),
        ),
      );

      await expect(adminService.getBackgroundTask("task-123")).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });
});
