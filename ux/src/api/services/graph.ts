/**
 * Graph Service
 *
 * Service for managing graph operations and analytics
 */

import { BaseService } from "./base";
import { ENDPOINTS } from "../config";
import type {
  SPARQLQuery,
  SearchRequest,
  CentralityRequest,
  PathRequest,
  NeighborsRequest,
} from "./missingTypes";

// Re-export types for use in hooks and components
export type {
  SPARQLQuery,
  SearchRequest,
  CentralityRequest,
  PathRequest,
  NeighborsRequest,
};

export interface GraphStats {
  [key: string]: unknown;
}

export interface GraphRefreshResponse {
  [key: string]: string;
}

export interface SPARQLResult {
  [key: string]: unknown;
}

export interface SearchAnalysisResult {
  [key: string]: unknown;
}

export interface CentralityResult {
  [key: string]: number;
}

export interface CommunityResult {
  [key: string]: string[];
}

export interface PathResult {
  path: string[] | null;
}

export interface NeighborsResult {
  [depth: string]: string[];
}

export interface TermInfoResult {
  [key: string]: unknown;
}

export interface DomainAnalysisResult {
  [key: string]: unknown;
}

export interface LayerAnalyticsResult {
  [key: string]: unknown;
}

export interface GraphExportParams extends Record<string, unknown> {
  format?: "json" | "turtle" | "graphml";
}

export interface TermSearchParams extends Record<string, unknown> {
  title: string;
  exact?: boolean;
}

export interface RelatedTermsParams extends Record<string, unknown> {
  term_id: string;
  max_depth?: number;
}

export interface DomainHierarchyParams extends Record<string, unknown> {
  layer_id?: string;
}

export interface LayerAnalyticsParams extends Record<string, unknown> {
  layer_id?: string;
}

export interface CommunityDetectionParams extends Record<string, unknown> {
  method?: string;
}

export interface RDFExportParams extends Record<string, unknown> {
  format?: string;
}

export class GraphService extends BaseService {
  // ================== Stats & Management ==================

  /**
   * Get comprehensive graph statistics
   */
  async getStats(): Promise<GraphStats> {
    return this.withErrorContext(
      () => this.getResource<GraphStats>(`${ENDPOINTS.GRAPH}/stats`),
      "get graph stats",
    );
  }

  /**
   * Refresh both SPARQL and NetworkX graphs from the database
   */
  async refresh(): Promise<GraphRefreshResponse> {
    return this.withErrorContext(
      () =>
        this.postResource<GraphRefreshResponse>(`${ENDPOINTS.GRAPH}/refresh`),
      "refresh graphs",
    );
  }

  // ================== SPARQL Operations ==================

