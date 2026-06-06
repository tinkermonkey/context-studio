import { useState } from "react";
import type { SchemaNodeDefinitionRefinementOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";

interface DefinitionRefinementReviewProps {
  outputSummary: SchemaNodeDefinitionRefinementOutputSummary | null;
}

type SelectedOption = "current" | number;

export function DefinitionRefinementReview({
  outputSummary,
}: DefinitionRefinementReviewProps) {
  const [selectedOption, setSelectedOption] = useState<SelectedOption>("current");

  if (!outputSummary) {
    return (
      <div
        data-testid="definition-refinement-empty"
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

  const candidates = outputSummary.candidates || [];
  const currentDefinition = outputSummary.current_definition || "";

  if (!currentDefinition && candidates.length === 0) {
    return (
      <div
        data-testid="definition-refinement-empty"
        style={{
          padding: "16px",
          color: "rgb(var(--canvas-fg-3))",
          fontSize: "12px",
        }}
      >
        No definitions available
      </div>
    );
  }

  const displayCandidates = candidates.slice(0, 3);

  return (
    <div
      data-testid="definition-refinement-review"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {currentDefinition && (
        <div
          data-testid="definition-refinement-current"
          style={{
            padding: "12px",
            border:
              selectedOption === "current"
                ? "2px solid rgb(var(--accent-cyan))"
                : "1px solid rgb(var(--canvas-border))",
            borderRadius: "4px",
            backgroundColor: "rgb(var(--canvas-bg-hover))",
            cursor: "pointer",
            transition: "border-color 0.2s",
          }}
          onClick={() => setSelectedOption("current")}
          role="radio"
          aria-checked={selectedOption === "current"}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setSelectedOption("current");
            }
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              marginBottom: "8px",
            }}
          >
            <input
              type="radio"
              name="definition-choice"
              value="current"
              checked={selectedOption === "current"}
              onChange={() => setSelectedOption("current")}
              aria-label="Keep current definition"
              style={{ marginTop: "2px", cursor: "pointer" }}
            />
            <span style={{ fontWeight: 600, fontSize: "13px" }}>
              Current Definition
            </span>
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "12px",
              color: "rgb(var(--canvas-fg-1))",
              lineHeight: 1.5,
            }}
          >
            {currentDefinition}
          </p>
        </div>
      )}

      {displayCandidates.map((candidate, idx) => (
        <div
          key={idx}
          data-testid={`definition-refinement-candidate-${idx}`}
          style={{
            padding: "12px",
            border:
              selectedOption === idx
                ? "2px solid rgb(var(--accent-cyan))"
                : "1px solid rgb(var(--canvas-border))",
            borderRadius: "4px",
            backgroundColor: "rgb(var(--canvas-bg-hover))",
            cursor: "pointer",
            transition: "border-color 0.2s",
          }}
          onClick={() => setSelectedOption(idx)}
          role="radio"
          aria-checked={selectedOption === idx}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setSelectedOption(idx);
            }
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              marginBottom: "8px",
              justifyContent: "space-between",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "8px",
                flex: 1,
              }}
            >
              <input
                type="radio"
                name="definition-choice"
                value={idx}
                checked={selectedOption === idx}
                onChange={() => setSelectedOption(idx)}
                aria-label={`Choose candidate ${idx + 1}`}
                style={{ marginTop: "2px", cursor: "pointer" }}
              />
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: "13px",
                    marginBottom: "4px",
                  }}
                >
                  Candidate {idx + 1}
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "4px",
                    marginBottom: "8px",
                  }}
                >
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "2px 6px",
                      backgroundColor: "rgb(var(--canvas-bg))",
                      border: "1px solid rgb(var(--canvas-border))",
                      borderRadius: "2px",
                    }}
                  >
                    Score: {(candidate.confidence * 100).toFixed(0)}%
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "2px 6px",
                      backgroundColor: "rgb(var(--canvas-bg))",
                      border: "1px solid rgb(var(--canvas-border))",
                      borderRadius: "2px",
                    }}
                  >
                    {candidate.source}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <p
            style={{
              margin: 0,
              fontSize: "12px",
              color: "rgb(var(--canvas-fg-1))",
              lineHeight: 1.5,
              marginBottom: candidate.rationale ? "8px" : 0,
            }}
          >
            {candidate.definition}
          </p>

          {candidate.rationale && (
            <div
              style={{
                fontSize: "11px",
                color: "rgb(var(--canvas-fg-3))",
                fontStyle: "italic",
                paddingTop: "8px",
                borderTop: "1px solid rgb(var(--canvas-border))",
                marginTop: "8px",
              }}
            >
              <strong>Rationale:</strong> {candidate.rationale}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
