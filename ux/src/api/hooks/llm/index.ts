/**
 * LLM Hooks
 * 
 * Export all LLM-related React Query hooks
 */

// Query hooks
export {
  useLLMHealth,
  useSimpleDefinition,
  useDefinitionWithDomain,
  useDefinitionWithParent,
  useDefinitionWithComponents,
  useDefinitionWithReferences,
  useComprehensiveDefinition,
} from './useLLMAnalysis';

// Mutation hooks
export {
  useSuggestDefinitionMutation,
  useGenerateSimpleDefinitionMutation,
  useGenerateDefinitionWithDomainMutation,
  useGenerateDefinitionWithParentMutation,
  useGenerateDefinitionWithComponentsMutation,
  useGenerateDefinitionWithReferencesMutation,
  useGenerateComprehensiveDefinitionMutation,
} from './useLLMMutations';

// Re-export types from service
export type {
  DefinitionSuggestionRequest,
  DefinitionSuggestionResponse,
  ComponentTerm,
  SelectedRelation,
  LLMHealthResponse,
  LLMSuccessResponse,
  LLMErrorResponse,
} from '../../services/llm';
