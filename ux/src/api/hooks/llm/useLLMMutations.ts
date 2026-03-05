/**
 * LLM Mutation Hooks
 *
 * React Query mutation hooks for Large Language Model operations
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import {
  llmService,
  type DefinitionSuggestionResponse,
  type DefinitionSuggestionRequest,
  type DomainDefinitionRequest,
  type DomainDefinitionResponse,
  type LayerDefinitionRequest,
  type LayerDefinitionResponse,
  type ComponentTerm,
} from "../../services/llm";

/**
 * Hook to suggest term definition using mutation pattern (for manual triggering)
 */
export const useSuggestTermDefinitionMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    DefinitionSuggestionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: DefinitionSuggestionRequest) =>
      llmService.suggestTermDefinition(request),
    ...options,
  });
};

/**
 * Hook to suggest domain definition using mutation pattern (for manual triggering)
 */
export const useSuggestDomainDefinitionMutation = (
  options?: UseMutationOptions<
    DomainDefinitionResponse,
    Error,
    DomainDefinitionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: DomainDefinitionRequest) =>
      llmService.suggestDomainDefinition(request),
    ...options,
  });
};

/**
 * Hook to suggest layer definition using mutation pattern (for manual triggering)
 */
export const useSuggestLayerDefinitionMutation = (
  options?: UseMutationOptions<
    LayerDefinitionResponse,
    Error,
    LayerDefinitionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: LayerDefinitionRequest) =>
      llmService.suggestLayerDefinition(request),
    ...options,
  });
};

/**
 * @deprecated Use useSuggestTermDefinitionMutation instead
 * Hook to suggest definition using mutation pattern (for manual triggering)
 */
export const useSuggestDefinitionMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    DefinitionSuggestionRequest
  >,
) => {
  console.warn(
    "useSuggestDefinitionMutation is deprecated, use useSuggestTermDefinitionMutation instead",
  );
  return useMutation({
    mutationFn: (request: DefinitionSuggestionRequest) =>
      llmService.suggestDefinition(request),
    ...options,
  });
};

/**
 * Hook to generate simple term definition using mutation pattern
 */
export const useGenerateSimpleTermDefinitionMutation = (
  options?: UseMutationOptions<DefinitionSuggestionResponse, Error, string>,
) => {
  return useMutation({
    mutationFn: (term: string) => llmService.generateSimpleTermDefinition(term),
    ...options,
  });
};

/**
 * Hook to generate simple domain definition using mutation pattern
 */
export const useGenerateSimpleDomainDefinitionMutation = (
  options?: UseMutationOptions<DomainDefinitionResponse, Error, string>,
) => {
  return useMutation({
    mutationFn: (domainTitle: string) =>
      llmService.generateSimpleDomainDefinition(domainTitle),
    ...options,
  });
};

/**
 * Hook to generate simple layer definition using mutation pattern
 */
export const useGenerateSimpleLayerDefinitionMutation = (
  options?: UseMutationOptions<LayerDefinitionResponse, Error, string>,
) => {
  return useMutation({
    mutationFn: (layerTitle: string) =>
      llmService.generateSimpleLayerDefinition(layerTitle),
    ...options,
  });
};

/**
 * @deprecated Use useGenerateSimpleTermDefinitionMutation instead
 * Hook to generate simple definition using mutation pattern
 */
export const useGenerateSimpleDefinitionMutation = (
  options?: UseMutationOptions<DefinitionSuggestionResponse, Error, string>,
) => {
  console.warn(
    "useGenerateSimpleDefinitionMutation is deprecated, use useGenerateSimpleTermDefinitionMutation instead",
  );
  return useMutation({
    mutationFn: (term: string) => llmService.generateSimpleDefinition(term),
    ...options,
  });
};

/**
 * Hook to generate term definition with domain context using mutation pattern
 */
export const useGenerateTermDefinitionWithDomainMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    { term: string; domainTitle: string; domainDefinition?: string }
  >,
) => {
  return useMutation({
    mutationFn: ({ term, domainTitle, domainDefinition }) =>
      llmService.generateTermDefinitionWithDomain(
        term,
        domainTitle,
        domainDefinition,
      ),
    ...options,
  });
};

/**
 * Hook to generate term definition with parent context using mutation pattern
 */
export const useGenerateTermDefinitionWithParentMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    {
      term: string;
      parentTermTitle: string;
      parentTermDefinition?: string;
      relationshipPredicate?: string;
    }
  >,
) => {
  return useMutation({
    mutationFn: ({
      term,
      parentTermTitle,
      parentTermDefinition,
      relationshipPredicate,
    }) =>
      llmService.generateTermDefinitionWithParent(
        term,
        parentTermTitle,
        parentTermDefinition,
        relationshipPredicate,
      ),
    ...options,
  });
};

