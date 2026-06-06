import { useState } from "react";
import { SegmentedControl } from "@tinkermonkey/heimdall-ui";
import type {
  SchemaNodeConnectionRefinementOutputSummary,
  Delta,
} from "@/api/hooks/pipeline/outputSummaryTypes";
import "./ReviewComponents.css";

interface ConnectionRefinementReviewProps {
  outputSummary: SchemaNodeConnectionRefinementOutputSummary | null;
}

type OperationType = "add" | "remove" | "modify";
type DeltaStatus = "pending" | "accepted" | "rejected";

export function ConnectionRefinementReview({
  outputSummary,
}: ConnectionRefinementReviewProps) {
  const [activeOperation, setActiveOperation] = useState<OperationType>("add");
  const [deltaStatus, setDeltaStatus] = useState<Record<string, DeltaStatus>>({});

  if (!outputSummary) {
    return (
      <div
        data-testid="connection-refinement-empty"
        className="review-empty"
      >
        No refinement candidates available
      </div>
    );
  }

  const deltas = outputSummary.deltas || [];

  if (deltas.length === 0) {
    return (
      <div
        data-testid="connection-refinement-empty"
        className="review-empty"
      >
        No connection deltas
      </div>
    );
  }

  const addDeltas = deltas.filter((d) => d.operation === "add");
  const removeDeltas = deltas.filter((d) => d.operation === "remove");
  const modifyDeltas = deltas.filter((d) => d.operation === "modify");

  const acceptDelta = (deltaKey: string) => {
    const current = deltaStatus[deltaKey] || "pending";
    setDeltaStatus((prev) => ({
      ...prev,
      [deltaKey]: current === "accepted" ? "pending" : "accepted",
    }));
  };

  const rejectDelta = (deltaKey: string) => {
    const current = deltaStatus[deltaKey] || "pending";
    setDeltaStatus((prev) => ({
      ...prev,
      [deltaKey]: current === "rejected" ? "pending" : "rejected",
    }));
  };

  const getOperationColor = (
    op: OperationType
  ): "emerald" | "rose" | "amber" => {
    switch (op) {
      case "add":
        return "emerald";
      case "remove":
        return "rose";
      case "modify":
        return "amber";
    }
  };

  const renderDelta = (delta: Delta, deltaKey: string) => {
    const status = deltaStatus[deltaKey] || "pending";
    const operationColor = getOperationColor(delta.operation);
    const bgColor =
      operationColor === "emerald"
        ? "rgb(var(--status-emerald) / 0.05)"
        : operationColor === "rose"
          ? "rgb(var(--status-rose) / 0.05)"
          : "rgb(var(--status-amber) / 0.05)";
    const borderColor =
      operationColor === "emerald"
        ? "rgb(var(--status-emerald) / 0.3)"
        : operationColor === "rose"
          ? "rgb(var(--status-rose) / 0.3)"
          : "rgb(var(--status-amber) / 0.3)";

    return (
      <div
        key={deltaKey}
        data-testid={`connection-delta-${deltaKey}`}
        className="connection-delta-card"
        style={{
          backgroundColor: bgColor,
          borderColor: borderColor,
        }}
        data-rejected={status === "rejected"}
      >
        <div className="connection-delta-header">
          <div className="connection-delta-details">
            <span
              className="connection-delta-operation-label"
              style={{ color: `rgb(var(--status-${operationColor}))` }}
            >
              {delta.operation}
            </span>

            {delta.operation === "modify" ? (
              <div className="connection-delta-triple">
                <span className="connection-delta-triple-text">
                  {delta.source_label || delta.source_id}
                </span>
                <span className="connection-delta-separator">→</span>
                <span className="connection-delta-triple-text">
                  {delta.target_label || delta.target_id}
                </span>
              </div>
            ) : (
              <span className="connection-delta-triple-text">
                {delta.operation === "add"
                  ? `${delta.source_label || delta.source_id} → ${delta.target_label || delta.target_id}`
                  : `${delta.source_label || delta.source_id} ← ${delta.target_label || delta.target_id}`}
              </span>
            )}
          </div>

          <div className="connection-delta-buttons">
            <button
              type="button"
              data-testid={`connection-accept-${deltaKey}`}
              onClick={() => acceptDelta(deltaKey)}
              aria-label={`Accept delta: ${status}`}
              className="candidate-action-button"
              data-accepted={status === "accepted"}
            >
              ✓ Accept
            </button>
            <button
              type="button"
              data-testid={`connection-reject-${deltaKey}`}
              onClick={() => rejectDelta(deltaKey)}
              aria-label={`Reject delta: ${status}`}
              className="candidate-action-button"
              data-rejected={status === "rejected"}
            >
              ✕ Reject
            </button>
          </div>
        </div>

        <div className="connection-delta-metadata">
          <span>
            Predicate:{" "}
            <span className="mono-text">
              {delta.relationship_type}
            </span>
          </span>
          <span>
            Score: {(delta.confidence * 100).toFixed(0)}%
          </span>
          <span>
            Source:{" "}
            <span className="mono-text">
              {delta.source}
            </span>
          </span>
        </div>

        {delta.operation === "modify" && (delta.before || delta.after) && (
          <div
            className="connection-delta-comparison"
            style={{ borderTopColor: borderColor }}
          >
            <div>
              <div
                className="comparison-section-label"
                data-type="before"
              >
                Before
              </div>
              <div
                className="comparison-section-value"
                data-type="before"
              >
                {delta.before || "—"}
              </div>
            </div>
            <div>
              <div
                className="comparison-section-label"
                data-type="after"
              >
                After
              </div>
              <div
                className="comparison-section-value"
                data-type="after"
              >
                {delta.after || "—"}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      data-testid="connection-refinement-review"
      className="connection-refinement-review"
    >
      <SegmentedControl
        value={activeOperation}
        onChange={(value) => setActiveOperation(value as OperationType)}
        options={[
          { value: "add", label: `Add (${addDeltas.length})` },
          { value: "remove", label: `Remove (${removeDeltas.length})` },
          { value: "modify", label: `Modify (${modifyDeltas.length})` },
        ]}
      />

      <div
        data-testid={`connection-deltas-${activeOperation}`}
        className="connection-deltas-container"
      >
        {activeOperation === "add" && (
          <>
            {addDeltas.length === 0 ? (
              <div className="review-empty">
                No connections to add
              </div>
            ) : (
              addDeltas.map((delta, idx) =>
                renderDelta(delta, `add-${idx}`)
              )
            )}
          </>
        )}

        {activeOperation === "remove" && (
          <>
            {removeDeltas.length === 0 ? (
              <div className="review-empty">
                No connections to remove
              </div>
            ) : (
              removeDeltas.map((delta, idx) =>
                renderDelta(delta, `remove-${idx}`)
              )
            )}
          </>
        )}

        {activeOperation === "modify" && (
          <>
            {modifyDeltas.length === 0 ? (
              <div className="review-empty">
                No connections to modify
              </div>
            ) : (
              modifyDeltas.map((delta, idx) =>
                renderDelta(delta, `modify-${idx}`)
              )
            )}
          </>
        )}
      </div>
    </div>
  );
}
