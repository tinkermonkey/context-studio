/**
 * Relationship Service
 *
 * Service for managing relationship entities
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  Relationship,
  RelationshipCreate,
  RelationshipUpdate,
  RelationshipListParams,
} from "../types/ontology";

export class RelationshipService extends BaseService {
  /**
   * List all relationships
   */
  async list(params?: RelationshipListParams): Promise<Relationship[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;
      if (params?.source_id)
        queryParams.source_id = params.source_id;
      if (params?.target_id)
        queryParams.target_id = params.target_id;
      if (params?.relationship_type) queryParams.relationship_type = params.relationship_type;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<Relationship>(
          ENDPOINTS.RELATIONSHIPS,
          queryParams,
        );
      }

      return this.getPage<Relationship>(
        ENDPOINTS.RELATIONSHIPS,
        queryParams,
      );
    }, "list");
  }

  /**
   * Get a specific relationship by ID
   */
  async get(id: string): Promise<Relationship> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<Relationship>(
        `${ENDPOINTS.RELATIONSHIPS}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new relationship
   */
  async create(data: RelationshipCreate): Promise<Relationship> {
    return this.withErrorContext(async () => {
      this.validateRequired(data.source_id, "source_id");
      this.validateRequired(data.target_id, "target_id");
      this.validateRequired(data.relationship_type, "relationship_type");

      return this.postResource<Relationship>(ENDPOINTS.RELATIONSHIPS, data);
    }, "create");
  }

  /**
   * Update an existing relationship
   */
  async update(id: string, data: RelationshipUpdate): Promise<Relationship> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      return this.putResource<Relationship>(
        `${ENDPOINTS.RELATIONSHIPS}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete a relationship
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(`${ENDPOINTS.RELATIONSHIPS}/${id}`);
    }, "delete");
  }
}

export const relationshipService = new RelationshipService();
