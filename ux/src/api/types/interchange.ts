/**
 * Interchange Type Definitions
 *
 * Type definitions for import/export operations (interchange)
 */

/**
 * Scope parameters for serialization operations.
 * Describes what should be exported or imported.
 */
export interface SerializationScope {
  scope_type: "whole_graph" | "taxonomy" | "scheme" | "entity_set";
  taxonomy_id?: string;
  scheme_id?: string;
  include_descendants?: boolean;
  entity_ids?: string[];
}

/**
 * Conflict detected during import dry-run.
 */
export interface ImportConflict {
  match_kind: "external_reference" | "uuid" | "title";
  incoming: Record<string, unknown>;
  existing?: string;
  default_resolution: ResolutionKind;
  available_resolutions: ResolutionKind[];
}

/**
 * Resolution strategy for import conflicts.
 */
export type ResolutionKind = "skip" | "overwrite" | "merge" | "rename" | "abort";

/**
 * Resolution applied to a conflict during import.
 */
export interface ResolutionRecord {
  match_kind: "external_reference" | "uuid" | "title";
  entity_id: string;
  resolution_chosen: ResolutionKind;
}

/**
 * Result of an import dry-run, describing what would be imported.
 */
export interface ImportPlanResponse {
  conflicts: ImportConflict[];
  new_entity_count: number;
  import_run_id?: string;
  warnings: string[];
  source_hash?: string;
  scope?: SerializationScope;
}

/**
 * Status of an import run.
 */
export type ImportRunStatus = "pending" | "committed" | "failed" | "rolled_back";

/**
 * Result of committing an import run.
 */
export interface ImportRunCommitResponse {
  id: string;
  created_at: string;
  created_by?: string;
  format: string;
  source_uri?: string;
  source_hash: string;
  scope: SerializationScope;
  resolutions: ResolutionRecord[];
  affected_entity_ids: string[];
  status: ImportRunStatus;
}

/**
 * Import run with change events.
 */
export interface ImportRun {
  id: string;
  created_at: string;
  created_by?: string;
  format: string;
  source_uri?: string;
  source_hash: string;
  scope: SerializationScope;
  resolutions: ResolutionRecord[];
  affected_entity_ids: string[];
  status: ImportRunStatus;
}

/**
 * Change event associated with an import run.
 */
export interface ChangeEvent {
  id: string;
  timestamp: string;
  entity_id: string;
  entity_type: string;
  change_type: string;
  import_run_id?: string;
  details?: Record<string, unknown>;
}

export interface ImportRunListParams {
  offset?: number;
  limit?: number;
  status?: ImportRunStatus;
}

export interface ChangeEventListParams {
  offset?: number;
  limit?: number;
  entity_type?: string;
  change_type?: string;
}
