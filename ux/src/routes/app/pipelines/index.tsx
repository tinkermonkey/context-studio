import { useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Icon } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { usePipelineTypes } from "@/api/hooks/pipeline/usePipelineTypes";
import { usePipelineRuns } from "@/api/hooks/pipeline/usePipelineRuns";
import { PipelineHubContent } from "@/components/pipeline/PipelineHubContent";
import type { components } from "@/api/types";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

export const Route = createFileRoute("/app/pipelines/")({
  component: PipelinesPage,
});

export function PipelinesPage() {
  const { data: typesData, isLoading: typesLoading, error: typesError, refetch: refetchTypes } = usePipelineTypes();
  const { data: runsData, isLoading: runsLoading } = usePipelineRuns({ limit: 100 });

  const runsByType = useMemo(() => {
    if (!runsData?.items) return new Map<string, PipelineRunResponse>();
    const map = new Map<string, PipelineRunResponse>();
    runsData.items.forEach((run: PipelineRunResponse) => {
      const existing = map.get(run.pipeline_type);
      if (!existing) {
        map.set(run.pipeline_type, run);
      } else if (run.created_at && existing.created_at) {
        const runDate = new Date(run.created_at).getTime();
        const existingDate = new Date(existing.created_at).getTime();
        if (runDate > existingDate) {
          map.set(run.pipeline_type, run);
        }
      }
    });
    return map;
  }, [runsData]);

  const types = typesData || [];

  if (typesError) {
    return (
      <div data-testid="pipelines-page">
        <PageHeader eyebrow="Pipelines" title="Pipeline Registry" />
        <ErrorBanner
          error={typesError}
          onRetry={() => refetchTypes()}
        />
      </div>
    );
  }

  if (!typesLoading && types.length === 0) {
    return (
      <div data-testid="pipelines-page">
        <PageHeader eyebrow="Pipelines" title="Pipeline Registry" />
        <EmptyState
          title="No pipeline types registered"
          description="The pipeline registry is empty. This should not occur during normal operation."
          icon={<Icon name="pipeline" size={48} />}
        />
      </div>
    );
  }

  return (
    <div data-testid="pipelines-page">
      <PageHeader eyebrow="Pipelines" title="Pipeline Registry" />
      <PipelineHubContent
        types={types}
        runsByType={runsByType}
        isLoading={typesLoading}
        isRunsLoading={runsLoading}
      />
    </div>
  );
}
