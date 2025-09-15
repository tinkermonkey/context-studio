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
  SourceStatus,
  UnifiedReferenceError,
  SourceUnavailableError,
  SearchTimeoutError,
} from "../types/unified";

export class UnifiedReferenceService extends BaseService {
  private readonly UNIFIED_ENDPOINT = `${ENDPOINTS.NLP_REFERENCE}/unified`;

  /**
   * Search across all unified reference sources
   */
  async search(request: UnifiedSearchRequest): Promise<UnifiedSearchResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(request, "Search request");
      this.validateRequired(request.query, "Search query");
      this.sanitizeString(request.query, "Search query", 1000);

      if (request.query.trim().length < 2) {
        throw new UnifiedReferenceError("Search query must be at least 2 characters");
      }

      if (request.sources && request.sources.length === 0) {
        throw new UnifiedReferenceError("At least one source must be selected");
      }

      try {
        return await this.postResource<UnifiedSearchResponse>(
          `${this.UNIFIED_ENDPOINT}/search`,
          request
        );
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          // Backend not implemented yet - return mock data for development
          return this.getMockSearchResponse(request);
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

      try {
        return await this.getResource<UnifiedNode>(
          `${this.UNIFIED_ENDPOINT}/node/${nodeId}`
        );
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          // Backend not implemented yet - return mock data for development
          return this.getMockNode(nodeId);
        }
        throw error;
      }
    }, "get unified node");
  }

  /**
   * Get links for a specific node
   */
  async getLinks(
    nodeId: string,
    direction: "from" | "to" | "both" = "both"
  ): Promise<UnifiedLink[]> {
    return this.withErrorContext(async () => {
      this.validateRequired(nodeId, "Node ID");
      this.sanitizeString(nodeId, "Node ID", 255);

      const params = { node_id: nodeId, direction };

      try {
        return await this.getResource<UnifiedLink[]>(
          `${this.UNIFIED_ENDPOINT}/links`,
          params
        );
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          // Backend not implemented yet - return mock data for development
          return this.getMockLinks(nodeId);
        }
        throw error;
      }
    }, "get node links");
  }

  /**
   * Get available reference sources
   */
  async getSources(): Promise<string[]> {
    return this.withErrorContext(async () => {
      try {
        return await this.getResource<string[]>(
          `${this.UNIFIED_ENDPOINT}/sources`
        );
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          // Backend not implemented yet - return default sources
          return ["conceptnet", "wordnet", "dbpedia", "wikidata", "schema_org"];
        }
        throw error;
      }
    }, "get available sources");
  }

  /**
   * Get source status information
   */
  async getSourceStatus(): Promise<SourceStatus[]> {
    return this.withErrorContext(async () => {
      try {
        return await this.getResource<SourceStatus[]>(
          `${this.UNIFIED_ENDPOINT}/sources/status`
        );
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          // Backend not implemented yet - return mock status
          return this.getMockSourceStatus();
        }
        throw error;
      }
    }, "get source status");
  }

  /**
   * Paginated search with load more functionality
   */
  async searchPaginated(
    request: UnifiedSearchRequest,
    cursor?: string
  ): Promise<UnifiedSearchResponse> {
    const paginatedRequest = {
      ...request,
      cursor,
    };

    return this.search(paginatedRequest);
  }

  // Mock data methods for development (when backend is not ready)
  private getMockSearchResponse(request: UnifiedSearchRequest): UnifiedSearchResponse {
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
      total_results: mockResults.length,
      search_type: request.search_type,
      sources: request.sources || ["conceptnet", "dbpedia"],
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

  private getMockSourceStatus(): SourceStatus[] {
    return [
      {
        name: "conceptnet",
        available: true,
        last_check: new Date().toISOString(),
        response_time_ms: 120,
      },
      {
        name: "wordnet",
        available: true,
        last_check: new Date().toISOString(),
        response_time_ms: 95,
      },
      {
        name: "dbpedia",
        available: true,
        last_check: new Date().toISOString(),
        response_time_ms: 200,
      },
      {
        name: "wikidata",
        available: false,
        last_check: new Date().toISOString(),
        error_message: "Connection timeout",
        response_time_ms: 5000,
      },
      {
        name: "schema_org",
        available: true,
        last_check: new Date().toISOString(),
        response_time_ms: 150,
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

    const validSearchTypes = ["title", "definition"];
    if (!validSearchTypes.includes(request.search_type)) {
      throw new UnifiedReferenceError(
        `Search type must be one of: ${validSearchTypes.join(", ")}`
      );
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