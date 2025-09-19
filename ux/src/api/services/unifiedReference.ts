/**
 * Unified Reference Service
 *
 * Service for accessing unified reference data across multiple sources
 * (DBpedia, ConceptNet, Wikidata, Schema.org, WordNet)
 */

import { BaseService } from "./base";
import {
  UnifiedSearchRequest,
  UnifiedSearchResponse,
  UnifiedNode,
  UnifiedLink,
  MultiSourceSearchRequest,
  MultiSourceSearchResponse,
  SearchNode,
  UnifiedReferenceError,
} from "../types/unified";

export class UnifiedReferenceService extends BaseService {
  private readonly SEARCH_ENDPOINT = `/api/nlp_analysis/reference/search`;

  /**
   * Search across all unified reference sources
   */
  async search(request: UnifiedSearchRequest): Promise<UnifiedSearchResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(request, "Search request");
      this.validateRequired(request.query, "Search query");
      this.sanitizeString(request.query, "Search query", 1000);

      if (request.query.trim().length < 2) {
        throw new UnifiedReferenceError(
          "Search query must be at least 2 characters",
        );
      }

      if (request.sources && request.sources.length === 0) {
        throw new UnifiedReferenceError("At least one source must be selected");
      }

      try {
        // Convert to backend-compatible request format
        const backendRequest: MultiSourceSearchRequest = {
          query: request.query,
          sources: request.sources,
          limit: request.limit || 20,
          offset: request.offset || 0,
        };

        const response = await this.postResource<MultiSourceSearchResponse>(
          this.SEARCH_ENDPOINT,
          backendRequest,
        );

        // Convert backend response to frontend format
        return {
          query: response.query,
          results: response.results.map(this.convertSearchNodeToUnifiedNode),
          links: response.links || [],
          total_results: response.total_results,
          total_links: response.total_links || 0,
          sources_searched: response.sources_searched,
          source_errors: response.source_errors,
          execution_time_ms: response.execution_time_ms,
        };
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          throw new UnifiedReferenceError(
            "Search endpoint not found. Please ensure the backend service is properly configured and running.",
            { cause: error }
          );
        }
        throw error;
      }
    }, "unified search");
  }

  /**
   * Get detailed information about a specific node
   */
  async getNode(nodeId: string): Promise<UnifiedNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(nodeId, "Node ID");
      this.sanitizeString(nodeId, "Node ID", 255);

      throw new UnifiedReferenceError(
        "Node details endpoint is not yet implemented. Please ensure the backend service supports this functionality."
      );
    }, "get unified node");
  }

  /**
   * Get links for a specific node
   */
  async getLinks(
    nodeId: string,
    direction: "from" | "to" | "both" = "both",
  ): Promise<UnifiedLink[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(nodeId, "Node ID");
      this.sanitizeString(nodeId, "Node ID", 255);

      throw new UnifiedReferenceError(
        "Node links endpoint is not yet implemented. Please ensure the backend service supports this functionality."
      );
    }, "get node links");
  }



  /**
   * Paginated search with load more functionality
   */
  async searchPaginated(
    request: UnifiedSearchRequest,
    cursor?: string,
  ): Promise<UnifiedSearchResponse> {
    const paginatedRequest = {
      ...request,
      cursor,
    };

    return this.search(paginatedRequest);
  }

  /**
   * Convert SearchNode from backend to UnifiedNode for frontend
   */
  private convertSearchNodeToUnifiedNode(node: SearchNode): UnifiedNode {
    return {
      id: node.id,
      title: node.title,
      definition: node.definition,
      source: node.source,
      confidence_score: node.confidence_score || 1.0,
      source_url: node.source_url,
      metadata: node.metadata,
      created_at: node.created_at,
      updated_at: node.updated_at,
      merged_from: node.merged_from,
    };
  }



}

// Export singleton instance
export const unifiedReferenceService = new UnifiedReferenceService();
