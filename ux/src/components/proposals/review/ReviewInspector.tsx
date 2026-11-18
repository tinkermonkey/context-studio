import { useEffect, useState, type RefObject } from "react";
import {
  Button,
  Chip,
  FormCallout,
  Panel,
  SegmentedControl,
  TextArea,
} from "@tinkermonkey/heimdall-ui";
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
import { ClassPill, IndividualPill, PredicatePill } from "./ReviewPills";
import {
  RelationshipDetails,
  RelationshipEditor,
  type EndCandidate,
  type EndInfo,
} from "./ReviewRelationship";
import type { ReviewSchema } from "./reviewSchema";
import type { GoldDraft, Tier } from "./goldModel";
import {
  REJECTION_REASONS,
  VERDICT_CHIP,
  endsToDecide,
  isElement,
  proposedClassId,
  reasonLabel,
  relationshipEdited,
  relationshipsOf,
  seqList,
  shownClassId,
  shownFields,
  verdictLabel,
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
  schema: ReviewSchema;
  /** An end of a relationship (a "$ref" or an individual's id), as the inspector shows it. */
  endOf: (value: unknown) => EndInfo;
  /** The individuals a relationship's ends can be changed to. */
  endCandidates: EndCandidate[];
  /** The proposal's taxonomy and dataset, for a near match's question. */
  taxonomyId: string;
  datasetId?: string | null;
  /** A near match's choice: an existing individual's id, or CREATE_NEW. */
  nearChoice: Choice;
  onNearChoice: (choice: Choice) => void;
  /** The taxonomy's classes that are not derived, for the picker. */
  pickable: ClassResponse[];
  /** The taxonomy's classes are still loading: no class can be shown or picked yet. */
  classesLoading?: boolean;
  /** Classes offered on keys 1-3: gold's acceptable ones, then those picked recently. */
  suggestions: ClassResponse[];
  /** The recently picked classes among the suggestions: each has a remove control. */
  recentIds: string[];
  onForgetClass: (classId: string) => void;
  /** The proposal takes decisions (it isn't reverted). */
  deciding: boolean;
  busy: boolean;
  /** The reason buttons, for X to focus. */
  reasonsRef: RefObject<HTMLDivElement | null>;
  onCorrect: () => void;
  onPickClass: (classId: string) => void;
  /** Accept a relationship with another predicate, source or target. */
  onAcceptEdited: (edit: Record<string, string>) => void;
  onReject: (reasonCode: RejectionReason, note: string) => void;
  /** Show one of the operation's passages in the source. */
  onShowPassage: (quote: string) => void;
  /** Gold mode: the operation's gold tier and aliases, and what the reviewer has noted. */
  gold?: GoldInspector;
}

/** What gold mode adds to the inspector for one operation. */
export interface GoldInspector {
  /** The tier gold gives it, when it is in gold. */
  goldTier?: Tier;
  aliases: string[];
  /** Class ids already in the element's acceptable_classes: shown as such, not toggled. */
  acceptableIds: string[];
  draft: GoldDraft;
  onDraft: (draft: GoldDraft) => void;
}

/** The tier control: core or supporting, starting from gold's. */
function TierControl({
  tier,
  onChange,
  disabled,
}: {
  tier: Tier;
  onChange: (tier: Tier) => void;
  disabled: boolean;
}) {
  return (
    <div className="review-tier" data-testid="review-tier">
      <span className="review-muted" id="review-tier-label">
        Tier
      </span>
      <SegmentedControl
        value={tier}
        onChange={(value) => onChange(value as Tier)}
        aria-labelledby="review-tier-label"
        disabled={disabled}
        options={[
          { value: "core", label: "Core" },
          { value: "supporting", label: "Supporting" },
        ]}
      />
    </div>
  );
}

function Eyebrow({ children }: { children: string }) {
  return <span className="review-eyebrow">{children}</span>;
}

/** A class on one line, cut with an ellipsis; the whole of it in the tooltip (the add form). */
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

