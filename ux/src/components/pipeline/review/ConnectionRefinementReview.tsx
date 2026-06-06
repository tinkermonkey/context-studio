import { useState } from "react";
import { SegmentedControl } from "@tinkermonkey/heimdall-ui";
import type {
  SchemaNodeConnectionRefinementOutputSummary,
  Delta,
} from "@/api/hooks/pipeline/outputSummaryTypes";

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
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
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
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
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
        style={{
          padding: "12px",
          backgroundColor: bgColor,
          border: `1px solid ${borderColor}`,
          borderRadius: "4px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          opacity: status === "rejected" ? 0.5 : 1,
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
            <span
              style={{
                fontWeight: 600,
                fontSize: "11px",
                textTransform: "uppercase",
                color: `rgb(var(--status-${operationColor}))`,
              }}
            >
              {delta.operation}
            </span>

            {delta.operation === "modify" ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    fontWeight: 500,
                    fontSize: "12px",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {delta.source_label || delta.source_id}
                </span>
                <span style={{ color: "rgb(var(--canvas-fg-3))" }}>→</span>
                <span
                  style={{
                    fontWeight: 500,
                    fontSize: "12px",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {delta.target_label || delta.target_id}
                </span>
              </div>
            ) : (
              <span style={{ fontWeight: 500, fontSize: "12px" }}>
                {delta.operation === "add"
                  ? `${delta.source_label || delta.source_id} → ${delta.target_label || delta.target_id}`
                  : `${delta.source_label || delta.source_id} ← ${delta.target_label || delta.target_id}`}
              </span>
            )}
          </div>

          <div style={{ display: "flex", gap: "4px" }}>
            <button
              type="button"
              data-testid={`connection-accept-${deltaKey}`}
              onClick={() => acceptDelta(deltaKey)}
              aria-label={`Accept delta: ${status}`}
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
              data-testid={`connection-reject-${deltaKey}`}
              onClick={() => rejectDelta(deltaKey)}
              aria-label={`Reject delta: ${status}`}
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

        <div
          style={{
            display: "flex",
            gap: "8px",
            fontSize: "11px",
            color: "rgb(var(--canvas-fg-3))",
          }}
        >
          <span>
            Predicate:{" "}
            <span
              style={{
                fontFamily: "var(--font-mono)",
                color: "rgb(var(--canvas-fg-2))",
              }}
            >
              {delta.relationship_type}
            </span>
          </span>
          <span>
            Score: {(delta.confidence * 100).toFixed(0)}%
          </span>
          <span>
            Source:{" "}
            <span style={{ fontFamily: "var(--font-mono)" }}>
              {delta.source}
            </span>
          </span>
        </div>

        {delta.operation === "modify" && (delta.before || delta.after) && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "8px",
              paddingTop: "8px",
              borderTop: `1px solid ${borderColor}`,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: "10px",
                  fontWeight: 600,
                  marginBottom: "4px",
                  color: "rgb(var(--status-rose))",
                }}
              >
                Before
              </div>
              <div
                style={{
                  fontSize: "11px",
                  padding: "6px",
                  backgroundColor: "rgb(var(--status-rose) / 0.1)",
                  border: "1px solid rgb(var(--status-rose) / 0.3)",
                  borderRadius: "2px",
                  fontFamily: "var(--font-mono)",
                  color: "rgb(var(--canvas-fg-1))",
                }}
              >
                {delta.before || "—"}
              </div>
            </div>
            <div>
              <div
                style={{
                  fontSize: "10px",
                  fontWeight: 600,
                  marginBottom: "4px",
                  color: "rgb(var(--status-emerald))",
                }}
              >
                After
              </div>
              <div
                style={{
                  fontSize: "11px",
                  padding: "6px",
                  backgroundColor: "rgb(var(--status-emerald) / 0.1)",
                  border: "1px solid rgb(var(--status-emerald) / 0.3)",
                  borderRadius: "2px",
                  fontFamily: "var(--font-mono)",
                  color: "rgb(var(--canvas-fg-1))",
                }}
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
      style={{ display: "flex", flexDirection: "column", gap: "12px" }}
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
        style={{ display: "flex", flexDirection: "column", gap: "8px" }}
      >
        {activeOperation === "add" && (
          <>
            {addDeltas.length === 0 ? (
              <div
                style={{
                  padding: "16px",
                  color: "rgb(var(--canvas-fg-3))",
                  fontSize: "12px",
                }}
              >
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
              <div
                style={{
                  padding: "16px",
                  color: "rgb(var(--canvas-fg-3))",
                  fontSize: "12px",
                }}
              >
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
              <div
                style={{
                  padding: "16px",
                  color: "rgb(var(--canvas-fg-3))",
                  fontSize: "12px",
                }}
              >
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
