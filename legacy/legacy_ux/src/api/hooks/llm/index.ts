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
} from "./useLLMAnalysis";

// Mutation hooks - New specific endpoints
export {
  useSuggestTermDefinitionMutation,
  useSuggestDomainDefinitionMutation,
  useSuggestLayerDefinitionMutation,
  useGenerateSimpleTermDefinitionMutation,
  useGenerateSimpleDomainDefinitionMutation,
  useGenerateSimpleLayerDefinitionMutation,
  useGenerateTermDefinitionWithDomainMutation,
  useGenerateTermDefinitionWithParentMutation,
  useGenerateTermDefinitionWithComponentsMutation,
  useGenerateTermDefinitionWithReferencesMutation,
  useGenerateComprehensiveTermDefinitionMutation,
  // Deprecated hooks for backward compatibility
  useSuggestDefinitionMutation,
  useGenerateSimpleDefinitionMutation,
  useGenerateDefinitionWithDomainMutation,
  useGenerateDefinitionWithParentMutation,
  useGenerateDefinitionWithComponentsMutation,
  useGenerateDefinitionWithReferencesMutation,
  useGenerateComprehensiveDefinitionMutation,
} from "./useLLMMutations";

// Traceability hooks
export {
  useLLMTraceabilityHealth,
  useExecutionAnalytics,
  useAnalyticsForTimeRange,
  useDashboardAnalytics,
  useExecutionHistory,
  useExecutionHistories,
  useRecentExecutions,
  useIsSystemHealthy,
  useAnalyticsWithRefresh,
  useExecutionHistoriesWithRefresh,
} from "./useLLMTraceability";

export {
  useRecordSelectionMutation,
  useRecordSuggestionSelectionMutation,
  useSilentSelectionRecording,
  useBatchSelectionRecording,
  useOptimisticSelectionRecording,
} from "./useLLMTraceabilityMutations";

// Re-export types from service
export type {
  DefinitionSuggestionRequest,
  DefinitionSuggestionResponse,
  DomainDefinitionRequest,
  DomainDefinitionResponse,
  LayerDefinitionRequest,
  LayerDefinitionResponse,
  ComponentTerm,
  SelectedRelation,
  LLMHealthResponse,
  LLMSuccessResponse,
  LLMErrorResponse,
} from "../../services/llm";

// Re-export traceability types
export type {
  SelectionRecordRequest,
  SelectionRecordResponse,
  AnalyticsFilters,
  ExecutionAnalyticsData,
  ExecutionAnalyticsResponse,
  SelectionRecord,
  ExecutionDetails,
  ExecutionHistoryData,
  ExecutionHistoryResponse,
  LLMTraceabilityHealthResponse,
  ExecutionHistoryFilters,
  SelectionTrackingContext,
  AnalyticsDashboardConfig,
  ExecutionHistoryConfig,
} from "../../types/traceability";

// Re-export traceability service
export { llmTraceabilityService } from "../../services/llmTraceability";
