import { useCallback, useEffect, useRef, useState } from "react";
import { useRunPipeline } from "./usePipelineMutations";
import { usePipelineRun } from "./usePipelineRuns";
import { ApiError } from "@/api/client/interceptors";
import { hasRunStatus } from "./runStatus";
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

/** The review tab a run belongs to, or null for pipeline types this page does not review. */
export function reviewKindOf(pipelineType: string): ReviewKind | null {
  if (pipelineType === PIPELINE_TYPE.schema) return "schema";
  if (pipelineType === PIPELINE_TYPE.individual) return "individual";
  return null;
}

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
  if (hasRunStatus(run.status, "completed")) return { status: "completed", run };
  if (hasRunStatus(run.status, "failed", "cancelled")) {
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

/** Run id to poll: only a slot whose run was returned but has not finished yet. */
const pollId = (slot: ReviewRunSlot) => (slot.status === "running" ? (slot.run?.id ?? "") : "");

export interface ExtractionReviewRunsOptions {
  /** How often a pending/running run is re-fetched until it finishes. */
  pollIntervalMs?: number;
}

/**
 * Starts schema_extraction and individual_extraction on the same paragraph and
 * tracks each run independently: one tab failing never blocks the other.
 * Unlike useRunWizard, this never navigates away — results are reviewed in place.
 */
export function useExtractionReviewRuns({
  pollIntervalMs = 2000,
}: ExtractionReviewRunsOptions = {}) {
  const { mutateAsync: runPipeline } = useRunPipeline();
  const [slots, setSlots] = useState<Record<ReviewKind, ReviewRunSlot>>({
    schema: IDLE,
    individual: IDLE,
  });

  // A run can come back pending/running (or be opened while still running):
  // poll it until it finishes, then move its slot to completed/failed.
  const { data: schemaPolled } = usePipelineRun(pollId(slots.schema), {
    refetchInterval: pollIntervalMs,
  });
  const { data: individualPolled } = usePipelineRun(pollId(slots.individual), {
    refetchInterval: pollIntervalMs,
  });
  useEffect(() => {
    const polled: Record<ReviewKind, PipelineRunResponse | undefined> = {
      schema: schemaPolled,
      individual: individualPolled,
    };
    setSlots((s) => {
      let next = s;
      for (const kind of ["schema", "individual"] as const) {
        const run = polled[kind];
        const slot = s[kind];
        if (!run || slot.status !== "running" || slot.run?.id !== run.id) continue;
        if (hasRunStatus(run.status, "pending", "running")) continue;
        next = { ...next, [kind]: slotFromRun(run) };
      }
      return next;
    });
  }, [schemaPolled, individualPolled]);
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

  /** Shows an existing run (e.g. opened from run history) in its tab. */
  const open = useCallback((run: PipelineRunResponse) => {
    const kind = reviewKindOf(run.pipeline_type);
    if (!kind) return;
    ++generation.current[kind];
    setSlots((s) => ({ ...s, [kind]: slotFromRun(run) }));
  }, []);

  const rerun = useCallback(
    (kind: ReviewKind) => (lastRequest ? runOne(kind, lastRequest) : Promise.resolve()),
    [lastRequest, runOne],
  );

  return { schema: slots.schema, individual: slots.individual, lastRequest, start, rerun, open };
}
