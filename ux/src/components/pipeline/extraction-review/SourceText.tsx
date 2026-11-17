import { useEffect, useRef, type KeyboardEvent } from "react";
import { segmentText, type KeyedSpan } from "./reviewUtils";
import "./ExtractionReview.css";

export interface SourceTextProps {
  text: string;
  spans: KeyedSpan[];
  activeKey?: string | null;
  onSelectKey: (key: string) => void;
  "data-testid"?: string;
  /** The container's class; defaults to the extraction review's. */
  className?: string;
  /** A highlight's classes, from the keys it covers; defaults to the extraction review's. */
  markClassName?: (keys: string[], active: boolean) => string;
  /** A highlight's accessible name; defaults to naming how many items an overlap links to. */
  markLabel?: (keys: string[], chunk: string) => string | undefined;
  /** Each highlight's data-testid. */
  markTestId?: string;
}

function defaultMarkClassName(keys: string[], active: boolean): string {
  return ["xr-span", active ? "xr-span--active" : "", keys.length > 1 ? "xr-span--overlap" : ""]
    .filter(Boolean)
    .join(" ");
}

function defaultMarkLabel(keys: string[], chunk: string): string | undefined {
  return keys.length > 1 ? `${chunk} (linked to ${keys.length} items)` : undefined;
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
  className = "xr-source-text",
  markClassName = defaultMarkClassName,
  markLabel = defaultMarkLabel,
  markTestId = "extraction-review-span",
}: SourceTextProps) {
  const segments = segmentText(text, spans);
  const containerRef = useRef<HTMLParagraphElement>(null);

  // Bring the active item's first highlight into view inside the scrolling box.
  useEffect(() => {
    const box = containerRef.current;
    if (!box || !activeKey) return;
    const mark = box.querySelector<HTMLElement>('mark[aria-current="true"]');
    if (!mark) return;
    const top = mark.offsetTop;
    if (top < box.scrollTop || top + mark.offsetHeight > box.scrollTop + box.clientHeight) {
      box.scrollTo?.({ top: Math.max(0, top - box.clientHeight / 3), behavior: "smooth" });
    }
  }, [activeKey, text]);

  return (
    <p className={className} data-testid={testId} ref={containerRef}>
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
        return (
          <mark
            key={start}
            className={markClassName(keys, active)}
            data-testid={markTestId}
            data-span-keys={keys.join(" ")}
            aria-current={active ? "true" : undefined}
            aria-label={markLabel(keys, chunk)}
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
