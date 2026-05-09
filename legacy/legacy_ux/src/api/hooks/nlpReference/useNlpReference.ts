/**
 * NLP Reference Query Hooks
 *
 * React Query hooks for external NLP reference data sources (DBpedia, ConceptNet, Wikidata, etc.)
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  nlpReferenceService,
  type DBpediaResourceParams,
  type DBpediaSearchParams,
  type ConceptNetQueryParams,
  type ConceptNetRelatedParams,
  type WikidataEntityParams,
  type SchemaOrgEntityParams,
  type SchemaOrgPropertyParams,
  type SchemaOrgReferenceSearchParams,
  type MultiSourceSearchResponse,
} from "../../services/nlpReference";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

// DBpedia Hooks
/**
 * Hook to get DBpedia resource data
 */
export const useDBpediaResource = (
  params: DBpediaResourceParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.NLP_REFERENCE,
      "dbpedia-resource",
      params,
    ),
    queryFn: () => nlpReferenceService.getDBpediaResource(params),
    enabled: !!params.resource_url,
    ...options,
  });
};

/**
 * Hook to search DBpedia entities
 */
export const useDBpediaSearch = (
  params: DBpediaSearchParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.NLP_REFERENCE,
      "dbpedia-search",
      params,
    ),
    queryFn: () => nlpReferenceService.searchDBpedia(params),
    enabled: !!params.query?.trim(),
    ...options,
  });
};

// ConceptNet Hooks
/**
 * Hook to query ConceptNet
 */
export const useConceptNetQuery = (
  params?: ConceptNetQueryParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.NLP_REFERENCE,
      "conceptnet-query",
      params,
    ),
    queryFn: () => nlpReferenceService.queryConceptNet(params),
    ...options,
  });
};

/**
 * Hook to get ConceptNet concept
 */
export const useConceptNetConcept = (
  conceptPath: string,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP_REFERENCE, "conceptnet-concept", {
      conceptPath,
    }),
    queryFn: () => nlpReferenceService.getConceptNetConcept(conceptPath),
    enabled: !!conceptPath,
    ...options,
  });
};

/**
 * Hook to get ConceptNet related concepts
 */
export const useConceptNetRelated = (
  conceptPath: string,
  params?: ConceptNetRelatedParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP_REFERENCE, "conceptnet-related", {
      conceptPath,
      ...params,
    }),
    queryFn: () =>
      nlpReferenceService.getConceptNetRelated(conceptPath, params),
    enabled: !!conceptPath,
    ...options,
  });
};

// Wikidata Hooks
/**
 * Hook to get Wikidata entity
 */
export const useWikidataEntity = (
  params: WikidataEntityParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.NLP_REFERENCE,
      "wikidata-entity",
      params,
    ),
    queryFn: () => nlpReferenceService.getWikidataEntity(params),
    enabled: !!params.entity_url,
    ...options,
  });
};

// Schema.org Reference Hooks
/**
 * Hook to get Schema.org entity via reference API
 */
export const useSchemaOrgReferenceEntity = (
  identifier: string,
  params?: SchemaOrgEntityParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP_REFERENCE, "schemaorg-entity", {
      identifier,
      ...params,
    }),
    queryFn: () => nlpReferenceService.getSchemaOrgEntity(identifier, params),
    enabled: !!identifier,
    ...options,
  });
};

/**
 * Hook to get Schema.org property via reference API
 */
export const useSchemaOrgReferenceProperty = (
  identifier: string,
  params?: SchemaOrgPropertyParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP_REFERENCE, "schemaorg-property", {
      identifier,
      ...params,
    }),
    queryFn: () => nlpReferenceService.getSchemaOrgProperty(identifier, params),
    enabled: !!identifier,
    ...options,
  });
};

/**
 * Hook to search Schema.org via reference API
 */
export const useSchemaOrgReferenceSearch = (
  params: SchemaOrgReferenceSearchParams,
  options?: UseQueryOptions<MultiSourceSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.NLP_REFERENCE,
      "schemaorg-search",
      params,
    ),
    queryFn: () => nlpReferenceService.searchSchemaOrg(params),
    enabled: !!params.query?.trim(),
    ...options,
  });
};

/**
 * Hook to get NLP reference APIs health status
 */
export const useNLPReferenceHealth = (
  options?: UseQueryOptions<unknown, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NLP_REFERENCE, "health"),
    queryFn: () => nlpReferenceService.getHealthStatus(),
    ...options,
  });
};
