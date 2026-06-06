import { useState } from "react";
import { Table } from "@tinkermonkey/heimdall-ui";
import type { IndividualExtractionOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./ReviewComponents.css";

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
        className="review-empty"
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
        className="review-empty"
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
      className="individual-extraction-review"
    >
      <Table
        columns={[
          {
            key: "subject" as const,
            label: "Subject",
            render: (v) => (
              <span className="individual-table-cell-label">{String(v)}</span>
            ),
          },
          {
            key: "predicate" as const,
            label: "Predicate",
            render: (v) => (
              <span className="individual-table-cell-mono">
                {String(v)}
              </span>
            ),
          },
          {
            key: "object" as const,
            label: "Object",
            render: (v) => (
              <span className="individual-table-cell-label">{String(v)}</span>
            ),
          },
          {
            key: "confidence" as const,
            label: "Confidence",
            width: "100px",
            render: (v) => (
              <span className="individual-table-cell-confidence">
                {(Number(v) * 100).toFixed(0)}%
              </span>
            ),
          },
          {
            key: "source" as const,
            label: "Source",
            width: "120px",
            render: (v) => (
              <span className="individual-table-cell-mono">
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

      <div className="individual-select-all-footer">
        <input
          type="checkbox"
          data-testid="individual-extraction-select-all"
          checked={allSelected}
          onChange={handleSelectAll}
          aria-label="Select all triples"
          className="individual-select-all-checkbox"
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
