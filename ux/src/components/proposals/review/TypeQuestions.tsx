import { type FocusEvent } from "react";
import { Chip, ProgressBar } from "@tinkermonkey/heimdall-ui";
import { useHoverOverlay } from "../HoverOverlay";
import {
  QUESTION_LABELS,
  effectiveOption,
  isPickable,
  type OptionDefinition,
  type Picks,
  type Reflection,
  type ReflectionOption,
} from "../tieredModel";
import "../proposals.css";

interface TypeQuestionsProps {
  operationId: string;
  reflection: Reflection;
  picks: Picks;
  /** Absent once decided (or without decisions): the answers are read-only. */
  onPick?: (question: string, option: string) => void;
  /** An answer's definition, shown beside the inspector on hover and focus. */
  definitionOf?: (question: string, option: ReflectionOption) => OptionDefinition | undefined;
}

/** An answer's definition, as the hover overlay shows it. */
function DefinitionContent({ definition }: { definition: OptionDefinition }) {
  return (
    <>
      <span className="definition-overlay__term">
        {definition.term}
        {definition.reversed && <span className="definition-overlay__note"> · reversed</span>}
      </span>
      <p className="definition-overlay__text">{definition.text}</p>
    </>
  );
}

/**
 * THE QUESTIONS IT ASKED (#1662): the three sorting questions a reflection
 * asked, each option a quick pick with its probability bar, marked current and
 * plan. Picking another answer than the plan's turns Accept plan into Accept
 * with my picks. An answer's definition shows beside the inspector on hover and
 * focus.
 */
export function TypeQuestions({
  operationId,
  reflection,
  picks,
  onPick,
  definitionOf,
}: TypeQuestionsProps) {
  // Beside the inspector; Escape dismisses it, a scroll moves it along with its answer.
  const overlay = useHoverOverlay("#review-inspector");
  const show = (id: string, definition: OptionDefinition | undefined, anchor: Element) =>
    definition
      ? overlay.show(
          id,
          <DefinitionContent definition={definition} />,
          anchor,
          "reflection-definition",
        )
      : overlay.hide(id);
  const hide = overlay.hide;
  return (
    <section className="review-block" aria-label="The questions it asked">
      <span className="review-eyebrow">THE QUESTIONS IT ASKED</span>
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
      {overlay.overlay}
    </section>
  );
}

/** The evidence pack the decision model read, block by block. */
export function EvidencePack({ blocks }: { blocks: string[] }) {
  return (
    <section className="review-block" aria-label="Evidence pack">
      <span className="review-eyebrow">{`EVIDENCE PACK · ${blocks.length}`}</span>
      {blocks.length > 0 ? (
        <div className="op-inspector__stack" data-testid="reflection-evidence-pack">
          {blocks.map((block, index) => (
            <pre key={index} className="reflection-evidence">
              {block}
            </pre>
          ))}
        </div>
      ) : (
        <p className="review-muted">No evidence pack recorded.</p>
      )}
    </section>
  );
}
