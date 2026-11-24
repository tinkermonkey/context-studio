import { useEffect, useRef, type ReactNode } from "react";
import { Chip, Panel, type ChipVariant } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import type { ConflictCluster } from "../tieredModel";
import type { OperationLink } from "./ReviewPills";
import type { ListSection } from "./reviewList";

export interface ElementRow {
  title: ReactNode;
  /**
   * Under the title: the class (an element) or the predicate (a relationship).
   */
  detail?: ReactNode;
  /** The detail as text, for its tooltip when it is cut. */
  detailTitle?: string;
  /** The change itself, inline, under the title (an update's was → now, a triple). */
  change?: ReactNode;
  probability: string;
  /** data-verdict: an element's verdict, else the decision state. */
  state: string;
  label: string;
  variant: ChipVariant;
  /** Its proposer changed it since it was first proposed (#1624). */
  amended?: boolean;
  /** Beside the status: stale, near match, no passage, in use and the like. */
  flags?: ReactNode;
}

/** Bulk selection: a checkbox on each row it can take. */
export interface ListSelection {
  checked: ReadonlySet<string>;
  toggle: (operationId: string) => void;
  /** Whether the row takes a checkbox (awaiting, and not a judgment or conflict change). */
  eligible: (operation: ProposedOperation) => boolean;
}

interface ReviewElementsPaneProps {
  sections: ListSection[];
  rowOf: (operation: ProposedOperation) => ElementRow;
  selectedId?: string;
  /** Opens an operation: its href (?selected=...), a plain click selecting it. */
  link: (operationId: string) => OperationLink;
  /** The pane's title and the list's accessible name. */
  title?: string;
  listLabel?: string;
  /** The filters, in the pane's header. */
  header?: ReactNode;
  /** Above the list: Select ▾ and the bulk bar. */
  toolbar?: ReactNode;
  emptyMessage: string;
  selection?: ListSelection;
  /** A conflict card, in the change-kind view. */
  renderConflict?: (cluster: ConflictCluster) => ReactNode;
  "data-testid"?: string;
}

/**
 * The operations to review, in sections (a layer, a change kind, or the
 * sequence), each row with its status; with `selection`, a checkbox on the rows
 * bulk decisions take.
 */
export function ReviewElementsPane({
  sections,
  rowOf,
  selectedId,
  link,
  title = "Elements",
  listLabel = "Elements to review",
  header,
  toolbar,
  emptyMessage,
  selection,
  renderConflict,
  "data-testid": testId = "review-elements",
}: ReviewElementsPaneProps) {
  const listRef = useRef<HTMLDivElement>(null);

  // Keep the selected row in view as J / K, a decision or a link move the selection.
  useEffect(() => {
    if (!selectedId) return;
    const row = listRef.current?.querySelector(`[data-row-id="${CSS.escape(selectedId)}"]`);
    row?.scrollIntoView?.({ block: "nearest" });
  }, [selectedId, sections]);

  const renderRow = (operation: ProposedOperation) => {
    const row = rowOf(operation);
    const selected = operation.id === selectedId;
    const anchor = (
      <a
        key={operation.id}
        {...link(operation.id)}
        role="option"
        aria-selected={selected}
        aria-controls="review-inspector"
        className={["review-row", selected && "review-row--selected"].filter(Boolean).join(" ")}
        data-row-id={operation.id}
        data-verdict={row.state}
        data-testid={`review-row-${operation.id}`}
      >
        <div className="review-row__text">
          <span className="review-row__title">{row.title}</span>
          {row.detail !== undefined && (
            <span className="review-row__class" title={row.detailTitle}>
              {row.detail}
            </span>
          )}
          {row.change !== undefined && <div className="review-row__change">{row.change}</div>}
        </div>
        <span className="review-row__meta">
          {row.amended && (
            <span
              className="review-row__amended"
              data-testid={`review-row-amended-${operation.id}`}
            >
              amended
            </span>
          )}
          {row.flags}
          <span className="review-row__p">{row.probability}</span>
          <Chip variant={row.variant}>{row.label}</Chip>
        </span>
      </a>
    );
    if (!selection) return anchor;
    const eligible = selection.eligible(operation);
    return (
      <div key={operation.id} className="review-row-line">
        <span className="review-row__check">
          {eligible && (
            <input
              type="checkbox"
              checked={selection.checked.has(operation.id)}
              onChange={() => selection.toggle(operation.id)}
              aria-label={`Select seq ${operation.seq}`}
              data-testid={`operation-check-${operation.id}`}
            />
          )}
        </span>
        {anchor}
      </div>
    );
  };

  return (
    <Panel
      className="review-pane review-pane--elements"
      role="region"
      aria-label={title === "Elements" ? "Proposed elements" : title}
      title={title}
      noPadding
      headerAction={header}
      data-testid={testId}
    >
      {toolbar}
      <div
        ref={listRef}
        className="review-scroll"
        role="listbox"
        aria-label={listLabel}
        data-testid="review-element-list"
      >
        {sections.length === 0 && (
          <p className="review-empty" data-testid="review-elements-empty">
            {emptyMessage}
          </p>
        )}
        {sections.map((section) => {
          const count = section.items.reduce(
            (n, item) => n + (item.type === "row" ? 1 : item.shown.length),
            0,
          );
          return (
            <div
              key={section.key}
              role="group"
              aria-label={section.label}
              data-testid={`review-group-${section.key}`}
            >
              <div className="review-group" aria-hidden="true">
                {section.label} · {count}
                {section.note && <span className="review-group__note">{section.note}</span>}
              </div>
              {section.items.map((item) =>
                item.type === "row" ? (
                  renderRow(item.operation)
                ) : (
                  <div key={item.cluster.id} className="review-conflict">
                    {renderConflict?.(item.cluster)}
                  </div>
                ),
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
