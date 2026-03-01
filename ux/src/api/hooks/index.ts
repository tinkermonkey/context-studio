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
export * from "./datasets";
export * from "./enabledModels";
// Graph hooks are imported selectively to avoid conflicts with structure_nodes
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
export * from "./llm";
export * from "./modelCapabilities";
export * from "./nlp";
export * from "./nlpReference";
export * from "./pipelineFlavors";
export * from "./predicates";
export * from "./rag";
export * from "./reference";
export * from "./schema";
export * from "./schemaOrg";
export * from "./structure_nodes";
