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

export interface SchemaExtractionOutputSummary {
  classes?: Array<{
    uri: string;
    label: string;
    description?: string;
    confidence: number;
    source: string;
  }>;
  properties?: Array<{
    uri: string;
    label: string;
    description?: string;
    confidence: number;
    source: string;
    kind?: string;
  }>;
  relationships?: Array<{
    source_uri: string;
    source_label: string;
    target_uri: string;
    target_label: string;
    relationship_type: string;
    confidence: number;
    source: string;
  }>;
}

export interface IndividualExtractionOutputSummary {
  triples?: Array<{
    subject: string;
    subject_label?: string;
    predicate: string;
    object: string;
    object_label?: string;
    confidence: number;
    source: string;
  }>;
}

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
