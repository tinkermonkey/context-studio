/**
 * NLP Reference Mutation Hooks
 * 
 * React Query mutation hooks for NLP reference operations (SPARQL queries)
 */

import { useMutation, UseMutationOptions } from '@tanstack/react-query';
import { 
  nlpReferenceService,
  type DBpediaSparqlRequest,
  type DBpediaSparqlResponse,
  type WikidataSparqlRequest,
  type WikidataSparqlResponse
} from '../../services/nlpReference';

/**
 * Hook to execute DBpedia SPARQL query
 */
export const useDBpediaSparql = (
  options?: UseMutationOptions<DBpediaSparqlResponse, Error, DBpediaSparqlRequest>
) => {
  return useMutation({
    mutationFn: (data: DBpediaSparqlRequest) => nlpReferenceService.queryDBpediaSparql(data),
    ...options,
  });
};

/**
 * Hook to execute Wikidata SPARQL query
 */
export const useWikidataSparql = (
  options?: UseMutationOptions<WikidataSparqlResponse, Error, WikidataSparqlRequest>
) => {
  return useMutation({
    mutationFn: (data: WikidataSparqlRequest) => nlpReferenceService.queryWikidataSparql(data),
    ...options,
  });
};
