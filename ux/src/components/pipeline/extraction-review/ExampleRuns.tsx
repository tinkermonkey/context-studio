import { Chip, Panel, Table } from "@tinkermonkey/heimdall-ui";
import { usePipelineRuns } from "@/api/hooks/pipeline/usePipelineRuns";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import type { components } from "@/api/types";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

const KIND_LABEL: Record<string, string> = {
  schema_extraction: "schema",
  individual_extraction: "individual",
};

const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString() : "—");

export interface ExampleRunsProps {
  exampleId: string;
  exampleTitle: string;
  onOpenRun?: (runId: string) => void;
}

/**
 * Earlier runs started from the same library example, so runs of one input
 * (different configurations, before and after a prompt change) can be opened
 * and compared.
 */
export function ExampleRuns({ exampleId, exampleTitle, onOpenRun }: ExampleRunsProps) {
  const { data, error, isLoading, refetch } = usePipelineRuns({ example_id: exampleId, limit: 20 });
  const runs = (data?.items ?? []).filter((r) => r.pipeline_type in KIND_LABEL);

  return (
    <Panel
      title="Earlier runs of this example"
      subtitle={`Runs started from "${exampleTitle}". Open one to review it on the same paragraph.`}
      noPadding
      data-testid="extraction-review-example-runs"
    >
      {error ? (
        <ErrorBanner
          error={error}
          compact
          onRetry={() => refetch()}
          message="Failed to load runs"
        />
      ) : (
        <Table<PipelineRunResponse>
          columns={[
            {
              key: "started_at",
              label: "Started",
              render: (_: unknown, r: PipelineRunResponse) => when(r.started_at ?? r.created_at),
            },
            {
              key: "pipeline_type",
              label: "Pipeline",
              width: "120px",
              render: (v: unknown) => <Chip variant="neutral">{KIND_LABEL[String(v)]}</Chip>,
            },
            { key: "implementation_id", label: "Implementation" },
            {
              key: "configuration_ref",
              label: "Configuration",
              render: (_: unknown, r: PipelineRunResponse) =>
                `${r.configuration_ref} v${r.configuration_version}`,
            },
            { key: "status", label: "Status", width: "120px" },
          ]}
          data={runs}
          rowKey="id"
          onRowClick={onOpenRun ? (r) => onOpenRun(r.id) : undefined}
          emptyState={
            <div className="xr-empty">
              {isLoading ? "Loading runs…" : "No runs of this example yet."}
            </div>
          }
        />
      )}
    </Panel>
  );
}
