/**
 * Schema.org Service
 *
 * Service for managing Schema.org entities and properties
 */

import { BaseService, ListParams } from "./base";
import { ENDPOINTS } from "../config";
import type { components } from "@/api/client/types";

// Type aliases for better readability
export type SchemaOrgStatus = components["schemas"]["SchemaOrgStatus"];
export type SchemaOrgEntityOut = components["schemas"]["SchemaOrgEntityOut"];
export type SchemaOrgPropertyOut =
  components["schemas"]["SchemaOrgPropertyOut"];
export type SearchResult = components["schemas"]["SearchResult"];

export interface SchemaOrgEntityListParams extends ListParams {
  query?: string;
  parent_id?: string;
  limit?: number;
  offset?: number;
}

export interface SchemaOrgPropertyListParams extends ListParams {
  query?: string;
  domain_includes?: string;
  range_includes?: string;
  limit?: number;
  offset?: number;
}

export interface SchemaOrgSearchParams extends Record<string, unknown> {
  query: string;
  search_type?: string;
  limit?: number;
  similarity_threshold?: number;
}

export interface RefreshParams extends Record<string, unknown> {
  force?: boolean;
}

export class SchemaOrgService extends BaseService {
  /**
   * Get Schema.org database status
   */
  async getStatus(): Promise<SchemaOrgStatus> {
    return this.withErrorContext(
      () => this.getResource<SchemaOrgStatus>(`${ENDPOINTS.SCHEMA_ORG}/status`),
      "get schema.org status",
    );
  }

  /**
   * Refresh Schema.org database
   */
  async refresh(params?: RefreshParams): Promise<unknown> {
    return this.withErrorContext(
      () =>
        this.postResource<unknown>(
          `${ENDPOINTS.SCHEMA_ORG}/refresh`,
          undefined,
          { params },
        ),
      "refresh schema.org",
    );
  }

  /**
   * List Schema.org entities
   */
  async listEntities(
    params?: SchemaOrgEntityListParams,
  ): Promise<SearchResult> {
    return this.withErrorContext(
      () =>
        this.getResource<SearchResult>(
          `${ENDPOINTS.SCHEMA_ORG}/entities`,
          params,
        ),
      "list schema.org entities",
    );
  }

  /**
   * Get a specific Schema.org entity by identifier
   */
  async getEntity(identifier: string): Promise<SchemaOrgEntityOut> {
    return this.withErrorContext(() => {
      this.validateRequired(identifier, "Entity identifier");
      this.sanitizeString(identifier, "Entity identifier", 255);
      return this.getResource<SchemaOrgEntityOut>(
        `${ENDPOINTS.SCHEMA_ORG}/entities/${identifier}`,
      );
    }, "get schema.org entity");
  }

  /**
   * List Schema.org properties
   */
  async listProperties(
    params?: SchemaOrgPropertyListParams,
  ): Promise<SearchResult> {
    return this.withErrorContext(
      () =>
        this.getResource<SearchResult>(
          `${ENDPOINTS.SCHEMA_ORG}/properties`,
          params,
        ),
      "list schema.org properties",
    );
  }

  /**
   * Get a specific Schema.org property by identifier
   */
  async getProperty(identifier: string): Promise<SchemaOrgPropertyOut> {
    return this.withErrorContext(() => {
      this.validateRequired(identifier, "Property identifier");
      this.sanitizeString(identifier, "Property identifier", 255);
      return this.getResource<SchemaOrgPropertyOut>(
        `${ENDPOINTS.SCHEMA_ORG}/properties/${identifier}`,
      );
    }, "get schema.org property");
  }

  /**
   * Search Schema.org entities and properties
   */
  async search(params: SchemaOrgSearchParams): Promise<SearchResult> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "Search parameters");
      this.validateRequired(params.query, "Search query");
      this.sanitizeString(params.query, "Search query", 1000);

      return this.getResource<SearchResult>(
        `${ENDPOINTS.SCHEMA_ORG}/search`,
        params,
      );
    }, "search schema.org");
  }
}

// Export singleton instance
export const schemaOrgService = new SchemaOrgService();
