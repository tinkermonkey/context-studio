import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useRunPipeline, useApplyRun } from "@/api/hooks/pipeline/usePipelineMutations";
import { usePipelineRun, usePipelineCandidates } from "@/api/hooks/pipeline/usePipelineRuns";
import { useToasts } from "@/components/ui/Toast";
import "./Suggesters.css";

interface GroundingSectionProps {
  classId: string;
}

export function GroundingSection({ classId }: GroundingSectionProps) {
  const [runId, setRunId] = useState<string | null>(null);
  const [appliedUris, setAppliedUris] = useState<Set<string>>(new Set());
  const [dismissedUris, setDismissedUris] = useState<Set<string>>(new Set());

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
    setAppliedUris(new Set());
    setDismissedUris(new Set());
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
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to run grounding pipeline");
    }
  };

  const handleAdd = async (uri: string, confidence: number) => {
    if (!runId) return;
    try {
      await applyMutation.mutateAsync({
        runId,
        params: { confidence_threshold: confidence, node_id: classId },
      });
      // The apply endpoint applies all candidates at or above the threshold
      const applied = new Set(allCandidates.filter((c) => c.confidence >= confidence).map((c) => c.uri));
      setAppliedUris((prev) => new Set([...prev, ...applied]));
      toast("success", "Grounding applied");
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to apply grounding");
    }
  };

  const handleDismiss = (uri: string) => {
    setDismissedUris((prev) => new Set([...prev, uri]));
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

      {isCompleted && allCandidates.length === 0 && (
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

      {isCompleted && visibleCandidates.length > 0 && (
        <>
          {visibleCandidates.map((candidate) => {
            const isApplied = appliedUris.has(candidate.uri);
            return (
              <div
                key={candidate.uri}
                className="grounding-proposal-card"
                data-testid={`grounding-proposal-${candidate.originalIdx}`}
              >
                <div className="grounding-proposal-header">
                  <span className="grounding-proposal-name">{candidate.label}</span>
                </div>
                {candidate.uri && (
                  <span className="grounding-proposal-url">{candidate.uri}</span>
                )}
                {candidate.description && (
                  <p className="suggest-field-candidate-text">{candidate.description}</p>
                )}
                {candidate.provenance && (
                  <p className="grounding-proposal-rationale">{candidate.provenance}</p>
                )}
                <div className="grounding-proposal-confidence">
                  <div
                    className="grounding-proposal-confidence-fill"
                    style={{ width: `${candidate.confidence * 100}%` }}
                    aria-label={`${(candidate.confidence * 100).toFixed(0)}% confidence`}
                  />
                </div>
                <div className="suggest-field-candidate-meta">
                  <span>{(candidate.confidence * 100).toFixed(0)}% confidence</span>
                  <span>·</span>
                  <span>{candidate.source}</span>
                </div>
                <div className="grounding-proposal-actions">
                  <button
                    type="button"
                    className="grounding-proposal-add-btn"
                    onClick={() => void handleAdd(candidate.uri, candidate.confidence)}
                    data-added={isApplied}
                    disabled={isApplied || applyMutation.isPending}
                    data-testid={`grounding-add-${candidate.originalIdx}`}
                  >
                    {isApplied ? "✓ Applied" : "Apply"}
                  </button>
                  <button
                    type="button"
                    className="grounding-proposal-dismiss-btn"
                    onClick={() => handleDismiss(candidate.uri)}
                    data-testid={`grounding-dismiss-${candidate.originalIdx}`}
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

      {isCompleted && allCandidates.length > 0 && visibleCandidates.length === 0 && (
        <p className="grounding-section-empty">All candidates dismissed</p>
      )}
    </div>
  );
}
