import { BaseService } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '@/api/client/types';

// Type aliases for better readability
export type PredicateOut = components['schemas']['PredicateOut'];
export type PredicateCreate = components['schemas']['PredicateCreate'];
export type PredicateUpdate = components['schemas']['PredicateUpdate'];
export type PaginatedPredicatesResponse = components['schemas']['PaginatedPredicatesResponse'];

export interface PredicateListParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
}

export class PredicateService extends BaseService {
  /**
   * List predicates with pagination and sorting
   */
  async list(params?: PredicateListParams): Promise<PaginatedPredicatesResponse> {
    return this.getResource<PaginatedPredicatesResponse>(ENDPOINTS.PREDICATES + '/', { params });
  }

  /**
   * Create a new predicate
   */
  async create(data: PredicateCreate): Promise<PredicateOut> {
    return this.withErrorContext(
      () => {
        this.validateRequired(data, 'Predicate data');
        this.validateRequired(data.title, 'Predicate title');
        this.sanitizeString(data.title, 'Predicate title', 255);
        
        return this.postResource<PredicateOut>(ENDPOINTS.PREDICATES + '/', data);
      },
      'create predicate'
    );
  }

  /**
   * Get a predicate by ID
   */
  async get(id: string): Promise<PredicateOut> {
    this.validateRequired(id, 'Predicate ID');
    return this.getResource<PredicateOut>(`${ENDPOINTS.PREDICATES}/${id}`);
  }

  /**
   * Update a predicate
   */
  async update(id: string, data: PredicateUpdate): Promise<PredicateOut> {
    return this.withErrorContext(
      () => {
        this.validateRequired(id, 'Predicate ID');
        this.validateRequired(data, 'Predicate update data');
        
        if (data.title) {
          this.sanitizeString(data.title, 'Predicate title', 255);
        }
        
        return this.putResource<PredicateOut>(`${ENDPOINTS.PREDICATES}/${id}`, data);
      },
      'update predicate'
    );
  }

  /**
   * Delete a predicate
   */
  async delete(id: string): Promise<void> {
    this.validateRequired(id, 'Predicate ID');
    return this.deleteResource(`${ENDPOINTS.PREDICATES}/${id}`);
  }

  /**
   * Get predicate by identifier
   */
  async getByIdentifier(identifier: string): Promise<PredicateOut> {
    this.validateRequired(identifier, 'Predicate identifier');
    return this.getResource<PredicateOut>(`${ENDPOINTS.PREDICATES}/by-identifier/${identifier}`);
  }

  /**
   * Get ConceptNet relations
   */
  async getConceptNetRelations(): Promise<string[]> {
    return this.getResource<string[]>(`${ENDPOINTS.PREDICATES}/conceptnet-relations`);
  }

  /**
   * Import predicates from ConceptNet
   */
  async importFromConceptNet(relations?: string[]): Promise<PredicateOut[]> {
    return this.postResource<PredicateOut[]>(`${ENDPOINTS.PREDICATES}/import-from-conceptnet`, relations);
  }

  /**
   * Get ConceptNet relation for a predicate
   */
  async getConceptNetRelation(id: string): Promise<string | null> {
    this.validateRequired(id, 'Predicate ID');
    return this.getResource<string | null>(`${ENDPOINTS.PREDICATES}/${id}/conceptnet-relation`);
  }

  /**
   * Get ConceptNet mapping for all predicates
   */
  async getConceptNetMapping(): Promise<Record<string, string>> {
    return this.getResource<Record<string, string>>(`${ENDPOINTS.PREDICATES}/conceptnet-mapping`);
  }
}

export const predicateService = new PredicateService();
