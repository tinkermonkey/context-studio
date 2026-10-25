/**
 * Type-specific output_summary shapes for pipeline runs.
 * Each pipeline type produces a distinct output structure.
 */

export type Delta = {
  operation: "add" | "remove" | "modify";
  source_id: string;
  source_label?: string;
  target_id: string;
  target_label?: string;
  relationship_type: string;
  confidence: number;
  source: string;
  before?: string;
  after?: string;
};

export interface SchemaNodeGroundingOutputSummary {
  node_label?: string;
  groundings?: Array<{
    uri: string;
    label: string;
    description?: string;
    confidence: number;
    source: string;
    match_rationale?: string;
  }>;
  total_candidates_evaluated?: number;
}

export interface SchemaNodeDefinitionRefinementOutputSummary {
  current_definition?: string;
  candidates?: Array<{
    definition: string;
    confidence: number;
    source: string;
    rationale?: string;
  }>;
  node_id?: string;
  node_label?: string;
}

export interface SchemaNodeConnectionRefinementOutputSummary {
  deltas?: Array<Delta>;
}
