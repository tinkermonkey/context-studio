import { useState } from "react";
import { Chip, Badge } from "@tinkermonkey/heimdall-ui";
import type { SchemaNodeGroundingOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";

interface GroundingReviewProps {
  outputSummary: SchemaNodeGroundingOutputSummary | null;
}

type CandidateStatus = "pending" | "accepted" | "rejected";

export function GroundingReview({ outputSummary }: GroundingReviewProps) {
  const [candidateStatus, setCandidateStatus] = useState<
    Record<string, CandidateStatus>
  >({});

  if (!outputSummary) {
    return (
      <div
        data-testid="grounding-empty"
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
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
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
      >
        No nodes to ground
      </div>
    );
  }

  const toggleCandidateStatus = (candidateKey: string) => {
    const current = candidateStatus[candidateKey] || "pending";
    if (current === "pending") {
      setCandidateStatus((prev) => ({
        ...prev,
        [candidateKey]: "accepted",
      }));
    } else if (current === "accepted") {
      setCandidateStatus((prev) => ({
        ...prev,
        [candidateKey]: "rejected",
      }));
    } else {
      setCandidateStatus((prev) => ({
        ...prev,
        [candidateKey]: "pending",
      }));
    }
  };

  return (
    <div
      data-testid="grounding-review"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      {groundedNodes.map((node) => (
        <div
          key={node.node_id}
          data-testid={`grounding-node-${node.node_id}`}
          style={{
            padding: "12px",
            border: "1px solid rgb(var(--canvas-border))",
            borderRadius: "4px",
            backgroundColor: "rgb(var(--canvas-bg-hover))",
          }}
        >
          <div style={{ marginBottom: "12px" }}>
            <span style={{ fontWeight: 600, fontSize: "13px" }}>
              {node.node_label}
            </span>
            <span
              style={{
                color: "rgb(var(--canvas-fg-3))",
                fontSize: "11px",
                marginLeft: "8px",
                fontFamily: "var(--font-mono)",
              }}
            >
              {node.node_id}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {node.candidates.map((candidate, idx) => {
              const candidateKey = `${node.node_id}-${idx}`;
              const status = candidateStatus[candidateKey] || "pending";

              return (
                <div
                  key={candidateKey}
                  data-testid={`grounding-candidate-${candidateKey}`}
                  style={{
                    padding: "8px",
                    backgroundColor: "rgb(var(--canvas-bg))",
                    border: "1px solid rgb(var(--canvas-border))",
                    borderRadius: "3px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                    opacity:
                      status === "rejected"
                        ? 0.5
                        : status === "accepted"
                          ? 1
                          : 0.75,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "8px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      <span style={{ fontWeight: 500, fontSize: "13px" }}>
                        {candidate.label}
                      </span>
                      <Chip
                        variant="neutral"
                        style={{
                          padding: "2px 6px",
                          fontSize: "10px",
                        }}
                      >
                        {candidate.source}
                      </Chip>
                    </div>
                    <div style={{ display: "flex", gap: "4px" }}>
                      <button
                        type="button"
                        onClick={() => toggleCandidateStatus(candidateKey)}
                        aria-label={`Toggle candidate status: ${status}`}
                        style={{
                          padding: "4px 8px",
                          fontSize: "11px",
                          fontWeight: 500,
                          border:
                            status === "accepted"
                              ? "1px solid rgb(var(--status-emerald))"
                              : "1px solid rgb(var(--canvas-border))",
                          backgroundColor:
                            status === "accepted"
                              ? "rgb(var(--status-emerald) / 0.1)"
                              : "transparent",
                          color:
                            status === "accepted"
                              ? "rgb(var(--status-emerald))"
                              : "rgb(var(--canvas-fg-2))",
                          borderRadius: "3px",
                          cursor: "pointer",
                        }}
                      >
                        ✓ Accept
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleCandidateStatus(candidateKey)}
                        aria-label={`Toggle candidate status: ${status}`}
                        style={{
                          padding: "4px 8px",
                          fontSize: "11px",
                          fontWeight: 500,
                          border:
                            status === "rejected"
                              ? "1px solid rgb(var(--status-rose))"
                              : "1px solid rgb(var(--canvas-border))",
                          backgroundColor:
                            status === "rejected"
                              ? "rgb(var(--status-rose) / 0.1)"
                              : "transparent",
                          color:
                            status === "rejected"
                              ? "rgb(var(--status-rose))"
                              : "rgb(var(--canvas-fg-2))",
                          borderRadius: "3px",
                          cursor: "pointer",
                        }}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>

                  {candidate.description && (
                    <span
                      style={{
                        fontSize: "11px",
                        color: "rgb(var(--canvas-fg-3))",
                      }}
                    >
                      {candidate.description}
                    </span>
                  )}

                  {candidate.match_rationale && (
                    <span
                      style={{
                        fontSize: "11px",
                        color: "rgb(var(--canvas-fg-2))",
                        fontStyle: "italic",
                      }}
                    >
                      Rationale: {candidate.match_rationale}
                    </span>
                  )}

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <span style={{ fontSize: "10px" }}>
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
