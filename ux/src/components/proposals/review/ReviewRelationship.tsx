import { useMemo, useState, type ReactNode } from "react";
import { Button, EntityPicker, FormCallout } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { ClassPill, IndividualPill, PredicatePill } from "./ReviewPills";
import { endEntityId, relationshipEdit, shownFields, type Verdict } from "./reviewModel";
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
}

/** An individual a relationship's end can be changed to. */
export interface EndCandidate {
  /** The individual's id in the workspace. */
  entityId: string;
  title: string;
  classId?: string;
  /** Its operation, when this proposal created it. */
  operationId?: string;
}

/** How many matches an end's search lists. */
const MATCHES_SHOWN = 20;
/** How many other relationship types are listed before the rest are left out. */
const TYPES_LISTED = 12;

/** One end of the relationship: the individual (primary), its class, and its decision. */
function TripleEnd({ role, end, testId }: { role: string; end: EndInfo; testId: string }) {
  return (
    <div className="review-triple__row" data-testid={testId}>
      <span className="review-triple__role">{role}</span>
      <span className="review-triple__end">
        <IndividualPill
          size="lg"
          title={end.title}
          classId={end.classId}
          status={end.status}
          verdict={end.verdict}
          operationId={end.operationId}
          data-testid={`${testId}-individual`}
        />
        {end.classId && <ClassPill classId={end.classId} data-testid={`${testId}-class`} />}
      </span>
    </div>
  );
}

/**
 * The relationship itself, read top to bottom: From its source (an individual
 * and its class), the predicate it states, To its target. The inspector's
 * header for a relationship.
 */
export function RelationshipTriple({
  operation,
  ends,
  title,
}: {
  operation: ProposedOperation;
  ends: { source: EndInfo; target: EndInfo };
  /** "source predicate target", the triple's accessible name. */
  title: string;
}) {
  const propertyId = shownFields(operation).property_definition_id as string | undefined;
  return (
    <div
      className="review-triple"
      role="group"
      aria-label={title}
      data-testid="review-inspector-title"
    >
      <TripleEnd role="From" end={ends.source} testId="review-end-source" />
      <div className="review-triple__row review-triple__row--predicate">
        <span className="review-triple__rail" aria-hidden="true" />
        <PredicatePill propertyId={propertyId} size="lg" data-testid="review-predicate-pill" />
      </div>
      <TripleEnd role="To" end={ends.target} testId="review-end-target" />
    </div>
  );
}

