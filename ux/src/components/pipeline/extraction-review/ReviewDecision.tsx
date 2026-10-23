import type { MouseEvent } from "react";
import { Button, Icon } from "@tinkermonkey/heimdall-ui";
import type { ReviewDecisionValue } from "@/api/hooks/pipeline/useApplyReviewedRun";
import "./ExtractionReview.css";

export interface ReviewDecisionProps {
  value: ReviewDecisionValue;
  onChange: (value: ReviewDecisionValue) => void;
  /** Label for the "yes" choice (Accept / Merge). */
  yes?: string;
  /** Label for the "no" choice (Reject / Keep separate). */
  no?: string;
  /** Icon-only square buttons for dense tables. */
  compact?: boolean;
  "data-testid"?: string;
}

/**
 * Accept / reject (or merge / keep-separate) toggle pair. Clicking the active
 * choice again returns the item to "pending". Clicks do not bubble, so the
 * pair can sit inside a clickable table row.
 */
export function ReviewDecision({
  value,
  onChange,
  yes = "Accept",
  no = "Reject",
  compact = false,
  "data-testid": testId,
}: ReviewDecisionProps) {
  const pick = (v: "yes" | "no") => (e: MouseEvent) => {
    e.stopPropagation();
    onChange(value === v ? "pending" : v);
  };
  return (
    <div className="xr-decision" role="group" aria-label="Review decision" data-testid={testId}>
      <Button
        size="sm"
        icon={compact}
        variant={value === "yes" ? "primary" : "ghost"}
        aria-pressed={value === "yes"}
        aria-label={yes}
        title={yes}
        onClick={pick("yes")}
        data-testid={testId ? `${testId}-yes` : undefined}
      >
        <Icon name="check" size={12} /> {compact ? null : yes}
      </Button>
      <Button
        size="sm"
        icon={compact}
        variant={value === "no" ? "danger" : "ghost"}
        aria-pressed={value === "no"}
        aria-label={no}
        title={no}
        onClick={pick("no")}
        data-testid={testId ? `${testId}-no` : undefined}
      >
        <Icon name="x" size={12} /> {compact ? null : no}
      </Button>
    </div>
  );
}
