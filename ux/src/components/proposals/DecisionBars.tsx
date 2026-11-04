import { Button } from "@tinkermonkey/heimdall-ui";
import "./proposals.css";

interface ThresholdBarProps {
  threshold: number;
  onThresholdChange: (threshold: number) => void;
  /** Awaiting operations at or above the threshold, neither stale nor blocked. */
  matching: number;
  awaiting: number;
  onSelect: () => void;
}

/**
 * The probability threshold, worked out in the browser: "Select N" checks the
 * awaiting operations at or above it. It only selects; nothing applies until
 * the reviewer accepts.
 */
export function ThresholdBar({
  threshold,
  onThresholdChange,
  matching,
  awaiting,
  onSelect,
}: ThresholdBarProps) {
  return (
    <div className="proposal-bar" data-testid="proposal-threshold-bar">
      <label htmlFor="proposal-threshold" className="proposal-bar__label">
        Probability threshold
      </label>
      <input
        id="proposal-threshold"
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={threshold}
        onChange={(e) => onThresholdChange(Number(e.target.value))}
        className="proposal-bar__slider"
        aria-valuetext={threshold.toFixed(2)}
        data-testid="proposal-threshold-slider"
      />
      <span className="proposal-bar__value" data-testid="proposal-threshold-value">
        {threshold.toFixed(2)}
      </span>
      <span className="proposal-bar__text" data-testid="proposal-threshold-count">
        {matching} of {awaiting} awaiting at or above
      </span>
      <Button
        variant="secondary"
        size="sm"
        disabled={matching === 0}
        onClick={onSelect}
        data-testid="proposal-threshold-select"
      >
        Select {matching}
      </Button>
      <span className="proposal-bar__note">
        Stale operations and blocked deletes are never selected by the threshold.
      </span>
    </div>
  );
}

interface SelectionBarProps {
  selected: number;
  /** Selected operations that are stale: Accept selected leaves them for Apply anyway. */
  stale: number;
  /**
   * Selected deletes of relationship types still in use: Accept selected skips
   * them; each needs a resolution in the inspector.
   */
  blocked?: number;
  busy?: boolean;
  onClear: () => void;
  onReject: () => void;
  onAccept: () => void;
}

/** Shown while operations are checked: accept or reject them together. */
export function SelectionBar({
  selected,
  stale,
  blocked = 0,
  busy,
  onClear,
  onReject,
  onAccept,
}: SelectionBarProps) {
  const acceptable = selected - stale - blocked;
  const notes = [
    stale > 0 &&
      `${stale} stale: Accept selected leaves ${stale === 1 ? "it" : "them"} for Apply anyway in the inspector.`,
    blocked > 0 &&
      `${blocked} blocked (in use): Accept selected skips ${blocked === 1 ? "it" : "them"}; resolve ${blocked === 1 ? "it" : "each"} in the inspector.`,
  ].filter(Boolean);
  return (
    <div className="proposal-bar proposal-bar--selection" data-testid="proposal-selection-bar">
      <span className="proposal-bar__count" data-testid="proposal-selection-count">
        {selected} selected
      </span>
      <span className="proposal-bar__text" data-testid="proposal-selection-note">
        {notes.length > 0
          ? notes.join(" ")
          : "Applied in seq order under this proposal's run; revert undoes them together."}
      </span>
      <span className="proposal-bar__actions">
        <Button variant="ghost" size="sm" onClick={onClear} data-testid="proposal-selection-clear">
          Clear
        </Button>
        <Button
          variant="danger"
          size="sm"
          disabled={busy}
          onClick={onReject}
          data-testid="proposal-selection-reject"
        >
          Reject selected
        </Button>
        <Button
          variant="primary"
          size="sm"
          disabled={busy || acceptable === 0}
          onClick={onAccept}
          data-testid="proposal-selection-accept"
        >
          Accept selected
        </Button>
      </span>
    </div>
  );
}
