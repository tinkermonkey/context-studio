import { useEffect, useRef } from "react";
import { Chip, Panel, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  VERDICT_CHIP,
  VERDICT_LABEL,
  type ElementFilter,
  type ElementGroup,
  type Verdict,
} from "./reviewModel";

export interface ElementRow {
  title: string;
  /** The class (an element) or predicate (a relationship) under the title. */
  detail: string;
  probability: string;
  verdict: Verdict;
}

interface ReviewElementsPaneProps {
  groups: ElementGroup[];
  filter: ElementFilter;
  onFilter: (filter: ElementFilter) => void;
  awaiting: number;
  total: number;
  rowOf: (operation: ProposedOperation) => ElementRow;
  selectedId?: string;
  onSelect: (operationId: string) => void;
}

/** The proposed elements grouped by layer, then the relationships, each with its status. */
export function ReviewElementsPane({
  groups,
  filter,
  onFilter,
  awaiting,
  total,
  rowOf,
  selectedId,
  onSelect,
}: ReviewElementsPaneProps) {
  const listRef = useRef<HTMLDivElement>(null);

  // Keep the selected row in view as J / K or a decision move the selection.
  useEffect(() => {
    if (!selectedId) return;
    const row = listRef.current?.querySelector(`[data-row-id="${CSS.escape(selectedId)}"]`);
    row?.scrollIntoView?.({ block: "nearest" });
  }, [selectedId]);

  return (
    <Panel
      className="review-pane review-pane--elements"
      role="region"
      aria-label="Proposed elements"
      title="Elements"
      noPadding
      headerAction={
        <div data-testid="review-filter">
          <SegmentedControl
            value={filter}
            onChange={(value) => onFilter(value as ElementFilter)}
            aria-label="Show elements"
            options={[
              { value: "awaiting", label: `Awaiting · ${awaiting}` },
              { value: "all", label: `All · ${total}` },
            ]}
          />
        </div>
      }
      data-testid="review-elements"
    >
      <div
        ref={listRef}
        className="review-scroll"
        role="listbox"
        aria-label="Elements to review"
        data-testid="review-element-list"
      >
        {groups.length === 0 && (
          <p className="review-empty" data-testid="review-elements-empty">
            {filter === "awaiting" ? "Nothing awaits a decision." : "Nothing to review."}
          </p>
        )}
        {groups.map((group) => (
          <div
            key={group.key}
            role="group"
            aria-label={group.label}
            data-testid={`review-group-${group.key}`}
          >
            <div className="review-group" aria-hidden="true">
              {group.label} · {group.operations.length}
            </div>
            {group.operations.map((operation) => {
              const row = rowOf(operation);
              const selected = operation.id === selectedId;
              return (
                <button
                  key={operation.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  aria-controls="review-inspector"
                  className={["review-row", selected && "review-row--selected"]
                    .filter(Boolean)
                    .join(" ")}
                  data-row-id={operation.id}
                  data-verdict={row.verdict}
                  onClick={() => onSelect(operation.id)}
                  data-testid={`review-row-${operation.id}`}
                >
                  <span className="review-row__text">
                    <span className="review-row__title">{row.title}</span>
                    <span className="review-row__class" title={row.detail}>
                      {row.detail}
                    </span>
                  </span>
                  <span className="review-row__meta">
                    <span className="review-row__p">{row.probability}</span>
                    <Chip variant={VERDICT_CHIP[row.verdict]}>{VERDICT_LABEL[row.verdict]}</Chip>
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </Panel>
  );
}
