import type {
  RecognitionPreviewResponse,
  SchemaExtractionCandidate,
  TripleCandidate,
} from "@/api/services/pipeline";
import type { PipelineRunResponse } from "@/api/hooks/pipeline/useExtractionReviewRuns";

export const XR_TEXT =
  "The Customer Portal lets policyholders submit insurance claims online. Each claim is reviewed by a Claims Adjuster through the Claims Review Service.";

export function span(quote: string) {
  const at = XR_TEXT.indexOf(quote);
  return at < 0 ? { quote, start: null, end: null } : { quote, start: at, end: at + quote.length };
}

export const SCHEMA_CANDIDATES: SchemaExtractionCandidate[] = [
  {
    candidate_type: "schema_class",
    candidate_id: "class-0",
    label: "Policyholder",
    confidence: 0.91,
    proposed_definition: "A person holding an insurance policy.",
    provenance: [span("policyholders")],
  },
  {
    candidate_type: "schema_class",
    candidate_id: "class-1",
    label: "Insurance Claim",
    confidence: 0.88,
    proposed_definition: "A request for compensation.",
    provenance: [span("insurance claims"), span("Each claim")],
  },
  {
    candidate_type: "schema_class",
    candidate_id: "class-2",
    label: "Turnaround SLA",
    confidence: 0.38,
    proposed_definition: null,
    provenance: [{ quote: "turnaround SLA", start: null, end: null }],
  },
  {
    candidate_type: "schema_property",
    candidate_id: "property-0",
    label: "submits",
    confidence: 0.86,
    proposed_definition: "The actor initiates a business object.",
    proposed_domain: "business.business-actor",
    proposed_range: "business.business-object",
    provenance: [span("submit")],
  },
  {
    candidate_type: "schema_connection",
    candidate_id: "connection-0",
    subject_ref: "Policyholder",
    predicate: "submits",
    object_ref: "Insurance Claim",
    confidence: 0.81,
    provenance: [span("policyholders submit insurance claims")],
  },
];

export const TRIPLES: TripleCandidate[] = [
  {
    candidate_type: "triple",
    candidate_id: "triple-0",
    subject: {
      kind: "individual",
      label: "Customer Portal",
      id: "ind_7c21",
      title: "Customer Self-Service Portal",
      class_ids: ["application.application-component"],
    },
    predicate: { kind: "property", label: "serves", property_definition_id: "pd_serves" },
    object: {
      kind: "individual",
      label: "Policyholder",
      id: null,
      class_ids: ["business.business-actor"],
    },
    confidence: 0.9,
    provenance: [span("Customer Portal lets policyholders")],
  },
  {
    candidate_type: "triple",
    candidate_id: "triple-1",
    subject: {
      kind: "individual",
      label: "Claims Adjuster",
      id: "ind_3a90",
      class_ids: ["motivation.stakeholder"],
    },
    predicate: { kind: "property", label: "uses", property_definition_id: null },
    object: {
      kind: "individual",
      label: "Claims Review Service",
      id: "ind_5e12",
      class_ids: ["application.application-service"],
    },
    confidence: 0.69,
    provenance: [span("Claims Adjuster through the Claims Review Service")],
  },
  {
    candidate_type: "triple",
    candidate_id: "triple-2",
    subject: {
      kind: "individual",
      label: "Claims Review Service",
      id: "ind_5e12",
      class_ids: ["application.application-service"],
    },
    predicate: { kind: "property", label: "resolution-window", property_definition_id: null },
    object: { kind: "literal", label: "48 hours", value: "PT48H", datatype: "xsd:duration" },
    confidence: 0.75,
    provenance: [],
  },
];

export const RECOGNITION: RecognitionPreviewResponse = {
  total_mentions: 3,
  matched_count: 2,
  unmatched_count: 1,
  skipped_count: 0,
  hits: [
    {
      mention_label: "Customer Portal",
      resolved_individual_id: "ind_7c21",
      resolved_individual_title: "Customer Self-Service Portal",
      match_method: "vector",
      match_score: 0.92,
      will_match_existing: true,
      candidate_class_ids: ["application.application-component"],
    },
    {
      mention_label: "Claims Adjuster",
      resolved_individual_id: "ind_3a90",
      resolved_individual_title: "Claims Adjuster",
      match_method: "exact",
      match_score: 1,
      will_match_existing: true,
      candidate_class_ids: ["motivation.stakeholder"],
    },
    {
      mention_label: "Policyholder",
      resolved_individual_id: null,
      resolved_individual_title: null,
      match_method: null,
      match_score: null,
      will_match_existing: false,
      candidate_class_ids: ["business.business-actor"],
    },
  ],
};

export function makeRun(overrides: Partial<PipelineRunResponse> = {}): PipelineRunResponse {
  return {
    id: "run-s",
    batch_run_id: "batch-1",
    pipeline_type: "schema_extraction",
    implementation_id: "default",
    configuration_ref: "schema-extraction-default",
    configuration_slug: "schema-extraction-default",
    configuration_version: 1,
    status: "completed",
    started_at: "2026-10-23T10:00:00Z",
    updated_at: "2026-10-23T10:00:11Z",
    failure_reason: null,
    ...overrides,
  };
}

/** Policyholder already exists; Insurance Claim is close to the existing "Claim" class. */
export const SCHEMA_RECOGNITION: RecognitionPreviewResponse = {
  total_mentions: 5,
  matched_count: 1,
  unmatched_count: 4,
  skipped_count: 0,
  hits: [],
  schema_hits: [
    {
      candidate_id: "class-0",
      candidate_type: "schema_class",
      label: "Policyholder",
      will_match_existing: true,
      existing_entity_id: "cls_policyholder",
      existing_entity_title: "Policyholder",
      match_method: "exact",
      match_score: 1,
    },
    {
      candidate_id: "class-1",
      candidate_type: "schema_class",
      label: "Insurance Claim",
      will_match_existing: false,
      existing_entity_id: "cls_claim",
      existing_entity_title: "Claim",
      match_method: "vector",
      match_score: 0.93,
    },
    {
      candidate_id: "class-2",
      candidate_type: "schema_class",
      label: "Turnaround SLA",
      will_match_existing: false,
    },
    {
      candidate_id: "property-0",
      candidate_type: "schema_property",
      label: "submits",
      will_match_existing: false,
    },
    {
      candidate_id: "connection-0",
      candidate_type: "schema_connection",
      label: "Policyholder → submits → Insurance Claim",
      will_match_existing: false,
    },
  ],
};

export const SCOPE = {
  taxonomyId: "tax-dr",
  taxonomyLabel: "Documentation Robotics · dr_spec",
  conceptSchemeId: "scheme-app",
  conceptSchemeLabel: "Application Layer · application",
};
