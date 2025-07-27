/**
 * Graph Service
 * 
 * Service for managing graph operations and analytics
 */

import { BaseService } from './base';
import { ENDPOINTS } from '../config';
import type { components } from '../client/types';

// Type aliases for better readability
export type SPARQLQuery = components['schemas']['SPARQLQuery'];
export type SearchRequest = components['schemas']['SearchRequest'];
export type CentralityRequest = components['schemas']['CentralityRequest'];
export type PathRequest = components['schemas']['PathRequest'];
export type NeighborsRequest = components['schemas']['NeighborsRequest'];

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

export interface GraphExportParams {
  format?: 'json' | 'turtle' | 'graphml';
}

export interface TermSearchParams {
  title: string;
  exact?: boolean;
}

export interface RelatedTermsParams {
  term_id: string;
  max_depth?: number;
}

export interface DomainHierarchyParams {
  layer_id?: string;
}

export interface LayerAnalyticsParams {
  layer_id?: string;
}

export interface CommunityDetectionParams {
  method?: string;
}

export interface RDFExportParams {
  format?: string;
}

export class GraphService extends BaseService {
  
  // ================== Stats & Management ==================
  
  /**
   * Get comprehensive graph statistics
   */
  async getStats(): Promise<GraphStats> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/stats`,
    });
  }

  /**
   * Refresh both SPARQL and NetworkX graphs from the database
   */
  async refresh(): Promise<GraphRefreshResponse> {
    return this.request({
      method: 'POST',
      url: `${ENDPOINTS.GRAPH}/refresh`,
    });
  }

  // ================== SPARQL Operations ==================
  
  /**
   * Execute a SPARQL query against the RDF graph
   */
  async executeSparqlQuery(data: SPARQLQuery): Promise<SPARQLResult[]> {
    return this.request({
      method: 'POST',
      url: `${ENDPOINTS.GRAPH}/sparql/query`,
      data,
    });
  }

  /**
   * Export the RDF graph in various formats
   */
  async exportRdf(params?: RDFExportParams): Promise<string> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/sparql/export`,
      params,
    });
  }

  /**
   * Get example SPARQL queries
   */
  async getSparqlExamples(): Promise<{ [key: string]: string }> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/examples/sparql`,
    });
  }

  // ================== Search Operations ==================
  
  /**
   * Search for terms by title using SPARQL
   */
  async searchTerms(params: TermSearchParams): Promise<Array<{ [key: string]: unknown }>> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/search/terms`,
      params,
    });
  }

  /**
   * Search for terms and provide comprehensive analysis
   */
  async searchAndAnalyze(data: SearchRequest): Promise<SearchAnalysisResult> {
    return this.request({
      method: 'POST',
      url: `${ENDPOINTS.GRAPH}/search/analyze`,
      data,
    });
  }

  // ================== Analytics Operations ==================
  
  /**
   * Calculate node centrality using NetworkX algorithms
   */
  async calculateCentrality(data: CentralityRequest): Promise<CentralityResult> {
    return this.request({
      method: 'POST',
      url: `${ENDPOINTS.GRAPH}/analytics/centrality`,
      data,
    });
  }

  /**
   * Detect communities in the graph using NetworkX algorithms
   */
  async detectCommunities(params?: CommunityDetectionParams): Promise<CommunityResult[]> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/analytics/communities`,
      params,
    });
  }

  // ================== Path & Neighbor Operations ==================
  
  /**
   * Find the shortest path between two nodes
   */
  async findShortestPath(data: PathRequest): Promise<string[] | null> {
    const result = await this.request<string[] | null>({
      method: 'POST',
      url: `${ENDPOINTS.GRAPH}/path/shortest`,
      data,
    });
    return result;
  }

  /**
   * Get neighbors of a node at specified depth
   */
  async getNeighbors(data: NeighborsRequest): Promise<NeighborsResult> {
    return this.request({
      method: 'POST',
      url: `${ENDPOINTS.GRAPH}/neighbors`,
      data,
    });
  }

  // ================== Term-specific Operations ==================
  
  /**
   * Find related terms using both SPARQL and NetworkX
   */
  async findRelatedTerms(termId: string, params?: { max_depth?: number }): Promise<{ [key: string]: unknown }> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/terms/${termId}/related`,
      params,
    });
  }

  /**
   * Get the full hierarchy for a term (ancestors and descendants)
   */
  async getTermHierarchy(termId: string): Promise<{ [key: string]: unknown }> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/terms/${termId}/hierarchy`,
    });
  }

  /**
   * Get detailed information about a specific term
   */
  async getTermInfo(termId: string): Promise<TermInfoResult | null> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/terms/${termId}/info`,
    });
  }

  // ================== Domain-specific Operations ==================
  
  /**
   * Comprehensive analysis of a domain's structure
   */
  async analyzeDomain(domainId: string): Promise<DomainAnalysisResult> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/domains/${domainId}/analyze`,
    });
  }

  /**
   * Get detailed information about a specific domain
   */
  async getDomainInfo(domainId: string): Promise<{ [key: string]: unknown } | null> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/domains/${domainId}/info`,
    });
  }

  /**
   * Get the domain hierarchy for a layer or all layers
   */
  async getDomainHierarchy(params?: DomainHierarchyParams): Promise<Array<{ [key: string]: unknown }>> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/domains/hierarchy`,
      params,
    });
  }

  // ================== Layer-specific Operations ==================
  
  /**
   * Get comprehensive analytics for a layer or all layers
   */
  async getLayerAnalytics(params?: LayerAnalyticsParams): Promise<LayerAnalyticsResult> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/layers/analytics`,
      params,
    });
  }

  /**
   * Get detailed information about a specific layer
   */
  async getLayerInfo(layerId: string): Promise<{ [key: string]: unknown } | null> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/layers/${layerId}/info`,
    });
  }

  // ================== Export Operations ==================
  
  /**
   * Export comprehensive graph data in various formats
   */
  async exportGraph(params?: GraphExportParams): Promise<unknown> {
    return this.request({
      method: 'GET',
      url: `${ENDPOINTS.GRAPH}/export`,
      params,
    });
  }
}

// Export singleton instance
export const graphService = new GraphService();
