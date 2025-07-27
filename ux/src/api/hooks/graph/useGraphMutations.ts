/**
 * Graph Mutation Hooks
 * 
 * React Query mutation hooks for graph operations
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { 
  graphService,
  type SPARQLQuery,
  type SearchRequest,
  type CentralityRequest,
  type PathRequest,
  type NeighborsRequest,
  type GraphRefreshResponse,
  type SPARQLResult,
  type SearchAnalysisResult,
  type CentralityResult,
  type NeighborsResult
} from '../../services/graph';
import { QUERY_KEYS } from '../../config';

/**
 * Hook to refresh graph data
 */
export const useGraphRefresh = (
  options?: UseMutationOptions<GraphRefreshResponse, Error, void>
) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: () => graphService.refresh(),
    onSuccess: () => {
      // Invalidate all graph queries after refresh
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.GRAPH],
      });
    },
    ...options,
  });
};

/**
 * Hook to execute SPARQL queries
 */
export const useSparqlQuery = (
  options?: UseMutationOptions<SPARQLResult[], Error, SPARQLQuery>
) => {
  return useMutation({
    mutationFn: (data: SPARQLQuery) => graphService.executeSparqlQuery(data),
    ...options,
  });
};

/**
 * Hook to search and analyze terms
 */
export const useSearchAndAnalyze = (
  options?: UseMutationOptions<SearchAnalysisResult, Error, SearchRequest>
) => {
  return useMutation({
    mutationFn: (data: SearchRequest) => graphService.searchAndAnalyze(data),
    ...options,
  });
};

/**
 * Hook to calculate centrality
 */
export const useCentralityCalculation = (
  options?: UseMutationOptions<CentralityResult, Error, CentralityRequest>
) => {
  return useMutation({
    mutationFn: (data: CentralityRequest) => graphService.calculateCentrality(data),
    ...options,
  });
};

/**
 * Hook to find shortest path
 */
export const useShortestPath = (
  options?: UseMutationOptions<string[] | null, Error, PathRequest>
) => {
  return useMutation({
    mutationFn: (data: PathRequest) => graphService.findShortestPath(data),
    ...options,
  });
};

/**
 * Hook to get neighbors
 */
export const useNeighborsQuery = (
  options?: UseMutationOptions<NeighborsResult, Error, NeighborsRequest>
) => {
  return useMutation({
    mutationFn: (data: NeighborsRequest) => graphService.getNeighbors(data),
    ...options,
  });
};
