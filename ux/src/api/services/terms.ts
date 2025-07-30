/**
 * Terms Service
 * 
 * Service for managing term entities
 */

import { BaseService, ListParams, FindParams, PaginatedResponse } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '@/api/types/openapi';

// Type aliases for better readability
export type TermOut = components['schemas']['TermOut'];
export type TermCreate = components['schemas']['TermCreate'];
export type TermUpdate = components['schemas']['TermUpdate'];
export type FindTermResult = components['schemas']['FindTermResult'];
export type PaginatedTermsResponse = components['schemas']['PaginatedTermsResponse'];

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
   * List terms with optional pagination
   * If no limit is specified, loads all terms across multiple pages
   */
  async list(params?: TermListParams): Promise<TermOut[]> {
    const url = ENDPOINTS.TERMS + '/';
    
    // If limit is explicitly set, use single page request
    if (params?.limit !== undefined) {
      return this.getPage<TermOut>(url, params);
    }
    
    // Otherwise, load all terms across all pages
    return this.getAllPaginated<TermOut>(url, params);
  }

  /**
   * List a specific page of terms
   */
  async listPage(params?: TermListParams): Promise<TermOut[]> {
    return this.getPage<TermOut>(ENDPOINTS.TERMS + '/', params);
  }

  /**
   * List a specific page of terms with pagination metadata
   */
  async listPageWithMetadata(params?: TermListParams): Promise<PaginatedResponse<TermOut>> {
    return this.getPaginatedResponse<TermOut>(ENDPOINTS.TERMS + '/', params);
  }

  /**
   * Get a specific term by ID
   */
  async get(id: string): Promise<TermOut> {
    return this.withErrorContext(
      () => {
        this.validateRequired(id, 'Term ID');
        return this.getResource<TermOut>(`${ENDPOINTS.TERMS}/${id}`);
      },
      'get term'
    );
  }

  /**
   * Create a new term
   */
  async create(data: TermCreate): Promise<TermOut> {
    return this.withErrorContext(
      () => {
        this.validateRequired(data, 'Term data');
        this.validateRequired(data.title, 'Term title');
        this.sanitizeString(data.title, 'Term title', 255);
        
        if (data.definition) {
          this.sanitizeString(data.definition, 'Term definition', 2000);
        }
        
        return this.postResource<TermOut>(ENDPOINTS.TERMS + '/', data);
      },
      'create term'
    );
  }

  /**
   * Update an existing term
   */
  async update(id: string, data: TermUpdate): Promise<TermOut> {
    return this.withErrorContext(
      () => {
        this.validateRequired(id, 'Term ID');
        this.validateRequired(data, 'Term update data');
        
        if (data.title) {
          this.sanitizeString(data.title, 'Term title', 255);
        }
        
        if (data.definition) {
          this.sanitizeString(data.definition, 'Term definition', 2000);
        }
        
        return this.putResource<TermOut>(`${ENDPOINTS.TERMS}/${id}`, data);
      },
      'update term'
    );
  }

  /**
   * Delete a term
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(
      () => {
        this.validateRequired(id, 'Term ID');
        return this.deleteResource<void>(`${ENDPOINTS.TERMS}/${id}`);
      },
      'delete term'
    );
  }

  /**
   * Find terms using semantic search
   */
  async find(params: TermFindParams): Promise<FindTermResult[]> {
    return this.withErrorContext(
      () => {
        this.validateRequired(params, 'Search parameters');
        this.validateRequired(params.query, 'Search query');
        this.sanitizeString(params.query, 'Search query', 1000);
        return this.postResource<FindTermResult[]>(`${ENDPOINTS.TERMS}/find`, params);
      },
      'find terms'
    );
  }

  /**
   * Move terms between domains (with lineage)
   */
  async moveTerms(data: components['schemas']['MoveTermRequest']): Promise<components['schemas']['MoveTermResponse']> {
    return this.withErrorContext(
      () => {
        this.validateRequired(data, 'MoveTermRequest');
        return this.postResource<components['schemas']['MoveTermResponse']>(`${ENDPOINTS.TERMS}/move`, data);
      },
      'move terms'
    );
  }
}

// Export singleton instance
export const termService = new TermService();
