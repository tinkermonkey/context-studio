/** Page sizes offered by the server-paginated list pages; the first is the default. */
export const LIST_PAGE_SIZES = [50, 100, 250] as const;

/**
 * Bounded fetch for the small, curated sets a view needs in full: taxonomies
 * and concept schemes (title maps, scheme filters, move targets) and the
 * classes of one scheme. Unbounded collections (all classes, individuals,
 * properties, relationships) are paged or searched server-side instead.
 */
export const SMALL_SET_LIMIT = 500;

/** Result count for a server-side "find any entity" picker search. */
export const ENTITY_SEARCH_LIMIT = 20;

/**
 * Heimdall RelationshipBuilder offers predicates as a fixed list with no
 * search, so relationship forms load a bounded, title-sorted set of them.
 */
export const PREDICATE_CHOICES_LIMIT = 500;

export const QUERY_KEYS = {
  // Admin
  health: ["health"] as const,
  metrics: ["metrics"] as const,
  config: ["config"] as const,
  mcpConnection: ["mcp-connection"] as const,
  backgroundTasks: ["background-tasks"] as const,
  statsTrends: (days?: number) => ["stats-trends", days] as const,
  datasets: () => ["datasets"] as const,
  dataset: (id: string) => ["datasets", id] as const,
  demoDatasets: ["demo-datasets"] as const,
  // Ontology
  // Root prefixes for invalidation — a 1-element key partial-matches every
  // parameterized sub-key (e.g. ["schemes"] matches ["schemes", taxId] and ["schemes", id]).
  taxonomies: ["taxonomies"] as const,
  taxonomy: (id: string) => ["taxonomies", id] as const,
  schemesRoot: ["schemes"] as const,
  schemes: (taxonomyId?: string) => ["schemes", taxonomyId] as const,
  scheme: (id: string) => ["schemes", id] as const,
  classesRoot: ["classes"] as const,
  classes: (params?: object) => ["classes", params] as const,
  class: (id: string) => ["classes", id] as const,
  // Content counts live under the classes root: class, individual and
  // relationship mutations already invalidate it.
  contentCountsRoot: ["classes", "counts"] as const,
  schemeCounts: (taxonomyId: string) => ["classes", "counts", "by-scheme", taxonomyId] as const,
  classCounts: (schemeId: string) => ["classes", "counts", "by-class", schemeId] as const,
  individualsRoot: ["individuals"] as const,
  individuals: (params?: object) => ["individuals", params] as const,
  individual: (id: string, resource?: string) =>
    resource ? (["individuals", id, resource] as const) : (["individuals", id] as const),
  properties: ["properties"] as const,
  property: (id: string) => ["properties", id] as const,
  relationshipsRoot: ["relationships"] as const,
  relationships: (params?: object) => ["relationships", params] as const,
  // Graph
  graph: ["graph"] as const,
  graphMetrics: ["graph", "metrics"] as const,
  graphView: ["graph", "view"] as const,
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
  // Change proposals (/api/proposals); "proposals" above is the changeset surface.
  changesRoot: ["changes"] as const,
  changeProposalsRoot: ["change-proposals"] as const,
  changeProposals: (params?: object) => ["change-proposals", "list", params] as const,
  changeProposal: (id: string) => ["change-proposals", id] as const,
  approvalPolicy: (taxonomyId: string) => ["approval-policy", taxonomyId] as const,
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
  pipelineConfiguration: (configId: string) => ["pipeline-configurations", configId] as const,
  pipelineRuns: (params?: object) => ["pipeline-runs", params] as const,
  pipelineRun: (runId: string) => ["pipeline-runs", runId] as const,
  pipelineCandidates: (runId: string) => ["pipeline-runs", runId, "candidates"] as const,
  pipelineSchemaExtractionCandidates: (runId: string) =>
    ["pipeline-runs", runId, "schema-extraction-candidates"] as const,
  pipelineIndividualExtractionCandidates: (runId: string) =>
    ["pipeline-runs", runId, "individual-extraction-candidates"] as const,
  pipelineRecognitionPreview: (runId: string, thresholds?: object) =>
    ["pipeline-runs", runId, "recognition-preview", thresholds] as const,
  pipelineRunChangeEvents: (runId: string, options?: object) =>
    ["pipeline-runs", runId, "change-events", options] as const,
  pipelineBatches: ["pipeline-batches"] as const,
  pipelineBatch: (batchId: string) => ["pipeline-batches", batchId] as const,
  // Chat
  chatStatus: ["chat-status"] as const,
} as const;
