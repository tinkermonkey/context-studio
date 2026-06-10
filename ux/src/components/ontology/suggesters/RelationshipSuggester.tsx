import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline, useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import { usePipelineRun, usePipelineCandidates } from "@/api/hooks/pipeline/usePipelineRuns";
import { useToasts } from "@/components/ui/Toast";
import "./Suggesters.css";

interface RelationshipSuggesterProps {
  classId: string;
}

export function RelationshipSuggester({ classId }: RelationshipSuggesterProps) {
  const [runId, setRunId] = useState<string | null>(null);
  const [dismissedUris, setDismissedUris] = useState<Set<string>>(new Set());
  const [acceptingUri, setAcceptingUri] = useState<string | null>(null);

  const { toast } = useToasts();
  const runMutation = useRunPipeline();
  const applyMutation = useApplyRun();
  const { data: run } = usePipelineRun(runId ?? "");

  const isRunning =
    runMutation.isPending ||
    run?.status === "PENDING" ||
    run?.status === "RUNNING";
  const isCompleted = run?.status === "COMPLETED";

  const { data: allCandidates = [] } = usePipelineCandidates(runId ?? "", isCompleted);

  const visibleCandidates = allCandidates
    .map((c, i) => ({ ...c, originalIdx: i }))
    .filter((c) => !dismissedUris.has(c.uri));

  const handleSuggest = async () => {
    setRunId(null);
    setDismissedUris(new Set());
    try {
      const result = await runMutation.mutateAsync({
        type: "schema_node_connection_refinement",
        request: {
          implementation_id: "default",
          configuration_ref: "default",
          node_id: classId,
        },
      });
      setRunId(result.id);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to run relationship pipeline");
    }
  };

  const handleAccept = async (uri: string, confidence: number) => {
    if (!runId) return;
    setAcceptingUri(uri);
    try {
      await applyMutation.mutateAsync({
        runId,
        params: { confidence_threshold: confidence, node_id: classId },
      });
      setDismissedUris((prev) => new Set([...prev, uri]));
      toast("success", "Relationship applied");
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to apply relationship");
    } finally {
      setAcceptingUri(null);
    }
  };

  const handleDismiss = (uri: string) => {
    setDismissedUris((prev) => new Set([...prev, uri]));
  };

  const hasRun = isCompleted || isRunning;

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
        <div className="relationship-suggester-shimmer" data-testid="relationship-suggester-loading">
          <div className="skeleton" style={{ height: 72 }} />
          <div className="skeleton" style={{ height: 72 }} />
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
            const isAccepting = acceptingUri === candidate.uri;
            return (
              <div
                key={candidate.uri}
                className="relationship-suggestion-card"
                data-testid={`relationship-suggestion-${candidate.originalIdx}`}
              >
                <div className="relationship-suggestion-triple">
                  <span className="relationship-suggestion-source">{candidate.label}</span>
                </div>
                {candidate.description && (
                  <p className="suggest-field-candidate-text">{candidate.description}</p>
                )}
                {candidate.provenance && (
                  <p className="suggest-field-candidate-rationale">{candidate.provenance}</p>
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
                    onClick={() => void handleAccept(candidate.uri, candidate.confidence)}
                    disabled={isAccepting || applyMutation.isPending}
                    data-testid={`relationship-accept-${candidate.originalIdx}`}
                  >
                    {isAccepting ? "Applying…" : "Accept"}
                  </button>
                  <button
                    type="button"
                    className="relationship-suggestion-dismiss-btn"
                    onClick={() => handleDismiss(candidate.uri)}
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
