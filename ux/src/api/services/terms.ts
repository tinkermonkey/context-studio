/**
 * Terms Service
 * 
 * Service for managing term entities
 */

import { BaseService, ListParams, FindParams } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type TermOut = components['schemas']['TermOut'];
export type TermCreate = components['schemas']['TermCreate'];
export type TermUpdate = components['schemas']['TermUpdate'];
export type FindTermResult = components['schemas']['FindTermResult'];

export interface TermListParams extends ListParams {
  domain_id?: string;
  layer_id?: string;
  parent_term_id?: string;
  sort?: 'title' | 'created_at';
}

export interface TermFindParams extends FindParams {
  query: string;
}

export class TermService extends BaseService {
  /**
   * List all terms
   */
  async list(params?: TermListParams): Promise<TermOut[]> {
    return this.getResource<TermOut[]>(ENDPOINTS.TERMS + '/', params);
  }

  /**
   * Get a specific term by ID
   */
  async get(id: string): Promise<TermOut> {
    return this.getResource<TermOut>(`${ENDPOINTS.TERMS}/${id}`);
  }

  /**
   * Create a new term
   */
  async create(data: TermCreate): Promise<TermOut> {
    return this.postResource<TermOut>(ENDPOINTS.TERMS + '/', data);
  }

  /**
   * Update an existing term
   */
  async update(id: string, data: TermUpdate): Promise<TermOut> {
    return this.putResource<TermOut>(`${ENDPOINTS.TERMS}/${id}`, data);
  }

  /**
   * Delete a term
   */
  async delete(id: string): Promise<void> {
    return this.deleteResource<void>(`${ENDPOINTS.TERMS}/${id}`);
  }

  /**
   * Find terms using semantic search
   */
  async find(params: TermFindParams): Promise<FindTermResult[]> {
    return this.postResource<FindTermResult[]>(`${ENDPOINTS.TERMS}/find`, params);
  }
}

// Export singleton instance
export const termService = new TermService();
