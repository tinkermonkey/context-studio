import { useMemo, useState, type ReactNode } from "react";
import { Button, Chip, FormCallout, TextInput } from "@tinkermonkey/heimdall-ui";
import { Check } from "lucide-react";
import type { ProposedOperation } from "@/api/services/proposals";
import { ClassPill, ClassTag, Diamond, IndividualPill, PredicatePill } from "./ReviewPills";
import {
  VERDICT_CHIP,
  endEntityId,
  endOperation,
  relationshipEdit,
  shownFields,
  shownTitle,
  type Verdict,
} from "./reviewModel";
import type { ReviewSchema } from "./reviewSchema";

/** One end of a relationship, as the inspector shows it. */
export interface EndInfo {
  title: string;
  classId?: string;
  /** Its verdict when it is an element of this proposal; undefined for one already in the workspace. */
  verdict?: Verdict;
  /** "correct", "awaiting", … or "in the workspace". */
  status: string;
  /** The element's operation, when it is one of this proposal's. */
  operationId?: string;
  /** A passage of its evidence, for its hover card. */
  quote?: string;
  /** How many relationships of the proposal it is an end of. */
  relationships?: number;
}

/** An individual a relationship's end can be changed to. */
export interface EndCandidate {
  /** The individual's id in the workspace. */
  entityId: string;
  title: string;
  classId?: string;
  /** Its operation, when it is an element of this proposal. */
  operationId?: string;
  /** An element of this proposal not applied yet: picked, it is named by its "$ref". */
  pending?: boolean;
}

/** How many results a correction row lists. */
const RESULTS_SHOWN = 8;

type Ends = { source: EndInfo; target: EndInfo };

/** The property a relationship states now (an edit's over the proposed one). */
function propertyOf(operation: ProposedOperation): string | undefined {
  return shownFields(operation).property_definition_id as string | undefined;
}

/**
 * What doesn't fit when the relationship's ends don't fit its type ("source is
 * x; realizes needs y"), else undefined; undefined too while the schema loads.
 */
export function misfitOf(
  operation: ProposedOperation,
  ends: Ends,
  schema: ReviewSchema,
): string | undefined {
  const propertyId = propertyOf(operation);
  const property = schema.property(propertyId);
  if (!property || !ends.source.classId || !ends.target.classId) return undefined;
  const predicate = schema.predicateLabel(propertyId);
  const problems: string[] = [];
  if (!schema.fits(ends.source.classId, property.domain_class_id)) {
    problems.push(
      `source is ${schema.classLabel(ends.source.classId)}; ${predicate} needs ${schema.classLabel(property.domain_class_id)}`,
    );
  }
  if (!schema.fits(ends.target.classId, property.range_class_id)) {
    problems.push(
      `target is ${schema.classLabel(ends.target.classId)}; ${predicate} needs ${schema.classLabel(property.range_class_id)}`,
    );
  }
  return problems.length > 0 ? problems.join(" · ") : undefined;
}

/** The header's title: the relationship as a sentence, its predicate a pill. */
export function RelationshipTitle({
  operation,
  ends,
  title,
}: {
  operation: ProposedOperation;
  ends: Ends;
  /** "source predicate target", its accessible name. */
  title: string;
}) {
  return (
    <h2 className="review-head__sentence" aria-label={title} data-testid="review-inspector-title">
      <span>{ends.source.title}</span>
      <PredicatePill propertyId={propertyOf(operation)} data-testid="review-title-predicate" />
      <span>{ends.target.title}</span>
    </h2>
  );
}

/** One end: a bordered card, the individual and its decision, then its class. */
function EndCard({ role, end, testId }: { role: string; end: EndInfo; testId: string }) {
  return (
    <div className="review-rel__row" data-testid={testId}>
      <span className="review-rel__role">{role}</span>
      <div className="review-end-card">
        <div className="review-end-card__line">
          <IndividualPill
            title={end.title}
            classId={end.classId}
            status={end.status}
            verdict={end.verdict}
            quote={end.quote}
            relationships={end.relationships}
            operationId={end.operationId}
            data-testid={`${testId}-individual`}
          />
          {end.verdict ? (
            <Chip variant={VERDICT_CHIP[end.verdict]} data-testid={`${testId}-status`}>
              {end.status}
            </Chip>
          ) : (
            <span className="review-muted" data-testid={`${testId}-status`}>
              {end.status}
            </span>
          )}
        </div>
        {end.classId && <ClassPill classId={end.classId} data-testid={`${testId}-class`} />}
      </div>
    </div>
  );
}

