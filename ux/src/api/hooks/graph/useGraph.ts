/**
 * Graph Query Hooks
 *
 * React Query hooks for graph operations
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  graphService,
  type GraphStats,
  type TermSearchParams,
  type RelatedTermsParams,
  type DomainHierarchyParams,
  type LayerAnalyticsParams,
  type CommunityDetectionParams,
  type RDFExportParams,
  type GraphExportParams,
  type TermInfoResult,
  type DomainAnalysisResult,
  type LayerAnalyticsResult,
} from "../../services/graph";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to get graph statistics
 */
export const useGraphStats = (options?: UseQueryOptions<GraphStats, Error>) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, "stats"),
    queryFn: () => graphService.getStats(),
    ...options,
  });
};

/**
 * Hook to search terms by title
 */
export const useTermSearch = (
  params: TermSearchParams,
  options?: UseQueryOptions<Array<{ [key: string]: unknown }>, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, "search-terms", { ...params }),
    queryFn: () => graphService.searchTerms(params),
    enabled: !!params.title && params.title.length > 0,
    ...options,
  });
};

/**
 * Hook to get detailed information about a specific term
 */
export const useTermInfo = (
  termId: string,
  options?: UseQueryOptions<TermInfoResult | null, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, `term-info-${termId}`),
    queryFn: () => graphService.getTermInfo(termId),
    enabled: !!termId,
    ...options,
  });
};

/**
 * Hook to find related terms
 */
export const useRelatedTerms = (
  termId: string,
  params?: { max_depth?: number },
  options?: UseQueryOptions<{ [key: string]: unknown }, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.GRAPH,
      `related-terms-${termId}`,
      params ? { ...params } : undefined,
    ),
    queryFn: () => graphService.findRelatedTerms(termId, params),
    enabled: !!termId,
    ...options,
  });
};

/**
 * Hook to get term hierarchy
 */
export const useTermHierarchy = (
  termId: string,
  options?: UseQueryOptions<{ [key: string]: unknown }, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, `term-hierarchy-${termId}`),
    queryFn: () => graphService.getTermHierarchy(termId),
    enabled: !!termId,
    ...options,
  });
};

/**
 * Hook to analyze a domain
 */
export const useDomainAnalysis = (
  domainId: string,
  options?: UseQueryOptions<DomainAnalysisResult, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, `domain-analysis-${domainId}`),
    queryFn: () => graphService.analyzeDomain(domainId),
    enabled: !!domainId,
    ...options,
  });
};

/**
 * Hook to get domain information
 */
export const useDomainInfo = (
  domainId: string,
  options?: UseQueryOptions<{ [key: string]: unknown } | null, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, `domain-info-${domainId}`),
    queryFn: () => graphService.getDomainInfo(domainId),
    enabled: !!domainId,
    ...options,
  });
};

/**
 * Hook to get domain hierarchy
 */
export const useDomainHierarchy = (
  params?: DomainHierarchyParams,
  options?: UseQueryOptions<Array<{ [key: string]: unknown }>, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.GRAPH,
      "domain-hierarchy",
      params ? { ...params } : undefined,
    ),
    queryFn: () => graphService.getDomainHierarchy(params),
    ...options,
  });
};

/**
 * Hook to get layer analytics
 */
export const useLayerAnalytics = (
  params?: LayerAnalyticsParams,
  options?: UseQueryOptions<LayerAnalyticsResult, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.GRAPH,
      "layer-analytics",
      params ? { ...params } : undefined,
    ),
    queryFn: () => graphService.getLayerAnalytics(params),
    ...options,
  });
};

/**
 * Hook to get layer information
 */
export const useLayerInfo = (
  layerId: string,
  options?: UseQueryOptions<{ [key: string]: unknown } | null, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, `layer-info-${layerId}`),
    queryFn: () => graphService.getLayerInfo(layerId),
    enabled: !!layerId,
    ...options,
  });
};

/**
 * Hook to detect communities
 */
export const useCommunityDetection = (
  params?: CommunityDetectionParams,
  options?: UseQueryOptions<string[][], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.GRAPH,
      "communities",
      params ? { ...params } : undefined,
    ),
    queryFn: () => graphService.detectCommunities(params),
    ...options,
  });
};

/**
 * Hook to get SPARQL examples
 */
export const useSparqlExamples = (
  options?: UseQueryOptions<{ [key: string]: string }, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.GRAPH, "sparql-examples"),
    queryFn: () => graphService.getSparqlExamples(),
    ...options,
  });
};

/**
 * Hook to export RDF data
 */
export const useRdfExport = (
  params?: RDFExportParams,
  options?: UseQueryOptions<string, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.GRAPH,
      "rdf-export",
      params ? { ...params } : undefined,
    ),
    queryFn: () => graphService.exportRdf(params),
    enabled: false, // Manual trigger only
    ...options,
  });
};

/**
 * Hook to export graph data
 */
export const useGraphExport = (
  params?: GraphExportParams,
  options?: UseQueryOptions<unknown, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.GRAPH,
      "graph-export",
      params ? { ...params } : undefined,
    ),
    queryFn: () => graphService.exportGraph(params),
    enabled: false, // Manual trigger only
    ...options,
  });
};
