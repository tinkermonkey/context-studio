import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { nearMatchHeldNote } from "../sourceModel";

export type BulkPick = "ready" | "threshold" | "awaiting" | "none";

interface BulkSelectProps {
  /** Awaiting, eligible, neither stale nor blocked nor held back. */
  ready: number;
  /** Awaiting and eligible, whatever their state: the bulk bar says what it leaves. */
  awaiting: number;
  /** Ready ones at or above the threshold; undefined when no operation has a probability. */
  atThreshold?: number;
  threshold: number;
  onThreshold: (threshold: number) => void;
  onPick: (pick: BulkPick) => void;
  disabled?: boolean;
  /** What All ready leaves out among the rows shown, and why; undefined when nothing. */
  leftOut?: string;
}

/**
 * Select ▾: checks all ready, those at or above a probability threshold, or
 * all awaiting, among the rows the filters show. It only checks; the bulk bar
 * decides.
 */
export function BulkSelect({
  ready,
  awaiting,
  atThreshold,
  threshold,
  onThreshold,
  onPick,
  disabled,
  leftOut,
}: BulkSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const sliderId = useId();

  // Closes on a click outside it, or Esc (focus back on the button).
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      rootRef.current?.querySelector<HTMLElement>("[data-testid=review-bulk-select]")?.focus();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pick = (choice: BulkPick) => {
    onPick(choice);
    setOpen(false);
  };

  return (
    <div className="review-bulk-select" ref={rootRef}>
      <Button
        variant="secondary"
        size="sm"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((o) => !o)}
        data-testid="review-bulk-select"
      >
        Select ▾
      </Button>
      {open && (
        <div
          id={menuId}
          className="review-bulk-menu"
          role="menu"
          aria-label="Select operations"
          data-testid="review-bulk-select-menu"
        >
          <button
            type="button"
            role="menuitem"
            className="review-bulk-menu__item"
            disabled={ready === 0}
            onClick={() => pick("ready")}
            data-testid="review-bulk-select-ready"
          >
            All ready · {ready}
          </button>
          {atThreshold !== undefined && (
            <div className="review-bulk-menu__threshold">
              <button
                type="button"
                role="menuitem"
                className="review-bulk-menu__item"
                disabled={atThreshold === 0}
                onClick={() => pick("threshold")}
                data-testid="review-bulk-select-threshold"
              >
                At or above p {threshold.toFixed(2)} · {atThreshold}
              </button>
              <label htmlFor={sliderId} className="review-bulk-menu__label">
                Threshold
              </label>
              <input
                id={sliderId}
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={threshold}
                onChange={(e) => onThreshold(Number(e.target.value))}
                className="proposal-bar__slider"
                aria-valuetext={threshold.toFixed(2)}
                data-testid="proposal-threshold-slider"
              />
              <span className="proposal-bar__value" data-testid="proposal-threshold-value">
                {threshold.toFixed(2)}
              </span>
            </div>
          )}
          <button
            type="button"
            role="menuitem"
            className="review-bulk-menu__item"
            disabled={awaiting === 0}
            onClick={() => pick("awaiting")}
            data-testid="review-bulk-select-awaiting"
          >
            All awaiting · {awaiting}
          </button>
          <button
            type="button"
            role="menuitem"
            className="review-bulk-menu__item"
            onClick={() => pick("none")}
            data-testid="review-bulk-select-none"
          >
            None
          </button>
          {leftOut && (
            <p className="review-bulk-menu__note" data-testid="review-bulk-select-note">
              {leftOut}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

interface BulkBarProps {
  selected: number;
  /** Selected operations that are stale: Accept selected leaves them for Apply anyway. */
  stale: number;
  /**
   * Selected deletes of relationship types still in use: Accept selected skips
   * them; each needs a resolution in the inspector.
   */
  blocked?: number;
  /** Selected near matches and what names them: Accept selected leaves them for a choice. */
  nearMatches?: ProposedOperation[];
  /** Selected operations without a passage and what names them: Accept selected holds them back. */
  noPassage?: ProposedOperation[];
  busy?: boolean;
  /** An apply is running: Accept selected says so (aria-busy). */
  applying?: boolean;
  onClear: () => void;
  onReject: () => void;
  onAccept: () => void;
}

/** Shown while operations are checked: accept or reject them together. */
export function BulkBar({
  selected,
  stale,
  blocked = 0,
  nearMatches = [],
  noPassage = [],
  busy,
  applying,
  onClear,
  onReject,
  onAccept,
}: BulkBarProps) {
  const acceptable = selected - stale - blocked - nearMatches.length - noPassage.length;
  const unplaced = noPassage.length;
  const notes = [
    stale > 0 &&
      `${stale} stale: Accept selected leaves ${stale === 1 ? "it" : "them"} for Apply anyway in the inspector.`,
    blocked > 0 &&
      `${blocked} blocked (in use): Accept selected skips ${blocked === 1 ? "it" : "them"}; resolve ${blocked === 1 ? "it" : "each"} in the inspector.`,
    nearMatchHeldNote(nearMatches),
    unplaced > 0 &&
      `${unplaced} without a passage: Accept selected holds ${unplaced === 1 ? "it" : "them"} back; accept ${unplaced === 1 ? "it" : "each"} on its own.`,
  ].filter(Boolean);
  return (
    <div
      className="proposal-bar proposal-bar--selection review-bulk-bar"
      role="region"
      aria-label="Selected operations"
      data-testid="proposal-selection-bar"
    >
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
          aria-busy={applying ? true : undefined}
          onClick={onAccept}
          data-testid="proposal-selection-accept"
        >
          Accept selected
        </Button>
      </span>
    </div>
  );
}
