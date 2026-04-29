/**
 * LLM Analysis Hooks
 *
 * React Query hooks for Large Language Model operations
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  llmService,
  type DefinitionSuggestionResponse,
  type DefinitionSuggestionRequest,
  type LLMHealthResponse,
  type ComponentTerm,
} from "../../services/llm";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to get LLM service health status
 */
export const useLLMHealth = (
  options?: UseQueryOptions<LLMHealthResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "health"),
    queryFn: () => llmService.healthCheck(),
    staleTime: 1 * 60 * 1000, // 1 minute - health checks should be relatively fresh
    gcTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
    ...options,
  });
};

/**
 * Hook to generate a simple definition for a term
 */
export const useSimpleDefinition = (
  term: string | null,
  options?: UseQueryOptions<DefinitionSuggestionResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "simple-definition", {
      term: term || "",
    }),
    queryFn: () => {
      if (!term) {
        throw new Error("Term is required for definition generation");
      }
      return llmService.generateSimpleDefinition(term);
    },
    enabled: !!term && term.trim().length > 0,
    staleTime: 10 * 60 * 1000, // 10 minutes - definitions are relatively stable
    gcTime: 30 * 60 * 1000, // 30 minutes
    ...options,
  });
};

/**
 * Hook to generate a definition with domain context
 */
export const useDefinitionWithDomain = (
  term: string | null,
  domainTitle: string | null,
  domainDefinition?: string | null,
  options?: UseQueryOptions<DefinitionSuggestionResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "definition-with-domain", {
      term: term || "",
      domainTitle: domainTitle || "",
      domainDefinition: domainDefinition || "",
    }),
    queryFn: () => {
      if (!term || !domainTitle) {
        throw new Error(
          "Term and domain title are required for definition generation",
        );
      }
      return llmService.generateDefinitionWithDomain(
        term,
        domainTitle,
        domainDefinition || undefined,
      );
    },
    enabled:
      !!term &&
      term.trim().length > 0 &&
      !!domainTitle &&
      domainTitle.trim().length > 0,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    ...options,
  });
};

/**
 * Hook to generate a definition with parent term context
 */
export const useDefinitionWithParent = (
  term: string | null,
  parentTermTitle: string | null,
  parentTermDefinition?: string | null,
  relationshipPredicate?: string | null,
  options?: UseQueryOptions<DefinitionSuggestionResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "definition-with-parent", {
      term: term || "",
      parentTermTitle: parentTermTitle || "",
      parentTermDefinition: parentTermDefinition || "",
      relationshipPredicate: relationshipPredicate || "",
    }),
    queryFn: () => {
      if (!term || !parentTermTitle) {
        throw new Error(
          "Term and parent term title are required for definition generation",
        );
      }
      return llmService.generateDefinitionWithParent(
        term,
        parentTermTitle,
        parentTermDefinition || undefined,
        relationshipPredicate || undefined,
      );
    },
    enabled:
      !!term &&
      term.trim().length > 0 &&
      !!parentTermTitle &&
      parentTermTitle.trim().length > 0,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    ...options,
  });
};

/**
 * Hook to generate a definition with component terms context
 */
export const useDefinitionWithComponents = (
  term: string | null,
  componentTerms: ComponentTerm[] | null,
  options?: UseQueryOptions<DefinitionSuggestionResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "definition-with-components", {
      term: term || "",
      componentTerms: JSON.stringify(componentTerms || []),
    }),
    queryFn: () => {
      if (!term || !componentTerms || componentTerms.length === 0) {
        throw new Error(
          "Term and component terms are required for definition generation",
        );
      }
      return llmService.generateDefinitionWithComponents(term, componentTerms);
    },
    enabled:
      !!term &&
      term.trim().length > 0 &&
      !!componentTerms &&
      componentTerms.length > 0,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    ...options,
  });
};

/**
 * Hook to generate a definition with external reference context
 */
export const useDefinitionWithReferences = (
  term: string | null,
   
  dbpediaContext?: Record<string, any> | null,
   
  wikidataContext?: Record<string, any> | null,
  options?: UseQueryOptions<DefinitionSuggestionResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "definition-with-references", {
      term: term || "",
      dbpediaContext: JSON.stringify(dbpediaContext || {}),
      wikidataContext: JSON.stringify(wikidataContext || {}),
    }),
    queryFn: () => {
      if (!term) {
        throw new Error("Term is required for definition generation");
      }
      return llmService.generateDefinitionWithReferences(
        term,
        dbpediaContext || undefined,
        wikidataContext || undefined,
      );
    },
    enabled:
      !!term &&
      term.trim().length > 0 &&
      ((!!dbpediaContext && Object.keys(dbpediaContext).length > 0) ||
        (!!wikidataContext && Object.keys(wikidataContext).length > 0)),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    ...options,
  });
};

/**
 * Hook to generate a comprehensive definition with all available context
 */
export const useComprehensiveDefinition = (
  request: DefinitionSuggestionRequest | null,
  options?: UseQueryOptions<DefinitionSuggestionResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LLM, "comprehensive-definition", {
      request: JSON.stringify(request || {}),
    }),
    queryFn: () => {
      if (!request) {
        throw new Error(
          "Complete request is required for comprehensive definition generation",
        );
      }
      // Support both legacy and new request formats
       
      const term = (request as any).term || request.context_data?.term;
      if (!term) {
        throw new Error(
          "Request must contain term in either legacy format or context_data",
        );
      }
      return llmService.generateComprehensiveDefinition(request);
    },
    enabled:
      !!request &&
       
      (!!(request as any).term || !!request.context_data?.term) &&
       
      (((request as any).term && (request as any).term.trim().length > 0) ||
        (request.context_data?.term &&
          (request.context_data.term as string).trim().length > 0)),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    ...options,
  });
};
