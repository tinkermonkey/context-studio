import { useState } from "react";
import { TextArea as Textarea } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline, useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import {
  usePipelineRun,
  usePipelineCandidates,
  type CandidateResponse,
} from "@/api/hooks/pipeline/usePipelineRuns";
import { useToasts } from "@/components/ui/Toast";
import "./Suggesters.css";

interface SuggestFieldProps {
  entityId?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  testId?: string;
}

export function SuggestField({
  entityId,
  value,
  onChange,
  placeholder,
  rows = 4,
  testId,
}: SuggestFieldProps) {
  const [runId, setRunId] = useState<string | null>(null);
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());

  const { toast } = useToasts();
  const runMutation = useRunPipeline();
  const applyMutation = useApplyRun();
  const { data: run } = usePipelineRun(runId ?? "");

  const isRunning = runMutation.isPending || run?.status === "PENDING" || run?.status === "RUNNING";
  const isCompleted = run?.status === "COMPLETED";
  const isFailed = run?.status === "FAILED";

  const { data: allCandidatesRaw = [] } = usePipelineCandidates(runId ?? "", isCompleted);

  const allCandidates = allCandidatesRaw.map((c, i) => ({ ...c, originalIdx: i }));
  const visibleCandidates = allCandidates.filter((c) => !dismissedIndices.has(c.originalIdx));

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
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to run suggestion pipeline");
    }
  };

  const applyCandidate = async (
    candidate: CandidateResponse & { originalIdx: number },
  ): Promise<boolean> => {
    if (!runId) return false;
    try {
      await applyMutation.mutateAsync({
        runId,
        params: { confidence_threshold: candidate.confidence, node_id: entityId },
      });
      return true;
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to apply suggestion");
      return false;
    }
  };

  const handleReplace = async (candidate: CandidateResponse & { originalIdx: number }) => {
    if (!candidate.description) return;
    const success = await applyCandidate(candidate);
    if (success) {
      onChange(candidate.description);
      setRunId(null);
    }
  };

  const handleAppend = async (candidate: CandidateResponse & { originalIdx: number }) => {
    if (!candidate.description) return;
    const success = await applyCandidate(candidate);
    if (success) {
      onChange(value ? `${value}\n\n${candidate.description}` : candidate.description);
      setRunId(null);
    }
  };

  const handleDismiss = (originalIdx: number) => {
    setDismissedIndices((prev) => new Set([...prev, originalIdx]));
  };

  const handleDismissAll = () => {
    setRunId(null);
    setDismissedIndices(new Set());
  };

  return (
    <div className="suggest-field-wrapper" data-testid={testId ? `${testId}-wrapper` : undefined}>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
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

      {isFailed && (
        <div className="suggester-error" data-testid="suggest-field-error">
          <p className="suggester-error-message">
            {run?.failure_reason ?? "Suggestion pipeline failed"}
          </p>
          <div className="suggester-error-actions">
            <button
              type="button"
              className="suggest-field-action-btn"
              onClick={() => void handleSuggest()}
              data-testid="suggest-field-retry-btn"
            >
              Try again
            </button>
          </div>
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
              {candidate.description && (
                <p className="suggest-field-candidate-text">{candidate.description}</p>
              )}
              {candidate.provenance && (
                <p className="suggest-field-candidate-rationale">{candidate.provenance}</p>
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
                  onClick={() => void handleReplace(candidate)}
                  disabled={applyMutation.isPending || !candidate.description}
                  data-testid={`suggest-candidate-replace-${candidate.originalIdx}`}
                >
                  Replace
                </button>
                <button
                  type="button"
                  className="suggest-field-action-btn suggest-field-action-append"
                  onClick={() => void handleAppend(candidate)}
                  disabled={applyMutation.isPending || !candidate.description}
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
