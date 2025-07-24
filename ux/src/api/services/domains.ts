/**
 * Domains Service
 * 
 * Service for managing domain entities
 */

import { BaseService, ListParams, FindParams, PaginatedResponse } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type DomainOut = components['schemas']['DomainOut'];
export type DomainCreate = components['schemas']['DomainCreate'];
export type DomainUpdate = components['schemas']['DomainUpdate'];
export type FindDomainResult = components['schemas']['FindDomainResult'];
export type PaginatedDomainsResponse = components['schemas']['PaginatedDomainsResponse'];

export interface DomainListParams extends ListParams {
  layer_id?: string;
  sort?: 'title' | 'created_at';
}

export interface DomainFindParams extends FindParams {
  query: string;
}

export class DomainService extends BaseService {
  /**
   * List domains with optional pagination
   * If no limit is specified, loads all domains across multiple pages
   */
  async list(params?: DomainListParams): Promise<DomainOut[]> {
    const url = ENDPOINTS.DOMAINS + '/';
    
    // If limit is explicitly set, use single page request
    if (params?.limit !== undefined) {
      return this.getPage<DomainOut>(url, params);
    }
    
    // Otherwise, load all domains across all pages
    return this.getAllPaginated<DomainOut>(url, params);
  }

  /**
   * List a specific page of domains
   */
  async listPage(params?: DomainListParams): Promise<DomainOut[]> {
    return this.getPage<DomainOut>(ENDPOINTS.DOMAINS + '/', params);
  }

  /**
   * List a specific page of domains with pagination metadata
   */
  async listPageWithMetadata(params?: DomainListParams): Promise<PaginatedResponse<DomainOut>> {
    return this.getPaginatedResponse<DomainOut>(ENDPOINTS.DOMAINS + '/', params);
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
