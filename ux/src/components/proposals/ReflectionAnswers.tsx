import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type FocusEvent,
} from "react";
import { createPortal } from "react-dom";
import { Chip, InspectorPanel, ProgressBar } from "@tinkermonkey/heimdall-ui";
import {
  QUESTION_LABELS,
  effectiveOption,
  isPickable,
  type OptionDefinition,
  type Picks,
  type Reflection,
  type ReflectionOption,
} from "./tieredModel";
import "./proposals.css";

interface ReflectionAnswersProps {
  operationId: string;
  reflection: Reflection;
  picks: Picks;
  /** Absent once decided (or without decisions): the answers are read-only. */
  onPick?: (question: string, option: string) => void;
  /** An answer's definition, shown beside the inspector on hover and focus. */
  definitionOf?: (question: string, option: ReflectionOption) => OptionDefinition | undefined;
}

/** The overlay's width and its gap from the inspector's edge, in px. */
const OVERLAY_WIDTH = 360;
const OVERLAY_GAP = 12;

interface OpenDefinition {
  id: string;
  definition: OptionDefinition;
  /** The answer it describes: a scroll moves the overlay along with it. */
  anchor: Element;
  style: CSSProperties;
}

function inspectorOf(anchor: Element): Element {
  return anchor.closest("[data-testid='operation-inspector']") ?? anchor;
}

/** True while the answer is in view: inside the window and the inspector's visible box. */
function inView(anchor: Element): boolean {
  const option = anchor.getBoundingClientRect();
  const panel = inspectorOf(anchor).getBoundingClientRect();
  return (
    option.bottom > Math.max(0, panel.top) &&
    option.top < Math.min(window.innerHeight, panel.bottom)
  );
}

/**
 * Where the overlay goes: level with the answer, just left of the inspector,
 * or under the answer when there is no room beside it.
 */
function overlayStyle(anchor: Element): CSSProperties {
  const option = anchor.getBoundingClientRect();
  const panel = inspectorOf(anchor).getBoundingClientRect();
  if (panel.left >= OVERLAY_WIDTH + OVERLAY_GAP * 2) {
    return {
      top: option.top,
      left: panel.left - OVERLAY_WIDTH - OVERLAY_GAP,
      width: OVERLAY_WIDTH,
    };
  }
  const left = Math.min(option.left, window.innerWidth - OVERLAY_WIDTH - OVERLAY_GAP);
  return { top: option.bottom + 4, left: Math.max(OVERLAY_GAP, left), width: OVERLAY_WIDTH };
}

/** An answer's definition, beside the inspector (a portal, so the inspector's scroll can't clip it). */
function DefinitionOverlay({ open }: { open: OpenDefinition }) {
  const { definition } = open;
  const ref = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(open.style.top as number);
  // A long definition moves up so all of it stays in the window.
  useLayoutEffect(() => {
    const height = ref.current?.offsetHeight ?? 0;
    const wanted = open.style.top as number;
    setTop(Math.max(OVERLAY_GAP, Math.min(wanted, window.innerHeight - height - OVERLAY_GAP)));
  }, [open]);
  return createPortal(
    <div
      ref={ref}
      id={open.id}
      role="tooltip"
      className="definition-overlay"
      style={{ ...open.style, top }}
      data-testid="reflection-definition"
    >
      <span className="definition-overlay__term">
        {definition.term}
        {definition.reversed && <span className="definition-overlay__note"> · reversed</span>}
      </span>
      <p className="definition-overlay__text">{definition.text}</p>
    </div>,
    document.body,
  );
}

/**
 * The three sorting questions a reflection asked, each option a radio button
 * with its probability bar, marked current and plan. Picking another answer
 * than the plan's turns Accept plan into Accept with my picks.
 */
