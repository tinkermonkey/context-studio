import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline } from "@/api/hooks/pipeline/usePipelineMutations";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import type { SchemaNodeGroundingOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./Suggesters.css";

interface GroundingSectionProps {
  classId: string;
}

export function GroundingSection({ classId }: GroundingSectionProps) {
  const [runId, setRunId] = useState<string | null>(null);
  const [addedIndices, setAddedIndices] = useState<Set<number>>(new Set());
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());

  const runMutation = useRunPipeline();
  const { data: run } = usePipelineRun(runId ?? "");

  const isRunning =
    runMutation.isPending ||
    run?.status === "PENDING" ||
    run?.status === "RUNNING";
  const isCompleted = run?.status === "COMPLETED";

  const outputSummary = isCompleted
    ? (run?.output_summary as SchemaNodeGroundingOutputSummary | null)
    : null;

  const allGroundings = outputSummary?.groundings ?? [];
  const visibleGroundings = allGroundings
    .map((g, i) => ({ ...g, originalIdx: i }))
    .filter((g) => !dismissedIndices.has(g.originalIdx));

  const handleSuggest = async () => {
    setRunId(null);
    setAddedIndices(new Set());
    setDismissedIndices(new Set());
    try {
      const result = await runMutation.mutateAsync({
        type: "schema_node_grounding",
        request: {
          implementation_id: "default",
          configuration_ref: "default",
          node_id: classId,
        },
      });
      setRunId(result.id);
    } catch {
      // error visible via toast from mutation
    }
  };

  const handleAdd = (originalIdx: number) => {
    setAddedIndices((prev) => new Set([...prev, originalIdx]));
  };

  const handleDismiss = (originalIdx: number) => {
    setDismissedIndices((prev) => new Set([...prev, originalIdx]));
  };

  const hasRun = isCompleted || isRunning;

  return (
    <div className="grounding-section" data-testid="grounding-section">
      {!hasRun && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void handleSuggest()}
          data-testid="grounding-suggest-btn"
        >
          ✦ Suggest grounding
        </Button>
      )}

      {isRunning && (
        <div className="grounding-section-shimmer" data-testid="grounding-section-loading">
          <div className="skeleton" style={{ height: 80 }} />
          <div className="skeleton" style={{ height: 80 }} />
        </div>
      )}

      {isCompleted && allGroundings.length === 0 && (
        <>
          <p className="grounding-section-empty">No grounding candidates found</p>
          <div className="grounding-section-footer">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="grounding-suggest-retry-btn"
            >
              ✦ Suggest again
            </Button>
          </div>
        </>
      )}

      {isCompleted && visibleGroundings.length > 0 && (
        <>
          {visibleGroundings.map((grounding) => {
            const isAdded = addedIndices.has(grounding.originalIdx);
            return (
              <div
                key={grounding.originalIdx}
                className="grounding-proposal-card"
                data-testid={`grounding-proposal-${grounding.originalIdx}`}
              >
                <div className="grounding-proposal-header">
                  <span className="grounding-proposal-name">{grounding.label}</span>
                </div>
                {grounding.uri && (
                  <span className="grounding-proposal-url">{grounding.uri}</span>
                )}
                {grounding.description && (
                  <p className="suggest-field-candidate-text">{grounding.description}</p>
                )}
                {grounding.match_rationale && (
                  <p className="grounding-proposal-rationale">{grounding.match_rationale}</p>
                )}
                <div className="grounding-proposal-confidence">
                  <div
                    className="grounding-proposal-confidence-fill"
                    style={{ width: `${grounding.confidence * 100}%` }}
                    aria-label={`${(grounding.confidence * 100).toFixed(0)}% confidence`}
                  />
                </div>
                <div className="suggest-field-candidate-meta">
                  <span>{(grounding.confidence * 100).toFixed(0)}% confidence</span>
                  <span>·</span>
                  <span>{grounding.source}</span>
                </div>
                <div className="grounding-proposal-actions">
                  <button
                    type="button"
                    className="grounding-proposal-add-btn"
                    onClick={() => handleAdd(grounding.originalIdx)}
                    data-added={isAdded}
                    data-testid={`grounding-add-${grounding.originalIdx}`}
                  >
                    {isAdded ? "✓ Added" : "Add"}
                  </button>
                  <button
                    type="button"
                    className="grounding-proposal-dismiss-btn"
                    onClick={() => handleDismiss(grounding.originalIdx)}
                    data-testid={`grounding-dismiss-${grounding.originalIdx}`}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            );
          })}
          <div className="grounding-section-footer">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="grounding-suggest-retry-btn"
            >
              ✦ Suggest again
            </Button>
          </div>
        </>
      )}

      {isCompleted && allGroundings.length > 0 && visibleGroundings.length === 0 && (
        <p className="grounding-section-empty">All candidates dismissed</p>
      )}
    </div>
  );
}
