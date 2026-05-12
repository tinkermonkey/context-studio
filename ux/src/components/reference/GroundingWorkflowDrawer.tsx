import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { useToasts } from "@/components/ui/Toast";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useUndoDelete } from "@/hooks/useUndoDelete";
import {
  useGroundingWorkflow,
  useUpdateGroundingWorkflow,
  useDeleteGroundingWorkflow,
  useRunGroundingWorkflow,
  useGroundingWorkflowRuns,
} from "@/api/hooks/reference";

interface GroundingWorkflowDrawerProps {
  workflowId: string;
  onClose: () => void;
}

export function GroundingWorkflowDrawer({ workflowId, onClose }: GroundingWorkflowDrawerProps) {
  const { data: workflow, isLoading, error, refetch } = useGroundingWorkflow(workflowId);
  const { data: runs = [], isLoading: runsLoading } = useGroundingWorkflowRuns(workflowId);
  const updateMutation = useUpdateGroundingWorkflow();
  const deleteMutation = useDeleteGroundingWorkflow();
  const runMutation = useRunGroundingWorkflow();
  const { toast } = useToasts();
  const {
    performDelete,
    undo,
    deletedId: _deletedId,
  } = useUndoDelete({
    onDelete: deleteMutation.mutateAsync,
  });

  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState(workflow?.title || "");
  const [isSaving, setIsSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleNameChange = async (newName: string) => {
    if (!workflow || newName === workflow.title) {
      setIsEditingName(false);
      return;
    }

    setIsSaving(true);
    try {
      await updateMutation.mutateAsync({
        id: workflowId,
        data: { title: newName },
      });
      setIsEditingName(false);
      toast("success", "Workflow name updated");
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Failed to update name");
      setEditedName(workflow.title);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRunNow = async () => {
    try {
      await runMutation.mutateAsync(workflowId);
      toast("success", "Workflow started");
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Failed to run workflow");
    }
  };

  const handleDeleteConfirm = async () => {
    try {
      await performDelete(workflowId);
      toast("success", "Workflow deleted", undefined, {
        action: { label: "Undo", onAction: undo },
        autoDismissMs: 8000,
      });
      onClose();
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Failed to delete workflow");
    }
  };

  if (isLoading) {
    return (
      <div className="kv" data-testid="grounding-workflow-drawer">
        <Skeleton height={32} />
        <Skeleton height={24} style={{ marginTop: "var(--space-3)" }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="kv" data-testid="grounding-workflow-drawer">
        <ErrorBanner
          error={error}
          onRetry={refetch}
          message="Failed to load workflow"
          compact
        />
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="kv" data-testid="grounding-workflow-drawer">
        <div className="kv-row">
          <span className="muted-text">Workflow not found</span>
        </div>
      </div>
    );
  }

  const statusColor =
    workflow.status === "active" ? "emerald" : workflow.status === "error" ? "rose" : "gray";

  const lastRun = workflow.last_run ? new Date(workflow.last_run).toLocaleString() : "Never";

  return (
    <div className="kv" data-testid="grounding-workflow-drawer">
      <div className="kv-row">
        <div className="kv-label">Workflow</div>
        <div className="kv-value">
          {isEditingName ? (
            <input
              type="text"
              value={editedName}
              onChange={(e) => setEditedName(e.target.value)}
              onBlur={() => handleNameChange(editedName)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleNameChange(editedName);
                } else if (e.key === "Escape") {
                  setIsEditingName(false);
                  setEditedName(workflow.title);
                }
              }}
              autoFocus
              disabled={isSaving}
              style={{
                flex: 1,
                padding: "var(--space-1) var(--space-2)",
                border: "1px solid var(--canvas-fg-3)",
                borderRadius: "var(--radius-sm)",
                fontSize: "inherit",
              }}
              data-testid="workflow-name-edit-input"
            />
          ) : (
            <button
              onClick={() => {
                setIsEditingName(true);
                setEditedName(workflow.title);
              }}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                fontSize: "inherit",
                fontWeight: "inherit",
                textAlign: "left",
              }}
              data-testid="workflow-name-display"
            >
              {workflow.title}
            </button>
          )}
        </div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Source</div>
        <div className="kv-value">
          <Chip color="cyan">{workflow.source}</Chip>
        </div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Class Scope</div>
        <div className="kv-value">
          <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
            {workflow.class_scope.length > 0 ? (
              workflow.class_scope.map((scope) => (
                <Chip key={scope} color="violet">
                  {scope}
                </Chip>
              ))
            ) : (
              <span className="muted-text">—</span>
            )}
          </div>
        </div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Status</div>
        <div className="kv-value">
          <Chip color={statusColor}>{workflow.status}</Chip>
        </div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Last Run</div>
        <div className="kv-value muted-text">{lastRun}</div>
      </div>

      {workflow.last_run_record_count !== undefined && (
        <div className="kv-row">
          <div className="kv-label">Records</div>
          <div className="kv-value">{workflow.last_run_record_count}</div>
        </div>
      )}

      {runs.length > 0 && (
        <div className="kv-row">
          <div className="kv-label">Run History</div>
          <div className="kv-value">
            <div style={{ width: "100%" }}>
              {runsLoading ? (
                <Skeleton height={20} />
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  {runs.slice(0, 5).map((run) => (
                    <div
                      key={run.id}
                      style={{
                        padding: "var(--space-2)",
                        backgroundColor: "var(--canvas-bg-2)",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "var(--text-xs)",
                      }}
                      data-testid={`workflow-run-${run.id}`}
                    >
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "var(--space-1)",
                        }}
                      >
                        <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                          {new Date(run.timestamp).toLocaleString()}
                        </span>
                        <Chip color={run.status === "success" ? "emerald" : "rose"}>
                          {run.status}
                        </Chip>
                      </div>
                      <div style={{ color: "var(--canvas-fg-3)" }}>{run.record_count} records</div>
                      {run.error_message && (
                        <div style={{ color: "var(--rose-600)", marginTop: "var(--space-1)" }}>
                          {run.error_message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="kv-row">
        <div className="kv-label">Actions</div>
        <div className="kv-value" style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant="primary"
            size="sm"
            onClick={handleRunNow}
            disabled={runMutation.isPending}
            data-testid="workflow-run-now-button"
          >
            {runMutation.isPending ? "Running..." : "Run Now"}
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            disabled={deleteMutation.isPending}
            data-testid="workflow-delete-button"
          >
            {deleteMutation.isPending ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title="Delete Workflow"
        message="Are you sure you want to delete this workflow? This action cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
