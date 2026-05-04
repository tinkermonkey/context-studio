/**
 * Interchange Service
 *
 * Service for managing data interchange operations (import/export)
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import {
  SerializationScope,
  ImportPlanResponse,
  ImportRunCommitResponse,
  ImportRun,
  ChangeEvent,
  ImportRunListParams,
  ChangeEventListParams,
  ResolutionRecord,
  ImportConflict,
  ResolutionKind,
} from "../types/interchange";

// Re-export types for backward compatibility
export type {
  SerializationScope,
  ImportConflict,
  ResolutionKind,
  ResolutionRecord,
  ImportPlanResponse,
  ImportRunCommitResponse,
  ImportRun,
  ChangeEvent,
  ImportRunListParams,
  ChangeEventListParams,
};

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
   * @param resolutions Optional conflict resolutions to apply when committing (dryRun=false)
   * @returns Import plan or committed run
   */
  async importFile(
    format: string,
    file: File,
    dryRun: boolean = true,
    resolutions?: ResolutionRecord[],
  ): Promise<ImportPlanResponse | ImportRunCommitResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(format, "format");
      this.validateRequired(file, "file");

      const formData = new FormData();
      formData.append("format", format);
      formData.append("file", file);
      formData.append("dry_run", String(dryRun));

      if (!dryRun && resolutions) {
        formData.append("resolutions", JSON.stringify(resolutions));
      }

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

      return this.getPage<ImportRun>(ENDPOINTS.INTERCHANGE.RUNS, queryParams);
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
