/**
 * Interchange Service
 *
 * Service for managing data interchange operations (import/export)
 */

import { BaseService, ListParams } from "./base";
import { ENDPOINTS } from "../config";
import { apiLogger } from "../utils/logger";

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

export interface ImportRunListParams extends ListParams {
  status?: ImportRunStatus;
}

export interface ChangeEventListParams extends ListParams {
  entity_type?: string;
  change_type?: string;
}

/**
 * TODO: Types will be regenerated from OpenAPI spec once #658 (interchange routes)
 * is implemented. The above types match the domain contract and will be replaced
 * with auto-generated types from ux/src/api/client/types.ts when available.
 */

export class InterchangeService extends BaseService {
  /**
   * Export ontology data in the specified format
   * @param format Export format (skos, owl, graphml, etc.)
   * @param scope Scope of data to export
   * @returns Binary file as Blob
   */
  async exportFile(format: string, scope: SerializationScope): Promise<Blob> {
    return this.withErrorContext(async () => {
      this.validateRequired(format, "format");
      this.validateRequired(scope, "scope");

      const response = await this.client.request<Blob>({
        method: "POST",
        url: ENDPOINTS.INTERCHANGE.EXPORT,
        data: {
          format,
          scope,
        },
        responseType: "blob",
      });
      return response.data;
    }, "exportFile");
  }

  /**
   * Import ontology data from a file
   * @param format Import format (skos, owl, graphml, etc.)
   * @param file File to import
   * @param dryRun If true, returns plan without committing; if false, commits and returns run
   * @returns Import plan or committed run
   */
  async importFile(
    format: string,
    file: File,
    dryRun: boolean = true,
  ): Promise<ImportPlanResponse | ImportRunCommitResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(format, "format");
      this.validateRequired(file, "file");

      const formData = new FormData();
      formData.append("format", format);
      formData.append("file", file);
      formData.append("dry_run", String(dryRun));

      return this.request<ImportPlanResponse | ImportRunCommitResponse>({
        method: "POST",
        url: ENDPOINTS.INTERCHANGE.IMPORT,
        data: formData,
      });
    }, "importFile");
  }

  /**
   * List all import runs with pagination
   * @param params Pagination and filter parameters
   * @returns Paginated list of import runs
   */
  async listRuns(params?: ImportRunListParams): Promise<ImportRun[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.status !== undefined) queryParams.status = params.status;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<ImportRun>(
          ENDPOINTS.INTERCHANGE.RUNS,
          queryParams,
        );
      }

      return this.getPage<ImportRun>(
        ENDPOINTS.INTERCHANGE.RUNS,
        queryParams,
      );
    }, "listRuns");
  }

  /**
   * Get a specific import run by ID
   * @param id Import run ID
   * @returns Import run details
   */
  async getRun(id: string): Promise<ImportRun> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<ImportRun>(ENDPOINTS.INTERCHANGE.RUN(id));
    }, "getRun");
  }

  /**
   * Get change events associated with an import run
   * @param id Import run ID
   * @param params Pagination parameters
   * @returns Paginated list of change events
   */
  async getRunChangeEvents(
    id: string,
    params?: ChangeEventListParams,
  ): Promise<ChangeEvent[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.entity_type !== undefined)
        queryParams.entity_type = params.entity_type;
      if (params?.change_type !== undefined)
        queryParams.change_type = params.change_type;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<ChangeEvent>(
          ENDPOINTS.INTERCHANGE.RUN_CHANGE_EVENTS(id),
          queryParams,
        );
      }

      return this.getPage<ChangeEvent>(
        ENDPOINTS.INTERCHANGE.RUN_CHANGE_EVENTS(id),
        queryParams,
      );
    }, "getRunChangeEvents");
  }
}

export const interchangeService = new InterchangeService();
