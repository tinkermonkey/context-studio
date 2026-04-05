import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  PredicateOut,
  PredicateCreate,
  PredicateUpdate,
  PaginatedPredicatesResponse,
  ExternalPredicateOut,
  PaginatedExternalPredicatesResponse,
} from "./missingTypes";

// Re-export types for use in hooks and components
export type {
  PredicateOut,
  PredicateCreate,
  PredicateUpdate,
  PaginatedPredicatesResponse,
  ExternalPredicateOut,
  PaginatedExternalPredicatesResponse,
};

// Type aliases for better readability
export type PredicateDiscoveryResponse = Record<string, unknown>;
export type PredicateDiscoveryStatus = Record<string, unknown>;
export type SimilarPredicateOut = ExternalPredicateOut;

export interface FindSimilarResponse {
  results: ExternalPredicateOut[];
  total_count?: number;
  [key: string]: unknown;
}

export type ClusterOut = Record<string, unknown>;
export type ClusterPredicatesResponse = Record<string, unknown>;

export interface PredicateListParams {
  skip?: number;
  limit?: number;
  sort_by?: string;
}

export interface ListExternalPredicatesParams extends Record<string, unknown> {
  source?: string;
  skip?: number;
  limit?: number;
}

export interface SearchExternalPredicatesParams
  extends Record<string, unknown> {
  query: string;
  source?: string;
  limit?: number;
  threshold?: number;
}

export interface FindSimilarParams extends Record<string, unknown> {
  source?: string;
  limit?: number;
  threshold?: number;
  use_cache?: boolean;
}

export interface ClusterPredicatesParams extends Record<string, unknown> {
  predicate_ids?: string[];
  min_similarity?: number;
  min_cluster_size?: number;
  eps?: number;
  max_predicates?: number;
}

export interface DiscoverPredicatesParams extends Record<string, unknown> {
  sources?: string[];
}

export class PredicateService extends BaseService {
  /**
   * List predicates with pagination and sorting
   * @param {PredicateListParams} params - Optional pagination and sorting parameters
   * @param {number} params.skip - Number of records to skip
   * @param {number} params.limit - Maximum number of records to return
   * @param {string} params.sort_by - Field to sort by
   * @returns {Promise<PaginatedPredicatesResponse>} Paginated list of predicates
   */
  async list(
    params?: PredicateListParams,
  ): Promise<PaginatedPredicatesResponse> {
    return this.getResource<PaginatedPredicatesResponse>(
      ENDPOINTS.PREDICATES + "/",
      { params },
    );
  }

  /**
   * Create a new predicate
   * @param {PredicateCreate} data - Predicate creation data
   * @param {string} data.title - Title of the predicate (required)
   * @param {string} data.definition - Definition of the predicate (optional)
   * @param {string} data.identifier - Unique identifier (optional, auto-generated if not provided)
   * @returns {Promise<PredicateOut>} Created predicate
   */
  async create(data: PredicateCreate): Promise<PredicateOut> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Predicate data");
      this.validateRequired(data.title, "Predicate title");
      this.sanitizeString((data.title as unknown as string) || '', "Predicate title", 255);

