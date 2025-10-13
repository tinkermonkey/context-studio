import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type { components } from "@/api/client/types";

// Type aliases for better readability
export type PredicateOut = components["schemas"]["PredicateOut"];
export type PredicateCreate = components["schemas"]["PredicateCreate"];
export type PredicateUpdate = components["schemas"]["PredicateUpdate"];
export type PaginatedPredicatesResponse =
  components["schemas"]["PaginatedPredicatesResponse"];
export type ExternalPredicateOut = components["schemas"]["ExternalPredicateOut"];
export type PaginatedExternalPredicatesResponse =
  components["schemas"]["PaginatedExternalPredicatesResponse"];
export type PredicateDiscoveryResponse =
  components["schemas"]["PredicateDiscoveryResponse"];
export type PredicateDiscoveryStatus =
  components["schemas"]["PredicateDiscoveryStatus"];
export type SimilarPredicateOut = components["schemas"]["SimilarPredicateOut"];
export type FindSimilarResponse = components["schemas"]["FindSimilarResponse"];
export type ClusterOut = components["schemas"]["ClusterOut"];
export type ClusterPredicatesResponse =
  components["schemas"]["ClusterPredicatesResponse"];

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
   */
  async create(data: PredicateCreate): Promise<PredicateOut> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Predicate data");
      this.validateRequired(data.title, "Predicate title");
      this.sanitizeString(data.title, "Predicate title", 255);

      return this.postResource<PredicateOut>(ENDPOINTS.PREDICATES + "/", data);
    }, "create predicate");
  }

  /**
   * Get a predicate by ID
   */
  async get(id: string): Promise<PredicateOut> {
    this.validateRequired(id, "Predicate ID");
    return this.getResource<PredicateOut>(`${ENDPOINTS.PREDICATES}/${id}`);
  }

  /**
   * Update a predicate
   */
  async update(id: string, data: PredicateUpdate): Promise<PredicateOut> {
    return this.withErrorContext(() => {
      this.validateRequired(id, "Predicate ID");
      this.validateRequired(data, "Predicate update data");

      if (data.title) {
        this.sanitizeString(data.title, "Predicate title", 255);
      }

      return this.putResource<PredicateOut>(
        `${ENDPOINTS.PREDICATES}/${id}`,
        data,
      );
    }, "update predicate");
  }

  /**
   * Delete a predicate
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
   * Discover predicates from external knowledge sources
   */
  async discoverPredicates(
    params?: DiscoverPredicatesParams,
  ): Promise<PredicateDiscoveryResponse> {
    return this.withErrorContext(
      () =>
        this.postResource<PredicateDiscoveryResponse>(
          `${ENDPOINTS.PREDICATES}/discover`,
          null,
          params,
        ),
      "discover predicates",
    );
  }

  /**
   * Get the status of a predicate discovery task
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
   * List external predicates with pagination
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

  // ================== Similarity Search ==================

  /**
   * Find similar external predicates for a given predicate
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
        params,
      );
    }, "find similar predicates");
  }

  /**
   * Invalidate the similarity search cache
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
   */
  async clusterPredicates(
    params?: ClusterPredicatesParams,
  ): Promise<ClusterPredicatesResponse> {
    return this.withErrorContext(
      () =>
        this.postResource<ClusterPredicatesResponse>(
          `${ENDPOINTS.PREDICATES}/cluster-predicates`,
          null,
          params,
        ),
      "cluster predicates",
    );
  }
}

export const predicateService = new PredicateService();
