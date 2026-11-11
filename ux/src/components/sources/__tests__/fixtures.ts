import type { LastExtraction, LastExtractionRun, Source } from "@/api/services/sources";
import type { components } from "@/api/types";

type PipelineRun = components["schemas"]["PipelineRunResponse"];
type PipelineConfiguration = components["schemas"]["PipelineConfigurationResponse"];

export function createSource(overrides?: Partial<Source>): Source {
  return {
    id: "src-1",
    taxonomy_id: "tax-house",
    dataset_id: "ds-home",
    kind: "pdf",
    title: "Whirlpool refrigerator: use and care guide",
    origin: "wrf555sdfz-use-care.pdf",
    content_type: "application/pdf",
    bytes: 2_400_000,
    pages: 4,
    chars: 20_000,
    page_starts: [0, 5000, 10000, 15000],
    headings: [],
    status: "ready",
    failure: null,
    failure_detail: null,
    created_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 3600_000).toISOString(),
    removed_at: null,
    last_extraction: null,
    ...overrides,
  };
}

export function createLastExtractionRun(overrides?: Partial<LastExtractionRun>): LastExtractionRun {
  return {
    run_id: "run-1234abcd",
    pipeline: "individual_extraction",
    status: "running",
    items_done: 0,
    items_total: 3,
    proposal_id: null,
    operations: null,
    ...overrides,
  };
}

export function createLastExtraction(
  runs: LastExtractionRun[] = [createLastExtractionRun()],
  overrides?: Partial<LastExtraction>,
): LastExtraction {
  return {
    started_at: new Date(Date.now() - 3600_000).toISOString(),
    dataset_id: "ds-home",
    runs,
    ...overrides,
  };
}

export function createRun(overrides?: Partial<PipelineRun>): PipelineRun {
  return {
    id: "run-1234abcd",
    batch_run_id: "batch-1",
    pipeline_type: "individual_extraction",
    implementation_id: "default",
    configuration_ref: "extraction-default",
    configuration_slug: "extraction-default",
    configuration_version: 1,
    input_summary: { source_id: "src-1" },
    output_summary: {},
    status: "running",
    created_at: new Date(Date.now() - 3600_000).toISOString(),
    items_done: 0,
    items_total: 3,
    proposal_id: null,
    ...overrides,
  };
}

export function createConfiguration(
  overrides?: Partial<PipelineConfiguration>,
): PipelineConfiguration {
  return {
    id: "cfg-1",
    config_ref: "extraction-default",
    pipeline_type: "individual_extraction",
    implementation_id: "default",
    name: "Default",
    provider: "anthropic",
    model: "claude-sonnet",
    enabled: true,
    version: 1,
    ...overrides,
  } as PipelineConfiguration;
}
