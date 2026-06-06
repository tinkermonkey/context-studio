import { useState } from "react";
import { Table } from "@tinkermonkey/heimdall-ui";
import type { IndividualExtractionOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";

interface IndividualExtractionReviewProps {
  outputSummary: IndividualExtractionOutputSummary | null;
}

export function IndividualExtractionReview({
  outputSummary,
}: IndividualExtractionReviewProps) {
  const [selectedTriples, setSelectedTriples] = useState<(string | number)[]>([]);

  if (!outputSummary) {
    return (
      <div
        data-testid="individual-extraction-empty"
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
      >
        No extraction candidates available
      </div>
    );
  }

  const triples = outputSummary.triples || [];

  if (triples.length === 0) {
    return (
      <div
        data-testid="individual-extraction-empty"
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
      >
        No triples extracted
      </div>
    );
  }

  const allSelected =
    triples.length > 0 && selectedTriples.length === triples.length;

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedTriples([]);
    } else {
      setSelectedTriples(triples.map((_, i) => `triple-${i}`));
    }
  };

  return (
    <div
      data-testid="individual-extraction-review"
      style={{ display: "flex", flexDirection: "column" }}
    >
      <Table
        columns={[
          {
            key: "subject" as const,
            label: "Subject",
            render: (v) => (
              <span style={{ fontWeight: 500 }}>{String(v)}</span>
            ),
          },
          {
            key: "predicate" as const,
            label: "Predicate",
            render: (v) => (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "12px",
                }}
              >
                {String(v)}
              </span>
            ),
          },
          {
            key: "object" as const,
            label: "Object",
            render: (v) => (
              <span style={{ fontWeight: 500 }}>{String(v)}</span>
            ),
          },
          {
            key: "confidence" as const,
            label: "Confidence",
            width: "100px",
            render: (v) => (
              <span style={{ textAlign: "center" }}>
                {(Number(v) * 100).toFixed(0)}%
              </span>
            ),
          },
          {
            key: "source" as const,
            label: "Source",
            width: "120px",
            render: (v) => (
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "11px",
                  color: "rgb(var(--canvas-fg-3))",
                }}
              >
                {String(v)}
              </span>
            ),
          },
        ]}
        data={triples}
        rowKey={(row, index) => `triple-${index}`}
        selectable
        selectedRows={selectedTriples}
        onSelectRows={setSelectedTriples}
        emptyState={<span>No triples extracted</span>}
      />

      <div
        style={{
          padding: "8px",
          borderTop: "1px solid rgb(var(--canvas-border))",
          display: "flex",
          alignItems: "center",
          fontSize: "12px",
        }}
      >
        <input
          type="checkbox"
          data-testid="individual-extraction-select-all"
          checked={allSelected}
          onChange={handleSelectAll}
          aria-label="Select all triples"
          style={{ marginRight: "8px", cursor: "pointer" }}
        />
        <span>
          {selectedTriples.length === 0
            ? "Select all"
            : `${selectedTriples.length} of ${triples.length} selected`}
        </span>
      </div>
    </div>
  );
}
