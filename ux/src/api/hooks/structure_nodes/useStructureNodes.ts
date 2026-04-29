/**
 * Structure Nodes Query Hooks (DEPRECATED - For UI Backward Compatibility)
 *
 * These hooks are deprecated and exist only for backward compatibility with existing UI components.
 * New development should use entity-specific hooks instead.
 *
 * The old API used a unified StructureNode type with node_type discriminator.
 * The new API uses entity-specific types: Taxonomy, ConceptScheme, OntologyClass, Relationship, PropertyDefinition.
 *
 * This mapping is approximate and should be refactored to use the new entity-specific hooks:
 * - useLayerNodes() -> useTaxonomies()
 * - useDomainNodes() -> useConceptSchemes()
 * - useTermNodes() -> useOntologyClasses()
 */

import {
  useQuery,
  UseQueryOptions,
} from "@tanstack/react-query";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  StructureNode,
  StructureNodeListParams,
  NodeType,
  FindStructureNodeResult,
  StructureNodeFindParams,
} from "../../types/structureNodes";

/**
 * DEPRECATED: Map legacy structure node concepts to new ontology entities
 * This is a placeholder that returns empty arrays - components should migrate to entity-specific hooks
 */
export const useStructureNodes = (
  params?: StructureNodeListParams,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, undefined, params),
    queryFn: async () => {
      console.warn(
        "useStructureNodes is deprecated. Use entity-specific hooks instead: useTaxonomies, useConceptSchemes, useOntologyClasses, etc.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Fetch a single page of structure nodes
 */
export const useStructureNodesPage = (
  params?: StructureNodeListParams,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, "page", params),
    queryFn: async () => {
      console.warn(
        "useStructureNodesPage is deprecated. Use entity-specific hooks instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Fetch a specific structure node by ID
 */
export const useStructureNode = (
  id: string,
  options?: UseQueryOptions<StructureNode, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, id),
    queryFn: async () => {
      console.warn(
        "useStructureNode is deprecated. Use entity-specific hooks instead.",
      );
      throw new Error(
        "useStructureNode is deprecated. Migrate to entity-specific hooks: useTaxonomy, useConceptScheme, useOntologyClass, etc.",
      );
    },
    enabled: !!id,
    ...options,
  });
};

/**
 * DEPRECATED: Convenience hook for layers
 * Maps to useTaxonomies in the new API
 */
export const useLayerNodes = (
  params?: Omit<StructureNodeListParams, "node_type">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, "layers", params),
    queryFn: async () => {
      console.warn(
        "useLayerNodes is deprecated. Use useTaxonomies() instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Convenience hook for domains
 * Maps to useConceptSchemes in the new API
 */
export const useDomainNodes = (
  layerId?: string,
  params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.CONCEPT_SCHEMES, "domains", {
      layerId,
      ...params,
    }),
    queryFn: async () => {
      console.warn(
        "useDomainNodes is deprecated. Use useConceptSchemes() instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Convenience hook for terms
 * Maps to useOntologyClasses in the new API
 */
export const useTermNodes = (
  parentId?: string,
  params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.ONTOLOGY_CLASSES, "terms", {
      parentId,
      ...params,
    }),
    queryFn: async () => {
      console.warn(
        "useTermNodes is deprecated. Use useOntologyClasses() instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Find structure nodes using semantic search
 */
export const useStructureNodeFind = (
  params: StructureNodeFindParams,
  options?: UseQueryOptions<FindStructureNodeResult[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, "find", params),
    queryFn: async () => {
      console.warn(
        "useStructureNodeFind is deprecated. Use entity-specific search hooks instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Search structure nodes
 */
export const useStructureNodeSearch = (
  query: string,
  limit?: number,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, "search", { query, limit }),
    queryFn: async () => {
      console.warn(
        "useStructureNodeSearch is deprecated. Use entity-specific search hooks instead.",
      );
      return [];
    },
    enabled: !!query,
    ...options,
  });
};
