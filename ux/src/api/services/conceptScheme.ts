/**
 * Concept Scheme Service
 *
 * Service for managing concept scheme entities
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  ConceptScheme,
  ConceptSchemeCreate,
  ConceptSchemeUpdate,
  ConceptSchemeListParams,
} from "../types/ontology";

export class ConceptSchemeService extends BaseService {
  /**
   * List all concept schemes
   */
  async list(params?: ConceptSchemeListParams): Promise<ConceptScheme[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.taxonomy_id) queryParams.taxonomy_id = params.taxonomy_id;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<ConceptScheme>(
          ENDPOINTS.CONCEPT_SCHEMES,
          queryParams,
        );
      }

      return this.getPage<ConceptScheme>(
        ENDPOINTS.CONCEPT_SCHEMES,
        queryParams,
      );
    }, "list");
  }

  /**
   * Get a specific concept scheme by ID
   */
  async get(id: string): Promise<ConceptScheme> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<ConceptScheme>(
        `${ENDPOINTS.CONCEPT_SCHEMES}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new concept scheme within a taxonomy
   */
  async create(taxonomyId: string, data: ConceptSchemeCreate): Promise<ConceptScheme> {
    return this.withErrorContext(async () => {
      this.validateRequired(taxonomyId, "taxonomyId");
      this.validateRequired(data.title, "title");
      this.sanitizeString(data.title, "title", 255);

      return this.postResource<ConceptScheme>(
        `${ENDPOINTS.TAXONOMIES}/${taxonomyId}/schemes`,
        data,
      );
    }, "create");
  }

  /**
   * Update an existing concept scheme
   */
  async update(id: string, data: ConceptSchemeUpdate): Promise<ConceptScheme> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      if (data.title) {
        this.sanitizeString(data.title, "title", 255);
      }

      return this.putResource<ConceptScheme>(
        `${ENDPOINTS.CONCEPT_SCHEMES}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete a concept scheme
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(
        `${ENDPOINTS.CONCEPT_SCHEMES}/${id}`,
      );
    }, "delete");
  }
}

export const conceptSchemeService = new ConceptSchemeService();
