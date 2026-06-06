import { useState } from "react";
import type { SchemaNodeDefinitionRefinementOutputSummary } from "@/api/hooks/pipeline/outputSummaryTypes";
import "./ReviewComponents.css";

interface DefinitionRefinementReviewProps {
  outputSummary: SchemaNodeDefinitionRefinementOutputSummary | null;
  selectedOption?: SelectedOption;
  onSelectOption?: (option: SelectedOption) => void;
}

type SelectedOption = "current" | number;

export function DefinitionRefinementReview({
  outputSummary,
  selectedOption: externalSelectedOption,
  onSelectOption: externalOnSelectOption,
}: DefinitionRefinementReviewProps) {
  const [internalSelectedOption, setInternalSelectedOption] = useState<SelectedOption>("current");

  // Use external state if provided, otherwise use internal state
  const selectedOption = externalSelectedOption ?? internalSelectedOption;
  const setSelectedOption = externalOnSelectOption ?? setInternalSelectedOption;

  if (!outputSummary) {
    return (
      <div
        data-testid="definition-refinement-empty"
        className="review-empty"
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
        className="review-empty"
      >
        No definitions available
      </div>
    );
  }

  const displayCandidates = candidates.slice(0, 3);

  return (
    <div
      data-testid="definition-refinement-review"
      role="radiogroup"
      className="definition-refinement-review"
    >
      {currentDefinition && (
        <div
          data-testid="definition-refinement-current"
          className="definition-option-card"
          data-selected={selectedOption === "current"}
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
          <div className="definition-option-title">
            <input
              type="radio"
              data-testid="definition-refinement-radio-current"
              name="definition-choice"
              value="current"
              checked={selectedOption === "current"}
              onChange={() => setSelectedOption("current")}
              aria-label="Keep current definition"
              className="definition-radio-input"
            />
            <span className="definition-option-label">
              Current Definition
            </span>
          </div>
          <p className="definition-text">
            {currentDefinition}
          </p>
        </div>
      )}

      {displayCandidates.map((candidate, idx) => (
        <div
          key={idx}
          data-testid={`definition-refinement-candidate-${idx}`}
          className="definition-option-card"
          data-selected={selectedOption === idx}
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
          <div className="definition-option-title-spaced">
            <div className="definition-option-title">
              <input
                type="radio"
                data-testid={`definition-refinement-radio-candidate-${idx}`}
                name="definition-choice"
                value={idx}
                checked={selectedOption === idx}
                onChange={() => setSelectedOption(idx)}
                aria-label={`Choose candidate ${idx + 1}`}
                className="definition-radio-input"
              />
              <div className="definition-option-content">
                <div className="definition-candidate-number">
                  Candidate {idx + 1}
                </div>
                <div className="definition-candidate-badges">
                  <span className="definition-candidate-badge">
                    Score: {(candidate.confidence * 100).toFixed(0)}%
                  </span>
                  <span className="definition-candidate-badge">
                    {candidate.source}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <p className="definition-text">
            {candidate.definition}
          </p>

          {candidate.rationale && (
            <div className="definition-rationale">
              <strong>Rationale:</strong> {candidate.rationale}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