export function ReflectionAnswers({
  operationId,
  reflection,
  picks,
  onPick,
  definitionOf,
}: ReflectionAnswersProps) {
  const [open, setOpen] = useState<OpenDefinition>();
  // Escape dismisses the overlay without moving focus or the pointer. A scroll
  // (the inspector bringing a focused answer into view, say) moves it along
  // with its answer, and closes it once the answer is out of view.
  const anchor = open?.anchor;
  useEffect(() => {
    if (!anchor) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(undefined);
    const onScroll = () =>
      setOpen((current) =>
        current && inView(current.anchor)
          ? { ...current, style: overlayStyle(current.anchor) }
          : undefined,
      );
    document.addEventListener("keydown", onKey);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [anchor]);
  const show = (id: string, definition: OptionDefinition | undefined, anchor: Element) =>
    setOpen(definition ? { id, definition, anchor, style: overlayStyle(anchor) } : undefined);
  const hide = (id: string) => setOpen((current) => (current?.id === id ? undefined : current));
  return (
    <InspectorPanel.Section title="Reflection answers">
      <div className="op-inspector__stack" data-testid="reflection-answers">
        {reflection.questions.map((q) => {
          const chosen = effectiveOption(reflection, q.question, picks)?.option;
          const name = `reflection-${operationId}-${q.question}`;
          return (
            <fieldset
              key={q.question}
              className="reflection-question"
              data-testid={`reflection-question-${q.question}`}
            >
              <legend className="reflection-question__label">
                {QUESTION_LABELS[q.question] ?? q.question}
              </legend>
              <div className="reflection-question__options">
                {q.options.map((o, index) => {
                  const pickable = !!onPick && isPickable(reflection, q.question, o, picks);
                  const id = `${name}-${index}`;
                  const marked = o.current || o.plan;
                  const definition = definitionOf?.(q.question, o);
                  const overlayId = `${id}-definition`;
                  // Screen readers get the definition from hidden text, whether or not the overlay shows.
                  const describedBy =
                    [marked && `${id}-marks`, definition && `${id}-definition-text`]
                      .filter(Boolean)
                      .join(" ") || undefined;
                  const onFocus = (e: FocusEvent<HTMLElement>) =>
                    show(overlayId, definition, e.currentTarget);
                  return (
                    <label
                      key={o.option}
                      htmlFor={id}
                      className={[
                        "reflection-option",
                        chosen === o.option && "reflection-option--chosen",
                        !pickable && "reflection-option--fixed",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      data-testid={`reflection-option-${q.question}-${o.option}`}
                      data-defined={definition ? "true" : undefined}
                      onMouseEnter={(e) => show(overlayId, definition, e.currentTarget)}
                      onMouseLeave={() => hide(overlayId)}
                      onFocus={onFocus}
                      onBlur={() => hide(overlayId)}
                    >
                      <input
                        id={id}
                        type="radio"
                        name={name}
                        value={o.option}
                        checked={chosen === o.option}
                        disabled={!pickable}
                        onChange={() => onPick?.(q.question, o.option)}
                        className="reflection-option__radio"
                        aria-labelledby={`${id}-name ${id}-p`}
                        aria-describedby={describedBy}
                      />
                      <span
                        id={`${id}-name`}
                        className="reflection-option__name"
                        // A read-only answer's radio is disabled: its name takes focus instead.
                        tabIndex={definition && !pickable ? 0 : undefined}
                        aria-describedby={!pickable ? describedBy : undefined}
                      >
                        {o.option}
                      </span>
                      {definition && (
                        <span id={`${id}-definition-text`} hidden>
                          {definition.reversed
                            ? `${definition.term}, reversed: ${definition.text}`
                            : `${definition.term}: ${definition.text}`}
                        </span>
                      )}
                      <span id={`${id}-marks`} className="reflection-option__marks">
                        {o.current && <Chip variant="neutral">current</Chip>}
                        {o.plan && <Chip variant="amber">plan</Chip>}
                      </span>
                      <span className="reflection-option__bar">
                        <ProgressBar
                          percent={o.probability * 100}
                          color={o.plan ? "amber" : "neutral"}
                          height={4}
                          label={`${o.option} probability`}
                        />
                      </span>
                      <span id={`${id}-p`} className="reflection-option__p">
                        p {o.probability.toFixed(2)}
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          );
        })}
      </div>
      {open && <DefinitionOverlay open={open} />}
    </InspectorPanel.Section>
  );
}

/** The evidence pack the decision model read, block by block. */
export function EvidencePack({ blocks }: { blocks: string[] }) {
  return (
    <InspectorPanel.Section title="Evidence pack" count={blocks.length}>
      {blocks.length > 0 ? (
        <div className="op-inspector__stack" data-testid="reflection-evidence-pack">
          {blocks.map((block, index) => (
            <pre key={index} className="reflection-evidence">
              {block}
            </pre>
          ))}
        </div>
      ) : (
        <p className="entity-note">No evidence pack recorded.</p>
      )}
    </InspectorPanel.Section>
  );
}
