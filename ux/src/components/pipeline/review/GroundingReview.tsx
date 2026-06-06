import { useState } from "react";
import { Chip } from "@tinkermonkey/heimdall-ui";
import type { SchemaNodeGroundingOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./ReviewComponents.css";

interface GroundingReviewProps {
  outputSummary: SchemaNodeGroundingOutputSummary | null;
  candidateStatus?: Record<string, CandidateStatus>;
  onCandidateStatusChange?: (candidateStatus: Record<string, CandidateStatus>) => void;
}

type CandidateStatus = "pending" | "accepted" | "rejected";

export function GroundingReview({
  outputSummary,
  candidateStatus: externalCandidateStatus,
  onCandidateStatusChange: externalOnCandidateStatusChange,
}: GroundingReviewProps) {
  const [internalCandidateStatus, setInternalCandidateStatus] = useState<
    Record<string, CandidateStatus>
  >({});

  // Use external state if provided, otherwise use internal state
  const candidateStatus = externalCandidateStatus ?? internalCandidateStatus;

  const setCandidateStatus = (
    update: Record<string, CandidateStatus> | ((prev: Record<string, CandidateStatus>) => Record<string, CandidateStatus>)
  ) => {
    if (externalOnCandidateStatusChange) {
      const newValue = typeof update === "function" ? update(candidateStatus) : update;
      externalOnCandidateStatusChange(newValue);
    } else {
      setInternalCandidateStatus(update);
    }
  };

  if (!outputSummary) {
    return (
      <div
        data-testid="grounding-empty"
        className="review-empty"
      >
        No grounding candidates available
      </div>
    );
  }

  const groundedNodes = outputSummary.grounded_nodes || [];

  if (groundedNodes.length === 0) {
    return (
      <div
        data-testid="grounding-empty"
        className="review-empty"
      >
        No nodes to ground
      </div>
    );
  }

  const acceptCandidate = (candidateKey: string) => {
    const current = candidateStatus[candidateKey] || "pending";
    setCandidateStatus((prev) => ({
      ...prev,
      [candidateKey]: current === "accepted" ? "pending" : "accepted",
    }));
  };

  const rejectCandidate = (candidateKey: string) => {
    const current = candidateStatus[candidateKey] || "pending";
    setCandidateStatus((prev) => ({
      ...prev,
      [candidateKey]: current === "rejected" ? "pending" : "rejected",
    }));
  };

  return (
    <div
      data-testid="grounding-review"
      className="grounding-review"
    >
      {groundedNodes.map((node) => (
        <div
          key={node.node_id}
          data-testid={`grounding-node-${node.node_id}`}
          className="grounding-node-section"
        >
          <div className="grounding-node-header">
            <span className="grounding-node-label">
              {node.node_label}
            </span>
            <span className="grounding-node-id">
              {node.node_id}
            </span>
          </div>

          <div className="grounding-candidates-list">
            {node.candidates.map((candidate, idx) => {
              const candidateKey = `${node.node_id}-${idx}`;
              const status = candidateStatus[candidateKey] || "pending";

              return (
                <div
                  key={candidateKey}
                  data-testid={`grounding-candidate-${candidateKey}`}
                  className="grounding-candidate-card"
                  data-status={status}
                >
                  <div className="grounding-candidate-header">
                    <div className="grounding-candidate-info">
                      <span className="grounding-candidate-label">
                        {candidate.label}
                      </span>
                      <Chip
                        variant="neutral"
                      >
                        {candidate.source}
                      </Chip>
                    </div>
                    <div className="grounding-candidate-buttons">
                      <button
                        type="button"
                        data-testid={`grounding-accept-${candidateKey}`}
                        onClick={() => acceptCandidate(candidateKey)}
                        aria-label={`Accept candidate: ${status}`}
                        className="candidate-action-button"
                        data-accepted={status === "accepted"}
                      >
                        ✓ Accept
                      </button>
                      <button
                        type="button"
                        data-testid={`grounding-reject-${candidateKey}`}
                        onClick={() => rejectCandidate(candidateKey)}
                        aria-label={`Reject candidate: ${status}`}
                        className="candidate-action-button"
                        data-rejected={status === "rejected"}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>

                  {candidate.description && (
                    <span className="grounding-candidate-description">
                      {candidate.description}
                    </span>
                  )}

                  {candidate.match_rationale && (
                    <span className="grounding-candidate-rationale">
                      Rationale: {candidate.match_rationale}
                    </span>
                  )}

                  <div className="grounding-candidate-score">
                    <span>
                      Score: {(candidate.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
