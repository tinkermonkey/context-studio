import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline, useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import {
  usePipelineRun,
  usePipelineCandidates,
  type CandidateItem,
} from "@/api/hooks/pipeline/usePipelineRuns";
import { provenanceText } from "./provenanceText";
import { useToasts } from "@/components/ui/Toast";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";
import "./Suggesters.css";

interface RelationshipSuggesterProps {
  classId: string;
}

export function RelationshipSuggester({ classId }: RelationshipSuggesterProps) {
  const [runId, setRunId] = useState<string | null>(null);
  // Refinement candidates carry no uri, so they are tracked by index.
  const [dismissedIndices, setDismissedIndices] = useState<Set<number>>(new Set());
  const [acceptingIdx, setAcceptingIdx] = useState<number | null>(null);

  const { toast } = useToasts();
  const runMutation = useRunPipeline();
  const applyMutation = useApplyRun();
  const { data: run } = usePipelineRun(runId ?? "");

  const isRunning = runMutation.isPending || hasRunStatus(run?.status, "pending", "running");
  const isCompleted = hasRunStatus(run?.status, "completed");
  const isFailed = hasRunStatus(run?.status, "failed");

  const { data: candidateItems = [] } = usePipelineCandidates(runId ?? "", isCompleted);
  const allCandidates = candidateItems.filter(
    (c): c is Extract<CandidateItem, { candidate_type: "refinement" }> =>
      c.candidate_type === "refinement",
  );

  const visibleCandidates = allCandidates
    .map((c, i) => ({ ...c, originalIdx: i }))
    .filter((c) => !dismissedIndices.has(c.originalIdx));

  const handleSuggest = async () => {
    setRunId(null);
    setDismissedIndices(new Set());
    try {
      const result = await runMutation.mutateAsync({
        type: "schema_node_connection_refinement",
        // Nothing is named: the server runs the type's default implementation and configuration.
        request: {
          scope_id: classId,
        },
      });
      setRunId(result.id);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to run relationship pipeline");
    }
  };

  const handleAccept = async (idx: number, candidateId: string) => {
    if (!runId) return;
    setAcceptingIdx(idx);
    try {
      const result = await applyMutation.mutateAsync({
        runId,
        params: { node_id: classId },
        body: { accepted_candidate_ids: [candidateId] },
      });
      setDismissedIndices((prev) => new Set([...prev, idx]));
      if (result.relationships_created + result.relationships_removed > 0) {
        toast("success", "Relationship applied");
      } else if (result.relationships_modified > 0) {
        toast("warning", "Changing an existing relationship isn't supported yet; nothing changed");
      } else {
        toast("info", "Nothing changed: the relationship is already as suggested");
      }
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to apply relationship");
    } finally {
      setAcceptingIdx(null);
    }
  };

  const handleDismiss = (idx: number) => {
    setDismissedIndices((prev) => new Set([...prev, idx]));
  };

  const hasRun = isCompleted || isRunning || isFailed;

  return (
    <div className="relationship-suggester" data-testid="relationship-suggester">
      {!hasRun && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void handleSuggest()}
          data-testid="relationship-suggester-btn"
        >
          ✦ Suggest relationships
        </Button>
      )}

      {isRunning && (
        <div
          className="relationship-suggester-shimmer"
          data-testid="relationship-suggester-loading"
        >
          <div className="skeleton" style={{ height: 72 }} />
          <div className="skeleton" style={{ height: 72 }} />
        </div>
      )}

      {isFailed && (
        <div className="suggester-error" data-testid="relationship-suggester-error">
          <p className="suggester-error-message">
            {run?.failure_reason ?? "Relationship pipeline failed"}
          </p>
          <div className="suggester-error-actions">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="relationship-error-retry-btn"
            >
              Try again
            </Button>
          </div>
        </div>
      )}

      {isCompleted && visibleCandidates.length === 0 && (
        <>
          <p className="relationship-suggester-empty">No relationship suggestions available</p>
          <div className="relationship-suggester-footer">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="relationship-suggester-retry-btn"
            >
              ✦ Suggest again
            </Button>
          </div>
        </>
      )}

      {isCompleted && visibleCandidates.length > 0 && (
        <>
          {visibleCandidates.map((candidate) => {
            const isAccepting = acceptingIdx === candidate.originalIdx;
            return (
              <div
                key={candidate.originalIdx}
                className="relationship-suggestion-card"
                data-testid={`relationship-suggestion-${candidate.originalIdx}`}
              >
                <div className="relationship-suggestion-label">
                  <span className="relationship-suggestion-source">{candidate.label}</span>
                </div>
                {candidate.description && (
                  <p className="suggest-field-candidate-text">{candidate.description}</p>
                )}
                {provenanceText(candidate.provenance) && (
                  <p className="suggest-field-candidate-rationale">
                    {provenanceText(candidate.provenance)}
                  </p>
                )}
                <div className="relationship-suggestion-confidence">
                  <div
                    className="relationship-suggestion-confidence-fill"
                    style={{ width: `${candidate.confidence * 100}%` }}
                    aria-label={`${(candidate.confidence * 100).toFixed(0)}% confidence`}
                  />
                </div>
                <div className="relationship-suggestion-meta">
                  <span>{(candidate.confidence * 100).toFixed(0)}% confidence</span>
                  <span>·</span>
                  <span>{candidate.source}</span>
                </div>
                <div className="relationship-suggestion-actions">
                  <button
                    type="button"
                    className="relationship-suggestion-accept-btn"
                    onClick={() => void handleAccept(candidate.originalIdx, candidate.candidate_id)}
                    disabled={isAccepting || applyMutation.isPending}
                    data-testid={`relationship-accept-${candidate.originalIdx}`}
                  >
                    {isAccepting ? "Applying…" : "Accept"}
                  </button>
                  <button
                    type="button"
                    className="relationship-suggestion-dismiss-btn"
                    onClick={() => handleDismiss(candidate.originalIdx)}
                    data-testid={`relationship-dismiss-${candidate.originalIdx}`}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            );
          })}
          <div className="relationship-suggester-footer">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void handleSuggest()}
              data-testid="relationship-suggester-retry-btn"
            >
              ✦ Suggest again
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
