import { useCallback, useRef, useState } from "react";
import { useRunPipeline } from "./usePipelineMutations";
import { ApiError } from "@/api/client/interceptors";
import type { components } from "@/api/types";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];
export type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

export type ReviewKind = "schema" | "individual";

export interface ReviewRunSlot {
  status: "idle" | "running" | "completed" | "failed";
  run?: PipelineRunResponse;
  error?: string;
}

export interface ReviewScopeRef {
  id: string;
  label: string;
}

/** Everything one "Run extraction" click needs; kept so a single tab can be re-run. */
export interface ExtractionReviewRequest {
  text: string;
  taxonomy: ReviewScopeRef;
  conceptScheme: ReviewScopeRef;
  implementationId: string;
  schemaConfigRef: string;
  individualConfigRef: string;
  /** Model from the chosen configuration; the pipelines read it from the run input. */
  schemaModel?: string | null;
  individualModel?: string | null;
}

const PIPELINE_TYPE: Record<ReviewKind, string> = {
  schema: "schema_extraction",
  individual: "individual_extraction",
};

function buildRunRequest(kind: ReviewKind, req: ExtractionReviewRequest): PipelineRunRequest {
  if (kind === "schema") {
    return {
      implementation_id: req.implementationId,
      configuration_ref: req.schemaConfigRef,
      documents: [req.text],
      scope: req.taxonomy.id,
      scope_name: req.taxonomy.label,
      concept_scheme_id: req.conceptScheme.id,
      ...(req.schemaModel ? { model: req.schemaModel } : {}),
    } as PipelineRunRequest;
  }
  return {
    implementation_id: req.implementationId,
    configuration_ref: req.individualConfigRef,
    text: req.text,
    ontology_id: req.taxonomy.id,
    ontology_name: req.taxonomy.label,
    ...(req.individualModel ? { model: req.individualModel } : {}),
  } as PipelineRunRequest;
}

function slotFromRun(run: PipelineRunResponse): ReviewRunSlot {
  // The API reports status in lower case ("completed"); compare case-insensitively.
  const status = run.status.toUpperCase();
  if (status === "COMPLETED") return { status: "completed", run };
  if (status === "FAILED" || status === "CANCELLED") {
    return { status: "failed", run, error: run.failure_reason ?? `Run ${run.status}` };
  }
  return { status: "running", run };
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "The pipeline run failed.";
}

const IDLE: ReviewRunSlot = { status: "idle" };

/**
 * Starts schema_extraction and individual_extraction on the same paragraph and
 * tracks each run independently: one tab failing never blocks the other.
 * Unlike useRunWizard, this never navigates away — results are reviewed in place.
 */
export function useExtractionReviewRuns() {
  const { mutateAsync: runPipeline } = useRunPipeline();
  const [slots, setSlots] = useState<Record<ReviewKind, ReviewRunSlot>>({
    schema: IDLE,
    individual: IDLE,
  });
  const [lastRequest, setLastRequest] = useState<ExtractionReviewRequest | null>(null);
  // Per-kind generation counters so a superseded run's late result is dropped.
  const generation = useRef<Record<ReviewKind, number>>({ schema: 0, individual: 0 });

  const runOne = useCallback(
    async (kind: ReviewKind, req: ExtractionReviewRequest) => {
      const gen = ++generation.current[kind];
      setSlots((s) => ({ ...s, [kind]: { status: "running" } }));
      let next: ReviewRunSlot;
      try {
        const run = await runPipeline({
          type: PIPELINE_TYPE[kind],
          request: buildRunRequest(kind, req),
        });
        next = slotFromRun(run);
      } catch (err) {
        next = { status: "failed", error: errorMessage(err) };
      }
      if (generation.current[kind] === gen) {
        setSlots((s) => ({ ...s, [kind]: next }));
      }
    },
    [runPipeline],
  );

  const start = useCallback(
    (req: ExtractionReviewRequest) => {
      setLastRequest(req);
      return Promise.allSettled([runOne("schema", req), runOne("individual", req)]);
    },
    [runOne],
  );

  const rerun = useCallback(
    (kind: ReviewKind) => (lastRequest ? runOne(kind, lastRequest) : Promise.resolve()),
    [lastRequest, runOne],
  );

  return { schema: slots.schema, individual: slots.individual, lastRequest, start, rerun };
}
