import { useState } from "react";
import { ConfirmDialog, Button } from "@tinkermonkey/heimdall-ui";
import { Loader } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { useRevertRun } from "@/api/hooks/pipeline/usePipelineMutations";
import type { components } from "@/api/types";
import "./RunRevertControls.css";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];
type RevertRunResponse = components["schemas"]["RevertRunResponse"];

interface RunRevertControlsProps {
  run: PipelineRunResponse;
  applyResult?: ApplyRunResponse;
  isReverted?: boolean;
  onRevertSuccess?: (result: RevertRunResponse) => void;
}

export function RunRevertControls({
  run,
  applyResult,
  isReverted = false,
  onRevertSuccess,
}: RunRevertControlsProps) {
  const { toast } = useToasts();
  const [showDialog, setShowDialog] = useState(false);
  const revertMutation = useRevertRun();

  const handleRevert = async () => {
    try {
      const result = await revertMutation.mutateAsync(run.id);
      toast("success", "Run reverted successfully");
      setShowDialog(false);

      if (onRevertSuccess) {
        onRevertSuccess(result);
      }
    } catch (error) {
      toast("error", "Revert failed", error instanceof Error ? error.message : "Unknown error");
    }
  };

  if (!applyResult) {
    return null;
  }

  if (isReverted) {
    return (
      <Button
        variant="ghost"
        disabled
        title="This run has already been reverted"
        data-testid="run-revert-button-disabled"
      >
        Already reverted
      </Button>
    );
  }

  // Calculate total items that were applied
  const totalApplied =
    (applyResult.classes_created || 0) +
    (applyResult.classes_updated || 0) +
    (applyResult.properties_created || 0) +
    (applyResult.relationships_created || 0) +
    (applyResult.relationships_modified || 0) +
    (applyResult.individuals_created || 0) +
    (applyResult.external_references_created || 0);

  // Get sample IDs for display
  const sampleIds = [
    ...(applyResult.created_class_ids?.slice(0, 2) || []),
    ...(applyResult.created_individual_ids?.slice(0, 2) || []),
    ...(applyResult.created_relationship_ids?.slice(0, 2) || []),
    ...(applyResult.created_property_definition_ids?.slice(0, 2) || []),
  ].slice(0, 3);

  return (
    <>
      <Button
        onClick={() => setShowDialog(true)}
        disabled={revertMutation.isPending}
        variant="secondary"
        data-testid="run-revert-button"
        aria-label="Revert this apply"
      >
        {revertMutation.isPending ? (
          <>
            <Loader size={16} className="spin" />
            Reverting...
          </>
        ) : (
          "Revert this apply"
        )}
      </Button>

      <ConfirmDialog
        isOpen={showDialog}
        onClose={() => setShowDialog(false)}
        onConfirm={handleRevert}
        title="Revert run results"
        data-testid="run-revert-confirm-dialog"
        message={
          <div className="run-revert-dialog-content">
            <p>
              This will remove all <strong>{totalApplied} applied candidates</strong> from your
              ontology.
            </p>

            {applyResult.classes_created > 0 && (
              <div className="revert-item-count">
                <span className="count">{applyResult.classes_created}</span>
                <span>Classes created</span>
              </div>
            )}

            {applyResult.properties_created > 0 && (
              <div className="revert-item-count">
                <span className="count">{applyResult.properties_created}</span>
                <span>Properties created</span>
              </div>
            )}

            {(applyResult.relationships_created || 0) + (applyResult.relationships_modified || 0) >
              0 && (
              <div className="revert-item-count">
                <span className="count">
                  {(applyResult.relationships_created || 0) +
                    (applyResult.relationships_modified || 0)}
                </span>
                <span>Relationships affected</span>
              </div>
            )}

            {applyResult.individuals_created > 0 && (
              <div className="revert-item-count">
                <span className="count">{applyResult.individuals_created}</span>
                <span>Individuals created</span>
              </div>
            )}

            {sampleIds.length > 0 && (
              <div className="revert-sample-ids">
                <p className="sample-ids-label">Sample IDs:</p>
                <div className="sample-ids-list">
                  {sampleIds.map((id, idx) => (
                    <code key={idx} className="sample-id">
                      {id}
                    </code>
                  ))}
                </div>
              </div>
            )}

            <p className="revert-warning">This action cannot be undone.</p>
          </div>
        }
        confirmLabel="Revert"
        variant="danger"
      />
    </>
  );
}
