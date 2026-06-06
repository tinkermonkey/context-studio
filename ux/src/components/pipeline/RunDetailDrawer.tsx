import { Loader, AlertCircle } from "lucide-react";
import {
  InspectorPanel,
  KVGrid,
  Chip,
} from "@tinkermonkey/heimdall-ui";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import { formatDate } from "@/utils/dateFormatting";

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
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "32px 0" }}>
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
        <div style={{ padding: "16px", color: "rgb(var(--status-rose))" }}>
          <AlertCircle size={16} style={{ marginRight: "8px", display: "inline" }} />
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
    { key: "ID", value: <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>{run.id}</span> },
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
            style={{
              padding: "12px",
              background: "rgb(var(--status-rose) / 0.1)",
              border: "1px solid rgb(var(--status-rose))",
              borderRadius: "4px",
              color: "rgb(var(--status-rose))",
              fontSize: "12px",
              fontFamily: "var(--font-mono)",
              wordBreak: "break-word",
            }}
            data-testid="run-failure-reason"
          >
            {run.failure_reason}
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "COMPLETED" && (
        <InspectorPanel.Section title="Results">
          <div data-testid="run-completed-section">
            <div style={{ marginBottom: "12px" }}>
              <strong>Candidates</strong>
              <div style={{ marginTop: "4px" }}>
                <Chip variant="neutral">
                  {(run.output_summary as any)?.candidate_count ?? 0} candidates
                </Chip>
              </div>
            </div>

            <div style={{ marginBottom: "12px" }}>
              <strong>Review Content</strong>
              <div
                style={{
                  padding: "12px",
                  background: "rgb(var(--canvas-bg-hover))",
                  borderRadius: "4px",
                  fontSize: "12px",
                  color: "rgb(var(--canvas-fg-3))",
                  marginTop: "4px",
                }}
                data-testid="run-review-placeholder"
              >
                Candidate review content will be displayed here (Phase 6)
              </div>
            </div>

            <div>
              <strong>Apply</strong>
              <div
                style={{
                  padding: "12px",
                  background: "rgb(var(--canvas-bg-hover))",
                  borderRadius: "4px",
                  fontSize: "12px",
                  color: "rgb(var(--canvas-fg-3))",
                  marginTop: "4px",
                }}
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
            style={{
              padding: "12px",
              background: "rgb(var(--canvas-bg-hover))",
              borderRadius: "4px",
              fontSize: "12px",
              color: "rgb(var(--canvas-fg-3))",
            }}
            data-testid="run-pending-placeholder"
          >
            This run is pending execution
          </div>
        </InspectorPanel.Section>
      )}

      {run.status === "RUNNING" && (
        <InspectorPanel.Section title="Status">
          <div
            style={{
              padding: "12px",
              background: "rgb(var(--canvas-bg-hover))",
              borderRadius: "4px",
              fontSize: "12px",
              color: "rgb(var(--canvas-fg-3))",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
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
