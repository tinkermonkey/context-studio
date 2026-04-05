/**
 * Datasets Service
 *
 * Service for managing dataset entities and operations
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  DatasetResponse,
  CreateDatasetRequest,
  AddExistingDatasetRequest,
  UpdateDatasetDirectoryRequest,
  ActionLogResponse,
  ActionLogEntry,
} from "./missingTypes";

// Re-export types for use in hooks and components
export type {
  DatasetResponse,
  CreateDatasetRequest,
  AddExistingDatasetRequest,
  UpdateDatasetDirectoryRequest,
  ActionLogResponse,
  ActionLogEntry,
};

export interface ActionLogParams extends Record<string, unknown> {
  days?: number;
}

export class DatasetService extends BaseService {
  /**
   * List all datasets
   */
  async list(): Promise<DatasetResponse[]> {
    return this.withErrorContext(
      () => this.getResource<DatasetResponse[]>(ENDPOINTS.DATASETS),
      "list datasets",
    );
  }

  /**
   * Get a specific dataset by ID
   */
  async get(id: string): Promise<DatasetResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Dataset ID");
      return this.getResource<DatasetResponse>(`${ENDPOINTS.DATASETS}/${id}`);
    }, "get dataset");
  }

  /**
   * Create a new dataset
   */
  async create(data: CreateDatasetRequest): Promise<DatasetResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Dataset data");
      this.validateRequired(data.title, "Dataset title");
      this.validateRequired(data.filename, "Dataset filename");
      this.sanitizeString((data.title as unknown as string) || '', "Dataset title", 255);
      this.sanitizeString((data.filename as unknown as string) || '', "Dataset filename", 255);

      return this.postResource<DatasetResponse>(ENDPOINTS.DATASETS, data);
    }, "create dataset");
  }

  /**
   * Delete a dataset
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Dataset ID");
      return this.deleteResource<void>(`${ENDPOINTS.DATASETS}/${id}`);
    }, "delete dataset");
  }

  /**
   * Get the currently active dataset
   */
  async getActive(): Promise<DatasetResponse> {
    return this.withErrorContext(
      () => this.getResource<DatasetResponse>(`${ENDPOINTS.DATASETS}/active`),
      "get active dataset",
    );
  }

  /**
   * Activate a dataset
   */
  async activate(id: string): Promise<void> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Dataset ID");
      return this.postResource<void>(`${ENDPOINTS.DATASETS}/${id}/activate`);
    }, "activate dataset");
  }

  /**
   * Forget a dataset (remove from inventory but keep file)
   */
  async forget(id: string): Promise<void> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Dataset ID");
      return this.postResource<void>(`${ENDPOINTS.DATASETS}/${id}/forget`);
    }, "forget dataset");
  }

  /**
   * Add an existing dataset file to the inventory
   */
  async addExisting(data: AddExistingDatasetRequest): Promise<DatasetResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Dataset data");
      this.validateRequired(data.title, "Dataset title");
      this.validateRequired(data.file_path, "Dataset file path");
      this.sanitizeString((data.title as unknown as string) || '', "Dataset title", 255);
      this.sanitizeString((data.file_path as unknown as string) || '', "Dataset file path", 1000);

      return this.postResource<DatasetResponse>(
        `${ENDPOINTS.DATASETS}/add-existing`,
        data,
      );
    }, "add existing dataset");
  }

  /**
   * Get the datasets directory path
   */
  async getDirectory(): Promise<unknown> {
    return this.withErrorContext(
      () => this.getResource<unknown>(`${ENDPOINTS.DATASETS}/directory`),
      "get datasets directory",
    );
  }

  /**
   * Update the datasets directory path
   */
  async updateDirectory(
    data: UpdateDatasetDirectoryRequest,
  ): Promise<{ success: boolean; message: string }> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Directory data");
      this.validateRequired(data.datasets_directory, "Datasets directory");
      this.sanitizeString((data.datasets_directory as unknown as string) || '', "Datasets directory", 1000);

      return this.postResource<{ success: boolean; message: string }>(
        `${ENDPOINTS.DATASETS}/directory`,
        data,
      );
    }, "update datasets directory");
  }

  /**
   * Get startup info (which dataset will be loaded on server startup)
   */
  async getStartupInfo(): Promise<unknown> {
    return this.withErrorContext(
      () => this.getResource<unknown>(`${ENDPOINTS.DATASETS}/startup-info`),
      "get startup info",
    );
  }

  /**
   * Get dataset action log
   */
  async getActionLog(params?: ActionLogParams): Promise<ActionLogResponse> {
    return this.withErrorContext(
      () =>
        this.getResource<ActionLogResponse>(
          `${ENDPOINTS.DATASETS}/action-log`,
          params,
        ),
      "get action log",
    );
  }
}

// Export singleton instance
export const datasetService = new DatasetService();
