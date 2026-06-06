export const QUERY_KEYS = {
  // Admin
  health: ["health"] as const,
  metrics: ["metrics"] as const,
  config: ["config"] as const,
  backgroundTasks: ["background-tasks"] as const,
  statsTrends: (days?: number) => ["stats-trends", days] as const,
  datasets: () => ["datasets"] as const,
  dataset: (id: string) => ["datasets", id] as const,
  demoDatasets: ["demo-datasets"] as const,
  // Ontology
  taxonomies: ["taxonomies"] as const,
  taxonomy: (id: string) => ["taxonomies", id] as const,
  schemes: (taxonomyId?: string) => ["schemes", taxonomyId] as const,
  scheme: (id: string) => ["schemes", id] as const,
  classes: (params?: object) => ["classes", params] as const,
  class: (id: string) => ["classes", id] as const,
  individuals: (params?: object) => ["individuals", params] as const,
  individual: (id: string, resource?: string) =>
    resource ? (["individuals", id, resource] as const) : (["individuals", id] as const),
  properties: ["properties"] as const,
  property: (id: string) => ["properties", id] as const,
  relationships: (params?: object) => ["relationships", params] as const,
  // Graph
  graph: ["graph"] as const,
  graphMetrics: ["graph", "metrics"] as const,
  graphPath: (sourceId: string, targetId: string) => ["graph", "path", sourceId, targetId] as const,
  // Extraction
  extraction: ["extraction"] as const,
  // Versioning
  changes: (params?: object) => ["changes", params] as const,
  changesets: ["changesets"] as const,
  proposals: (proposalId?: string) =>
    proposalId ? (["proposals", proposalId] as const) : (["proposals"] as const),
  proposalConflicts: (proposalId: string) => ["proposals", proposalId, "conflicts"] as const,
  syncStatus: ["sync-status"] as const,
  // Reference
  referenceSearch: (q?: string) => ["reference-search", q] as const,
  referenceStatus: ["reference-status"] as const,
  groundingWorkflows: ["grounding-workflows"] as const,
  groundingWorkflow: (id: string) => ["grounding-workflows", id] as const,
  groundingWorkflowRuns: (id: string) => ["grounding-workflows", id, "runs"] as const,
  // Pipeline
  pipelineTypes: ["pipeline-types"] as const,
  pipelineImplementations: (type: string) => ["pipeline-types", type, "implementations"] as const,
  pipelineConfigurations: (type: string, implId: string) =>
    ["pipeline-types", type, "implementations", implId, "configurations"] as const,
  pipelineRuns: (params?: object) => ["pipeline-runs", params] as const,
  pipelineRun: (runId: string) => ["pipeline-runs", runId] as const,
  pipelineCandidates: (runId: string) => ["pipeline-runs", runId, "candidates"] as const,
  pipelineBatches: ["pipeline-batches"] as const,
  pipelineBatch: (batchId: string) => ["pipeline-batches", batchId] as const,
} as const;
