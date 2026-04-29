/**
 * Ontology Class Service
 *
 * Service for managing ontology class entities
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  OntologyClass,
  OntologyClassCreate,
  OntologyClassUpdate,
  OntologyClassListParams,
} from "../types/ontology";

export class OntologyClassService extends BaseService {
  /**
   * List all ontology classes
   */
  async list(params?: OntologyClassListParams): Promise<OntologyClass[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.scheme_id) queryParams.scheme_id = params.scheme_id;
      if (params?.parent_class_id)
        queryParams.parent_class_id = params.parent_class_id;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<OntologyClass>(
          ENDPOINTS.ONTOLOGY_CLASSES,
          queryParams,
        );
      }

      return this.getPage<OntologyClass>(
        ENDPOINTS.ONTOLOGY_CLASSES,
        queryParams,
      );
    }, "list");
  }

  /**
   * Get a specific ontology class by ID
   */
  async get(id: string): Promise<OntologyClass> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<OntologyClass>(
        `${ENDPOINTS.ONTOLOGY_CLASSES}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new ontology class within a scheme
   */
  async create(schemeId: string, data: OntologyClassCreate): Promise<OntologyClass> {
    return this.withErrorContext(async () => {
      this.validateRequired(schemeId, "schemeId");
      this.validateRequired(data.title, "title");
      this.sanitizeString(data.title, "title", 255);

      if (data.definition) {
        this.sanitizeString(data.definition, "definition", 10000);
      }

      return this.postResource<OntologyClass>(
        `${ENDPOINTS.CONCEPT_SCHEMES}/${schemeId}/classes`,
        data,
      );
    }, "create");
  }

  /**
   * Update an existing ontology class
   */
  async update(id: string, data: OntologyClassUpdate): Promise<OntologyClass> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      if (data.title) {
        this.sanitizeString(data.title, "title", 255);
      }

      if (data.definition) {
        this.sanitizeString(data.definition, "definition", 10000);
      }

      return this.putResource<OntologyClass>(
        `${ENDPOINTS.ONTOLOGY_CLASSES}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete an ontology class
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(
        `${ENDPOINTS.ONTOLOGY_CLASSES}/${id}`,
      );
    }, "delete");
  }
}

export const ontologyClassService = new OntologyClassService();
