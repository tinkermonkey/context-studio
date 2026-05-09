/**
 * Property Definition Service
 *
 * Service for managing property definition entities
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  PropertyDefinition,
  PropertyDefinitionCreate,
  PropertyDefinitionUpdate,
  PropertyDefinitionListParams,
} from "../types/ontology";

export class PropertyDefinitionService extends BaseService {
  /**
   * List all property definitions
   */
  async list(
    params?: PropertyDefinitionListParams,
  ): Promise<PropertyDefinition[]> {
    return this.withErrorContext(async () => {
      const queryParams: Record<string, unknown> = {};
      if (params?.offset !== undefined) queryParams.offset = params.offset;
      if (params?.limit !== undefined) queryParams.limit = params.limit;

      // If no limit specified, load all
      if (params?.limit === undefined) {
        return this.getAllPaginated<PropertyDefinition>(
          ENDPOINTS.PROPERTY_DEFINITIONS,
          queryParams,
        );
      }

      return this.getPage<PropertyDefinition>(
        ENDPOINTS.PROPERTY_DEFINITIONS,
        queryParams,
      );
    }, "list");
  }

  /**
   * Get a specific property definition by ID
   */
  async get(id: string): Promise<PropertyDefinition> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.getResource<PropertyDefinition>(
        `${ENDPOINTS.PROPERTY_DEFINITIONS}/${id}`,
      );
    }, "get");
  }

  /**
   * Create a new property definition
   */
  async create(data: PropertyDefinitionCreate): Promise<PropertyDefinition> {
    return this.withErrorContext(async () => {
      this.validateRequired(data.identifier, "identifier");
      this.validateRequired(data.title, "title");
      this.sanitizeString(data.title, "title", 255);

      return this.postResource<PropertyDefinition>(
        ENDPOINTS.PROPERTY_DEFINITIONS,
        data,
      );
    }, "create");
  }

  /**
   * Update an existing property definition
   */
  async update(
    id: string,
    data: PropertyDefinitionUpdate,
  ): Promise<PropertyDefinition> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");

      if (data.title) {
        this.sanitizeString(data.title, "title", 255);
      }

      return this.putResource<PropertyDefinition>(
        `${ENDPOINTS.PROPERTY_DEFINITIONS}/${id}`,
        data,
      );
    }, "update");
  }

  /**
   * Delete a property definition
   */
  async delete(id: string): Promise<void> {
    return this.withErrorContext(async () => {
      this.validateRequired(id, "id");
      return this.deleteResource<void>(
        `${ENDPOINTS.PROPERTY_DEFINITIONS}/${id}`,
      );
    }, "delete");
  }
}

export const propertyDefinitionService = new PropertyDefinitionService();
