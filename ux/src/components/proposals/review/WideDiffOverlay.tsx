import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button, SideBySideDiff } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { changeRows, fieldLabel } from "../proposalModel";
import { textDiffLines } from "../textDiff";
import { WIDE_CHAR_PX, WIDE_MIN_WIDTH, stepField } from "./wideDiff";

/** Keys typed into a field are text, not overlay commands. */
function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

interface WideDiffOverlayProps {
  operation: ProposedOperation;
  /** Its title, as the inspector shows it. */
  title: string;
  /** The changed field shown now. */
  field: string;
  /** Its long changes, in row order: the tabs. */
  fields: string[];
  onField: (field: string) => void;
  /** J / K: the next or previous operation with a long change. */
  onStep: (by: 1 | -1) => void;
  onClose: () => void;
}

/**
 * A long text change read wide (#1661): over the panes left of the inspector,
 * which stays beside it to decide. The changed fields are tabs (↑ ↓ or ‹ ›
 * step between them), J / K move to the next operation with a long change, and
 * Esc or ✕ close it. The diff is Heimdall's SideBySideDiff, sentence by
 * sentence (each removed sentence before the one replacing it), wrapped to the
 * overlay's width, with long unchanged runs folded.
 */
export function WideDiffOverlay({
  operation,
  title,
  field,
  fields,
  onField,
  onStep,
  onClose,
}: WideDiffOverlayProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef(new Map<string, HTMLButtonElement>());
  const [width, setWidth] = useState(100);
  const row = changeRows(operation).find((r) => r.field === field);
  const lines = textDiffLines(
    typeof row?.before === "string" ? row.before : "",
    typeof row?.after === "string" ? row.after : "",
    width,
  );

  // Rows wrap to the overlay's width, measured when it lays out and on resize.
  useLayoutEffect(() => {
    const measure = () => {
      const px = rootRef.current?.clientWidth ?? 0;
      // The panel's padding and the diff's gutter and line padding take about 150px.
      if (px > 0) setWidth(Math.max(WIDE_MIN_WIDTH, Math.floor((px - 150) / WIDE_CHAR_PX)));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  // The selected tab takes focus as the overlay opens and as the field changes.
  useEffect(() => {
    tabRefs.current.get(field)?.focus({ preventScroll: true });
  }, [field]);

  // Keys while it is open: arrows step fields, J / K operations, Esc closes. Only while
  // focus is in the overlay or on nothing: the inspector's arrow keys and a hover
  // overlay's Esc stay theirs.
  const onKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onKey.current = (event) => {
    if (event.defaultPrevented || typing(event.target)) return;
    const target = event.target;
    const ours =
      !(target instanceof Node) ||
      target === document.body ||
      target === document.documentElement ||
      !!rootRef.current?.contains(target);
    if (!ours) return;
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key;
    if (key === "Escape") {
      event.preventDefault();
      onClose();
    } else if (key === "ArrowDown" || key === "ArrowRight") {
      event.preventDefault();
      onField(stepField(fields, field, 1));
    } else if (key === "ArrowUp" || key === "ArrowLeft") {
      event.preventDefault();
      onField(stepField(fields, field, -1));
    } else if (key.toLowerCase() === "j" || key.toLowerCase() === "k") {
      event.preventDefault();
      onStep(key.toLowerCase() === "j" ? 1 : -1);
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  const label = fieldLabel(field);
  return (
    <div
      ref={rootRef}
      className="wide-diff"
      role="dialog"
      aria-modal="false"
      aria-label={`${label} of ${title}, side by side`}
      data-testid="review-wide-diff"
    >
      <div className="wide-diff__panel">
        <div className="wide-diff__head">
          <div className="wide-diff__title">
            <span className="review-eyebrow">
              {`WIDE DIFF · ${operation.op} · ${operation.kind} · seq ${operation.seq}`}
            </span>
            <span className="wide-diff__name">{title}</span>
          </div>
          <span className="wide-diff__keys review-keys">↑ ↓ field · J / K next · Esc</span>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Close the wide diff"
            onClick={onClose}
            data-testid="review-wide-close"
          >
            ✕
          </Button>
        </div>
        <div className="wide-diff__tabs">
          <Button
            variant="ghost"
            size="sm"
            aria-label="Previous field"
            disabled={fields.length < 2}
            onClick={() => onField(stepField(fields, field, -1))}
            data-testid="review-wide-prev"
          >
            ‹
          </Button>
          <div role="tablist" aria-label="Changed fields" className="wide-diff__tablist">
            {fields.map((name) => (
              <button
                key={name}
                ref={(el) => {
                  if (el) tabRefs.current.set(name, el);
                  else tabRefs.current.delete(name);
                }}
                type="button"
                role="tab"
                id={`review-wide-tab-${name}`}
                aria-selected={name === field}
                aria-controls="review-wide-panel"
                tabIndex={name === field ? 0 : -1}
                className={["wide-diff__tab", name === field && "wide-diff__tab--selected"]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onField(name)}
                data-testid={`review-wide-tab-${name}`}
              >
                {fieldLabel(name)}
              </button>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Next field"
            disabled={fields.length < 2}
            onClick={() => onField(stepField(fields, field, 1))}
            data-testid="review-wide-next"
          >
            ›
          </Button>
        </div>
        <div
          id="review-wide-panel"
          role="tabpanel"
          aria-labelledby={`review-wide-tab-${field}`}
          className="wide-diff__body"
        >
          <SideBySideDiff
            lines={lines}
            aria-label={`${label}: what changed`}
            data-testid="review-wide-lines"
          />
        </div>
      </div>
    </div>
  );
}
