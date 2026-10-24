import { useState } from "react";
import { ConfirmDialog, Button } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import type { components } from "@/api/types";
import "./RunApplyControls.css";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];

/**
 * Node-scoped pipelines (grounding, definition and connection refinement) do not
 * accept explicit candidate ids on apply, so apply is threshold-based: only
 * candidates at or above this confidence are written.
 */
const NODE_APPLY_CONFIDENCE_THRESHOLD = 0.95;

interface RunApplyControlsProps {
  run: PipelineRunResponse;
  /** Number of candidates the reviewer accepted in the drawer's review UI. */
  selectedCount: number;
  onApplySuccess?: (result: ApplyRunResponse) => void;
  isApplied?: boolean;
  targetName?: string;
}

export function RunApplyControls({
  run,
  selectedCount,
  onApplySuccess,
  isApplied = false,
  targetName,
}: RunApplyControlsProps) {
  const { toast } = useToasts();
  const [showDialog, setShowDialog] = useState(false);
  const applyMutation = useApplyRun();

  const nodeId = (): string | null => {
    const inputSummary = run.input_summary as Record<string, unknown> | undefined;
    if (!inputSummary || typeof inputSummary !== "object") return null;
    return inputSummary.node_id ? String(inputSummary.node_id) : null;
  };

  const handleApply = async () => {
    const node = nodeId();
    if (!node) {
      toast("error", "Cannot apply", "Missing or invalid required parameter: node_id");
      return;
    }
    try {
      const result = await applyMutation.mutateAsync({
        runId: run.id,
        params: { confidence_threshold: NODE_APPLY_CONFIDENCE_THRESHOLD, node_id: node },
      });
      toast("success", "Results applied successfully");
      setShowDialog(false);
      onApplySuccess?.(result);
    } catch (error) {
      toast("error", "Apply failed", error instanceof Error ? error.message : "Unknown error");
    }
  };

  if (isApplied) {
    return (
      <Button
        variant="ghost"
        disabled
        title="This run has already been applied"
        data-testid="run-apply-button-disabled"
      >
        Already applied
      </Button>
    );
  }

  return (
    <>
      <Button
        onClick={() => setShowDialog(true)}
        disabled={applyMutation.isPending || selectedCount === 0}
        data-testid="run-apply-button"
        aria-label="Apply selected candidates"
      >
        {selectedCount > 0 ? `Apply selected (${selectedCount})` : "No candidates selected"}
      </Button>

      <ConfirmDialog
        isOpen={showDialog}
        onClose={() => setShowDialog(false)}
        onConfirm={handleApply}
        title="Apply run results"
        data-testid="run-apply-confirm-dialog"
        message={
          <div className="run-apply-dialog-content">
            <p>
              You are about to apply <strong>{selectedCount} candidates</strong> to{" "}
              <code className="run-apply-target">{targetName || run.implementation_id}</code>
            </p>
            <div className="run-apply-threshold-warning">
              <span className="warning-icon">⚠</span>
              <p>
                A conservative confidence threshold of{" "}
                <strong>{NODE_APPLY_CONFIDENCE_THRESHOLD.toFixed(2)}</strong> will be used. Only
                candidates above this threshold will be applied.
              </p>
            </div>
          </div>
        }
        confirmLabel="Apply"
        variant="primary"
      />
    </>
  );
}
