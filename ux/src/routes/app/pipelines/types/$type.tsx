import { createFileRoute } from "@tanstack/react-router";
import { PipelineTypeDetail } from "@/components/pipeline/PipelineTypeDetail";

interface PipelineTypeSearchParams {
  impl?: string;
  config?: string;
}

export const Route = createFileRoute("/app/pipelines/types/$type")({
  component: PipelineTypeDetailPage,
  validateSearch: (search: Record<string, unknown>): PipelineTypeSearchParams => {
    return {
      impl: typeof search.impl === "string" ? search.impl : undefined,
      config: typeof search.config === "string" ? search.config : undefined,
    };
  },
});

export function PipelineTypeDetailPage() {
  return <PipelineTypeDetail />;
}