  /**
   * Execute a SPARQL query against the RDF graph
   */
  async executeSparqlQuery(data: SPARQLQuery): Promise<SPARQLResult[]> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "SPARQL query data");
      this.validateRequired(data.query, "SPARQL query");
      this.sanitizeString((data.query as unknown as string) || '', "SPARQL query", 10000);

      return this.postResource<SPARQLResult[]>(
        `${ENDPOINTS.GRAPH}/sparql/query`,
        data,
      );
    }, "execute SPARQL query");
  }

  /**
   * Export the RDF graph in various formats
   */
  async exportRdf(params?: RDFExportParams): Promise<string> {
    return this.withErrorContext(
      () =>
        this.getResource<string>(`${ENDPOINTS.GRAPH}/sparql/export`, params),
      "export RDF",
    );
  }

  /**
   * Get example SPARQL queries
   */
  async getSparqlExamples(): Promise<{ [key: string]: string }> {
    return this.withErrorContext(
      () =>
        this.getResource<{ [key: string]: string }>(
          `${ENDPOINTS.GRAPH}/examples/sparql`,
        ),
      "get SPARQL examples",
    );
  }

  // ================== Search Operations ==================

  /**
   * Search for terms by title using SPARQL
   */
  async searchTerms(
    params: TermSearchParams,
  ): Promise<Array<{ [key: string]: unknown }>> {
    return this.withErrorContext(() => {
      this.validateRequired(params, "Search parameters");
      this.validateRequired(params.title, "Search title");
      this.sanitizeString((params.title as unknown as string) || '', "Search title", 1000);

      return this.getResource<Array<{ [key: string]: unknown }>>(
        `${ENDPOINTS.GRAPH}/search/terms`,
        params,
      );
    }, "search terms");
  }

  /**
   * Search for terms and provide comprehensive analysis
   */
  async searchAndAnalyze(data: SearchRequest): Promise<SearchAnalysisResult> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Search request data");
      this.validateRequired(data.term, "Search term");
      this.sanitizeString((data.term as unknown as string) || '', "Search term", 1000);

      return this.postResource<SearchAnalysisResult>(
        `${ENDPOINTS.GRAPH}/search/analyze`,
        data,
      );
    }, "search and analyze");
  }

  // ================== Analytics Operations ==================

  /**
   * Calculate node centrality using NetworkX algorithms
   */
  async calculateCentrality(
    data: CentralityRequest,
  ): Promise<CentralityResult> {
    return this.withErrorContext(
      () =>
        this.postResource<CentralityResult>(
          `${ENDPOINTS.GRAPH}/analytics/centrality`,
          data,
        ),
      "calculate centrality",
    );
  }

  /**
   * Detect communities in the graph using NetworkX algorithms
   */
  async detectCommunities(
    params?: CommunityDetectionParams,
  ): Promise<string[][]> {
    return this.withErrorContext(
      () =>
        this.getResource<string[][]>(
          `${ENDPOINTS.GRAPH}/analytics/communities`,
          params,
        ),
      "detect communities",
    );
  }

  // ================== Path & Neighbor Operations ==================

  /**
   * Find the shortest path between two nodes
   */
  async findShortestPath(data: PathRequest): Promise<string[] | null> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Path request data");
      this.validateRequired(data.source_id, "Source ID");
      this.validateRequired(data.target_id, "Target ID");

      return this.postResource<string[] | null>(
        `${ENDPOINTS.GRAPH}/path/shortest`,
        data,
      );
    }, "find shortest path");
  }

  /**
   * Get neighbors of a node at specified depth
   */
  async getNeighbors(data: NeighborsRequest): Promise<NeighborsResult> {
    return this.withErrorContext(() => {
      this.validateRequired(data, "Neighbors request data");
      this.validateRequired(data.entity_id, "Entity ID");

      return this.postResource<NeighborsResult>(
        `${ENDPOINTS.GRAPH}/neighbors`,
        data,
      );
    }, "get neighbors");
  }

  // ================== Term-specific Operations ==================

  /**
   * Find related terms using both SPARQL and NetworkX
   */
  async findRelatedTerms(
    termId: string,
    params?: { max_depth?: number },
  ): Promise<{ [key: string]: unknown }> {
    return this.withErrorContext(() => {
      this.validateRequired(termId, "Term ID");
      return this.getResource<{ [key: string]: unknown }>(
        `${ENDPOINTS.GRAPH}/terms/${termId}/related`,
        params,
      );
    }, "find related terms");
  }

  /**
   * Get the full hierarchy for a term (ancestors and descendants)
   */
  async getTermHierarchy(termId: string): Promise<{ [key: string]: unknown }> {
    return this.withErrorContext(() => {
      this.validateRequired(termId, "Term ID");
      return this.getResource<{ [key: string]: unknown }>(
        `${ENDPOINTS.GRAPH}/terms/${termId}/hierarchy`,
      );
    }, "get term hierarchy");
  }

  /**
   * Get detailed information about a specific term
   */
  async getTermInfo(termId: string): Promise<TermInfoResult | null> {
    return this.withErrorContext(() => {
      this.validateRequired(termId, "Term ID");
      return this.getResource<TermInfoResult | null>(
        `${ENDPOINTS.GRAPH}/terms/${termId}/info`,
      );
    }, "get term info");
  }

  // ================== Domain-specific Operations ==================

  /**
   * Comprehensive analysis of a domain's structure
   */
  async analyzeDomain(domainId: string): Promise<DomainAnalysisResult> {
    return this.withErrorContext(() => {
      this.validateRequired(domainId, "Domain ID");
      return this.getResource<DomainAnalysisResult>(
        `${ENDPOINTS.GRAPH}/domains/${domainId}/analyze`,
      );
    }, "analyze domain");
  }

  /**
   * Get detailed information about a specific domain
   */
  async getDomainInfo(
    domainId: string,
  ): Promise<{ [key: string]: unknown } | null> {
    return this.withErrorContext(() => {
      this.validateRequired(domainId, "Domain ID");
      return this.getResource<{ [key: string]: unknown } | null>(
        `${ENDPOINTS.GRAPH}/domains/${domainId}/info`,
      );
    }, "get domain info");
  }

  /**
   * Get the domain hierarchy for a layer or all layers
   */
  async getDomainHierarchy(
    params?: DomainHierarchyParams,
  ): Promise<Array<{ [key: string]: unknown }>> {
    return this.withErrorContext(
      () =>
        this.getResource<Array<{ [key: string]: unknown }>>(
          `${ENDPOINTS.GRAPH}/domains/hierarchy`,
          params,
        ),
      "get domain hierarchy",
    );
  }

  // ================== Layer-specific Operations ==================

  /**
   * Get comprehensive analytics for a layer or all layers
   */
  async getLayerAnalytics(
    params?: LayerAnalyticsParams,
  ): Promise<LayerAnalyticsResult> {
    return this.withErrorContext(
      () =>
        this.getResource<LayerAnalyticsResult>(
          `${ENDPOINTS.GRAPH}/layers/analytics`,
          params,
        ),
      "get layer analytics",
    );
  }

  /**
   * Get detailed information about a specific layer
   */
  async getLayerInfo(
    layerId: string,
  ): Promise<{ [key: string]: unknown } | null> {
    return this.withErrorContext(() => {
      this.validateRequired(layerId, "Layer ID");
      return this.getResource<{ [key: string]: unknown } | null>(
        `${ENDPOINTS.GRAPH}/layers/${layerId}/info`,
      );
    }, "get layer info");
  }

  // ================== Export Operations ==================

  /**
   * Export comprehensive graph data in various formats
   */
  async exportGraph(params?: GraphExportParams): Promise<unknown> {
    return this.withErrorContext(
      () => this.getResource<unknown>(`${ENDPOINTS.GRAPH}/export`, params),
      "export graph",
    );
  }
}

// Export singleton instance
export const graphService = new GraphService();
