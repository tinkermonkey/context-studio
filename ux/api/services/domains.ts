/**
 * Domains Service
 * 
 * Service for managing domain entities
 */

import { BaseService, ListParams, FindParams } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
type DomainOut = components['schemas']['DomainOut'];
type DomainCreate = components['schemas']['DomainCreate'];
type DomainUpdate = components['schemas']['DomainUpdate'];
type FindDomainResult = components['schemas']['FindDomainResult'];

export interface DomainListParams extends ListParams {
  layer_id?: string;
  sort?: 'title' | 'created_at';
}

export interface DomainFindParams extends FindParams {
  query: string;
}

export class DomainService extends BaseService {
  /**
   * List all domains
   */
  async list(params?: DomainListParams): Promise<DomainOut[]> {
    return this.getResource<DomainOut[]>(ENDPOINTS.DOMAINS + '/', params);
  }

  /**
   * Get a specific domain by ID
   */
  async get(id: string): Promise<DomainOut> {
    return this.getResource<DomainOut>(`${ENDPOINTS.DOMAINS}/${id}`);
  }

  /**
   * Create a new domain
   */
  async create(data: DomainCreate): Promise<DomainOut> {
    return this.postResource<DomainOut>(ENDPOINTS.DOMAINS + '/', data);
  }

  /**
   * Update an existing domain
   */
  async update(id: string, data: DomainUpdate): Promise<DomainOut> {
    return this.putResource<DomainOut>(`${ENDPOINTS.DOMAINS}/${id}`, data);
  }

  /**
   * Delete a domain
   */
  async delete(id: string): Promise<void> {
    return this.deleteResource<void>(`${ENDPOINTS.DOMAINS}/${id}`);
  }

  /**
   * Find domains using semantic search
   */
  async find(params: DomainFindParams): Promise<FindDomainResult[]> {
    return this.postResource<FindDomainResult[]>(`${ENDPOINTS.DOMAINS}/find`, params);
  }
}

// Export singleton instance
export const domainService = new DomainService();
