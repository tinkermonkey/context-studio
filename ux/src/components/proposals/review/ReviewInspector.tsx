import { useState, type RefObject } from "react";
import { Button, Chip, FormCallout, Panel, TextArea } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation, RejectionReason } from "@/api/services/proposals";
import type { components } from "@/api/types";
import { formatProbability } from "../proposalModel";
import { NearMatchChoice } from "../SourcePassage";
import {
  CREATE_NEW,
  isNearMatch,
  sourcePassagesOf,
  type NearMatchChoice as Choice,
} from "../sourceModel";
import { ReviewClassPicker } from "./ReviewClassPicker";
import {
  REJECTION_REASONS,
  VERDICT_CHIP,
  VERDICT_LABEL,
  endsToDecide,
  isElement,
  proposedClassId,
  reasonLabel,
  relationshipsOf,
  seqList,
  shownClassId,
  verdictOf,
} from "./reviewModel";

type ClassResponse = components["schemas"]["ClassResponse"];

/** A definition longer than this is clamped to a few lines, with Show more. */
export const LONG_DEFINITION = 240;

/** What the inspector needs to name things: titles, classes, predicates. */
export interface ReviewNames {
  /** An element's title, or a relationship's "from predicate to". */
  titleOf: (operation: ProposedOperation) => string;
  classOf: (classId: string | undefined) => ClassResponse | undefined;
  /** A class as the reviewer reads it (see classLabel), else its id. */
  classLabel: (classId: string | undefined) => string;
  /** A relationship's ends and predicate. */
  relationshipParts: (operation: ProposedOperation) => {
    from: string;
    predicate: string;
    to: string;
  };
}

interface ReviewInspectorProps {
  operation: ProposedOperation;
  operations: ProposedOperation[];
  names: ReviewNames;
  /** The proposal's taxonomy and dataset, for a near match's question. */
  taxonomyId: string;
  datasetId?: string | null;
  /** A near match's choice: an existing individual's id, or CREATE_NEW. */
  nearChoice: Choice;
  onNearChoice: (choice: Choice) => void;
  /** The taxonomy's classes that are not derived, for the picker. */
  pickable: ClassResponse[];
  /** Classes picked earlier in this review, offered on keys 1-3. */
  suggestions: ClassResponse[];
  /** The proposal takes decisions (it isn't reverted). */
  deciding: boolean;
  busy: boolean;
  /** The reason buttons, for X to focus. */
  reasonsRef: RefObject<HTMLDivElement | null>;
  onCorrect: () => void;
  onPickClass: (classId: string) => void;
  onReject: (reasonCode: RejectionReason, note: string) => void;
  onSelect: (operationId: string) => void;
}

function Eyebrow({ children }: { children: string }) {
  return <span className="review-eyebrow">{children}</span>;
}

/** A class on one line, cut with an ellipsis; the whole of it in the tooltip. */
export function ClassChip({
  label,
  "data-testid": testId,
}: {
  label: string;
  "data-testid"?: string;
}) {
  return (
    <Chip form="id-tag" className="review-class-chip" title={label} data-testid={testId}>
      <span className="review-ellipsis">{label}</span>
    </Chip>
  );
}