/**
 * The relationship itself, read top to bottom: FROM its source, the
 * predicate between the ends (whether they fit the schema, and what it
 * means), TO its target.
 */
export function RelationshipBlock({
  operation,
  ends,
  schema,
}: {
  operation: ProposedOperation;
  ends: Ends;
  schema: ReviewSchema;
}) {
  const propertyId = propertyOf(operation);
  const misfit = misfitOf(operation, ends, schema);
  const known = !!schema.property(propertyId) && !!ends.source.classId && !!ends.target.classId;
  return (
    <section
      className="review-block review-rel"
      aria-label="The relationship"
      data-testid="review-relationship-block"
    >
      <EndCard role="FROM" end={ends.source} testId="review-end-source" />
      <div className="review-rel__row">
        <span />
        <div className="review-rel__link">
          <span className="review-rel__connector" aria-hidden="true" />
          <div className="review-rel__predicate" data-testid="review-predicate">
            {misfit ? (
              <div className="review-misfit" data-testid="review-ends-misfit" role="alert">
                <PredicatePill
                  propertyId={propertyId}
                  size="lg"
                  direction="down"
                  misfit
                  data-testid="review-predicate-pill"
                />
                <span className="review-misfit__text">{misfit}</span>
              </div>
            ) : (
              <div className="review-rel__fit">
                <PredicatePill
                  propertyId={propertyId}
                  size="lg"
                  direction="down"
                  data-testid="review-predicate-pill"
                />
                {known && (
                  <span className="review-fit" data-testid="review-ends-fit">
                    <Check size={12} strokeWidth={2.6} aria-hidden="true" />
                    both ends fit the schema
                  </span>
                )}
              </div>
            )}
            <p className="review-rel__definition" data-testid="review-predicate-definition">
              {schema.predicateDefinition(propertyId) ??
                (schema.loading ? "Loading…" : "No definition yet.")}
            </p>
          </div>
        </div>
      </div>
      <EndCard role="TO" end={ends.target} testId="review-end-target" />
    </section>
  );
}

type Field = "property_definition_id" | "source_id" | "target_id";
type Draft = Partial<Record<Field, string>>;

const ROW_LABEL: Record<Field, string> = {
  property_definition_id: "Predicate",
  source_id: "Source",
  target_id: "Target",
};
const ROW_KEY: Record<Field, string> = {
  property_definition_id: "predicate",
  source_id: "source",
  target_id: "target",
};

/** One row of Or correct it: its label, its value now, and Change (or Cancel, Undo). */
function CorrectionRow({
  field,
  value,
  changed,
  open,
  canChange,
  disabled,
  note,
  onToggle,
  onUndo,
  children,
}: {
  field: Field;
  value: ReactNode;
  changed: boolean;
  open: boolean;
  canChange: boolean;
  disabled: boolean;
  /** A line under the value: why it can't change. */
  note?: string;
  onToggle: () => void;
  onUndo: () => void;
  children?: ReactNode;
}) {
  const key = ROW_KEY[field];
  return (
    <div
      className={[
        "review-fix",
        open && "review-fix--open",
        changed && !open && "review-fix--changed",
      ]
        .filter(Boolean)
        .join(" ")}
      data-testid={`review-better-${key}`}
    >
      <div className="review-fix__line">
        <span className="review-fix__label" id={`review-fix-${key}-label`}>
          {ROW_LABEL[field]}
        </span>
        <span className="review-fix__value" data-testid={`review-draft-${key}`}>
          {value}
        </span>
        {changed && !open ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={onUndo}
            aria-label={`Keep the proposed ${key}`}
            data-testid={`review-draft-${key}-undo`}
          >
            Undo
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            disabled={disabled || !canChange}
            aria-expanded={open}
            aria-controls={`review-fix-${key}-panel`}
            onClick={onToggle}
            data-testid={`review-change-${key}`}
          >
            {open ? "Cancel" : "Change"}
          </Button>
        )}
      </div>
      {note && <span className="review-fix__note">{note}</span>}
      {open && (
        <div
          className="review-fix__panel"
          id={`review-fix-${key}-panel`}
          role="group"
          aria-labelledby={`review-fix-${key}-label`}
        >
          {children}
        </div>
      )}
    </div>
  );
}

