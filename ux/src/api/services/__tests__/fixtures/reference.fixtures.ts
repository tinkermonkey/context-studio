/**
 * Test fixtures for ReferenceService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";
import type {
  GroundingWorkflowResponse,
  GroundingWorkflowCreate,
  GroundingWorkflowUpdate,
  WorkflowRun,
} from "@/api/types/manual/grounding";

export function createReferenceSearchRequest(
  overrides?: Partial<components["schemas"]["ReferenceSearchRequest"]>,
): components["schemas"]["ReferenceSearchRequest"] {
  return {
    term: "artificial intelligence",
    limit: 10,
    sources: ["wikipedia", "dbpedia"],
    ...overrides,
  };
}

export function createReferenceSearchResponse(
  overrides?: Partial<components["schemas"]["ReferenceSearchResponseSchema"]>,
): components["schemas"]["ReferenceSearchResponseSchema"] {
  return {
    term: "artificial intelligence",
    results: [
      {
        uri: "https://en.wikipedia.org/wiki/Artificial_intelligence",
        label: "Artificial Intelligence",
        description: "The simulation of human intelligence",
        confidence: 1.0,
        source: "wikipedia",
      },
    ],
    sources_searched: ["wikipedia", "dbpedia"],
    total_results: 1,
    ...overrides,
  };
}

export function createReferenceStatusResponse(
  overrides?: Partial<components["schemas"]["ReferenceStatusResponseSchema"]>,
): components["schemas"]["ReferenceStatusResponseSchema"] {
  return {
    sources: [
      {
        name: "wikipedia",
        available: true,
      },
      {
        name: "dbpedia",
        available: true,
      },
    ],
    sources_available: 2,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}

export function createGroundingWorkflow(
  overrides?: Partial<GroundingWorkflowResponse>,
): GroundingWorkflowResponse {
  return {
    id: "workflow-123",
    title: "DBpedia Grounding",
    description: "Grounds entities using DBpedia",
    source: "dbpedia",
    class_scope: ["Entity", "Person", "Place"],
    status: "active",
    last_run: new Date().toISOString(),
    last_run_record_count: 42,
    ...overrides,
  };
}

export function createGroundingWorkflowCreate(
  overrides?: Partial<GroundingWorkflowCreate>,
): GroundingWorkflowCreate {
  return {
    title: "New Grounding Workflow",
    source: "wikipedia",
    class_scope: ["Entity"],
    ...overrides,
  };
}

export function createGroundingWorkflowUpdate(
  overrides?: Partial<GroundingWorkflowUpdate>,
): GroundingWorkflowUpdate {
  return {
    title: "Updated Workflow",
    status: "active",
    ...overrides,
  };
}

export function createWorkflowRun(
  overrides?: Partial<WorkflowRun>,
): WorkflowRun {
  return {
    id: "run-123",
    workflow_id: "workflow-123",
    status: "success",
    record_count: 100,
    timestamp: new Date().toISOString(),
    ...overrides,
  };
}
