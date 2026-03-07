/**
 * NLP Reference Mutation Hooks
 *
 * React Query mutation hooks for NLP reference operations (SPARQL queries)
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import {
  nlpReferenceService,
  type DBpediaSparqlRequest,
  type WikidataSparqlRequest,
  type MultiSourceSearchResponse,
} from "../../services/nlpReference";

/**
 * Hook to execute DBpedia SPARQL query
 */
export const useDBpediaSparql = (
  options?: UseMutationOptions<
    MultiSourceSearchResponse,
    Error,
    DBpediaSparqlRequest
  >,
) => {
  return useMutation({
    mutationFn: (data: DBpediaSparqlRequest) =>
      nlpReferenceService.queryDBpediaSparql(data),
    ...options,
  });
};

/**
 * Hook to execute Wikidata SPARQL query
 */
export const useWikidataSparql = (
  options?: UseMutationOptions<
    MultiSourceSearchResponse,
    Error,
    WikidataSparqlRequest
  >,
) => {
  return useMutation({
    mutationFn: (data: WikidataSparqlRequest) =>
      nlpReferenceService.queryWikidataSparql(data),
    ...options,
  });
};
