import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Icon, Button } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { usePipelineTypes } from "@/api/hooks/pipeline/usePipelineTypes";
import { PipelineTypeContent } from "@/components/pipeline/PipelineTypeContent";
import "./pipelines.css";

export const Route = createFileRoute("/app/pipelines/")({
  component: PipelinesPage,
});

export function PipelinesPage() {
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState<string | null>(null);

  const { data: types, isLoading, error, refetch } = usePipelineTypes();

  const typeList = types ?? [];
  const activeType = selectedType ?? typeList[0]?.pipeline_type ?? null;

  if (error) {
    return (
      <div data-testid="pipelines-page">
        <PageHeader eyebrow="Pipelines" title="Pipeline Types" />
        <ErrorBanner error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  if (!isLoading && typeList.length === 0) {
    return (
      <div data-testid="pipelines-page">
        <PageHeader eyebrow="Pipelines" title="Pipeline Types" />
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
      <PageHeader
        eyebrow="Pipelines"
        title="Pipeline Types"
        subtitle="Pipeline types are system-defined. Curate their configurations — provider, model, prompts, and parameters."
        actions={
          <>
            <Button variant="ghost" onClick={() => navigate({ to: "/app/pipelines/runs" })}>
              All runs
            </Button>
          </>
        }
      />

      <div className="pipelines-master-detail">
        {/* Left: types list */}
        <div className="pipelines-types-list" role="listbox" aria-label="Pipeline types">
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="pipeline-type-list-skeleton" />
              ))
            : typeList.map((t) => {
                const isActive = t.pipeline_type === activeType;
                return (
                  <button
                    key={t.pipeline_type}
                    className={`pipeline-type-list-item ${isActive ? "pipeline-type-list-item--active" : ""}`}
                    onClick={() => setSelectedType(t.pipeline_type)}
                    data-testid={`pipeline-type-list-item-${t.pipeline_type}`}
                    role="option"
                    aria-selected={isActive}
                  >
                    <span className="pipeline-type-list-body">
                      <span className="pipeline-type-list-name">{t.pipeline_type}</span>
                      <span className="pipeline-type-list-desc">{t.description}</span>
                    </span>
                  </button>
                );
              })}
        </div>

        {/* Right: type configs + editor */}
        {activeType ? (
          <PipelineTypeContent pipelineType={activeType} />
        ) : (
          <div className="pipeline-type-list-empty" data-testid="pipeline-type-no-selection">
            <Icon name="pipeline" size={32} />
            <p>Select a pipeline type to manage its configurations.</p>
          </div>
        )}
      </div>
    </div>
  );
}
