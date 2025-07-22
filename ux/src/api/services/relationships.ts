/**
 * Term Relationships Service
 * 
 * Service for managing term relationship entities
 */

import { BaseService, ListParams } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type TermRelationshipOut = components['schemas']['TermRelationshipOut'];
export type TermRelationshipCreate = components['schemas']['TermRelationshipCreate'];
export type TermRelationshipUpdate = components['schemas']['TermRelationshipUpdate'];

export interface RelationshipListParams extends ListParams {
  source_term_id?: string;
  target_term_id?: string;
  predicate?: string;
}

export class RelationshipService extends BaseService {
  /**
   * List all term relationships
   */
  async list(params?: RelationshipListParams): Promise<TermRelationshipOut[]> {
    return this.getResource<TermRelationshipOut[]>(ENDPOINTS.RELATIONSHIPS + '/', params);
  }

  /**
   * Get a specific term relationship by ID
   */
  async get(id: string): Promise<TermRelationshipOut> {
    return this.getResource<TermRelationshipOut>(`${ENDPOINTS.RELATIONSHIPS}/${id}`);
  }

  /**
   * Create a new term relationship
   */
  async create(data: TermRelationshipCreate): Promise<TermRelationshipOut> {
    return this.postResource<TermRelationshipOut>(ENDPOINTS.RELATIONSHIPS + '/', data);
  }

  /**
   * Update an existing term relationship
   */
  async update(id: string, data: TermRelationshipUpdate): Promise<TermRelationshipOut> {
    return this.putResource<TermRelationshipOut>(`${ENDPOINTS.RELATIONSHIPS}/${id}`, data);
  }

  /**
   * Delete a term relationship
   */
  async delete(id: string): Promise<void> {
    return this.deleteResource<void>(`${ENDPOINTS.RELATIONSHIPS}/${id}`);
  }
}

// Export singleton instance
export const relationshipService = new RelationshipService();
