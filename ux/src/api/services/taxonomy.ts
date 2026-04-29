/**
 * Taxonomy Service
 *
 * Service for managing taxonomy entities
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  Taxonomy,
  TaxonomyCreate,
  TaxonomyUpdate,
  TaxonomyListParams,
} from "../types/ontology";

export class TaxonomyService extends BaseService {
  /**
   * List all taxonomies
   */
  async list(params?: TaxonomyListParams): Promise<Taxonomy[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.skip !== undefined) queryParams.skip = params.skip;
      if (params?.limit !== undefined) queryParams.limit = params.limit;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<Taxonomy>(ENDPOINTS.TAXONOMIES, queryParams);
      }

      return this.getPage<Taxonomy>(ENDPOINTS.TAXONOMIES, queryParams);
    }, "list");
  }

  /**
   * Get a specific taxonomy by ID
   */
  async get(id: string): Promise<Taxonomy> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<Taxonomy>(`${ENDPOINTS.TAXONOMIES}/${id}`);
    }, "get");
  }

  /**
   * Create a new taxonomy
   */
  async create(data: TaxonomyCreate): Promise<Taxonomy> {
    return this.withErrorContext(async () => {
      this.validateRequired(data.title, "title");
      this.sanitizeString(data.title, "title", 255);

      return this.postResource<Taxonomy>(ENDPOINTS.TAXONOMIES, data);
    }, "create");
  }

  /**
   * Update an existing taxonomy
   */
  async update(id: string, data: TaxonomyUpdate): Promise<Taxonomy> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      if (data.title) {
        this.sanitizeString(data.title, "title", 255);
      }

      return this.putResource<Taxonomy>(
        `${ENDPOINTS.TAXONOMIES}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete a taxonomy
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(`${ENDPOINTS.TAXONOMIES}/${id}`);
    }, "delete");
  }
}

export const taxonomyService = new TaxonomyService();
