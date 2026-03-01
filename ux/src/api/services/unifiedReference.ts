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
  SourceType,
} from "../types/unified";
import {
  SOURCE_ENDPOINTS,
  getEnabledSources,
} from "../types/streamingReference";

export class UnifiedReferenceService extends BaseService {
  private readonly SEARCH_ENDPOINT = `/api/reference/search`;

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

        // Backend now returns normalized data directly
        return {
          query: response.query,
          results: response.results,
          links: response.links || [],
          total_results: response.total_results,
          total_links: response.total_links,
          sources_queried: response.sources_queried,
          source_errors: response.source_errors,
          offset: response.offset,
          limit: response.limit,
          search_time_ms: response.search_time_ms,
        };
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          throw new UnifiedReferenceError(
            "Search endpoint not found. Please ensure the backend service is properly configured and running.",
            undefined,
            error
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
   * Search a specific reference source directly
   */
  async searchSource(
    source: SourceType,
    request: UnifiedSearchRequest
  ): Promise<UnifiedSearchResponse> {
    return this.withErrorContext(async () => {
      this.validateRequired(request, "Search request");
      this.validateRequired(request.query, "Search query");
      this.sanitizeString(request.query, "Search query", 1000);

      if (request.query.trim().length < 2) {
        throw new UnifiedReferenceError(
          "Search query must be at least 2 characters"
        );
      }

      const config = SOURCE_ENDPOINTS[source];
      if (!config || !config.enabled) {
        throw new UnifiedReferenceError(
          `Source ${source} is not available or not enabled`
        );
      }

      try {
        const params = {
          query: request.query,
          limit: request.limit || 20,
          offset: request.offset || 0,
        };

        const response = await this.getResource<MultiSourceSearchResponse>(
          config.endpoint,
          params
        );

        // Backend now returns normalized data directly
        return {
          query: response.query,
          results: response.results,
          links: response.links || [],
          total_results: response.total_results,
          total_links: response.total_links,
          sources_queried: response.sources_queried,
          source_errors: response.source_errors,
          offset: response.offset,
          limit: response.limit,
          search_time_ms: response.search_time_ms,
        };
      } catch (error) {
        if (error instanceof Error && error.message.includes("404")) {
          throw new UnifiedReferenceError(
            `${source} search endpoint not found. Please ensure the backend service supports this source.`,
            undefined,
            error
          );
        }
        throw error;
      }
    }, `${source} search`);
  }


  /**
   * Get available sources and their status
   */
  async getAvailableSources(): Promise<Record<SourceType, { enabled: boolean; endpoint: string }>> {
    return this.withErrorContext(async () => {
      const sources: Record<SourceType, { enabled: boolean; endpoint: string }> = {} as Record<SourceType, { enabled: boolean; endpoint: string }>;

      Object.entries(SOURCE_ENDPOINTS).forEach(([source, config]) => {
        sources[source as SourceType] = {
          enabled: config.enabled,
          endpoint: config.endpoint,
        };
      });

      return sources;
    }, "get available sources");
  }

  /**
   * Test connectivity to a specific source
   */
  async testSourceConnectivity(source: SourceType): Promise<{
    available: boolean;
    responseTime?: number;
    error?: string;
  }> {
    return this.withErrorContext(async () => {
      const config = SOURCE_ENDPOINTS[source];
      if (!config) {
        return {
          available: false,
          error: `Source ${source} is not configured`,
        };
      }

      if (!config.enabled) {
        return {
          available: false,
          error: `Source ${source} is disabled`,
        };
      }

      const startTime = Date.now();

      try {
        // Try a minimal search to test connectivity
        await this.getResource(config.endpoint, {
          query: "test",
          limit: 1,
        });

        return {
          available: true,
          responseTime: Date.now() - startTime,
        };
      } catch (error) {
        return {
          available: false,
          responseTime: Date.now() - startTime,
          error: error instanceof Error ? error.message : "Unknown error",
        };
      }
    }, `test ${source} connectivity`);
  }




}

// Export singleton instance
export const unifiedReferenceService = new UnifiedReferenceService();
