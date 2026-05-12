/**
 * Grounding Workflow Types
 *
 * TEMPORARY PLACEHOLDER - These types will be replaced with auto-generated types from the OpenAPI spec
 * once the backend implements the grounding workflow endpoints and updates the OpenAPI documentation.
 *
 * When the backend schema is finalized:
 * 1. Run `/local-server/scripts/update_api_specs.py` to update the OpenAPI spec
 * 2. Run `npm run generate-types` in /ux to regenerate types from the spec
 * 3. Remove this file and update imports in reference.ts to use generated types from @/api/types
 */

export interface GroundingWorkflowResponse {
  id: string;
  title: string;
  description?: string;
  source: string;
  class_scope: string[];
  status: "active" | "inactive" | "error";
  last_run?: string;
  last_run_record_count?: number;
}

export interface GroundingWorkflowCreate {
  title: string;
  source: string;
  class_scope: string[];
}

export interface GroundingWorkflowUpdate {
  title?: string;
  source?: string;
  class_scope?: string[];
  status?: "active" | "inactive" | "error";
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: "success" | "failed" | "running";
  record_count: number;
  timestamp: string;
  error_message?: string;
}