      return this.postResource<PredicateOut>(ENDPOINTS.PREDICATES + "/", data);
    }, "create predicate");
  }

  /**
   * Get a predicate by ID
   * @param {string} id - Predicate ID
   * @returns {Promise<PredicateOut>} Predicate data
   */
  async get(id: string): Promise<PredicateOut> {
    this.validateRequired(id, "Predicate ID");
    return this.getResource<PredicateOut>(`${ENDPOINTS.PREDICATES}/${id}`);
  }

  /**
   * Update a predicate
   * @param {string} id - Predicate ID
   * @param {PredicateUpdate} data - Predicate update data
   * @param {string} data.title - Updated title (optional)
   * @param {string} data.definition - Updated definition (optional)
   * @param {string} data.identifier - Updated identifier (optional)
   * @returns {Promise<PredicateOut>} Updated predicate
   */
  async update(id: string, data: PredicateUpdate): Promise<PredicateOut> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Predicate ID");
      this.validateRequired(data, "Predicate update data");

      if (data.title) {
        this.sanitizeString((data.title as unknown as string) || '', "Predicate title", 255);
      }

      return this.putResource<PredicateOut>(
        `${ENDPOINTS.PREDICATES}/${id}`,
        data,
      );
    }, "update predicate");
  }

  /**
   * Delete a predicate
   * @param {string} id - Predicate ID
   * @returns {Promise<void>}
   */
  async delete(id: string): Promise<void> {
    this.validateRequired(id, "Predicate ID");
    return this.deleteResource(`${ENDPOINTS.PREDICATES}/${id}`);
  }

  /**
   * Get predicate by identifier
   */
  async getByIdentifier(identifier: string): Promise<PredicateOut> {
    this.validateRequired(identifier, "Predicate identifier");
    return this.getResource<PredicateOut>(
      `${ENDPOINTS.PREDICATES}/by-identifier/${identifier}`,
    );
  }

  /**
   * Get ConceptNet relations
   */
  async getConceptNetRelations(): Promise<string[]> {
    return this.getResource<string[]>(
      `${ENDPOINTS.PREDICATES}/conceptnet-relations`,
    );
  }

  /**
   * Import predicates from ConceptNet
   */
  async importFromConceptNet(relations?: string[]): Promise<PredicateOut[]> {
    return this.postResource<PredicateOut[]>(
      `${ENDPOINTS.PREDICATES}/import-from-conceptnet`,
      relations,
    );
  }

  /**
   * Get ConceptNet relation for a predicate
   */
  async getConceptNetRelation(id: string): Promise<string | null> {
    this.validateRequired(id, "Predicate ID");
    return this.getResource<string | null>(
      `${ENDPOINTS.PREDICATES}/${id}/conceptnet-relation`,
    );
  }

  /**
   * Get ConceptNet mapping for all predicates
   */
  async getConceptNetMapping(): Promise<Record<string, string>> {
    return this.getResource<Record<string, string>>(
      `${ENDPOINTS.PREDICATES}/conceptnet-mapping`,
    );
  }

  // ================== External Predicates Discovery ==================

  /**
   * Discover predicates from external knowledge sources (async background task)
   * @param {DiscoverPredicatesParams} params - Discovery parameters
   * @param {string[]} params.sources - Optional list of sources to discover from (e.g., ['conceptnet', 'dbpedia'])
   * @returns {Promise<PredicateDiscoveryResponse>} Task ID and status for tracking the discovery process
   */
  async discoverPredicates(
    params?: DiscoverPredicatesParams,
  ): Promise<PredicateDiscoveryResponse> {
    return this.withErrorContext(
      () =>
        this.postResource<PredicateDiscoveryResponse>(
          `${ENDPOINTS.PREDICATES}/discover`,
          null,
          { params },
        ),
      "discover predicates",
    );
  }

  /**
   * Get the status of a predicate discovery task
   * @param {string} taskId - The task ID returned from discoverPredicates
   * @returns {Promise<PredicateDiscoveryStatus>} Current status of the discovery task
   */
  async getDiscoveryStatus(taskId: string): Promise<PredicateDiscoveryStatus> {
    return this.withErrorContext(() => {
      this.validateRequired(taskId, "Task ID");
      return this.getResource<PredicateDiscoveryStatus>(
        `${ENDPOINTS.PREDICATES}/discover/${taskId}`,
      );
    }, "get discovery status");
  }

  /**
   * List external predicates with pagination and source filtering
   * @param {ListExternalPredicatesParams} params - Query parameters
   * @param {string} params.source - Optional source filter (e.g., 'conceptnet', 'dbpedia')
   * @param {number} params.skip - Number of records to skip
   * @param {number} params.limit - Maximum number of records to return
   * @returns {Promise<PaginatedExternalPredicatesResponse>} Paginated list of external predicates
   */
  async listExternalPredicates(
    params?: ListExternalPredicatesParams,
  ): Promise<PaginatedExternalPredicatesResponse> {
    return this.withErrorContext(
      () =>
        this.getResource<PaginatedExternalPredicatesResponse>(
          `${ENDPOINTS.PREDICATES}/external`,
          params,
        ),
      "list external predicates",
    );
  }

  /**
   * Search external predicates using vector similarity
   * @param {SearchExternalPredicatesParams} params - Search parameters
   * @param {string} params.query - Search query text (required)
   * @param {string} params.source - Optional source filter (e.g., 'conceptnet', 'dbpedia')
   * @param {number} params.limit - Maximum number of results (default: 20, max: 100)
   * @param {number} params.threshold - Minimum similarity threshold (0.0-1.0, default: 0.6)
   * @returns {Promise<any>} Search results with similarity scores
   */
  async searchExternalPredicates(
    params: SearchExternalPredicatesParams,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ): Promise<any> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "Search parameters");
      this.validateRequired(params.query, "Search query");

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return this.getResource<any>(
        `${ENDPOINTS.PREDICATES}/external/search`,
        params,
      );
    }, "search external predicates");
  }

  // ================== Similarity Search ==================

  /**
   * Find similar external predicates for a given predicate using vector similarity
   * @param {string} id - Predicate ID to find similar predicates for
   * @param {FindSimilarParams} params - Search parameters
   * @param {string} params.source - Optional source filter
   * @param {number} params.limit - Maximum number of results (default: 20)
   * @param {number} params.threshold - Minimum similarity threshold (0.0-1.0, default: 0.7)
   * @param {boolean} params.use_cache - Whether to use cached results (default: true)
   * @returns {Promise<FindSimilarResponse>} List of similar predicates with similarity scores
   */
  async findSimilarPredicates(
    id: string,
    params?: FindSimilarParams,
  ): Promise<FindSimilarResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Predicate ID");

      return this.postResource<FindSimilarResponse>(
        `${ENDPOINTS.PREDICATES}/${id}/find-similar`,
        null,
        { params },
      );
    }, "find similar predicates");
  }

  /**
   * Invalidate the similarity search cache to force fresh calculations
   * @returns {Promise<Object>} Success status and number of cache entries cleared
   */
  async invalidateSimilarityCache(): Promise<{
    success: boolean;
    message: string;
    cache_entries_cleared: number;
  }> {
    return this.withErrorContext(
      () =>
        this.postResource<{
          success: boolean;
          message: string;
          cache_entries_cleared: number;
        }>(`${ENDPOINTS.PREDICATES}/invalidate-similarity-cache`),
      "invalidate similarity cache",
    );
  }

  // ================== Clustering ==================

  /**
   * Cluster similar predicates using DBSCAN algorithm
   * @param {ClusterPredicatesParams} params - Clustering parameters
   * @param {string[]} params.predicate_ids - Optional list of specific predicate IDs to cluster
   * @param {number} params.min_similarity - Minimum similarity threshold for clustering
   * @param {number} params.min_cluster_size - Minimum number of predicates to form a cluster
   * @param {number} params.eps - DBSCAN epsilon parameter (maximum distance between predicates)
   * @param {number} params.max_predicates - Maximum number of predicates to analyze
   * @returns {Promise<ClusterPredicatesResponse>} Clusters with representative predicates and statistics
   */
  async clusterPredicates(
    params?: ClusterPredicatesParams,
  ): Promise<ClusterPredicatesResponse> {
    return this.withErrorContext(
      () =>
        this.postResource<ClusterPredicatesResponse>(
          `${ENDPOINTS.PREDICATES}/cluster-predicates`,
          null,
          { params },
        ),
      "cluster predicates",
    );
  }
}

export const predicateService = new PredicateService();
