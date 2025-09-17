/**
 * Unified Reference Service
 *
 * Service for accessing unified reference data across multiple sources
 * (DBpedia, ConceptNet, Wikidata, Schema.org, WordNet)
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import {
  UnifiedSearchRequest,
  UnifiedSearchResponse,
  UnifiedNode,
  UnifiedLink,
  SourceType,
  MultiSourceSearchRequest,
  MultiSourceSearchResponse,
  SearchNode,
  UnifiedReferenceError,
  SourceUnavailableError,
  SearchTimeoutError,
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
          console.warn("Multi-source search endpoint not found, using mock data");
          return this.getMockSearchResponse(request);
        }
        throw error;
      }
    }, "unified search");
  }

  /**
   * Get detailed information about a specific node
   * Note: This endpoint doesn't exist in the backend yet, returns mock data
   */
  async getNode(nodeId: string): Promise<UnifiedNode> {
    return this.withErrorContext(async () => {
      this.validateRequired(nodeId, "Node ID");
      this.sanitizeString(nodeId, "Node ID", 255);

      // Backend endpoint not implemented yet - return mock data
      console.warn("Node details endpoint not implemented, using mock data");
      return this.getMockNode(nodeId);
    }, "get unified node");
  }

  /**
   * Get links for a specific node
   * Note: This endpoint doesn't exist in the backend yet, returns mock data
   */
  async getLinks(
    nodeId: string,
    direction: "from" | "to" | "both" = "both",
  ): Promise<UnifiedLink[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(nodeId, "Node ID");
      this.sanitizeString(nodeId, "Node ID", 255);

      // Backend endpoint not implemented yet - return mock data
      console.warn("Node links endpoint not implemented, using mock data");
      return this.getMockLinks(nodeId);
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

  // Mock data methods for development (when backend is not ready)
  private getMockSearchResponse(
    request: UnifiedSearchRequest,
  ): UnifiedSearchResponse {
    const mockResults: UnifiedNode[] = [
      {
        id: "mock-1",
        title: `Mock result for "${request.query}"`,
        definition: `This is a mock definition for the search term "${request.query}". The backend implementation is not yet available.`,
        source: "conceptnet",
        confidence_score: 0.95,
        created_at: new Date().toISOString(),
      },
      {
        id: "mock-2",
        title: `Another result for "${request.query}"`,
        definition: `Alternative mock definition for "${request.query}".`,
        source: "dbpedia",
        confidence_score: 0.87,
        merged_from: ["wikidata"],
        source_url: "https://dbpedia.org/page/Mock",
      },
    ];

    return {
      query: request.query,
      results: mockResults,
      links: [], // No mock links for now
      total_results: mockResults.length,
      total_links: 0,
      sources_searched: request.sources || ["conceptnet", "dbpedia"],
      execution_time_ms: 150,
      source_errors: {
        schema_org: "Mock error: Service temporarily unavailable",
      },
    };
  }

  private getMockNode(nodeId: string): UnifiedNode {
    return {
      id: nodeId,
      title: `Mock Node ${nodeId}`,
      definition: `This is a mock node with ID ${nodeId}. The backend implementation is not yet available.`,
      source: "conceptnet",
      confidence_score: 1.0,
      created_at: new Date().toISOString(),
      metadata: {
        mock: true,
        note: "Backend not implemented",
      },
    };
  }

  private getMockLinks(nodeId: string): UnifiedLink[] {
    return [
      {
        id: "mock-link-1",
        source_node_id: nodeId,
        target_node_id: "mock-target-1",
        predicate: "RelatedTo",
        source: "conceptnet",
        confidence_score: 0.9,
      },
      {
        id: "mock-link-2",
        source_node_id: "mock-source-1",
        target_node_id: nodeId,
        predicate: "IsA",
        source: "wordnet",
        confidence_score: 0.85,
      },
    ];
  }


  /**
   * Validate search request parameters
   */
  private validateSearchRequest(request: UnifiedSearchRequest): void {
    if (request.limit && (request.limit < 1 || request.limit > 100)) {
      throw new UnifiedReferenceError("Limit must be between 1 and 100");
    }

    if (request.offset && request.offset < 0) {
      throw new UnifiedReferenceError("Offset must be non-negative");
    }

  }

  /**
   * Helper method to determine if an error is recoverable
   */
  private isRecoverableError(error: Error): boolean {
    return (
      error.message.includes("timeout") ||
      error.message.includes("network") ||
      error.message.includes("503") ||
      error.message.includes("502")
    );
  }
}

// Export singleton instance
export const unifiedReferenceService = new UnifiedReferenceService();
