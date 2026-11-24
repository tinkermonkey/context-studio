import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useRunPipeline, useEnqueueBatchRuns, type BatchRunSpec } from "./usePipelineMutations";
import type { components } from "@/api/types";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export interface FormErrors {
  [key: string]: string | undefined;
}

export interface UseRunWizardOptions {
  type: string;
}

export function useRunWizard(options: UseRunWizardOptions) {
  const { type } = options;
  const navigate = useNavigate();
  const { mutateAsync: runPipeline } = useRunPipeline();
  const { mutateAsync: enqueueBatchRuns } = useEnqueueBatchRuns();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const handleSubmit = async (request: PipelineRunRequest): Promise<void> => {
    setIsSubmitting(true);
    setErrors({});

    try {
      // Started in the background: the pending run comes back at once and the
      // run drawer follows it, so a long run is not cut off by the request timeout.
      const run = await runPipeline({
        type,
        request: { ...request, async: true },
      });

      await navigate({
        to: "/app/pipelines/runs",
        search: { selected: run.id },
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  // One run per spec, enqueued as one batch. A single run opens in its drawer;
  // several open the runs list, where each shows as it progresses.
  const handleSubmitBatch = async (specs: BatchRunSpec[]): Promise<void> => {
    setIsSubmitting(true);
    setErrors({});

    try {
      const { run_ids: runIds } = await enqueueBatchRuns(specs);
      await navigate({
        to: "/app/pipelines/runs",
        search: runIds.length === 1 ? { selected: runIds[0] } : {},
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    isSubmitting,
    errors,
    setErrors,
    handleSubmit,
    handleSubmitBatch,
  };
}
