import { useState } from "react";
import { ConfirmDialog, Button } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import type { components } from "@/api/types";
import "./RunApplyControls.css";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];

interface RunApplyControlsProps {
  run: PipelineRunResponse;
  pipelineType: string;
  outputSummary?: unknown;
  selectedCandidates: {
    classes: (string | number)[];
    properties: (string | number)[];
    relationships: (string | number)[];
    individuals: (string | number)[];
    groundingCandidates: (string | number)[];
    refinementCandidates: (string | number)[];
  };
  onApplySuccess?: (result: ApplyRunResponse) => void;
  isApplied?: boolean;
}

export function RunApplyControls({
  run,
  pipelineType,
  outputSummary,
  selectedCandidates,
  onApplySuccess,
  isApplied = false,
}: RunApplyControlsProps) {
  const { toast } = useToasts();
  const [showDialog, setShowDialog] = useState(false);
  const applyMutation = useApplyRun();

  const totalSelected =
    (selectedCandidates.classes?.length || 0) +
    (selectedCandidates.properties?.length || 0) +
    (selectedCandidates.relationships?.length || 0) +
    (selectedCandidates.individuals?.length || 0) +
    (selectedCandidates.groundingCandidates?.length || 0) +
    (selectedCandidates.refinementCandidates?.length || 0);

  // Calculate minimum confidence threshold from selected candidates
  const getMinConfidenceThreshold = (): number => {
    if (totalSelected === 0) {
      return 0.5; // default to 0.5 if no candidates selected
    }

    let minConfidence = 1;
    let foundConfidence = false;

    // For schema extraction, check classes, properties, and relationships
    if (pipelineType === "schema_extraction" && outputSummary) {
      const summary = outputSummary as any;

      if (selectedCandidates.classes.length > 0 && summary.classes) {
        summary.classes.forEach((item: any, idx: number) => {
          if (selectedCandidates.classes.includes(`class-${idx}`)) {
            if (typeof item.confidence === "number") {
              minConfidence = Math.min(minConfidence, item.confidence);
              foundConfidence = true;
            }
          }
        });
      }

      if (selectedCandidates.properties.length > 0 && summary.properties) {
        summary.properties.forEach((item: any, idx: number) => {
          if (selectedCandidates.properties.includes(`prop-${idx}`)) {
            if (typeof item.confidence === "number") {
              minConfidence = Math.min(minConfidence, item.confidence);
              foundConfidence = true;
            }
          }
        });
      }

      if (selectedCandidates.relationships.length > 0 && summary.relationships) {
        summary.relationships.forEach((item: any, idx: number) => {
          if (selectedCandidates.relationships.includes(`rel-${idx}`)) {
            if (typeof item.confidence === "number") {
              minConfidence = Math.min(minConfidence, item.confidence);
              foundConfidence = true;
            }
          }
        });
      }
    }

    // If we found actual confidence values, use them
    // Otherwise, use 0 to include all selected candidates
    return foundConfidence ? Math.max(minConfidence - 0.01, 0) : 0;
  };

  const handleApply = async () => {
    try {
      const confidenceThreshold = getMinConfidenceThreshold();

      const params: Record<string, unknown> = {
        confidence_threshold: confidenceThreshold,
      };

      // Add scope parameters based on pipeline type
      if (run.pipeline_type === "schema_extraction") {
        // Schema extraction doesn't require additional scope
      } else if (run.pipeline_type === "individual_extraction") {
        // Individual extraction may require taxonomy_id
        if (run.input_summary?.taxonomy_id) {
          params.taxonomy_id = run.input_summary.taxonomy_id;
        }
      } else if (run.pipeline_type === "schema_node_grounding") {
        // Grounding requires node_id
        if (run.input_summary?.node_id) {
          params.node_id = run.input_summary.node_id;
        }
      } else if (run.pipeline_type === "schema_node_definition_refinement") {
        // Definition refinement requires node_id
        if (run.input_summary?.node_id) {
          params.node_id = run.input_summary.node_id;
        }
      } else if (run.pipeline_type === "schema_node_connection_refinement") {
        // Connection refinement requires node_id
        if (run.input_summary?.node_id) {
          params.node_id = run.input_summary.node_id;
        }
      }

      const result = await applyMutation.mutateAsync({
        runId: run.id,
        params: params as any,
      });

      toast("success", "Results applied successfully");
      setShowDialog(false);

      if (onApplySuccess) {
        onApplySuccess(result);
      }
    } catch (error) {
      toast(
        "error",
        "Apply failed",
        error instanceof Error ? error.message : "Unknown error",
      );
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
        disabled={applyMutation.isPending || totalSelected === 0}
        data-testid="run-apply-button"
        aria-label="Apply selected candidates"
      >
        {totalSelected > 0 ? `Apply selected (${totalSelected})` : "No candidates selected"}
      </Button>

      <ConfirmDialog
        isOpen={showDialog}
        onClose={() => setShowDialog(false)}
        onConfirm={handleApply}
        title="Apply run results"
        message={
          <div className="run-apply-dialog-content">
            <p>
              You are about to apply <strong>{totalSelected} candidates</strong> to{" "}
              <code className="run-apply-target">{run.implementation_id}</code>
            </p>
            <div className="run-apply-threshold-warning">
              <span className="warning-icon">⚠</span>
              <p>
                Confidence threshold will be set to <strong>0</strong> to include all selected
                candidates. Any candidates above this threshold that were not explicitly selected
                will also be applied.
              </p>
            </div>
            {totalSelected === 0 && (
              <p className="run-apply-error">Please select at least one candidate to apply.</p>
            )}
          </div>
        }
        confirmLabel="Apply"
        variant="primary"
      />
    </>
  );
}