/** What the relationship's predicate means, and the classes its type allows. */
export function PredicateMeaning({
  operation,
  schema,
}: {
  operation: ProposedOperation;
  schema: ReviewSchema;
}) {
  const propertyId = shownFields(operation).property_definition_id as string | undefined;
  const property = schema.property(propertyId);
  return (
    <div className="review-section" data-testid="review-predicate">
      <span className="review-eyebrow">{`What ${schema.predicateLabel(propertyId)} means`}</span>
      <p className="review-definition" data-testid="review-predicate-definition">
        {schema.predicateDefinition(propertyId) ??
          (schema.loading ? "Loading…" : "No definition yet.")}
      </p>
      {property && (
        <div className="review-chips" data-testid="review-predicate-allowed">
          <span className="review-muted">Allowed from</span>
          {property.domain_class_id ? (
            <ClassPill classId={property.domain_class_id} />
          ) : (
            <span className="review-muted">any class</span>
          )}
          <span className="review-muted">to</span>
          {property.range_class_id ? (
            <ClassPill classId={property.range_class_id} />
          ) : (
            <span className="review-muted">any class</span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Whether the relationship's ends fit its type: undefined while the schema
 * loads or the type is unknown.
 */
export function endsFit(
  operation: ProposedOperation,
  ends: { source: EndInfo; target: EndInfo },
  schema: ReviewSchema,
): boolean | undefined {
  const property = schema.property(
    shownFields(operation).property_definition_id as string | undefined,
  );
  if (!property || !ends.source.classId || !ends.target.classId) return undefined;
  return (
    schema.fits(ends.source.classId, property.domain_class_id) &&
    schema.fits(ends.target.classId, property.range_class_id)
  );
}

type Draft = { property_definition_id?: string; source_id?: string; target_id?: string };

/** One of the three alternatives: a heading, what it offers, then its controls. */
function Alternative({
  id,
  title,
  note,
  children,
  "data-testid": testId,
}: {
  id: string;
  title: string;
  note: ReactNode;
  children: ReactNode;
  "data-testid": string;
}) {
  return (
    <section className="review-alternative" aria-labelledby={id} data-testid={testId}>
      <span id={id} className="review-eyebrow">
        {title}
      </span>
      <span className="review-alternative__note">{note}</span>
      {children}
    </section>
  );
}

/** Search the end candidates of one role, and pick one. */
function EndSearch({
  role,
  candidates,
  current,
  disabled,
  onPick,
}: {
  role: "source" | "target";
  candidates: EndCandidate[];
  current?: string;
  disabled: boolean;
  onPick: (candidate: EndCandidate) => void;
}) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return candidates
      .filter((c) => c.entityId !== current && c.title.toLowerCase().includes(needle))
      .slice(0, MATCHES_SHOWN)
      .map((c) => ({ id: c.entityId, label: c.title }));
  }, [candidates, current, query]);
  return (
    <EntityPicker
      inputId={`review-end-search-${role}`}
      query={query}
      onQueryChange={setQuery}
      results={results}
      onSelect={(result) => {
        setQuery("");
        const picked = candidates.find((c) => c.entityId === result.id);
        if (picked) onPick(picked);
      }}
      onClear={() => setQuery("")}
      placeholder="Search individuals…"
      placement="top-start"
      disabled={disabled || candidates.length === 0}
    />
  );
}

/**
 * A better predicate, source or target for a relationship: the predicates the
 * schema allows between the ends' classes, and for each end the individuals
 * (of this proposal, accepted, or already in the dataset) of a class the
 * chosen type allows. Three alternatives of one shape; the changes collect
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
  ends: { source: EndInfo; target: EndInfo };
  candidates: EndCandidate[];
  schema: ReviewSchema;
  busy: boolean;
  onAccept: (edit: Record<string, string>) => void;
}) {
  const [draft, setDraft] = useState<Draft>({});
  const proposed = shownFields(operation);
  const propertyId = draft.property_definition_id ?? (proposed.property_definition_id as string);
  const byId = new Map(candidates.map((c) => [c.entityId, c]));
  const sourceId = draft.source_id ?? endEntityId(proposed.source_id, operations);
  const targetId = draft.target_id ?? endEntityId(proposed.target_id, operations);
  const sourceClass = draft.source_id ? byId.get(draft.source_id)?.classId : ends.source.classId;
  const targetClass = draft.target_id ? byId.get(draft.target_id)?.classId : ends.target.classId;
  const property = schema.property(propertyId);
  const types = schema.allowedTypes(sourceClass, targetClass);
  const others = types.filter((p) => p.id !== (proposed.property_definition_id as string));
  const fitting = (role: "source" | "target") =>
    candidates.filter((c) =>
      schema.fits(
        c.classId,
        role === "source" ? property?.domain_class_id : property?.range_class_id,
      ),
    );
  const edit = relationshipEdit(operation, operations, draft);
  const predicate = schema.predicateLabel(propertyId);

  const endNote = (role: "source" | "target") => {
    const wanted = role === "source" ? property?.domain_class_id : property?.range_class_id;
    const count = fitting(role).length;
    return (
      <>
        {count} {count === 1 ? "individual" : "individuals"} of{" "}
        {wanted ? schema.classLabel(wanted) : "any class"}, the {role} {predicate} allows
      </>
    );
  };

  const chosenEnd = (role: "source" | "target") => {
    const id = draft[`${role}_id`];
    const picked = id ? byId.get(id) : undefined;
    if (!picked) return null;
    return (
      <div className="review-alternative__pick" data-testid={`review-draft-${role}`}>
        <span className="review-muted">Your pick</span>
        <IndividualPill
          title={picked.title}
          classId={picked.classId}
          operationId={picked.operationId}
        />
        {picked.classId && <ClassPill classId={picked.classId} />}
        <button
          type="button"
          className="review-link"
          onClick={() => setDraft((d) => ({ ...d, [`${role}_id`]: undefined }))}
          aria-label={`Keep the proposed ${role}`}
          data-testid={`review-draft-${role}-undo`}
        >
          Undo
        </button>
      </div>
    );
  };

  return (
    <div className="review-alternatives" data-testid="review-relationship-editor">
      <Alternative
        id="review-better-predicate-title"
        title="Or a better predicate"
        note={
          <>
            Those the schema allows from {schema.classLabel(sourceClass)} to{" "}
            {schema.classLabel(targetClass)}
          </>
        }
        data-testid="review-better-predicate"
      >
        {others.length === 0 ? (
          <span className="review-muted" data-testid="review-predicate-none">
            {schema.loading
              ? "Loading the schema…"
              : "The schema allows no other predicate between these classes."}
          </span>
        ) : (
          <div
            className="review-alternative__options"
            role="group"
            aria-labelledby="review-better-predicate-title"
          >
            {others.slice(0, TYPES_LISTED).map((type, i) => {
              const pressed = draft.property_definition_id === type.id;
              return (
                <button
                  key={type.id}
                  type="button"
                  className={["review-alt", pressed && "review-alt--pressed"]
                    .filter(Boolean)
                    .join(" ")}
                  aria-pressed={pressed}
                  disabled={busy}
                  onClick={() =>
                    setDraft((d) => ({
                      ...d,
                      property_definition_id: pressed ? undefined : type.id,
                    }))
                  }
                  data-testid={`review-predicate-option-${i + 1}`}
                >
                  <span className="review-alt__class">
                    {schema.predicateLabel(type.id)} · {schema.classLabel(type.domain_class_id)} →{" "}
                    {schema.classLabel(type.range_class_id)}
                  </span>
                  {schema.predicateDefinition(type.id) && (
                    <span className="review-alt__definition">
                      {schema.predicateDefinition(type.id)}
                    </span>
                  )}
                </button>
              );
            })}
            {others.length > TYPES_LISTED && (
              <span className="review-muted">and {others.length - TYPES_LISTED} more</span>
            )}
          </div>
        )}
      </Alternative>

      {(["source", "target"] as const).map((role) => (
        <Alternative
          key={role}
          id={`review-better-${role}-title`}
          title={`Or a better ${role}`}
          note={endNote(role)}
          data-testid={`review-better-${role}`}
        >
          <EndSearch
            role={role}
            candidates={fitting(role)}
            current={role === "source" ? sourceId : targetId}
            disabled={busy}
            onPick={(c) => setDraft((d) => ({ ...d, [`${role}_id`]: c.entityId }))}
          />
          {chosenEnd(role)}
        </Alternative>
      ))}

      <div className="review-alternatives__footer">
        <span className="review-muted">
          Ends are individuals of this proposal that are accepted, or already in the dataset.
        </span>
        <div className="review-chips">
          <Button
            variant="primary"
            size="sm"
            disabled={busy || !edit}
            onClick={() => edit && onAccept(edit)}
            data-testid="review-accept-edited"
          >
            Accept with these changes
          </Button>
          {Object.values(draft).some(Boolean) && (
            <button
              type="button"
              className="review-link"
              onClick={() => setDraft({})}
              data-testid="review-draft-clear"
            >
              Clear changes
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/** A warning that the relationship's ends don't fit its type (after a class changed, say). */
export function EndsMisfit({
  schema,
  operation,
}: {
  schema: ReviewSchema;
  operation: ProposedOperation;
}) {
  const propertyId = shownFields(operation).property_definition_id as string | undefined;
  const property = schema.property(propertyId);
  return (
    <FormCallout variant="warn" icon="alert" data-testid="review-ends-misfit">
      Its ends don&apos;t fit {schema.predicateLabel(propertyId)} (from{" "}
      {schema.classLabel(property?.domain_class_id)} to{" "}
      {schema.classLabel(property?.range_class_id)}
      ), so it can&apos;t apply as it is. Choose a better predicate or end, or reject it.
    </FormCallout>
  );
}
