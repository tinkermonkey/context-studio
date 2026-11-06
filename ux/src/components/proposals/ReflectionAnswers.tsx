import { Chip, InspectorPanel, ProgressBar } from "@tinkermonkey/heimdall-ui";
import {
  QUESTION_LABELS,
  effectiveOption,
  isPickable,
  type Picks,
  type Reflection,
} from "./tieredModel";
import "./proposals.css";

interface ReflectionAnswersProps {
  operationId: string;
  reflection: Reflection;
  picks: Picks;
  /** Absent once decided (or without decisions): the answers are read-only. */
  onPick?: (question: string, option: string) => void;
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
}: ReflectionAnswersProps) {
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
              <div role="radiogroup" aria-label={QUESTION_LABELS[q.question] ?? q.question}>
                {q.options.map((o) => {
                  const pickable = !!onPick && isPickable(q.question, o);
                  const id = `${name}-${o.option}`;
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
                        aria-label={`${o.option}, p ${o.probability.toFixed(2)}`}
                      />
                      <span className="reflection-option__name">{o.option}</span>
                      <span className="reflection-option__marks">
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
                      <span className="reflection-option__p">{o.probability.toFixed(2)}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          );
        })}
      </div>
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
