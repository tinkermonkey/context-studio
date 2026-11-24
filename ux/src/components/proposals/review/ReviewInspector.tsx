import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { Button, Chip, FormCallout, Panel, TextArea } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation, RejectionReason } from "@/api/services/proposals";
import type { components } from "@/api/types";
import { formatProbability, isAwaiting } from "../proposalModel";
import { NearMatchChoice } from "../SourcePassage";
import {
  CREATE_NEW,
  isNearMatch,
  sourcePassagesOf,
  type NearMatchChoice as Choice,
} from "../sourceModel";
import { ReviewClassPicker } from "./ReviewClassPicker";
import { TierControl } from "./TierControl";
import {
  ClassPill,
  ClassTag,
  IndividualPill,
  PredicatePill,
  PredicateTag,
  useOperationLink,
} from "./ReviewPills";
import {
  RelationshipBlock,
  RelationshipEditor,
  RelationshipTitle,
  misfitOf,
  type EndCandidate,
  type EndInfo,
} from "./ReviewRelationship";
import type { ReviewSchema } from "./reviewSchema";
import type { GoldDraft, Tier } from "./goldModel";
import {
  END_REJECTED_REASON,
  REJECTION_REASONS,
  VERDICT_CHIP,
  endRejectedNote,
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
  /**
   * Bumped by the page on key X: each new value opens the reason step, as the
   * "Not an element" button does. The value the inspector mounts with opens nothing.
   */
  rejectPrompt?: number;
  onCorrect: () => void;
  onPickClass: (classId: string) => void;
  /** Accept a relationship with another predicate, source or target. */
  onAcceptEdited: (edit: Record<string, string>) => void;
  onReject: (reasonCode: RejectionReason, note: string) => void;
  /** A rejected element: reject the relationships still awaiting a decision that use it. */
  onRejectRelationships?: () => void;
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

function Eyebrow({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <span className="review-eyebrow" id={id}>
      {children}
    </span>
  );
}

/** One section of the inspector: padded, ruled off from the next. */
function Block({
  label,
  className,
  blockRef,
  children,
  "data-testid": testId,
}: {
  label: string;
  className?: string;
  blockRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
  "data-testid"?: string;
}) {
  return (
    <section
      ref={blockRef}
      className={["review-block", className].filter(Boolean).join(" ")}
      aria-label={label}
      data-testid={testId}
    >
      {children}
    </section>
  );
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
            verdict={endOf(now[name]).verdict}
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
 * The selected element or relationship, one skeleton for both: what it is,
 * the evidence, what the schema says, decide, change it, gold only.
 *
 * A relationship reads as the relationship itself: FROM its source, the
 * predicate between (whether the ends fit, what it means), TO its target; then
 * Correct, Or correct it (predicate, source or target), or not a relationship.
 * An element: its class, what that means, the decision (Correct, a better
 * class, or not an element), then the relationships it is an end of. A
 * decided one shows how it was decided and can be decided again.
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
  rejectPrompt = 0,
  onCorrect,
  onPickClass,
  onAcceptEdited,
  onReject,
  onRejectRelationships,
  onShowPassage,
  gold,
  classesLoading = false,
}: ReviewInspectorProps) {
  const [note, setNote] = useState("");
  const [changing, setChanging] = useState(false);
  // "Not an element" (or X) was pressed: the reasons are highlighted with a prompt.
  const [prompting, setPrompting] = useState(false);
  const reasonsRef = useRef<HTMLDivElement>(null);
  const reasonsBlockRef = useRef<HTMLElement>(null);
  // A new decision closes the change controls and the prompt.
  useEffect(() => {
    setChanging(false);
    setPrompting(false);
  }, [operation.status, operation.applied_fields, operation.reason_code]);
  // In gold mode rejecting an element needs a note: it becomes the excluded entry's reason.
  const noteMissing = !!gold && isElement(operation) && !note.trim();
  const draft = gold?.draft;
  const tier = draft?.tier ?? gold?.goldTier ?? "core";
  const element = isElement(operation);
  const kind = element ? "an element" : "a relationship";
  const verdict = verdictOf(operation);
  const awaiting = verdict === "awaiting";
  const classId = shownClassId(operation);
  const cls = names.classOf(classId);
  const quotes = sourcePassagesOf(operation).flatMap((p) => (p.quote ? [p.quote] : []));
  const relationships = element ? relationshipsOf(operation, operations) : [];
  // A rejected element's relationships still awaiting a decision: rejected with it, on request.
  const awaitingRelationships = verdict === "rejected" ? relationships.filter(isAwaiting) : [];
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
  // The ends no longer fit its type (an end's class changed): it can't apply as it is.
  const misfit = !!relationshipEnds && !!misfitOf(operation, relationshipEnds, schema);
  // An end was rejected: rejecting this too is the decision left (one click, or key X).
  const endRejected = ends.rejected.length > 0;
  const rejectForEnd = () =>
    onReject(END_REJECTED_REASON, note.trim() || endRejectedNote(ends.rejected.map((e) => e.seq)));
  /**
   * Open the reason step (the "Not …" button and key X): highlight the reasons with a
   * prompt, bring them into view and focus the first reason, or, while gold mode still
   * needs a note, the note. The rejection is recorded when a reason is picked.
   */
  const openReasons = () => {
    setPrompting(true);
    reasonsBlockRef.current?.scrollIntoView?.({ block: "nearest" });
    const reason = reasonsRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)");
    (reason ?? document.getElementById("review-note"))?.focus();
  };
  // Key X: the page bumps rejectPrompt.
  const seenPrompt = useRef(rejectPrompt);
  useEffect(() => {
    if (rejectPrompt === seenPrompt.current) return;
    seenPrompt.current = rejectPrompt;
    if (canDecide) openReasons();
  });

  const evidence = quotes.length > 0 && (
    <Block label="Evidence" data-testid="review-evidence">
      <div className="review-block__head">
        <Eyebrow>{element ? `EVIDENCE · ${quotes.length}` : "EVIDENCE"}</Eyebrow>
        {!element && (
          <button
            type="button"
            className="review-link review-link--accent"
            onClick={() => onShowPassage(quotes[0])}
            data-testid="review-show-in-source"
          >
            Show in source
          </button>
        )}
      </div>
      {quotes.map((quote, i) => (
        <button
          key={i}
          type="button"
          className={["review-evidence", i > 0 && "review-evidence--more"]
            .filter(Boolean)
            .join(" ")}
          aria-label={`Show in the source: ${quote}`}
          onClick={() => onShowPassage(quote)}
          data-testid={`review-evidence-${i + 1}`}
        >
          {quote}
        </button>
      ))}
    </Block>
  );

  const decide = canDecide && (
    <Block label="Decide" data-testid="review-decide">
      <Eyebrow>{awaiting ? "DECIDE" : "DECIDE AGAIN"}</Eyebrow>
      {ends.rejected.length > 0 ? (
        <FormCallout variant="warn" icon="alert" data-testid="review-ends-callout">
          {seqList(ends.rejected)} {ends.rejected.length === 1 ? "was" : "were"} rejected, so this
          relationship can&apos;t apply as proposed. Reject it too, or give it another end.
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
      <div className="review-chips">
        {endRejected && (
          <Button
            variant="primary"
            size="sm"
            disabled={busy}
            onClick={rejectForEnd}
            aria-keyshortcuts={awaiting ? "X" : undefined}
            data-testid="review-reject-end"
          >
            Reject: an end was rejected
          </Button>
        )}
        {!endRejected && (
          <Button
            variant="primary"
            size="sm"
            disabled={busy || ends.undecided.length > 0 || alreadyCorrect || misfit}
            onClick={onCorrect}
            aria-keyshortcuts={awaiting ? "A" : undefined}
            data-testid="review-correct"
          >
            {usingExisting ? "Correct: use existing" : "Correct"}
          </Button>
        )}
        <Button
          variant="secondary"
          size="sm"
          disabled={busy}
          onClick={openReasons}
          aria-keyshortcuts={awaiting && !endRejected ? "X" : undefined}
          data-testid="review-not"
        >
          {element ? "Not an element" : "Not a relationship"}
        </Button>
        {awaiting && (
          <span className="review-keys">
            {element
              ? "A · 1-3 · X · J / K next"
              : endRejected
                ? "X · J / K next"
                : "A · X · J / K next"}
          </span>
        )}
      </div>
    </Block>
  );

  const betterClass = canDecide && element && (
    <Block label="Or a better class" data-testid="review-better-class">
      <Eyebrow>OR A BETTER CLASS</Eyebrow>
      {usingExisting && (
        <span className="review-muted" data-testid="review-class-locked">
          The existing individual keeps its classes. Choose Create new to give this one another
          class.
        </span>
      )}
      {suggestions.length > 0 && (
        <div className="review-suggestions">
          {suggestions.map((suggestion, i) => {
            // Keys 1-3 pick the first three.
            const keyed = i < 3 && awaiting;
            const acceptable = !!gold?.acceptableIds.includes(suggestion.id);
            const defensible = acceptable || !!draft?.alsoDefensible.includes(suggestion.id);
            const recent = recentIds.includes(suggestion.id) && !acceptable;
            return (
              <span key={suggestion.id} className="review-suggestion">
                <button
                  type="button"
                  className="review-suggestion__pick"
                  disabled={busy || usingExisting}
                  aria-keyshortcuts={keyed ? String(i + 1) : undefined}
                  aria-label={`Accept as ${names.classLabel(suggestion.id)}`}
                  title={suggestion.description ?? undefined}
                  onClick={() => onPickClass(suggestion.id)}
                  data-testid={`review-suggestion-${i + 1}`}
                >
                  {keyed && <span className="review-suggestion__key">{i + 1} </span>}
                  {names.classLabel(suggestion.id)}
                </button>
                {gold && draft && (
                  <button
                    type="button"
                    className={[
                      "review-suggestion__defensible",
                      defensible && "review-suggestion__defensible--on",
                      acceptable && "review-suggestion__defensible--gold",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    aria-pressed={defensible}
                    aria-label={
                      acceptable
                        ? `${names.classLabel(suggestion.id)} is acceptable in gold`
                        : `${names.classLabel(suggestion.id)} is also defensible`
                    }
                    title={acceptable ? "Acceptable in gold" : "Also defensible"}
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
                    {acceptable ? "in gold" : "defensible"}
                  </button>
                )}
                {recent && (
                  <button
                    type="button"
                    className="review-forget"
                    aria-label={`Remove ${names.classLabel(suggestion.id)} from recent classes`}
                    onClick={() => onForgetClass(suggestion.id)}
                    data-testid={`review-suggestion-${i + 1}-remove`}
                  >
                    ×
                  </button>
                )}
              </span>
            );
          })}
          {recentIds.length > 0 && <span className="review-muted">recent keeps 2</span>}
        </div>
      )}
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
    </Block>
  );

  const reasons = canDecide && (
    <Block
      label={`Not ${kind}`}
      className={prompting ? "review-block--prompt" : undefined}
      blockRef={reasonsBlockRef}
      data-testid="review-reasons-block"
    >
      <Eyebrow>{`OR NOT ${kind.toUpperCase()}, BECAUSE`}</Eyebrow>
      {prompting && (
        <span className="review-prompt" role="status" data-testid="review-reasons-prompt">
          {noteMissing
            ? "Write why in the note, then pick a reason to reject it."
            : "Pick a reason to reject it."}
        </span>
      )}
      <div
        ref={reasonsRef}
        className="review-reasons"
        role="group"
        aria-label={element ? "Not an element, because" : "Not a relationship, because"}
        aria-keyshortcuts={awaiting && !endRejected ? "X" : undefined}
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
    </Block>
  );

  const decided = !awaiting && (
    <Block label="Decision">
      <Eyebrow>DECIDED</Eyebrow>
      <Decided operation={operation} endOf={endOf} />
      {deciding && (
        <>
          <div className="review-chips">
            <Button
              variant="secondary"
              size="sm"
              aria-expanded={changing}
              aria-controls="review-change"
              onClick={() => setChanging((c) => !c)}
              data-testid="review-change-decision"
            >
              {changing ? "Keep this decision" : "Change the decision"}
            </Button>
          </div>
          <span className="review-block__subtitle" data-testid="review-change-note">
            {element
              ? "Changing it reopens this individual and the relationships that use it."
              : "Changing it reopens this relationship."}
          </span>
        </>
      )}
    </Block>
  );

  const goldFooter = gold && draft && deciding && (
    <section className="review-block review-block--gold" aria-label="Gold only">
      <TierControl
        tier={tier}
        kind={element ? "element" : "relationship"}
        label="GOLD ONLY · TIER"
        disabled={busy}
        onChange={(next) => gold.onDraft({ ...draft, tier: next })}
      />
    </section>
  );

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
        <div className="review-inspector__top">
          <span className="review-eyebrow" data-testid="review-inspector-eyebrow">
            {element ? "Individual" : "Relationship"}
            {probability}
          </span>
          <Chip variant={VERDICT_CHIP[verdict]} data-testid="review-inspector-status">
            {verdictLabel(operation)}
          </Chip>
        </div>
        {relationshipEnds ? (
          <RelationshipTitle
            operation={operation}
            ends={relationshipEnds}
            title={names.titleOf(operation)}
          />
        ) : (
          <>
            <h2 className="review-inspector__title" data-testid="review-inspector-title">
              {names.titleOf(operation)}
            </h2>
            <ClassPill classId={classId} size="lg" data-testid="review-inspector-class" />
          </>
        )}
        {gold && gold.aliases.length > 0 && (
          <span className="review-block__subtitle" data-testid="review-gold-aliases">
            Also called {gold.aliases.join(", ")}
          </span>
        )}
      </div>

      <div className="review-inspector__body">
        {operation.status === "failed" && (
          <div className="review-block">
            <div className="review-failed" role="alert" data-testid="review-failed">
              The last apply failed: {operation.reason ?? "no reason given"}
            </div>
          </div>
        )}

        {relationshipEnds && (
          <RelationshipBlock operation={operation} ends={relationshipEnds} schema={schema} />
        )}

        {evidence}

        {element && (
          <Block label="What the class means" data-testid="review-definition">
            <Eyebrow>WHAT THE CLASS MEANS</Eyebrow>
            {classesLoading ? (
              <p className="review-definition review-muted" data-testid="review-definition-loading">
                Loading…
              </p>
            ) : (
              <Definition key={classId} text={cls?.description} />
            )}
          </Block>
        )}

        {decided}
        <div id="review-change" className="review-change">
          {decide}
          {betterClass}
          {canDecide && relationshipEnds && (
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
          {reasons}
        </div>

        {element && (
          <Block label="Its relationships" data-testid="review-relationships">
            <Eyebrow>{`ITS RELATIONSHIPS · ${relationships.length}`}</Eyebrow>
            {deciding && onRejectRelationships && awaitingRelationships.length > 0 && (
              <FormCallout variant="warn" icon="alert" data-testid="review-relationships-callout">
                <span className="review-callout-action">
                  <span>
                    {awaitingRelationships.length === 1
                      ? "1 relationship uses it and still awaits a decision."
                      : `${awaitingRelationships.length} relationships use it and still await a decision.`}
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={busy}
                    onClick={onRejectRelationships}
                    data-testid="review-reject-relationships"
                  >
                    {awaitingRelationships.length === 1 ? "Reject it too" : "Reject them too"}
                  </Button>
                </span>
              </FormCallout>
            )}
            {relationships.length === 0 ? (
              <span className="review-muted">
                None proposed. Relationships are decided after their ends.
              </span>
            ) : (
              <ul className="review-relationships">
                {relationships.map((relationship) => (
                  <RelationshipRow
                    key={relationship.id}
                    relationship={relationship}
                    element={operation}
                    endOf={endOf}
                  />
                ))}
              </ul>
            )}
          </Block>
        )}

        {goldFooter}
      </div>
    </Panel>
  );
}

/**
 * One of an element's relationships: a card linking to it, read as a sentence
 * with "this" for the element ("Reference Check realizes → this", or "this
 * realizes → Paste Check"), its decision on the right, then the other end's class.
 */
function RelationshipRow({
  relationship,
  element,
  endOf,
}: {
  relationship: ProposedOperation;
  element: ProposedOperation;
  endOf: (value: unknown) => EndInfo;
}) {
  const fields = shownFields(relationship);
  const outgoing =
    endOf(fields.source_id).operationId === element.id ||
    endOf(relationship.fields?.source_id).operationId === element.id;
  const other = endOf(outgoing ? fields.target_id : fields.source_id);
  const verdict = verdictOf(relationship);
  const { href, onClick } = useOperationLink()(relationship.id);
  const predicate = (
    <PredicateTag propertyId={fields.property_definition_id as string | undefined} />
  );
  const name = <span className="review-relrow__name">{other.title}</span>;
  const self = <span className="review-relrow__self">this</span>;
  return (
    <li>
      <a
        className="review-relrow"
        href={href}
        onClick={onClick}
        data-direction={outgoing ? "out" : "in"}
        data-testid={`review-relationship-${relationship.id}`}
      >
        <span className="review-relrow__line">
          <span className="review-relrow__sentence">
            {outgoing ? (
              <>
                {self}
                {predicate}
                {name}
              </>
            ) : (
              <>
                {name}
                {predicate}
                {self}
              </>
            )}
          </span>
          <Chip variant={VERDICT_CHIP[verdict]}>{verdictLabel(relationship)}</Chip>
        </span>
        {other.classId && <ClassTag classId={other.classId} />}
      </a>
    </li>
  );
}