/** How a decided operation was decided, its classes and predicates as pills. */
function Decided({
  operation,
  endOf,
}: {
  operation: ProposedOperation;
  endOf: (value: unknown) => EndInfo;
}) {
  const verdict = verdictOf(operation);
  const element = isElement(operation);
  const reason = reasonLabel(operation.reason_code);
  const shown = shownClassId(operation);
  let body;
  if (verdict === "rejected") {
    body = (
      <span>{`Not ${element ? "an element" : "a relationship"}${reason ? `: ${reason}` : ""}.`}</span>
    );
  } else if (!element) {
    // What the edit changed, each as it is now beside what was proposed.
    const now = shownFields(operation);
    const proposed = operation.fields ?? {};
    const changed = (name: string) => relationshipEdited(operation) && now[name] !== proposed[name];
    const end = (name: "source_id" | "target_id", label: string) =>
      changed(name) && (
        <span className="review-chips" data-testid={`review-decided-${name}`}>
          {label}
          <IndividualPill
            title={endOf(now[name]).title}
            classId={endOf(now[name]).classId}
            status={endOf(now[name]).status}
            operationId={endOf(now[name]).operationId}
          />
          <span className="review-muted">proposed {endOf(proposed[name]).title}</span>
        </span>
      );
    body = relationshipEdited(operation) ? (
      <>
        <span>Accepted with changes:</span>
        {changed("property_definition_id") && (
          <span className="review-chips" data-testid="review-decided-predicate">
            Predicate
            <PredicatePill propertyId={now.property_definition_id as string | undefined} />
            <span className="review-muted">proposed</span>
            <PredicatePill propertyId={proposed.property_definition_id as string | undefined} />
          </span>
        )}
        {end("source_id", "From")}
        {end("target_id", "To")}
      </>
    ) : (
      <span>Accepted.</span>
    );
  } else if (operation.matched && verdict !== "added") {
    body = <span>Accepted as the existing individual it matched.</span>;
  } else {
    body = (
      <span className="review-chips">
        {verdict === "added" ? "Added by you as" : "Accepted as"}
        <ClassPill classId={shown} data-testid="review-decided-class" />
        {verdict === "changed" && (
          <>
            <span className="review-muted">proposed</span>
            <ClassPill classId={proposedClassId(operation)} />
          </>
        )}
      </span>
    );
  }
  return (
    <div className="review-decided" data-testid="review-decided">
      {body}
      {verdict === "rejected" && operation.reason && (
        <span className="review-muted" data-testid="review-decided-note">
          {operation.reason}
        </span>
      )}
    </div>
  );
}

/**
 * The selected element or relationship. An element: its evidence, its class
 * (a pill whose overlay explains it) and what it means, the decision (Correct,
 * a better class, or not an element with a reason), then the relationships it
 * is an end of. A relationship: its evidence, its ends with their classes and
 * decisions, its predicate and the classes it allows, and the decision
 * (Correct, a better predicate or end, or not a relationship). A decided one
 * shows how it was decided and can be decided again.
 */
