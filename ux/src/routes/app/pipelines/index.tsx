import { Button, FilterBar, Icon, Modal, PageHeader, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import { useState, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { usePipelines, useAllPipelineExecutions, useCreatePipeline } from "@/api/hooks/pipeline";
import { PipelineCard } from "@/components/pipeline/PipelineCard";
import { PipelineDetailPanel } from "@/components/pipeline/PipelineDetailPanel";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { PipelineCreateForm } from "@/components/pipeline/PipelineCreateForm";
import { useToasts } from "@/components/ui/Toast";
import { COPY } from "./-copy";

type StatusFilter = "all" | "running" | "success" | "idle" | "failed";

export function PipelinesContent() {
  const navigate = useNavigate({ from: "/app/pipelines/" });
  const { data: pipelines = [], isLoading, error, refetch } = usePipelines();
  const { data: allExecutions, error: executionsError } = useAllPipelineExecutions(undefined, 50);
  const createPipeline = useCreatePipeline();
  const { toast } = useToasts();

  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);

  const selectedPipeline = useMemo(
    () => pipelines.find((p) => p.id === selectedPipelineId) ?? null,
    [pipelines, selectedPipelineId],
  );

  const activeFilterChips = useMemo(() => {
    if (statusFilter === "all") return [];
    const labelMap: Record<Exclude<StatusFilter, "all">, string> = {
      running: COPY.FILTER_RUNNING,
      success: COPY.FILTER_SUCCESS,
      idle: COPY.FILTER_IDLE,
      failed: COPY.FILTER_FAILED,
    };
    return [{ id: "status", label: labelMap[statusFilter] }];
  }, [statusFilter]);

  const filteredPipelines = useMemo(() => {
    const getRunStatus = (pipelineId: string): "running" | "success" | "idle" | "failed" => {
      if (!allExecutions?.items) return "idle";
      const pipelineExecutions = allExecutions.items.filter(
        (e: any) => e.pipeline_config_id === pipelineId,
      );
      if (pipelineExecutions.length === 0) return "idle";
      const latestExecution = pipelineExecutions.reduce((latest: any, current: any) =>
        new Date(current.timestamp).getTime() > new Date(latest.timestamp).getTime()
          ? current
          : latest,
      );
      if (latestExecution.status === "success") return "success";
      if (latestExecution.status === "error" || latestExecution.status === "timeout") return "failed";
      return "idle";
    };

    let result = pipelines;

    if (searchFilter) {
      const query = searchFilter.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(query) ||
          p.pipeline.toLowerCase().includes(query) ||
          p.provider.toLowerCase().includes(query) ||
          p.model.toLowerCase().includes(query),
      );
    }

    if (statusFilter !== "all") {
      result = result.filter((p) => getRunStatus(p.id) === statusFilter);
    }

    return result.sort((a, b) => {
      const aStatus = getRunStatus(a.id);
      const bStatus = getRunStatus(b.id);
      const aFailed = aStatus === "failed" ? 1 : 0;
      const bFailed = bStatus === "failed" ? 1 : 0;
      if (aFailed !== bFailed) return bFailed - aFailed;
      return new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime();
    });
  }, [pipelines, searchFilter, statusFilter, allExecutions]);

  if (isLoading) {
    return (
      <div data-testid="pipelines-page" className="stack">
        <div className="flex-between">
          <div className="skeleton" style={{ width: 200, height: 32 }} />
          <div className="skeleton" style={{ width: 120, height: 32 }} />
        </div>
        <div className="skeleton" style={{ height: 40 }} />
        <div className="pipeline-list">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 120 }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="pipelines-page" className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={COPY.PIPELINES_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (pipelines.length === 0) {
    return (
      <div data-testid="pipelines-page">
        <EmptyState
          title={COPY.NO_PIPELINES_TITLE}
          description={COPY.NO_PIPELINES_DESCRIPTION}
          action={{
            label: COPY.CREATE_PIPELINE_CTA,
            onClick: () => setShowCreateModal(true),
          }}
        />
        <Modal isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title={COPY.CREATE_PIPELINE_TITLE}
        >
          <PipelineCreateForm
            isLoading={createPipeline.isPending}
            onCancel={() => setShowCreateModal(false)}
            onSubmit={async (data) => {
              const created = await createPipeline.mutateAsync(data);
              toast("success", COPY.CREATE_PIPELINE_SUCCESS(created.title));
              setShowCreateModal(false);
              setSelectedPipelineId(created.id);
            }}
          />
        </Modal>
      </div>
    );
  }

  const hasFilters = !!searchFilter || statusFilter !== "all";
  const showFilteredEmpty = pipelines.length > 0 && filteredPipelines.length === 0 && hasFilters;

  return (
    <div data-testid="pipelines-page" className="stack">
      <Modal isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={COPY.CREATE_PIPELINE_TITLE}
      >
        <PipelineCreateForm
          isLoading={createPipeline.isPending}
          onCancel={() => setShowCreateModal(false)}
          onSubmit={async (data) => {
            const created = await createPipeline.mutateAsync(data);
            toast("success", COPY.CREATE_PIPELINE_SUCCESS(created.title));
            setShowCreateModal(false);
            setSelectedPipelineId(created.id);
          }}
        />
      </Modal>

      <Modal isOpen={!!selectedPipeline}
        onClose={() => setSelectedPipelineId(null)}
        title={selectedPipeline?.title} data-testid="pipeline-edit-modal"
      >
        {selectedPipeline && <PipelineDetailPanel pipeline={selectedPipeline} />}
      </Modal>

      <PageHeader
        eyebrow="PIPELINES · workflow"
        title={COPY.PIPELINES_PAGE_TITLE}
        idChip="/pipelines"
        subtitle={COPY.PIPELINES_PAGE_SUBTITLE}
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="pipeline-add-button"
          >
            <Icon name="plus" size={13} />
            {COPY.NEW_PIPELINE_BUTTON}
          </Button>
        }
      />

      <div className="stack">
        <FilterBar
          searchPlaceholder={COPY.SEARCH_PIPELINES_PLACEHOLDER}
          filters={activeFilterChips}
          onSearchChange={setSearchFilter}
          onFilterRemove={() => setStatusFilter("all")}
          showingCount={filteredPipelines.length}
          totalCount={pipelines.length}
          data-testid="pipelines-search-input"
        />
        <SegmentedControl
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as StatusFilter)}
          options={[
            { value: "all", label: COPY.FILTER_ALL },
            { value: "running", label: COPY.FILTER_RUNNING },
            { value: "success", label: COPY.FILTER_SUCCESS },
            { value: "idle", label: COPY.FILTER_IDLE },
            { value: "failed", label: COPY.FILTER_FAILED },
          ]}
          aria-label={COPY.FILTER_PIPELINES_LABEL}
          data-testid="pipeline-status-filter"
        />
      </div>

      {executionsError && (
        <ErrorBanner
          error={executionsError}
          message={COPY.EXECUTIONS_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      )}

      {showFilteredEmpty ? (
        <EmptyState
          title={COPY.NO_PIPELINES_FILTERED_TITLE}
          description={COPY.NO_PIPELINES_FILTERED_DESCRIPTION}
        />
      ) : (
        <div data-testid="pipelines-grid" className="pipeline-list">
          {filteredPipelines.map((pipeline) => (
            <PipelineCard
              key={pipeline.id}
              pipeline={pipeline}
              selected={pipeline.id === selectedPipelineId}
              onClick={() => setSelectedPipelineId(pipeline.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/pipelines/")({
  component: PipelinesContent,
});
