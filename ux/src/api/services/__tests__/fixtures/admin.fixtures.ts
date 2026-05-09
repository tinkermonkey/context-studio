/**
 * Test fixtures for AdminService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

// ============================================================================
// Health & Metrics Fixtures
// ============================================================================

export function createSystemHealth(
  overrides?: Partial<components["schemas"]["SystemHealthResponse"]>
): components["schemas"]["SystemHealthResponse"] {
  return {
    status: "healthy",
    database_connected: true,
    nlp_pipeline_ready: true,
    embedding_model_loaded: true,
    uptime_seconds: 1234,
    checked_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createDatabaseHealth(
  overrides?: Partial<components["schemas"]["DatabaseHealthResponse"]>
): components["schemas"]["DatabaseHealthResponse"] {
  return {
    connected: true,
    ...overrides,
  };
}

export function createServiceMetrics(
  overrides?: Partial<components["schemas"]["ServiceMetricsResponse"]>
): components["schemas"]["ServiceMetricsResponse"] {
  return {
    uptime_seconds: 1234,
    ...overrides,
  };
}

export function createBackgroundTaskSummary(
  overrides?: Partial<components["schemas"]["BackgroundTaskSummaryResponse"]>
): components["schemas"]["BackgroundTaskSummaryResponse"] {
  return {
    total: 10,
    by_status: {
      running: 2,
      completed: 8,
      failed: 0,
    },
    ...overrides,
  };
}

// ============================================================================
// Configuration Fixtures
// ============================================================================

export function createAppConfiguration(
  overrides?: Partial<components["schemas"]["AppConfigurationResponse"]>
): components["schemas"]["AppConfigurationResponse"] {
  return {
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
      vector_store: {
        type: "sqlite",
        path: "local.db",
      },
    },
    ...overrides,
  };
}

export function createConfigSectionUpdateRequest(
  overrides?: Partial<components["schemas"]["ConfigSectionUpdateRequest"]>
): components["schemas"]["ConfigSectionUpdateRequest"] {
  return {
    updates: {
      model: "sentence-transformers/all-mpnet-base-v2",
    },
    ...overrides,
  };
}

// ============================================================================
// Background Task Fixtures
// ============================================================================

export function createBackgroundTask(
  overrides?: Partial<components["schemas"]["BackgroundTaskResponse"]>
): components["schemas"]["BackgroundTaskResponse"] {
  return {
    id: "task-123",
    name: "import_reference_data",
    status: "running",
    created_at: new Date().toISOString(),
    started_at: new Date().toISOString(),
    completed_at: null,
    error: null,
    ...overrides,
  };
}

export function createBackgroundTaskArray(
  count: number = 3
): components["schemas"]["BackgroundTaskResponse"][] {
  return Array.from({ length: count }, (_, i) =>
    createBackgroundTask({
      id: `task-${i + 1}`,
      name:
        i % 2 === 0 ? "import_reference_data" : "sync_external_sources",
      status: i === 0 ? "running" : "completed",
    })
  );
}
