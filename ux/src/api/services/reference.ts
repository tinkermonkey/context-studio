/**
 * Reference Service
 *
 * Service for managing reference database operations including filtering
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";

export interface FilterStatistics {
  relevant_predicates_count: number;
  irrelevant_predicates_count: number;
  total_mappings: number;
  external_predicate_count: number;
  filtering_ready: boolean;
  external_predicates_by_source: Record<string, number>;
}

export interface ReferenceNode {
  id: string;
  title: string;
  definition: string;
  source: string;
  external_id: string;
  created_at: string;
  updated_at: string;
}

export interface ReferenceLink {
  id: string;
  subject_node: string;
  predicate: string;
  object_node: string;
  created_at: string;
}

export interface NodeLinksParams {
  direction?: "inbound" | "outbound" | "both";
  predicate?: string;
  limit?: number;
  apply_relevance_filter?: boolean;
}

export interface NodeLinksResponse {
  node_id: string;
  direction: string;
  predicate?: string;
  total_links: number;
  links: ReferenceLink[];
  filtering_applied: boolean;
  filter_statistics?: {
    total_before_filter: number;
    total_after_filter: number;
    filtered_out: number;
    predicates_used: number;
  };
}

export interface PredicateExampleNode {
  id: string;
  title: string;
  source: string;
  external_id: string;
}

export interface PredicateExample {
  link_id: string;
  subject: PredicateExampleNode;
  predicate: {
    title: string;
    source: string;
    external_id: string;
  };
  object: PredicateExampleNode;
}

export interface PredicateExamplesResponse {
  predicate: {
    id: string;
    title: string;
    definition: string;
    source: string;
    external_id: string;
  };
  total_examples: number;
  examples: PredicateExample[];
}

export class ReferenceService extends BaseService {
  /**
   * Get reference link filtering statistics
   * @returns {Promise<FilterStatistics>} Statistics about relevant/irrelevant predicates and filtering status
   */
  async getFilterStatistics(): Promise<FilterStatistics> {
    return this.withErrorContext(
      () =>
        this.getResource<FilterStatistics>(
          ENDPOINTS.REFERENCE.FILTER_STATISTICS,
        ),
      "get filter statistics",
    );
  }

  /**
   * Get a reference node by ID
   * @param {string} nodeId - The ID of the reference node to retrieve
   * @returns {Promise<ReferenceNode>} The reference node data
   */
  async getNode(nodeId: string): Promise<ReferenceNode> {
    return this.withErrorContext(() => {
      this.validateRequired(nodeId, "Node ID");
      return this.getResource<ReferenceNode>(
        `${ENDPOINTS.REFERENCE.NODES}/${nodeId}`,
      );
    }, "get reference node");
  }

  /**
   * Get links for a reference node with optional filtering
   * @param {string} nodeId - The ID of the reference node
   * @param {NodeLinksParams} params - Optional parameters for filtering links
   * @returns {Promise<NodeLinksResponse>} Links for the node with optional filtering applied
   */
  async getNodeLinks(
    nodeId: string,
    params?: NodeLinksParams,
  ): Promise<NodeLinksResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(nodeId, "Node ID");
      return this.getResource<NodeLinksResponse>(
        `${ENDPOINTS.REFERENCE.NODES}/${nodeId}/links`,
        params as Record<string, unknown>,
      );
    }, "get node links");
  }

  /**
   * Get example uses of a predicate from the reference database
   * @param {string} source - The source of the predicate (e.g., 'schema.org', 'dbpedia')
   * @param {string} externalId - The external ID of the predicate (can contain slashes)
   * @param {number} limit - Maximum number of examples to return (default: 10)
   * @returns {Promise<PredicateExamplesResponse>} Example uses of the predicate
   */
  async getPredicateExamples(
    source: string,
    externalId: string,
    limit: number = 10,
  ): Promise<PredicateExamplesResponse> {
    return this.withErrorContext(() => {
      this.validateRequired(source, "Source");
      this.validateRequired(externalId, "External ID");
      // Note: external_id can contain slashes (e.g., '/r/RelatedTo' for ConceptNet)
      // We encode the source but not the external_id since the backend endpoint uses :path
      return this.getResource<PredicateExamplesResponse>(
        `/api/reference/ref-db/predicates/${encodeURIComponent(source)}/${externalId}/examples`,
        { limit },
      );
    }, "get predicate examples");
  }
}

// Export singleton instance
export const referenceService = new ReferenceService();
