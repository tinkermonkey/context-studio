import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { PageHeader, Icon, Button } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { usePipelineTypes } from "@/api/hooks/pipeline/usePipelineTypes";
import { PipelineTypeContent } from "@/components/pipeline/PipelineTypeContent";
import { RUN_WIZARDS } from "@/components/pipeline/wizards";
import "./pipelines.css";

/** What the page shows: a pipeline type, one of its implementations, one of that one's configurations. */
export interface PipelinesSearch {
  type?: string;
  impl?: string;
  /** A configuration's config_ref. */
  config?: string;
}

const text = (value: unknown) => (typeof value === "string" && value ? value : undefined);

export const Route = createFileRoute("/app/pipelines/")({
  component: PipelinesRoute,
  validateSearch: (search: Record<string, unknown>): PipelinesSearch => ({
    type: text(search.type),
    impl: text(search.impl),
    config: text(search.config),
  }),
});

function PipelinesRoute() {
  const navigate = useNavigate();
  const search = useSearch({ from: "/app/pipelines/" as any }) as PipelinesSearch;
  return (
    <PipelinesPage
      search={search}
      onSearchChange={(next) =>
        navigate({ to: "/app/pipelines" as any, search: next as any, replace: true })
      }
      onOpenRuns={() => navigate({ to: "/app/pipelines/runs" })}
      onRun={(type) => navigate({ to: "/app/pipelines/types/$type/run", params: { type } })}
    />
  );
}

export interface PipelinesPageProps {
  search: PipelinesSearch;
  onSearchChange: (search: PipelinesSearch) => void;
  onOpenRuns: () => void;
  /** Open the run wizard of a pipeline type. */
  onRun: (pipelineType: string) => void;
}

export function PipelinesPage({ search, onSearchChange, onOpenRuns, onRun }: PipelinesPageProps) {
  const { data: types, isLoading, error, refetch } = usePipelineTypes();

  const typeList = types ?? [];
  const activeType =
    typeList.find((t) => t.pipeline_type === search.type)?.pipeline_type ??
    typeList[0]?.pipeline_type ??
    null;

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
        subtitle="Pipeline types are system-defined. Each has one or more implementations; curate an implementation's configurations — provider, model, prompts, and parameters."
        actions={
          <Button variant="ghost" onClick={onOpenRuns} data-testid="pipelines-all-runs">
            All runs
          </Button>
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
                    onClick={() => onSearchChange({ type: t.pipeline_type })}
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

        {/* Right: the type's implementations, configurations and editor */}
        {activeType ? (
          <PipelineTypeContent
            // A type's editor state does not carry over to another type.
            key={activeType}
            pipelineType={activeType}
            implementationId={search.impl}
            configRef={search.config}
            onSelect={(selection) => onSearchChange({ type: activeType, ...selection })}
            onRun={RUN_WIZARDS[activeType] ? () => onRun(activeType) : undefined}
          />
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
