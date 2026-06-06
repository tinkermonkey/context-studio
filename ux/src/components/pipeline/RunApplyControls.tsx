import { useState } from "react";
import { ConfirmDialog, Button } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import type { ApplyParams } from "@/api/services/pipeline";
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
      const summary = outputSummary as unknown;

      if (typeof summary === "object" && summary !== null) {
        const summaryObj = summary as Record<string, unknown>;

        if (selectedCandidates.classes.length > 0 && Array.isArray(summaryObj.classes)) {
          summaryObj.classes.forEach((item: unknown, idx: number) => {
            if (selectedCandidates.classes.includes(`class-${idx}`)) {
              const itemObj = item as Record<string, unknown>;
              if (typeof itemObj.confidence === "number") {
                minConfidence = Math.min(minConfidence, itemObj.confidence);
                foundConfidence = true;
              }
            }
          });
        }

        if (selectedCandidates.properties.length > 0 && Array.isArray(summaryObj.properties)) {
          summaryObj.properties.forEach((item: unknown, idx: number) => {
            if (selectedCandidates.properties.includes(`prop-${idx}`)) {
              const itemObj = item as Record<string, unknown>;
              if (typeof itemObj.confidence === "number") {
                minConfidence = Math.min(minConfidence, itemObj.confidence);
                foundConfidence = true;
              }
            }
          });
        }

        if (selectedCandidates.relationships.length > 0 && Array.isArray(summaryObj.relationships)) {
          summaryObj.relationships.forEach((item: unknown, idx: number) => {
            if (selectedCandidates.relationships.includes(`rel-${idx}`)) {
              const itemObj = item as Record<string, unknown>;
              if (typeof itemObj.confidence === "number") {
                minConfidence = Math.min(minConfidence, itemObj.confidence);
                foundConfidence = true;
              }
            }
          });
        }
      }

      // If we found actual confidence values, use them
      // Otherwise, use 0.5 to include all selected candidates
      return foundConfidence ? Math.max(minConfidence - 0.01, 0) : 0.5;
    }

    // For non-schema-extraction pipelines, use a conservative threshold to avoid
    // applying unselected candidates. Use 0.95 as a high bar.
    return 0.95;
  };

  const validateScopeParameters = (): string | null => {
    const inputSummary = run.input_summary as Record<string, unknown> | undefined;

    if (!inputSummary || typeof inputSummary !== "object") {
      return "Invalid input summary: expected an object";
    }

    switch (run.pipeline_type) {
      case "schema_extraction":
        if (!("concept_scheme_id" in inputSummary)) {
          return "Missing required parameter: concept_scheme_id";
        }
        break;
      case "individual_extraction":
        if (!("taxonomy_id" in inputSummary)) {
          return "Missing required parameter: taxonomy_id";
        }
        break;
      case "schema_node_grounding":
      case "schema_node_definition_refinement":
      case "schema_node_connection_refinement":
        if (!("node_id" in inputSummary)) {
          return "Missing required parameter: node_id";
        }
        break;
    }

    return null;
  };

  const handleApply = async () => {
    try {
      const validationError = validateScopeParameters();
      if (validationError) {
        toast("error", "Cannot apply", validationError);
        return;
      }

      const confidenceThreshold = getMinConfidenceThreshold();

      const params: ApplyParams = {
        confidence_threshold: confidenceThreshold,
      };

      // Add scope parameters based on pipeline type
      const inputSummary = run.input_summary as Record<string, unknown>;
      if (run.pipeline_type === "schema_extraction") {
        params.concept_scheme_id = String(inputSummary.concept_scheme_id);
      } else if (run.pipeline_type === "individual_extraction") {
        params.taxonomy_id = String(inputSummary.taxonomy_id);
      } else if (
        run.pipeline_type === "schema_node_grounding" ||
        run.pipeline_type === "schema_node_definition_refinement" ||
        run.pipeline_type === "schema_node_connection_refinement"
      ) {
        params.node_id = String(inputSummary.node_id);
      }

      const result = await applyMutation.mutateAsync({
        runId: run.id,
        params,
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

  const confidenceThreshold = getMinConfidenceThreshold();

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
        data-testid="run-apply-confirm-dialog"
        message={
          <div className="run-apply-dialog-content">
            <p>
              You are about to apply <strong>{totalSelected} candidates</strong> to{" "}
              <code className="run-apply-target">{run.implementation_id}</code>
            </p>
            <div className="run-apply-threshold-warning">
              <span className="warning-icon">⚠</span>
              <p>
                Confidence threshold will be set to <strong>{confidenceThreshold.toFixed(2)}</strong> to include all selected
                candidates. Any candidates above this threshold that were not explicitly selected
                will also be applied.
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