/** What a class means, clamped to a few lines when long, with Show more / Show less. */
function Definition({ text }: { text?: string | null }) {
  const [open, setOpen] = useState(false);
  if (!text) return <p className="review-definition">No definition yet.</p>;
  const long = text.length > LONG_DEFINITION;
  return (
    <>
      <p
        id="review-definition-text"
        className={["review-definition", long && !open && "review-definition--clamped"]
          .filter(Boolean)
          .join(" ")}
      >
        {text}
      </p>
      {long && (
        <button
          type="button"
          className="review-link"
          aria-expanded={open}
          aria-controls="review-definition-text"
          onClick={() => setOpen((o) => !o)}
          data-testid="review-definition-toggle"
        >
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </>
  );
}

/** How a decided operation was decided, read-only. */
function Decided({ operation, names }: { operation: ProposedOperation; names: ReviewNames }) {
  const verdict = verdictOf(operation);
  const element = isElement(operation);
  const reason = reasonLabel(operation.reason_code);
  let text: string;
  if (verdict === "rejected") {
    text = `Not an element${reason ? `: ${reason}` : ""}.`;
  } else if (verdict === "added") {
    text = `Added by you as ${names.classLabel(shownClassId(operation))}.`;
  } else if (verdict === "changed") {
    text = `Accepted as ${names.classLabel(shownClassId(operation))} (proposed ${names.classLabel(proposedClassId(operation))}).`;
  } else if (operation.matched) {
    text = "Accepted as the existing individual it matched.";
  } else {
    text = element ? `Accepted as ${names.classLabel(shownClassId(operation))}.` : "Accepted.";
  }
  return (
    <div className="review-section" data-testid="review-decided">
      <Eyebrow>Decided</Eyebrow>
      <div className="review-decided">
        <span>{text}</span>
        {verdict === "rejected" && operation.reason && (
          <span className="review-muted" data-testid="review-decided-note">
            {operation.reason}
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * The selected element: its evidence, what its class means, and the decision:
 * Correct (or, for a near match, the existing individual it is), a better
 * class (suggestions on 1-3, or any class from the picker), or not an element
 * with a reason. Then the relationships it is an end of. A relationship is
 * decided Correct or not an element, after its new ends are decided.
 */
export function ReviewInspector({
  operation,
  operations,
  names,
  taxonomyId,
  datasetId,
  nearChoice,
  onNearChoice,
  pickable,
  suggestions,
  deciding,
  busy,
  reasonsRef,
  onCorrect,
  onPickClass,
  onReject,
  onSelect,
}: ReviewInspectorProps) {
  const [note, setNote] = useState("");
  const element = isElement(operation);
  const verdict = verdictOf(operation);
  const awaiting = verdict === "awaiting";
  const classId = shownClassId(operation);
  const cls = names.classOf(classId);
  const quotes = sourcePassagesOf(operation).flatMap((p) => (p.quote ? [p.quote] : []));
  const relationships = element ? relationshipsOf(operation, operations) : [];
  const probability =
    operation.probability === null || operation.probability === undefined
      ? ""
      : ` · p ${formatProbability(operation.probability)}`;
  const canDecide = deciding && awaiting;
  const nearMatch = element && isNearMatch(operation);
  // An existing individual is used as it is: the create's class can't change with it.
  const usingExisting = nearMatch && nearChoice !== CREATE_NEW;
  const ends = endsToDecide(operation, operations);

  return (
    <Panel
      id="review-inspector"
      className="review-pane review-pane--inspector"
      role="region"
      aria-label="Selected element"
      noPadding
      data-testid="review-inspector"
    >
      <div className="review-inspector__head">
        <span className="review-eyebrow" data-testid="review-inspector-eyebrow">
          {element ? "Individual" : "Relationship"}
          {probability}
        </span>
        <span className="review-inspector__title" data-testid="review-inspector-title">
          {names.titleOf(operation)}
        </span>
        <div className="review-chips">
          {element && (
            <ClassChip label={names.classLabel(classId)} data-testid="review-inspector-class" />
          )}
          <Chip variant={VERDICT_CHIP[verdict]} data-testid="review-inspector-status">
            {VERDICT_LABEL[verdict]}
          </Chip>
        </div>
      </div>

      <div className="review-inspector__body">
        {operation.status === "failed" && (
          <div className="review-failed" role="alert" data-testid="review-failed">
            The last apply failed: {operation.reason ?? "no reason given"}
          </div>
        )}

        {quotes.length > 0 && (
          <div className="review-section" data-testid="review-evidence">
            <Eyebrow>Evidence</Eyebrow>
            {quotes.map((quote, i) => (
              <blockquote key={i} className="review-evidence">
                {quote}
              </blockquote>
            ))}
          </div>
        )}

        {element && (
          <div className="review-section" data-testid="review-definition">
            <Eyebrow>{`What ${names.classLabel(classId)} means`}</Eyebrow>
            <Definition key={classId} text={cls?.description} />
          </div>
        )}

        {canDecide ? (
          <>
            <div className="review-section">
              <Eyebrow>Decide</Eyebrow>
              {ends.rejected.length > 0 ? (
                <FormCallout variant="warn" icon="alert" data-testid="review-ends-callout">
                  {seqList(ends.rejected)} {ends.rejected.length === 1 ? "was" : "were"} rejected,
                  so this relationship can&apos;t apply. Reject it.
                </FormCallout>
              ) : (
                ends.undecided.length > 0 && (
                  <FormCallout variant="info" icon="info" data-testid="review-ends-callout">
                    Decide {seqList(ends.undecided)} first: this relationship follows{" "}
                    {ends.undecided.length === 1 ? "its choice" : "their choices"}.
                  </FormCallout>
                )
              )}
              {nearMatch && (
                <NearMatchChoice
                  operation={operation}
                  taxonomyId={taxonomyId}
                  datasetId={datasetId}
                  choice={nearChoice}
                  onChoose={onNearChoice}
                  disabled={busy}
                />
              )}
              {ends.rejected.length === 0 && (
                <div className="review-chips">
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={busy || ends.undecided.length > 0}
                    onClick={onCorrect}
                    aria-keyshortcuts="A"
                    data-testid="review-correct"
                  >
                    {usingExisting ? "Correct: use existing" : "Correct"}
                  </Button>
                </div>
              )}
              <span className="review-keys">
                {element
                  ? "A correct · 1-3 pick a class · X not an element · J / K next"
                  : "A correct · X not an element · J / K next"}
              </span>
            </div>

            {element && (
              <div className="review-section" data-testid="review-better-class">
                <Eyebrow>Or a better class</Eyebrow>
                {usingExisting && (
                  <span className="review-muted" data-testid="review-class-locked">
                    The existing individual keeps its classes. Choose Create new to give this one
                    another class.
                  </span>
                )}
                {suggestions.map((suggestion, i) => (
                  <button
                    key={suggestion.id}
                    type="button"
                    className="review-alt"
                    disabled={busy || usingExisting}
                    aria-keyshortcuts={String(i + 1)}
                    title={names.classLabel(suggestion.id)}
                    onClick={() => onPickClass(suggestion.id)}
                    data-testid={`review-suggestion-${i + 1}`}
                  >
                    <span className="review-alt__class">
                      {i + 1} {names.classLabel(suggestion.id)}
                    </span>
                    {suggestion.description && (
                      <span className="review-alt__definition">{suggestion.description}</span>
                    )}
                  </button>
                ))}
                <ReviewClassPicker
                  classes={pickable}
                  current={cls}
                  disabled={busy || usingExisting}
                  onPick={onPickClass}
                />
              </div>
            )}

            <div className="review-section">
              <Eyebrow>Or not an element, because</Eyebrow>
              <div
                ref={reasonsRef}
                className="review-reasons"
                role="group"
                aria-label="Not an element, because"
                aria-keyshortcuts="X"
                data-testid="review-reasons"
              >
                {REJECTION_REASONS.map((reason) => (
                  <button
                    key={reason.code}
                    type="button"
                    className="review-reason"
                    disabled={busy}
                    onClick={() => onReject(reason.code, note)}
                    data-testid={`review-reason-${reason.code}`}
                  >
                    {reason.label}
                  </button>
                ))}
              </div>
              <label htmlFor="review-note" className="review-muted">
                Note, optional · kept with the decision
              </label>
              <TextArea
                id="review-note"
                rows={2}
                value={note}
                placeholder="e.g. a region the team targets, not a party with concerns"
                onChange={(e) => setNote(e.target.value)}
                data-testid="review-note"
              />
            </div>
          </>
        ) : (
          !awaiting && <Decided operation={operation} names={names} />
        )}

        {element && (
          <div className="review-section" data-testid="review-relationships">
            <Eyebrow>{`Its relationships · ${relationships.length}`}</Eyebrow>
            {relationships.length === 0 ? (
              <span className="review-muted">
                None proposed. Relationships are decided after their ends.
              </span>
            ) : (
              relationships.map((relationship) => {
                const parts = names.relationshipParts(relationship);
                const relVerdict = verdictOf(relationship);
                return (
                  <button
                    key={relationship.id}
                    type="button"
                    className="review-alt review-relationship"
                    aria-controls="review-inspector"
                    onClick={() => onSelect(relationship.id)}
                    data-testid={`review-relationship-${relationship.id}`}
                  >
                    <span className="review-relationship__end">{parts.from}</span>
                    <span className="review-relationship__predicate">{parts.predicate}</span>
                    <span className="review-relationship__end">{parts.to}</span>
                    <Chip variant={VERDICT_CHIP[relVerdict]}>{VERDICT_LABEL[relVerdict]}</Chip>
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
