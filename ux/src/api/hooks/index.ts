/**
 * API Hooks
 *
 * Barrel export for all React Query hooks
 *
 * Note: Performance hooks are not exported from this barrel to avoid naming conflicts
 * with the analytics module. Import performance hooks directly from:
 * @/api/hooks/performance
 */

export * from "./admin";
export * from "./analytics";
export * from "./backgroundTasks";
export * from "./configuration";
export * from "./conceptSchemes";
export * from "./datasets";
export * from "./enabledModels";
// Graph hooks are imported selectively to avoid conflicts
export {
  useGraphStats,
  useRelatedTerms,
  useTermInfo,
  useTermHierarchy,
  useDomainAnalysis,
  useDomainInfo,
  useDomainHierarchy,
  useLayerAnalytics,
  useLayerInfo,
  useCommunityDetection,
  useSparqlExamples,
  useRdfExport,
  useGraphExport,
  useGraphRefresh,
  useSparqlQuery,
  useSearchAndAnalyze,
  useCentralityCalculation,
  useShortestPath,
  useNeighborsQuery,
} from "./graph";
export * from "./individuals";
export * from "./interchange";
export * from "./llm";
export * from "./modelCapabilities";
export * from "./nlp";
export * from "./nlpReference";
export * from "./ontologyClasses";
export * from "./pipelineFlavors";
export * from "./propertyDefinitions";
export * from "./rag";
export * from "./reference";
export * from "./relationships";
export * from "./schema";
export * from "./taxonomies";
