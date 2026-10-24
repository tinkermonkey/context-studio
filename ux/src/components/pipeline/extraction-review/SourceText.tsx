import type { KeyboardEvent } from "react";
import { segmentText, type KeyedSpan } from "./reviewUtils";
import "./ExtractionReview.css";

export interface SourceTextProps {
  text: string;
  spans: KeyedSpan[];
  activeKey?: string | null;
  onSelectKey: (key: string) => void;
  "data-testid"?: string;
}

/**
 * Renders the source paragraph with every located provenance span highlighted.
 * Each highlight is linked to the item(s) whose provenance covers it: clicking
 * selects that item. Overlapping spans render as one segment per boundary with
 * the overlap class; clicking an overlapped segment cycles through its items.
 */
export function SourceText({
  text,
  spans,
  activeKey,
  onSelectKey,
  "data-testid": testId,
}: SourceTextProps) {
  const segments = segmentText(text, spans);

  return (
    <p className="xr-source-text" data-testid={testId}>
      {segments.map(({ start, end, covering }) => {
        const chunk = text.slice(start, end);
        if (covering.length === 0) return <span key={start}>{chunk}</span>;
        const keys = Array.from(new Set(covering.map((s) => s.key)));
        const activeIndex = activeKey ? keys.indexOf(activeKey) : -1;
        const active = activeIndex >= 0;
        // Re-clicking an active segment moves to the next covering item (overlaps).
        const select = () => onSelectKey(keys[(activeIndex + 1) % keys.length]);
        const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            select();
          }
        };
        const className = [
          "xr-span",
          active ? "xr-span--active" : "",
          keys.length > 1 ? "xr-span--overlap" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <mark
            key={start}
            className={className}
            data-testid="extraction-review-span"
            data-span-keys={keys.join(" ")}
            aria-current={active ? "true" : undefined}
            aria-label={keys.length > 1 ? `${chunk} (linked to ${keys.length} items)` : undefined}
            role="button"
            tabIndex={0}
            onClick={select}
            onKeyDown={onKeyDown}
          >
            {chunk}
          </mark>
        );
      })}
    </p>
  );
}
