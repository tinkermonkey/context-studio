/**
 * Layers Service
 * 
 * Service for managing layer entities
 */

import { BaseService, ListParams, FindParams, PaginatedResponse } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type LayerOut = components['schemas']['LayerOut'];
export type LayerCreate = components['schemas']['LayerCreate'];
export type LayerUpdate = components['schemas']['LayerUpdate'];
export type FindLayerResult = components['schemas']['FindLayerResult'];
export type PaginatedLayersResponse = components['schemas']['PaginatedLayersResponse'];

export interface LayerListParams extends ListParams {
  sort?: 'title' | 'created_at';
}

export interface LayerFindParams extends FindParams {
  query: string;
}

export class LayerService extends BaseService {
  /**
   * List layers with optional pagination
   * If no limit is specified, loads all layers across multiple pages
   */
  async list(params?: LayerListParams): Promise<LayerOut[]> {
    const url = ENDPOINTS.LAYERS + '/';
    
    // If limit is explicitly set, use single page request
    if (params?.limit !== undefined) {
      return this.getPage<LayerOut>(url, params);
    }
    
    // Otherwise, load all layers across all pages
    return this.getAllPaginated<LayerOut>(url, params);
  }

  /**
   * List a specific page of layers
   */
  async listPage(params?: LayerListParams): Promise<LayerOut[]> {
    return this.getPage<LayerOut>(ENDPOINTS.LAYERS + '/', params);
  }

  /**
   * List a specific page of layers with pagination metadata
   */
  async listPageWithMetadata(params?: LayerListParams): Promise<PaginatedResponse<LayerOut>> {
    return this.getPaginatedResponse<LayerOut>(ENDPOINTS.LAYERS + '/', params);
  }

  /**
   * Get a specific layer by ID
   */
  async get(id: string): Promise<LayerOut> {
    return this.getResource<LayerOut>(`${ENDPOINTS.LAYERS}/${id}`);
  }

  /**
   * Create a new layer
   */
  async create(data: LayerCreate): Promise<LayerOut> {
    return this.postResource<LayerOut>(ENDPOINTS.LAYERS + '/', data);
  }

  /**
   * Update an existing layer
   */
  async update(id: string, data: LayerUpdate): Promise<LayerOut> {
    return this.putResource<LayerOut>(`${ENDPOINTS.LAYERS}/${id}`, data);
  }

  /**
   * Delete a layer
   */
  async delete(id: string): Promise<void> {
    return this.deleteResource<void>(`${ENDPOINTS.LAYERS}/${id}`);
  }

  /**
   * Find layers using semantic search
   */
  async find(params: LayerFindParams): Promise<FindLayerResult[]> {
    return this.postResource<FindLayerResult[]>(`${ENDPOINTS.LAYERS}/find`, params);
  }
}

// Export singleton instance
export const layerService = new LayerService();
