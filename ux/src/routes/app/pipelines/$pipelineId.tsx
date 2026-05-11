import { createFileRoute, useParams, useNavigate } from "@tanstack/react-router";
import { usePipeline } from "@/api/hooks/pipeline";
import { usePipelines } from "@/api/hooks/pipeline";
import { PipelineCard } from "@/components/pipeline/PipelineCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { PipelineDetailPanel } from "@/components/pipeline/PipelineDetailPanel";
import { COPY } from "./-copy";

function PipelineDetailContent() {
  const { pipelineId } = useParams({ from: "/app/pipelines/$pipelineId" });
  const navigate = useNavigate({ from: "/app/pipelines/$pipelineId" });

  const { data: pipelines = [], isLoading: pipelinesLoading } = usePipelines();
  const {
    data: pipeline,
    isLoading: pipelineLoading,
    error: pipelineError,
    refetch: refetchPipeline,
  } = usePipeline(pipelineId);

  const isLoading = pipelinesLoading || pipelineLoading;

  if (isLoading) {
    return (
      <div data-testid="pipeline-detail" className="flex-row-center">
        <div className="grow">
          <div className="grid-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} height={120} />
            ))}
          </div>
        </div>
        <div style={{ width: "380px" }}>
          <Skeleton height={300} />
        </div>
      </div>
    );
  }

  if (pipelineError) {
    return (
      <div data-testid="pipeline-detail">
        <ErrorBanner
          error={pipelineError}
          message={COPY.PIPELINE_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
          onRetry={refetchPipeline}
        />
      </div>
    );
  }

  const handleClose = () => {
    navigate({ to: "/app/pipelines" });
  };

  return (
    <div data-testid="pipeline-detail">
      <SchemaPageLayout
        data={pipelines}
        selectedId={pipelineId}
        renderDrawerContent={(_selectedPipeline) =>
          pipeline && <PipelineDetailPanel pipeline={pipeline} onClose={handleClose} />
        }
      >
        <div className="grid-2">
          {pipelines.map((p) => (
            <div
              key={p.id}
              role="button"
              tabIndex={0}
              className="pipeline-card-wrapper"
              onClick={() => navigate({ to: `/app/pipelines/${p.id}` })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  navigate({ to: `/app/pipelines/${p.id}` });
                }
              }}
            >
              <PipelineCard pipeline={p} />
            </div>
          ))}
        </div>
      </SchemaPageLayout>
    </div>
  );
}

export const Route = createFileRoute("/app/pipelines/$pipelineId")({
  component: PipelineDetailContent,
});
