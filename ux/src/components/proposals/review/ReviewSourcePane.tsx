import { Panel } from "@tinkermonkey/heimdall-ui";
import { SourceText } from "@/components/pipeline/extraction-review/SourceText";
import type { KeyedSpan } from "@/components/pipeline/extraction-review/reviewUtils";
import { VERDICTS, VERDICT_LABEL, VERDICT_LEGEND, type Verdict } from "./reviewModel";

interface ReviewSourcePaneProps {
  title?: string;
  /** The whole source text; undefined while it loads or when it can't be read. */
  text?: string;
  /** Why there is no text to show, once that is known. */
  unavailable?: string;
  spans: KeyedSpan[];
  verdictOf: (operationId: string) => Verdict;
  titleOf: (operationId: string) => string;
  selectedId?: string;
  onSelect: (operationId: string) => void;
}

/** The source's whole text, each element's passages highlighted with its verdict. */
export function ReviewSourcePane({
  title,
  text,
  unavailable,
  spans,
  verdictOf,
  titleOf,
  selectedId,
  onSelect,
}: ReviewSourcePaneProps) {
  // The selected element's verdict colours an overlap it is part of; else the first one's.
  const shownKey = (keys: string[]) =>
    selectedId && keys.includes(selectedId) ? selectedId : keys[0];
  const markClassName = (keys: string[], active: boolean) =>
    [
      "review-mark",
      `review-mark--${verdictOf(shownKey(keys))}`,
      active ? "review-mark--selected" : "",
    ]
      .filter(Boolean)
      .join(" ");
  // The passage's own text first, then which element it is and its verdict.
  const markLabel = (keys: string[], chunk: string) => {
    const key = shownKey(keys);
    const more = keys.length > 1 ? `, and ${keys.length - 1} more` : "";
    return `${chunk} (${titleOf(key)}, ${VERDICT_LABEL[verdictOf(key)]}${more})`;
  };

  return (
    <Panel
      className="review-pane review-pane--source"
      role="region"
      aria-label="Source text"
      title="Source"
      headerAction={
        <div className="review-legend" data-testid="review-legend">
          {VERDICTS.map((verdict) => (
            <span key={verdict} className="review-legend__item">
              <span
                aria-hidden="true"
                className={`review-legend__swatch review-legend__swatch--${verdict}`}
              />
              {VERDICT_LEGEND[verdict]}
            </span>
          ))}
        </div>
      }
      data-testid="review-source"
    >
      {title && <h2 className="review-source__title">{title}</h2>}
      {text !== undefined ? (
        <>
          <SourceText
            text={text}
            spans={spans}
            activeKey={selectedId}
            onSelectKey={onSelect}
            className="review-source__text"
            markClassName={markClassName}
            markLabel={markLabel}
            markTestId="review-mark"
            data-testid="review-source-text"
          />
          <p className="review-source__hint">Click a highlight to open its element.</p>
        </>
      ) : (
        <p className="review-muted" data-testid="review-source-unavailable">
          {unavailable ?? "Loading the source…"}
        </p>
      )}
    </Panel>
  );
}