export function ReviewInspector({
  operation,
  operations,
  names,
  schema,
  endOf,
  endCandidates,
  taxonomyId,
  datasetId,
  nearChoice,
  onNearChoice,
  pickable,
  suggestions,
  recentIds,
  onForgetClass,
  deciding,
  busy,
  reasonsRef,
  onCorrect,
  onPickClass,
  onAcceptEdited,
  onReject,
  onShowPassage,
  gold,
  classesLoading = false,
}: ReviewInspectorProps) {
  const [note, setNote] = useState("");
  const [changing, setChanging] = useState(false);
  // A new decision closes the change controls.
  useEffect(
    () => setChanging(false),
    [operation.status, operation.applied_fields, operation.reason_code],
  );
  // In gold mode rejecting an element needs a note: it becomes the excluded entry's reason.
  const noteMissing = !!gold && isElement(operation) && !note.trim();
  const draft = gold?.draft;
  const tier = draft?.tier ?? gold?.goldTier ?? "core";
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
  // Decided: the decision can be changed while the review is open.
  const canDecide = deciding && (awaiting || changing);
  const nearMatch = element && isNearMatch(operation);
  // An existing individual is used as it is: the create's class can't change with it.
  const usingExisting = nearMatch && nearChoice !== CREATE_NEW;
  const ends = endsToDecide(operation, operations);
  const relationshipEnds = element
    ? undefined
    : {
        source: endOf(shownFields(operation).source_id),
        target: endOf(shownFields(operation).target_id),
      };
  // Already correct as proposed: nothing for Correct to change.
  const alreadyCorrect = verdict === "correct" && !operation.matched;

  return (
    <Panel
      id="review-inspector"
      className="review-pane review-pane--inspector"
      role="region"
      aria-label={element ? "Selected element" : "Selected relationship"}
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
        {gold && gold.aliases.length > 0 && (
          <span className="review-muted" data-testid="review-gold-aliases">
            Also called {gold.aliases.join(", ")}
          </span>
        )}
        <div className="review-chips">
          {element && (
            <ClassPill classId={classId} size="lg" data-testid="review-inspector-class" />
          )}
          <Chip variant={VERDICT_CHIP[verdict]} data-testid="review-inspector-status">
            {verdictLabel(operation)}
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
              <button
                key={i}
                type="button"
                className="review-evidence"
                aria-label={`Show in the source: ${quote}`}
                onClick={() => onShowPassage(quote)}
                data-testid={`review-evidence-${i + 1}`}
              >
                {quote}
              </button>
            ))}
          </div>
        )}

        {element && (
          <div className="review-section" data-testid="review-definition">
            <Eyebrow>{`What ${names.classLabel(classId)} means`}</Eyebrow>
            {classesLoading ? (
              <p className="review-definition review-muted" data-testid="review-definition-loading">
                Loading…
              </p>
            ) : (
              <Definition key={classId} text={cls?.description} />
            )}
          </div>
        )}

        {relationshipEnds && (
          <RelationshipDetails operation={operation} ends={relationshipEnds} schema={schema} />
        )}

        {!awaiting && (
          <div className="review-section">
            <Eyebrow>Decided</Eyebrow>
            <Decided operation={operation} endOf={endOf} />
            {deciding && (
              <button
                type="button"
                className="review-link"
                aria-expanded={changing}
                aria-controls="review-change"
                onClick={() => setChanging((c) => !c)}
                data-testid="review-change-decision"
              >
                {changing ? "Keep this decision" : "Change the decision"}
              </button>
            )}
          </div>
        )}

        {canDecide && (
          <div id="review-change" className="review-decide" data-testid="review-decide">
            <div className="review-section">
              <Eyebrow>{awaiting ? "Decide" : "Change the decision"}</Eyebrow>
              {!awaiting && (
                <span className="review-muted" data-testid="review-change-note">
                  {element && relationships.some((r) => r.status === "applied")
                    ? "Changing it undoes what it applied, and its accepted relationships wait for a decision again."
                    : "Changing it undoes what it applied; the new decision is the one that counts."}
                </span>
              )}
              {ends.rejected.length > 0 ? (
                <FormCallout variant="warn" icon="alert" data-testid="review-ends-callout">
                  {seqList(ends.rejected)} {ends.rejected.length === 1 ? "was" : "were"} rejected,
                  so this relationship can&apos;t apply as proposed. Reject it, or give it another
                  end.
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
              {gold && draft && (
                <TierControl
                  tier={tier}
                  disabled={busy}
                  onChange={(next) => gold.onDraft({ ...draft, tier: next })}
                />
              )}
              {ends.rejected.length === 0 && (
                <div className="review-chips">
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={busy || ends.undecided.length > 0 || alreadyCorrect}
                    onClick={onCorrect}
                    aria-keyshortcuts={awaiting ? "A" : undefined}
                    data-testid="review-correct"
                  >
                    {usingExisting ? "Correct: use existing" : "Correct"}
                  </Button>
                </div>
              )}
              {awaiting && (
                <span className="review-keys">
                  {element
                    ? "A correct · 1-3 pick a class · X not an element · J / K next"
                    : "A correct · X not a relationship · J / K next"}
                </span>
              )}
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
                {suggestions.map((suggestion, i) => {
                  // Keys 1-3 pick the first three.
                  const keyed = i < 3 && awaiting;
                  const acceptable = !!gold?.acceptableIds.includes(suggestion.id);
                  const defensible = acceptable || !!draft?.alsoDefensible.includes(suggestion.id);
                  const recent = recentIds.includes(suggestion.id) && !acceptable;
                  const pick = (
                    <button
                      key={suggestion.id}
                      type="button"
                      className="review-alt"
                      disabled={busy || usingExisting}
                      aria-keyshortcuts={keyed ? String(i + 1) : undefined}
                      title={names.classLabel(suggestion.id)}
                      onClick={() => onPickClass(suggestion.id)}
                      data-testid={`review-suggestion-${i + 1}`}
                    >
                      <span className="review-alt__class">
                        {keyed ? `${i + 1} ` : ""}
                        {names.classLabel(suggestion.id)}
                      </span>
                      {suggestion.description && (
                        <span className="review-alt__definition">{suggestion.description}</span>
                      )}
                    </button>
                  );
                  const forget = recent && (
                    <button
                      type="button"
                      className="review-forget"
                      aria-label={`Remove ${names.classLabel(suggestion.id)} from recent classes`}
                      onClick={() => onForgetClass(suggestion.id)}
                      data-testid={`review-suggestion-${i + 1}-remove`}
                    >
                      ×
                    </button>
                  );
                  if (!gold || !draft) {
                    return (
                      <div key={suggestion.id} className="review-alt-row">
                        {pick}
                        {forget}
                      </div>
                    );
                  }
                  return (
                    <div key={suggestion.id} className="review-alt-row">
                      {pick}
                      <button
                        type="button"
                        className={[
                          "review-defensible",
                          defensible && "review-defensible--on",
                          acceptable && "review-defensible--gold",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        aria-pressed={defensible}
                        aria-label={
                          acceptable
                            ? `${names.classLabel(suggestion.id)} is acceptable in gold`
                            : `${names.classLabel(suggestion.id)} is also defensible`
                        }
                        // Already in gold: write-gold only adds, so there is nothing to toggle.
                        disabled={busy || acceptable}
                        onClick={() =>
                          gold.onDraft({
                            ...draft,
                            alsoDefensible: defensible
                              ? draft.alsoDefensible.filter((id) => id !== suggestion.id)
                              : [...draft.alsoDefensible, suggestion.id],
                          })
                        }
                        data-testid={`review-defensible-${i + 1}`}
                      >
                        {acceptable ? "Acceptable in gold" : "Also defensible"}
                      </button>
                      {forget}
                    </div>
                  );
                })}
                {gold && draft && classId && !usingExisting && !classesLoading && (
                  <label className="review-check" data-testid="review-keep-old">
                    <input
                      type="checkbox"
                      checked={draft.keepOld}
                      disabled={busy}
                      onChange={(e) => gold.onDraft({ ...draft, keepOld: e.target.checked })}
                    />
                    Keep {names.classLabel(classId)} as also defensible
                  </label>
                )}
                <ReviewClassPicker
                  classes={pickable}
                  current={cls}
                  disabled={busy || usingExisting}
                  loading={classesLoading}
                  onPick={onPickClass}
                />
              </div>
            )}

            {relationshipEnds && (
              <RelationshipEditor
                key={operation.id}
                operation={operation}
                operations={operations}
                ends={relationshipEnds}
                candidates={endCandidates}
                schema={schema}
                busy={busy}
                onAccept={onAcceptEdited}
              />
            )}

            <div className="review-section">
              <Eyebrow>
                {element ? "Or not an element, because" : "Or not a relationship, because"}
              </Eyebrow>
              <div
                ref={reasonsRef}
                className="review-reasons"
                role="group"
                aria-label={element ? "Not an element, because" : "Not a relationship, because"}
                aria-keyshortcuts={awaiting ? "X" : undefined}
                data-testid="review-reasons"
              >
                {REJECTION_REASONS.map((reason) => (
                  <button
                    key={reason.code}
                    type="button"
                    className="review-reason"
                    disabled={
                      busy ||
                      noteMissing ||
                      (verdict === "rejected" &&
                        reason.code === operation.reason_code &&
                        note.trim() === (operation.reason ?? ""))
                    }
                    onClick={() => onReject(reason.code, note)}
                    data-testid={`review-reason-${reason.code}`}
                  >
                    {reason.label}
                  </button>
                ))}
              </div>
              <label htmlFor="review-note" className="review-muted">
                {gold && element
                  ? "Note, needed · the excluded entry's reason"
                  : "Note, optional · kept with the decision"}
              </label>
              <TextArea
                id="review-note"
                rows={2}
                value={note}
                aria-describedby={noteMissing ? "review-note-required" : undefined}
                placeholder="e.g. a region the team targets, not a party with concerns"
                onChange={(e) => setNote(e.target.value)}
                data-testid="review-note"
              />
              {noteMissing && (
                <span
                  id="review-note-required"
                  className="review-add__error"
                  data-testid="review-note-required"
                >
                  Write why it is not an element to reject it: the note becomes its excluded entry.
                </span>
              )}
            </div>
          </div>
        )}

        {element && (
          <div className="review-section" data-testid="review-relationships">
            <Eyebrow>{`Its relationships · ${relationships.length}`}</Eyebrow>
            {relationships.length === 0 ? (
              <span className="review-muted">
                None proposed. Relationships are decided after their ends.
              </span>
            ) : (
              <ul className="review-relationships">
                {relationships.map((relationship) => {
                  const fields = shownFields(relationship);
                  const outgoing =
                    endOf(fields.source_id).operationId === operation.id ||
                    endOf(relationship.fields?.source_id).operationId === operation.id;
                  const other = endOf(outgoing ? fields.target_id : fields.source_id);
                  const relVerdict = verdictOf(relationship);
                  return (
                    <li
                      key={relationship.id}
                      className="review-relationship"
                      data-testid={`review-relationship-${relationship.id}`}
                    >
                      <span
                        className="review-relationship__direction"
                        aria-label={outgoing ? "from this to" : "to this from"}
                      >
                        {outgoing ? "→" : "←"}
                      </span>
                      <PredicatePill
                        propertyId={fields.property_definition_id as string | undefined}
                        operationId={relationship.id}
                        data-testid={`review-relationship-${relationship.id}-open`}
                      />
                      <IndividualPill
                        title={other.title}
                        classId={other.classId}
                        status={other.status}
                        operationId={other.operationId}
                        data-testid={`review-relationship-${relationship.id}-end`}
                      />
                      {other.classId && <ClassPill classId={other.classId} />}
                      <Chip variant={VERDICT_CHIP[relVerdict]}>{verdictLabel(relationship)}</Chip>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
