import { useState } from "react";
import { TextArea as Textarea } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline } from "@/api/hooks/pipeline/usePipelineMutations";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import type { SchemaNodeDefinitionRefinementOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./Suggesters.css";

interface SuggestFieldProps {
  entityId: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  testId?: string;
}

export function SuggestField({ entityId, value, onChange, rows = 4, testId }: SuggestFieldProps) {
  const [runId, setRunId] = useState<string | null>(null);
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());

  const runMutation = useRunPipeline();
  const { data: run } = usePipelineRun(runId ?? "");

  const isRunning =
    runMutation.isPending ||
    run?.status === "PENDING" ||
    run?.status === "RUNNING";
  const isCompleted = run?.status === "COMPLETED";

  const outputSummary = isCompleted
    ? (run?.output_summary as SchemaNodeDefinitionRefinementOutputSummary | null)
    : null;
  const allCandidates = outputSummary?.candidates ?? [];
  const visibleCandidates = allCandidates
    .map((c, i) => ({ ...c, originalIdx: i }))
    .filter((c) => !dismissedIndices.has(c.originalIdx));

  const handleSuggest = async () => {
    setRunId(null);
    setDismissedIndices(new Set());
    try {
      const result = await runMutation.mutateAsync({
        type: "schema_node_definition_refinement",
        request: {
          implementation_id: "default",
          configuration_ref: "default",
          node_id: entityId,
          current_definition: value,
        },
      });
      setRunId(result.id);
    } catch {
      // error visible via toast from mutation
    }
  };

  const handleReplace = (definition: string) => {
    onChange(definition);
    setRunId(null);
  };

  const handleAppend = (definition: string) => {
    onChange(value ? `${value}\n\n${definition}` : definition);
    setRunId(null);
  };

  const handleDismiss = (originalIdx: number) => {
    setDismissedIndices((prev) => new Set([...prev, originalIdx]));
  };

  const handleDismissAll = () => {
    setRunId(null);
    setDismissedIndices(new Set());
  };

  return (
    <div
      className="suggest-field-wrapper"
      data-testid={testId ? `${testId}-wrapper` : undefined}
    >
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        rows={rows}
      />
      <div className="suggest-field-actions">
        <button
          type="button"
          className="suggest-field-action-btn"
          onClick={() => void handleSuggest()}
          disabled={isRunning || !entityId}
          data-testid={testId ? `${testId}-suggest-btn` : "suggest-field-btn"}
          style={{ fontSize: 11, padding: "2px 8px" }}
        >
          {isRunning ? "Suggesting…" : "✦ Suggest"}
        </button>
      </div>

      {isRunning && (
        <div className="suggest-field-shimmer" data-testid="suggest-field-loading">
          <div className="skeleton" style={{ height: 52 }} />
          <div className="skeleton" style={{ height: 52 }} />
        </div>
      )}

      {isCompleted && allCandidates.length === 0 && (
        <div className="suggest-field-empty">No suggestions available</div>
      )}

      {isCompleted && visibleCandidates.length > 0 && (
        <div className="suggest-field-proposals" data-testid="suggest-field-proposals">
          <div className="suggest-field-proposals-header">
            <span>Suggestions</span>
            <button
              type="button"
              className="suggest-field-dismiss-all-btn"
              onClick={handleDismissAll}
              data-testid="suggest-field-dismiss-all"
              aria-label="Dismiss all suggestions"
            >
              ✕
            </button>
          </div>
          {visibleCandidates.map((candidate) => (
            <div
              key={candidate.originalIdx}
              className="suggest-field-candidate"
              data-testid={`suggest-candidate-${candidate.originalIdx}`}
            >
              <p className="suggest-field-candidate-text">{candidate.definition}</p>
              {candidate.rationale && (
                <p className="suggest-field-candidate-rationale">{candidate.rationale}</p>
              )}
              <div className="suggest-field-candidate-meta">
                <span>{(candidate.confidence * 100).toFixed(0)}% confidence</span>
                <span>·</span>
                <span>{candidate.source}</span>
              </div>
              <div className="suggest-field-candidate-actions">
                <button
                  type="button"
                  className="suggest-field-action-btn suggest-field-action-replace"
                  onClick={() => handleReplace(candidate.definition)}
                  data-testid={`suggest-candidate-replace-${candidate.originalIdx}`}
                >
                  Replace
                </button>
                <button
                  type="button"
                  className="suggest-field-action-btn suggest-field-action-append"
                  onClick={() => handleAppend(candidate.definition)}
                  data-testid={`suggest-candidate-append-${candidate.originalIdx}`}
                >
                  Append
                </button>
                <button
                  type="button"
                  className="suggest-field-action-btn"
                  onClick={() => handleDismiss(candidate.originalIdx)}
                  data-testid={`suggest-candidate-dismiss-${candidate.originalIdx}`}
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {isCompleted && allCandidates.length > 0 && visibleCandidates.length === 0 && (
        <div className="suggest-field-empty">All suggestions dismissed</div>
      )}
    </div>
  );
}
