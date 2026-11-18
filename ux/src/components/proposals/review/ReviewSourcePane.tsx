import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { Panel } from "@tinkermonkey/heimdall-ui";
import { SourceText } from "@/components/pipeline/extraction-review/SourceText";
import type { KeyedSpan } from "@/components/pipeline/extraction-review/reviewUtils";
import { selectedPassage, type SelectedPassage } from "./addFromText";
import { VERDICTS, VERDICT_LABEL, VERDICT_LEGEND, type Verdict } from "./reviewModel";

/** Where the add form sits on screen: under the selection, or above it near the bottom. */
export interface PopoverAnchor {
  top: number;
  left: number;
}

/** The add form's width and about its height, to keep it on screen. */
const POPOVER_WIDTH = 340;
const POPOVER_HEIGHT = 320;
const MARGIN = 8;

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
  /** The source text's box: focusable, so focus can come back to it when the add form closes. */
  textRef?: RefObject<HTMLDivElement | null>;
  /** Selected text can be added as an element: called with the passage it picks out. */
  onSelectText?: (passage: SelectedPassage, anchor: PopoverAnchor) => void;
  /** Why selected text can't be added, when it can't. */
  addBlocked?: string;
  /** The add form, shown at `popoverAnchor`. */
  popover?: ReactNode;
  popoverAnchor?: PopoverAnchor;
  /** A mouse press outside the add form (and outside the source text) closes it. */
  onDismissPopover?: () => void;
  /**
   * A passage to bring into view and flash: where it starts in the text
   * (UTF-16), and a nonce so asking for the same passage again shows it again.
   */
  focus?: { start: number; nonce: number };
}

/** How long a passage shown from the inspector stays flashed, in ms. */
const FLASH_MS = 1600;

/** Keys pressed in a field or a dialog never start an add. */
function inFieldOrDialog(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLElement &&
    (target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.isContentEditable ||
      !!target.closest('[role="dialog"]'))
  );
}

/**
 * Where the add form goes, in window coordinates (it is fixed, so the panes'
 * clipping never cuts it): under the selection, or above it when there is no
 * room below, kept inside the window.
 */
function anchorFor(range: Range): PopoverAnchor {
  if (typeof range.getBoundingClientRect !== "function") return { top: MARGIN, left: MARGIN };
  const rect = range.getBoundingClientRect();
  const below = rect.bottom + 6;
  const above = rect.top - 6 - POPOVER_HEIGHT;
  const top =
    below + POPOVER_HEIGHT <= window.innerHeight - MARGIN ? below : Math.max(MARGIN, above);
  const left = Math.min(
    Math.max(MARGIN, rect.left),
    Math.max(MARGIN, window.innerWidth - POPOVER_WIDTH - MARGIN),
  );
  return { top: Math.round(top), left: Math.round(left) };
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
  textRef: givenTextRef,
  onSelectText,
  addBlocked,
  popover,
  popoverAnchor,
  onDismissPopover,
  focus,
}: ReviewSourcePaneProps) {
  const ownTextRef = useRef<HTMLDivElement>(null);
  const textRef = givenTextRef ?? ownTextRef;
  const anchorRef = useRef<HTMLDivElement>(null);
  const open = !!popover;
  const openRef = useRef(open);
  openRef.current = open;

  /** Offer the current selection for adding, if it lies inside the source text. */
  const readSelection = () => {
    const selection = window.getSelection();
    const container = textRef.current;
    if (!onSelectText || text === undefined || !container) return;
    if (!selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    const passage = selectedPassage(container, range, text);
    if (passage) onSelectText(passage, anchorFor(range));
  };
  const readSelectionRef = useRef(readSelection);
  readSelectionRef.current = readSelection;

  // A selection made from the keyboard (Shift with the arrows) ends on a key up.
  useEffect(() => {
    // Only for a selection in the source text, made outside any field, while no form is open.
    const onKeyUp = (event: KeyboardEvent) => {
      if (!(event.shiftKey || event.key === "Shift")) return;
      if (openRef.current || inFieldOrDialog(event.target)) return;
      const anchor = window.getSelection()?.anchorNode;
      if (!anchor || !textRef.current?.contains(anchor)) return;
      readSelectionRef.current();
    };
    document.addEventListener("keyup", onKeyUp);
    return () => document.removeEventListener("keyup", onKeyUp);
  }, [textRef]);

  // A press outside the open form closes it; one in the source text may start a new selection,
  // which its mouse up opens the form for.
  const dismissRef = useRef(onDismissPopover);
  dismissRef.current = onDismissPopover;
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      // The path as dispatched: a press that removes its own target (picking from the
      // class list) still counts as inside.
      const path = event.composedPath();
      const inside = [anchorRef.current, textRef.current].some((el) => !!el && path.includes(el));
      if (!inside) dismissRef.current?.();
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open, textRef]);

  // A passage asked for from the inspector: scroll the text to it and flash it.
  useEffect(() => {
    const box = textRef.current?.querySelector<HTMLElement>(".review-source__text");
    if (!focus || !box) return;
    const mark = box.querySelector<HTMLElement>(`mark[data-start="${focus.start}"]`);
    if (!mark) return;
    box.scrollTo?.({ top: Math.max(0, mark.offsetTop - box.clientHeight / 3), behavior: "smooth" });
    mark.classList.add("review-mark--flash");
    const timer = window.setTimeout(() => mark.classList.remove("review-mark--flash"), FLASH_MS);
    return () => {
      window.clearTimeout(timer);
      mark.classList.remove("review-mark--flash");
    };
  }, [focus, textRef]);

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
          <div className="review-source__frame">
            <div
              ref={textRef}
              className="review-source__selectable"
              // Focus comes back here when the add form closes.
              tabIndex={-1}
              onMouseUp={readSelection}
              data-testid="review-source-selectable"
            >
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
            </div>
            {popover && (
              <div
                ref={anchorRef}
                className="review-add__anchor"
                // At the selection on screen: worked out at run time.
                style={popoverAnchor}
              >
                {popover}
              </div>
            )}
          </div>
          <p className="review-source__hint" data-testid="review-source-hint">
            {onSelectText
              ? "Select any text to add an element the pipeline missed. Click a highlight to open it."
              : "Click a highlight to open it."}
          </p>
          {addBlocked && (
            <p className="review-source__hint" data-testid="review-add-unavailable">
              No element can be added here: {addBlocked}
            </p>
          )}
        </>
      ) : (
        <p className="review-muted" data-testid="review-source-unavailable">
          {unavailable ?? "Loading the source…"}
        </p>
      )}
    </Panel>
  );
}
