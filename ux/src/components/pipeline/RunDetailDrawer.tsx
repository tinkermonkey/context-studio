import { Loader, AlertCircle } from "lucide-react";
import {
  InspectorPanel,
  KVGrid,
  Chip,
} from "@tinkermonkey/heimdall-ui";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import { formatDate } from "@/utils/dateFormatting";
import "./RunDetailDrawer.css";

interface RunDetailDrawerProps {
  runId: string;
  onClose?: () => void;
}

export function RunDetailDrawer({ runId, onClose }: RunDetailDrawerProps) {
  const { data: run, isLoading, error } = usePipelineRun(runId);

  if (isLoading) {
    return (
      <InspectorPanel
        eyebrow="run"
        title="Loading…"
        id="loading"
        data-testid="run-detail-drawer"
      >
        <div className="run-detail-loading">
          <Loader size={20} className="spin" />
        </div>
      </InspectorPanel>
    );
  }

  if (error || !run) {
    return (
      <InspectorPanel
        eyebrow="run"
        title="Error"
        id="error"
        data-testid="run-detail-drawer"
      >
        <div className="run-detail-error">
          <AlertCircle size={16} className="run-detail-error-icon" />
          Failed to load run details
        </div>
      </InspectorPanel>
    );
  }

  const pipelineTypeDisplay = run.pipeline_type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  const statusColorMap: Record<string, "emerald" | "amber" | "rose" | "cyan" | "violet" | "neutral"> = {
    PENDING: "amber",
    RUNNING: "cyan",
    COMPLETED: "emerald",
    FAILED: "rose",
  };

  const metadataRows = [
    { key: "ID", value: <span className="run-detail-id">{run.id}</span> },
    { key: "Type", value: pipelineTypeDisplay },
    { key: "Implementation", value: run.configuration_slug || "—" },
    { key: "Configuration", value: `${run.configuration_ref} (v${run.configuration_version})` },
    { key: "Status", value: <Chip color={statusColorMap[run.status] || "neutral"}>{run.status}</Chip> },
    { key: "Started", value: formatDate(run.started_at) },
    { key: "Updated", value: formatDate(run.updated_at) },
  ];

  return (
    <InspectorPanel
      eyebrow="run"
      title={pipelineTypeDisplay}
      id={run.id}
      data-testid="run-detail-drawer"
    >
      <InspectorPanel.Section title="Metadata">
        <KVGrid rows={metadataRows} />
      </InspectorPanel.Section>

      {run.status === "FAILED" && run.failure_reason && (
        <InspectorPanel.Section title="Error">
          <div
            className="run-detail-failure-reason"
            data-testid="run-failure-reason"
          >
            {run.failure_reason}
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "COMPLETED" && (
        <InspectorPanel.Section title="Results">
          <div className="run-detail-results-section" data-testid="run-completed-section">
            <div className="run-detail-results-item">
              <strong>Candidates</strong>
              <div className="run-detail-candidates-wrapper">
                <Chip variant="neutral">
                  {(run.output_summary as any)?.candidate_count ?? 0} candidates
                </Chip>
              </div>
            </div>

            <div className="run-detail-results-item">
              <strong>Review Content</strong>
              <div
                className="run-detail-placeholder"
                data-testid="run-review-placeholder"
              >
                Candidate review content will be displayed here (Phase 6)
              </div>
            </div>

            <div className="run-detail-results-item">
              <strong>Apply</strong>
              <div
                className="run-detail-placeholder"
                data-testid="run-apply-placeholder"
              >
                Apply controls will be displayed here (Phase 7)
              </div>
            </div>
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "PENDING" && (
        <InspectorPanel.Section title="Status">
          <div
            className="run-detail-pending-placeholder"
            data-testid="run-pending-placeholder"
          >
            This run is pending execution
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "RUNNING" && (
        <InspectorPanel.Section title="Status">
          <div
            className="run-detail-running-placeholder"
            data-testid="run-running-placeholder"
          >
            <Loader size={14} className="spin" />
            This run is currently executing
          </div>
        </InspectorPanel.Section>
      )}
    </InspectorPanel>
  );
}
