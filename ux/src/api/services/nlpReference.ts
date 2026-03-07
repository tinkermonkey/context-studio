/**
 * NLP Reference Service
 *
 * Service for accessing external reference data sources (DBpedia, ConceptNet, Wikidata, Schema.org)
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type { components } from "@/api/client/types";

// Type aliases for better readability
export type ResponseFormat = components["schemas"]["ResponseFormat"];
export type MultiSourceSearchResponse =
  components["schemas"]["MultiSourceSearchResponse"];
export type DBpediaSparqlRequest =
  components["schemas"]["DBpediaSparqlRequest"];
export type WikidataSparqlRequest =
  components["schemas"]["WikidataSparqlRequest"];

// DBpedia parameters
export interface DBpediaResourceParams extends Record<string, unknown> {
  resource_url: string;
  format?: ResponseFormat;
}

export interface DBpediaSearchParams extends Record<string, unknown> {
  query: string;
  limit?: number;
  offset?: number;
  format?: ResponseFormat;
}

// ConceptNet parameters
export interface ConceptNetQueryParams extends Record<string, unknown> {
  start?: string;
  end?: string;
  node?: string;
  rel?: string;
  limit?: number;
  offset?: number;
}

export interface ConceptNetRelatedParams extends Record<string, unknown> {
  filter?: string;
  limit?: number;
}

// Wikidata parameters
export interface WikidataEntityParams extends Record<string, unknown> {
  entity_url: string;
  properties?: string;
  format?: ResponseFormat;
}

// Schema.org parameters
export interface SchemaOrgEntityParams extends Record<string, unknown> {
  include_inherited?: boolean;
  include_children?: boolean;
}

export interface SchemaOrgPropertyParams extends Record<string, unknown> {
  include_usage?: boolean;
}

export interface SchemaOrgReferenceSearchParams
  extends Record<string, unknown> {
  query: string;
  search_type?: "entities" | "properties" | "both";
  limit?: number;
  offset?: number;
  similarity_threshold?: number;
}

export class NLPReferenceService extends BaseService {
  // DBpedia methods
  /**
   * Get DBpedia resource data
   */
  async getDBpediaResource(
    params: DBpediaResourceParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "DBpedia parameters");
      this.validateRequired(params.resource_url, "Resource URL");
      this.sanitizeString(params.resource_url, "Resource URL", 2000);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/dbpedia/resource`,
        params,
      );
    }, "get DBpedia resource");
  }

  /**
   * Search DBpedia
   */
  async searchDBpedia(
    params: DBpediaSearchParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "DBpedia search parameters");
      this.validateRequired(params.query, "Search query");
      this.sanitizeString(params.query, "Search query", 1000);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/dbpedia/search`,
        params,
      );
    }, "search DBpedia");
  }

  /**
   * Execute DBpedia SPARQL query
   */
  async queryDBpediaSparql(
    data: DBpediaSparqlRequest,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "SPARQL request data");
      this.validateRequired(data.query, "SPARQL query");
      this.sanitizeString(data.query, "SPARQL query", 10000);

      return this.postResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/dbpedia/sparql`,
        data,
      );
    }, "query DBpedia SPARQL");
  }

  // ConceptNet methods
  /**
   * Query ConceptNet
   */
  async queryConceptNet(
    params?: ConceptNetQueryParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(
      () =>
        this.getResource<MultiSourceSearchResponse>(
          `${ENDPOINTS.NLP_REFERENCE}/conceptnet/query`,
          params,
        ),
      "query ConceptNet",
    );
  }

  /**
   * Get ConceptNet concept
   */
  async getConceptNetConcept(
    conceptPath: string,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(conceptPath, "Concept path");
      this.sanitizeString(conceptPath, "Concept path", 500);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/conceptnet/concept/${conceptPath}`,
      );
    }, "get ConceptNet concept");
  }

  /**
   * Get ConceptNet related concepts
   */
  async getConceptNetRelated(
    conceptPath: string,
    params?: ConceptNetRelatedParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(conceptPath, "Concept path");
      this.sanitizeString(conceptPath, "Concept path", 500);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/conceptnet/related/${conceptPath}`,
        params,
      );
    }, "get ConceptNet related");
  }

  // Wikidata methods
  /**
   * Execute Wikidata SPARQL query
   */
  async queryWikidataSparql(
    data: WikidataSparqlRequest,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Wikidata SPARQL request data");
      this.validateRequired(data.query, "SPARQL query");
      this.sanitizeString(data.query, "SPARQL query", 10000);

      return this.postResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/wikidata/sparql`,
        data,
      );
    }, "query Wikidata SPARQL");
  }

  /**
   * Get Wikidata entity
   */
  async getWikidataEntity(
    params: WikidataEntityParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "Wikidata entity parameters");
      this.validateRequired(params.entity_url, "Entity URL");
      this.sanitizeString(params.entity_url, "Entity URL", 2000);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/wikidata/entity`,
        params,
      );
    }, "get Wikidata entity");
  }

  // Schema.org reference methods
  /**
   * Get Schema.org entity via reference API
   */
  async getSchemaOrgEntity(
    identifier: string,
    params?: SchemaOrgEntityParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(identifier, "Entity identifier");
      this.sanitizeString(identifier, "Entity identifier", 255);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/schema-org/entity/${identifier}`,
        params,
      );
    }, "get Schema.org entity");
  }

  /**
   * Get Schema.org property via reference API
   */
  async getSchemaOrgProperty(
    identifier: string,
    params?: SchemaOrgPropertyParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(identifier, "Property identifier");
      this.sanitizeString(identifier, "Property identifier", 255);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/schema-org/property/${identifier}`,
        params,
      );
    }, "get Schema.org property");
  }

  /**
   * Search Schema.org via reference API
   */
  async searchSchemaOrg(
    params: SchemaOrgReferenceSearchParams,
  ): Promise<MultiSourceSearchResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "Schema.org search parameters");
      this.validateRequired(params.query, "Search query");
      this.sanitizeString(params.query, "Search query", 1000);

      return this.getResource<MultiSourceSearchResponse>(
        `${ENDPOINTS.NLP_REFERENCE}/schema-org/search`,
        params,
      );
    }, "search Schema.org");
  }

  /**
   * Health check for all reference APIs
   */
  async getHealthStatus(): Promise<unknown> {
    return this.withErrorContext(
      () => this.getResource<unknown>(`${ENDPOINTS.NLP_REFERENCE}/health`),
      "get reference APIs health",
    );
  }
}

// Export singleton instance
export const nlpReferenceService = new NLPReferenceService();