/**
 * Hook to generate term definition with components using mutation pattern
 */
export const useGenerateTermDefinitionWithComponentsMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    { term: string; componentTerms: ComponentTerm[] }
  >,
) => {
  return useMutation({
    mutationFn: ({ term, componentTerms }) =>
      llmService.generateTermDefinitionWithComponents(term, componentTerms),
    ...options,
  });
};

/**
 * Hook to generate term definition with references using mutation pattern
 */
export const useGenerateTermDefinitionWithReferencesMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    {
      term: string;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      dbpediaContext?: Record<string, any>;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      wikidataContext?: Record<string, any>;
    }
  >,
) => {
  return useMutation({
    mutationFn: ({ term, dbpediaContext, wikidataContext }) =>
      llmService.generateTermDefinitionWithReferences(
        term,
        dbpediaContext,
        wikidataContext,
      ),
    ...options,
  });
};

/**
 * Hook to generate comprehensive term definition using mutation pattern
 */
export const useGenerateComprehensiveTermDefinitionMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    DefinitionSuggestionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: DefinitionSuggestionRequest) =>
      llmService.generateComprehensiveTermDefinition(request),
    ...options,
  });
};

/**
 * @deprecated Use useGenerateTermDefinitionWithDomainMutation instead
 * Hook to generate definition with domain context using mutation pattern
 */
export const useGenerateDefinitionWithDomainMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    { term: string; domainTitle: string; domainDefinition?: string }
  >,
) => {
  console.warn(
    "useGenerateDefinitionWithDomainMutation is deprecated, use useGenerateTermDefinitionWithDomainMutation instead",
  );
  return useMutation({
    mutationFn: ({ term, domainTitle, domainDefinition }) =>
      llmService.generateDefinitionWithDomain(
        term,
        domainTitle,
        domainDefinition,
      ),
    ...options,
  });
};

/**
 * @deprecated Use useGenerateTermDefinitionWithParentMutation instead
 * Hook to generate definition with parent context using mutation pattern
 */
export const useGenerateDefinitionWithParentMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    {
      term: string;
      parentTermTitle: string;
      parentTermDefinition?: string;
      relationshipPredicate?: string;
    }
  >,
) => {
  console.warn(
    "useGenerateDefinitionWithParentMutation is deprecated, use useGenerateTermDefinitionWithParentMutation instead",
  );
  return useMutation({
    mutationFn: ({
      term,
      parentTermTitle,
      parentTermDefinition,
      relationshipPredicate,
    }) =>
      llmService.generateDefinitionWithParent(
        term,
        parentTermTitle,
        parentTermDefinition,
        relationshipPredicate,
      ),
    ...options,
  });
};

/**
 * @deprecated Use useGenerateTermDefinitionWithComponentsMutation instead
 * Hook to generate definition with components using mutation pattern
 */
export const useGenerateDefinitionWithComponentsMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    { term: string; componentTerms: ComponentTerm[] }
  >,
) => {
  console.warn(
    "useGenerateDefinitionWithComponentsMutation is deprecated, use useGenerateTermDefinitionWithComponentsMutation instead",
  );
  return useMutation({
    mutationFn: ({ term, componentTerms }) =>
      llmService.generateDefinitionWithComponents(term, componentTerms),
    ...options,
  });
};

/**
 * @deprecated Use useGenerateTermDefinitionWithReferencesMutation instead
 * Hook to generate definition with references using mutation pattern
 */
export const useGenerateDefinitionWithReferencesMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    {
      term: string;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      dbpediaContext?: Record<string, any>;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      wikidataContext?: Record<string, any>;
    }
  >,
) => {
  console.warn(
    "useGenerateDefinitionWithReferencesMutation is deprecated, use useGenerateTermDefinitionWithReferencesMutation instead",
  );
  return useMutation({
    mutationFn: ({ term, dbpediaContext, wikidataContext }) =>
      llmService.generateDefinitionWithReferences(
        term,
        dbpediaContext,
        wikidataContext,
      ),
    ...options,
  });
};

/**
 * @deprecated Use useGenerateComprehensiveTermDefinitionMutation instead
 * Hook to generate comprehensive definition using mutation pattern
 */
export const useGenerateComprehensiveDefinitionMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    DefinitionSuggestionRequest
  >,
) => {
  console.warn(
    "useGenerateComprehensiveDefinitionMutation is deprecated, use useGenerateComprehensiveTermDefinitionMutation instead",
  );
  return useMutation({
    mutationFn: (request: DefinitionSuggestionRequest) =>
      llmService.generateComprehensiveDefinition(request),
    ...options,
  });
};
