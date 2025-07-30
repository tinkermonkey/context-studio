/**
 * Datasets Service
 * 
 * Service for managing dataset entities and operations
 */

import { BaseService } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type DatasetResponse = components['schemas']['DatasetResponse'];
export type CreateDatasetRequest = components['schemas']['CreateDatasetRequest'];
export type AddExistingDatasetRequest = components['schemas']['AddExistingDatasetRequest'];
export type UpdateDatasetDirectoryRequest = components['schemas']['UpdateDatasetDirectoryRequest'];
export type ActionLogResponse = components['schemas']['ActionLogResponse'];
export type ActionLogEntry = components['schemas']['ActionLogEntry'];

export class DatasetService extends BaseService {
  /**
   * List all datasets
   */
  async list(): Promise<DatasetResponse[]> {
    return this.getResource<DatasetResponse[]>(ENDPOINTS.DATASETS);
  }

  /**
   * Get a specific dataset by ID
   */
  async get(id: string): Promise<DatasetResponse> {
    return this.getResource<DatasetResponse>(`${ENDPOINTS.DATASETS}/${id}`);
  }

  /**
   * Create a new dataset
   */
  async create(data: CreateDatasetRequest): Promise<DatasetResponse> {
    return this.postResource<DatasetResponse>(ENDPOINTS.DATASETS, data);
  }

  /**
   * Delete a dataset
   */
  async delete(id: string): Promise<void> {
    return this.deleteResource<void>(`${ENDPOINTS.DATASETS}/${id}`);
  }

  /**
   * Get the currently active dataset
   */
  async getActive(): Promise<DatasetResponse> {
    return this.getResource<DatasetResponse>(`${ENDPOINTS.DATASETS}/active`);
  }

  /**
   * Activate a dataset
   */
  async activate(id: string): Promise<void> {
    return this.postResource<void>(`${ENDPOINTS.DATASETS}/${id}/activate`, {});
  }

  /**
   * Forget a dataset (remove from inventory but keep file)
   */
  async forget(id: string): Promise<void> {
    return this.postResource<void>(`${ENDPOINTS.DATASETS}/${id}/forget`, {});
  }

  /**
   * Add an existing dataset file to the inventory
   */
  async addExisting(data: AddExistingDatasetRequest): Promise<DatasetResponse> {
    return this.postResource<DatasetResponse>(`${ENDPOINTS.DATASETS}/add-existing`, data);
  }

  /**
   * Get the datasets directory path
   */
  async getDirectory(): Promise<{ datasets_directory: string }> {
    return this.getResource<{ datasets_directory: string }>(`${ENDPOINTS.DATASETS}/directory`);
  }

  /**
   * Update the datasets directory path
   */
  async updateDirectory(data: UpdateDatasetDirectoryRequest): Promise<{ success: boolean; message: string }> {
    return this.postResource<{ success: boolean; message: string }>(`${ENDPOINTS.DATASETS}/directory`, data);
  }

  /**
   * Get startup info (which dataset will be loaded on server startup)
   */
  async getStartupInfo(): Promise<{ dataset_id?: string; dataset_title?: string }> {
    return this.getResource<{ dataset_id?: string; dataset_title?: string }>(`${ENDPOINTS.DATASETS}/startup-info`);
  }

  /**
   * Get dataset action log
   */
  async getActionLog(days?: number): Promise<ActionLogResponse> {
    const params = days ? `?days=${days}` : '';
    return this.getResource<ActionLogResponse>(`${ENDPOINTS.DATASETS}/action-log${params}`);
  }
}

// Export singleton instance
export const datasetService = new DatasetService();
