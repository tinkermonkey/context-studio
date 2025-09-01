/**
 * LLM Mutation Hooks
 * 
 * React Query mutation hooks for Large Language Model operations
 */

import { useMutation, UseMutationOptions } from '@tanstack/react-query';
import { 
  llmService, 
  type DefinitionSuggestionResponse, 
  type DefinitionSuggestionRequest,
  type ComponentTerm 
} from '../../services/llm';

/**
 * Hook to suggest definition using mutation pattern (for manual triggering)
 */
export const useSuggestDefinitionMutation = (
  options?: UseMutationOptions<DefinitionSuggestionResponse, Error, DefinitionSuggestionRequest>
) => {
  return useMutation({
    mutationFn: (request: DefinitionSuggestionRequest) => llmService.suggestDefinition(request),
    ...options,
  });
};

/**
 * Hook to generate simple definition using mutation pattern
 */
export const useGenerateSimpleDefinitionMutation = (
  options?: UseMutationOptions<DefinitionSuggestionResponse, Error, string>
) => {
  return useMutation({
    mutationFn: (term: string) => llmService.generateSimpleDefinition(term),
    ...options,
  });
};

/**
 * Hook to generate definition with domain context using mutation pattern
 */
export const useGenerateDefinitionWithDomainMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    { term: string; domainTitle: string; domainDefinition?: string }
  >
) => {
  return useMutation({
    mutationFn: ({ term, domainTitle, domainDefinition }) =>
      llmService.generateDefinitionWithDomain(term, domainTitle, domainDefinition),
    ...options,
  });
};

/**
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
  >
) => {
  return useMutation({
    mutationFn: ({ term, parentTermTitle, parentTermDefinition, relationshipPredicate }) =>
      llmService.generateDefinitionWithParent(term, parentTermTitle, parentTermDefinition, relationshipPredicate),
    ...options,
  });
};

/**
 * Hook to generate definition with components using mutation pattern
 */
export const useGenerateDefinitionWithComponentsMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    { term: string; componentTerms: ComponentTerm[] }
  >
) => {
  return useMutation({
    mutationFn: ({ term, componentTerms }) =>
      llmService.generateDefinitionWithComponents(term, componentTerms),
    ...options,
  });
};

/**
 * Hook to generate definition with references using mutation pattern
 */
export const useGenerateDefinitionWithReferencesMutation = (
  options?: UseMutationOptions<
    DefinitionSuggestionResponse,
    Error,
    {
      term: string;
      dbpediaContext?: Record<string, any>;
      wikidataContext?: Record<string, any>;
    }
  >
) => {
  return useMutation({
    mutationFn: ({ term, dbpediaContext, wikidataContext }) =>
      llmService.generateDefinitionWithReferences(term, dbpediaContext, wikidataContext),
    ...options,
  });
};

/**
 * Hook to generate comprehensive definition using mutation pattern
 */
export const useGenerateComprehensiveDefinitionMutation = (
  options?: UseMutationOptions<DefinitionSuggestionResponse, Error, DefinitionSuggestionRequest>
) => {
  return useMutation({
    mutationFn: (request: DefinitionSuggestionRequest) =>
      llmService.generateComprehensiveDefinition(request),
    ...options,
  });
};