/** The individuals an end can change to: a search over them, and the matches as a list. */
function EndChoices({
  role,
  candidates,
  current,
  hint,
  wanted,
  onPick,
}: {
  role: "source" | "target";
  candidates: EndCandidate[];
  /** The values the end holds now (a "$ref" and the id it stands for): not offered again. */
  current: (string | undefined)[];
  hint: ReactNode;
  /** The class the relationship type needs at this end, for the empty state. */
  wanted: string;
  onPick: (candidate: EndCandidate) => void;
}) {
  const [query, setQuery] = useState("");
  const offered = useMemo(
    () => candidates.filter((c) => !current.includes(c.entityId)),
    [candidates, current],
  );
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return offered
      .filter((c) => !needle || c.title.toLowerCase().includes(needle))
      .slice(0, RESULTS_SHOWN);
  }, [offered, query]);
  const inputId = `review-end-search-${role}`;
  return (
    <>
      <label htmlFor={inputId} className="review-fix__hint">
        {hint}
      </label>
      <TextInput
        id={inputId}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search individuals…"
        autoFocus
        data-testid={`review-end-search-${role}`}
      />
      {results.length > 0 ? (
        <ul className="review-results" aria-label={`Individuals for the ${role}`}>
          {results.map((c) => (
            <li key={c.entityId}>
              <button
                type="button"
                className="review-result"
                onClick={() => onPick(c)}
                data-testid={`review-end-option-${role}`}
              >
                <span className="review-result__name">{c.title}</span>
                {c.classId && <ClassTag classId={c.classId} />}
                {c.operationId && (
                  <span className="review-muted review-result__where">
                    {c.pending ? "in this proposal, awaiting" : "in this proposal"}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        // Why nothing is listed: nothing of the class the type needs, or nothing by that text.
        <span className="review-fix__hint" data-testid={`review-end-empty-${role}`}>
          {offered.length === 0
            ? `No ${wanted} individual is in this proposal or the dataset.`
            : `No ${wanted} individual matches “${query.trim()}”.`}
        </span>
      )}
    </>
  );
}

/** An end as the editor holds it: its value (an id or a "$ref") and how it reads. */
interface EndValue {
  value: string | undefined;
  title: string;
  classId?: string;
  /** An element of this proposal not applied yet. */
  pending?: boolean;
  operationId?: string;
}

/**
 * Or correct it: the predicate, source and target in three rows of one shape,
 * and Reverse. Change opens a row: the predicates the schema allows between the
 * ends' classes, or the individuals of a class the type allows: this
 * proposal's elements that aren't rejected (a pending one by its "$ref") and
 * the dataset's. Reverse swaps the ends; when the predicate doesn't allow the
 * reversed direction it offers the predicates that do. The changes collect
 * into a draft, accepted together.
 */
export function RelationshipEditor({
  operation,
  operations,
  ends,
  candidates,
  schema,
  busy,
  onAccept,
}: {
  operation: ProposedOperation;
  operations: ProposedOperation[];
  ends: Ends;
  candidates: EndCandidate[];
  schema: ReviewSchema;
  busy: boolean;
  onAccept: (edit: Record<string, string>) => void;
}) {
  const [draft, setDraft] = useState<Draft>({});
  // How each end the draft holds reads (picked from the list, or swapped by Reverse).
  const [picked, setPicked] = useState<Partial<Record<"source_id" | "target_id", EndValue>>>({});
  const [open, setOpen] = useState<Field>();
  const proposed = shownFields(operation);
  const proposedProperty = proposed.property_definition_id as string;
  const propertyId = draft.property_definition_id ?? proposedProperty;
  /** An end now: the draft's, else the proposed one. */
  const endNow = (role: "source" | "target"): EndValue => {
    const field = `${role}_id` as const;
    if (draft[field]) return picked[field] ?? { value: draft[field], title: draft[field]! };
    const value = proposed[field] as string | undefined;
    const create = endOperation(value, operations);
    return {
      value,
      title: ends[role].title,
      classId: ends[role].classId,
      operationId: create?.id,
      pending: !!create && create.status !== "applied",
    };
  };
  const source = endNow("source");
  const target = endNow("target");
  const sourceClass = source.classId;
  const targetClass = target.classId;
  const property = schema.property(propertyId);
  const others = schema.allowedTypes(sourceClass, targetClass).filter((p) => p.id !== propertyId);
  const fitting = (role: "source" | "target") =>
    candidates.filter((c) =>
      schema.fits(
        c.classId,
        role === "source" ? property?.domain_class_id : property?.range_class_id,
      ),
    );
  const edit = relationshipEdit(operation, operations, draft);
  // The draft's ends don't fit its predicate (after Reverse, or another end): it can't apply.
  const misfit =
    !!edit &&
    !!property &&
    !schema.loading &&
    (!schema.fits(sourceClass, property.domain_class_id) ||
      !schema.fits(targetClass, property.range_class_id));
  // An end the draft names among this proposal's elements that hasn't applied: decide it
  // first, or, when it was rejected (a proposed end Reverse kept), pick another.
  const unapplied = [draft.source_id ? source : undefined, draft.target_id ? target : undefined]
    .filter((end): end is EndValue => !!end?.pending)
    .map((end) => operations.find((o) => o.id === end.operationId))
    .filter((o): o is ProposedOperation => !!o);
  const rejectedPick = unapplied.filter((o) => o.status === "rejected");
  const pendingPick = unapplied.filter((o) => o.status !== "rejected");
  const set = (field: Field, value: string | undefined) => {
    setDraft((d) => ({ ...d, [field]: value }));
    setOpen(undefined);
  };
  const pick = (role: "source" | "target", c: EndCandidate) => {
    setPicked((p) => ({ ...p, [`${role}_id`]: { value: c.entityId, ...c } }));
    set(`${role}_id`, c.entityId);
  };
  const toggle = (field: Field) => setOpen((o) => (o === field ? undefined : field));
  /** Swap the ends in the draft; back to the proposed ends when swapped twice. */
  const reverse = () => {
    const swapped = { source_id: target, target_id: source };
    setPicked((p) => ({ ...p, ...swapped }));
    setDraft((d) => ({ ...d, source_id: target.value, target_id: source.value }));
    // When the predicate doesn't allow the reversed direction, open its row on the ones that do.
    const reversedFits =
      !property ||
      (schema.fits(target.classId, property.domain_class_id) &&
        schema.fits(source.classId, property.range_class_id));
    const reversedOthers = schema
      .allowedTypes(target.classId, source.classId)
      .filter((p) => p.id !== propertyId);
    setOpen(reversedFits || reversedOthers.length === 0 ? undefined : "property_definition_id");
  };
  const reversed =
    !!draft.source_id &&
    !!draft.target_id &&
    draft.source_id === (proposed.target_id as string) &&
    draft.target_id === (proposed.source_id as string);

  const endValue = (role: "source" | "target") => (
    <span className="review-fix__name">{(role === "source" ? source : target).title}</span>
  );
  const wantedLabel = (role: "source" | "target") => {
    const wanted = role === "source" ? property?.domain_class_id : property?.range_class_id;
    return wanted ? schema.classLabel(wanted) : "";
  };
  const endHint = (role: "source" | "target") => {
    const wanted = wantedLabel(role);
    const count = fitting(role).length;
    return (
      <>
        {count} {wanted || "any class"} {count === 1 ? "individual" : "individuals"}, in this
        proposal or the dataset
      </>
    );
  };

  return (
    <section
      className="review-block"
      aria-labelledby="review-correct-it-title"
      data-testid="review-relationship-editor"
    >
      <div className="review-block__head">
        <div className="review-block__title">
          <span id="review-correct-it-title" className="review-eyebrow">
            OR CORRECT IT
          </span>
          <span className="review-block__subtitle">
            Change any of the three, or reverse it, then accept. Choices are only what the schema
            allows.
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          disabled={busy}
          aria-pressed={reversed}
          onClick={reverse}
          data-testid="review-reverse"
        >
          ⇄ Reverse
        </Button>
      </div>

      <CorrectionRow
        field="property_definition_id"
        value={
          <PredicatePill
            propertyId={propertyId}
            size="sm"
            data-testid="review-draft-predicate-pill"
          />
        }
        changed={!!draft.property_definition_id}
        open={open === "property_definition_id"}
        canChange={others.length > 0}
        disabled={busy}
        note={
          others.length === 0 && open !== "property_definition_id"
            ? schema.loading
              ? "Loading the schema…"
              : `No other predicate is allowed from ${schema.classLabel(sourceClass)} to ${schema.classLabel(targetClass)}.`
            : undefined
        }
        onToggle={() => toggle("property_definition_id")}
        onUndo={() => set("property_definition_id", undefined)}
      >
        <span className="review-fix__hint">
          {others.length} allowed from {schema.classLabel(sourceClass)} to{" "}
          {schema.classLabel(targetClass)}
        </span>
        <ul className="review-results" aria-label="Predicates allowed">
          {others.map((type, i) => (
            <li key={type.id}>
              <button
                type="button"
                className="review-result review-result--predicate"
                onClick={() => set("property_definition_id", type.id)}
                data-testid={`review-predicate-option-${i + 1}`}
              >
                <span className="review-result__predicate">
                  <span className="review-pill review-pill--predicate review-pill--sm">
                    <span className="review-pill__text">{schema.predicateLabel(type.id)} →</span>
                  </span>
                  <span className="review-result__classes">
                    <Diamond /> {schema.classLabel(type.range_class_id)}
                  </span>
                </span>
                {schema.predicateDefinition(type.id) && (
                  <span className="review-result__definition">
                    {schema.predicateDefinition(type.id)}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </CorrectionRow>

      {(["source", "target"] as const).map((role) => (
        <CorrectionRow
          key={role}
          field={`${role}_id`}
          value={endValue(role)}
          changed={!!draft[`${role}_id`]}
          open={open === `${role}_id`}
          canChange
          disabled={busy}
          onToggle={() => toggle(`${role}_id`)}
          onUndo={() => set(`${role}_id`, undefined)}
        >
          <EndChoices
            role={role}
            candidates={fitting(role)}
            current={[
              (role === "source" ? source : target).value,
              endEntityId((role === "source" ? source : target).value, operations),
            ]}
            hint={endHint(role)}
            wanted={wantedLabel(role)}
            onPick={(c) => pick(role, c)}
          />
        </CorrectionRow>
      ))}

      {misfit && (
        <FormCallout variant="warn" icon="alert" data-testid="review-editor-misfit">
          {others.length > 0
            ? `${schema.predicateLabel(propertyId)} isn't allowed from ${schema.classLabel(sourceClass)} to ${schema.classLabel(targetClass)}. Pick one of the ${others.length} that are, above.`
            : `No predicate is allowed from ${schema.classLabel(sourceClass)} to ${schema.classLabel(targetClass)}.`}
        </FormCallout>
      )}
      {rejectedPick.length > 0 && (
        <FormCallout variant="warn" icon="alert" data-testid="review-editor-rejected-end">
          {`${rejectedPick.map((o) => `#${o.seq} ${shownTitle(o)}`).join(" and ")} ${rejectedPick.length === 1 ? "was" : "were"} rejected: pick ${rejectedPick.length === 1 ? "another end" : "other ends"}.`}
        </FormCallout>
      )}
      {pendingPick.length > 0 && (
        <FormCallout variant="info" icon="info" data-testid="review-editor-pending">
          {`Decide ${pendingPick.map((o) => `#${o.seq} ${shownTitle(o)}`).join(" and ")} first: ${pendingPick.length === 1 ? "this end follows its choice" : "these ends follow their choices"}.`}
        </FormCallout>
      )}

      <div className="review-block__end">
        <Button
          variant="secondary"
          size="sm"
          disabled={busy || !edit || misfit || pendingPick.length > 0}
          onClick={() => edit && onAccept(edit)}
          data-testid="review-accept-edited"
        >
          Accept with these changes
        </Button>
      </div>
    </section>
  );
}
