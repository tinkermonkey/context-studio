/**
 * Interchange Type Definitions
 *
 * Type definitions for import/export operations (interchange)
 * Generated types are imported from the OpenAPI spec where available
 */

import type { components } from "@/api/client/types";

/**
 * SerializationScope - Scope parameters for serialization operations.
 * Describes what should be exported or imported.
 */
export type SerializationScope =
  components["schemas"]["SerializationScopeResponse"];

/**
 * SerializationScopeResponse - Describes what was serialized.
 */
export type SerializationScopeResponse =
  components["schemas"]["SerializationScopeResponse"];

/**
 * ResolutionRecord - Resolution applied to a conflict during import.
 */
export type ResolutionRecord =
  components["schemas"]["ResolutionRecordResponse"];

/**
 * ChangeEvent - Change event associated with an import run.
 */
export type ChangeEvent =
  components["schemas"]["InterchangeChangeEventResponse"];

/**
 * ChangeEventResponse - Response containing change event data.
 */
export type ChangeEventResponse =
  components["schemas"]["InterchangeChangeEventResponse"];

/**
 * ImportRunResponse - Response containing import run data.
 */
export type ImportRunResponse = components["schemas"]["ImportRunResponse"];

/**
 * ImportRunListResponse - Paginated list of import runs.
 * Uses generic ListResponse pattern.
 */
export type ImportRunListResponse =
  components["schemas"]["ListResponse_ImportRunResponse_"];

/**
 * ChangeEventListResponse - Paginated list of change events.
 * Uses generic ListResponse pattern.
 */
export type ChangeEventListResponse =
  components["schemas"]["ListResponse_InterchangeChangeEventResponse_"];

/**
 * Resolution strategy for import conflicts.
 */
export type ResolutionKind =
  | "skip"
  | "overwrite"
  | "merge"
  | "rename"
  | "abort";

/**
 * Incoming entity from import file.
 *
 * Shape varies by serialization format (SKOS, OWL, GraphML),
 * but the following fields are always extracted and available:
 * - id: Unique identifier for deduplication and keying
 * - title: Display label
 *
 * Additional fields (description, properties, etc.) depend on source format.
 */
export interface IncomingEntity {
  id: string;
  title: string;
  [key: string]: unknown;
}

/**
 * ImportConflict - Conflict detected during import dry-run.
 * This is generated from the OpenAPI spec.
 */
export type ImportConflict = components["schemas"]["ImportConflictResponse"];

/**
 * ImportPlanResponse - Result of an import dry-run, describing what would be imported.
 * This is generated from the OpenAPI spec.
 */
export type ImportPlanResponse = components["schemas"]["ImportPlanResponse"];

/**
 * Type guards and narrowing utilities for weak generated types.
 *
 * The generated OpenAPI types use `unknown` for fields that should be typed.
 * These utilities provide type-safe narrowing.
 */

/**
 * Narrow an ImportConflict's incoming field to the expected IncomingEntity type.
 * The generated type uses `unknown` but we know it has id and title from the backend.
 */
export function getIncomingEntity(conflict: ImportConflict): IncomingEntity {
  const incoming = conflict.incoming as IncomingEntity;
  return incoming;
}

/**
 * Get the default resolution for a conflict, with null-safety.
 * The generated type may have undefined but should always have a default.
 */
export function getDefaultResolution(conflict: ImportConflict): ResolutionKind {
  // Cast to string to access the value, then validate it's a valid ResolutionKind
  const resolution = conflict.default_resolution as ResolutionKind;
  return resolution ?? "skip"; // Fallback to skip if somehow undefined
}

/**
 * Status of an import run.
 */
export type ImportRunStatus =
  | "pending"
  | "committed"
  | "failed"
  | "rolled_back";

/**
 * Result of committing an import run.
 */
export type ImportRunCommitResponse = ImportRunResponse;

/**
 * Import run with change events.
 */
export type ImportRun = ImportRunResponse;

/**
 * Query parameters for listing import runs.
 */
export interface ImportRunListParams {
  offset?: number;
  limit?: number;
  status?: ImportRunStatus;
}

/**
 * Query parameters for listing change events.
 */
export interface ChangeEventListParams {
  offset?: number;
  limit?: number;
  entity_type?: string;
  change_type?: string;
}
