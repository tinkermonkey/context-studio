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
        params,
      );
    }, "get node links");
  }
}

// Export singleton instance
export const referenceService = new ReferenceService();
