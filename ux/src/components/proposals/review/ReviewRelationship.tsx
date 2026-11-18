import { useMemo, useState } from "react";
import { Button, Chip, EntityPicker } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { ClassPill, IndividualPill, PredicatePill } from "./ReviewPills";
import {
  VERDICT_CHIP,
  endEntityId,
  relationshipEdit,
  shownFields,
  type Verdict,
} from "./reviewModel";
import type { ReviewSchema } from "./reviewSchema";

/** One end of a relationship, as the inspector shows it. */
export interface EndInfo {
  title: string;
  classId?: string;
  /** Its verdict when it is an element of this proposal; undefined for one already in the workspace. */
  verdict?: Verdict;
  /** "accepted", "awaiting", … or "in the workspace". */
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

function Eyebrow({ children }: { children: string }) {
  return <span className="review-eyebrow">{children}</span>;
}

function EndRow({ role, end, testId }: { role: string; end: EndInfo; testId: string }) {
  return (
    <div className="review-end" data-testid={testId}>
      <span className="review-end__role">{role}</span>
      <span className="review-end__pills">
        <IndividualPill
          title={end.title}
          classId={end.classId}
          status={end.status}
          operationId={end.operationId}
          data-testid={`${testId}-individual`}
        />
        {end.classId && <ClassPill classId={end.classId} data-testid={`${testId}-class`} />}
        {end.verdict ? (
          <Chip variant={VERDICT_CHIP[end.verdict]} data-testid={`${testId}-status`}>
            {end.status}
          </Chip>
        ) : (
          <span className="review-muted" data-testid={`${testId}-status`}>
            {end.status}
          </span>
        )}
      </span>
    </div>
  );
}

/**
 * A relationship's ends (each individual with its class and decision), its
 * predicate with what it means, and the classes its type allows.
 */
export function RelationshipDetails({
  operation,
  ends,
  schema,
}: {
  operation: ProposedOperation;
  ends: { source: EndInfo; target: EndInfo };
  schema: ReviewSchema;
}) {
  const propertyId = shownFields(operation).property_definition_id as string | undefined;
  const property = schema.property(propertyId);
  return (
    <>
      <div className="review-section" data-testid="review-relationship-ends">
        <Eyebrow>Ends</Eyebrow>
        <EndRow role="From" end={ends.source} testId="review-end-source" />
        <EndRow role="To" end={ends.target} testId="review-end-target" />
      </div>
      <div className="review-section" data-testid="review-predicate">
        <Eyebrow>{`What ${schema.predicateLabel(propertyId)} means`}</Eyebrow>
        <div className="review-chips">
          <PredicatePill propertyId={propertyId} data-testid="review-predicate-pill" />
          {property && <span className="review-muted">{property.title}</span>}
        </div>
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
    </>
  );
}

type Draft = { property_definition_id?: string; source_id?: string; target_id?: string };

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
  const inputId = `review-end-search-${role}`;
  return (
    <div className="review-section" data-testid={`review-better-${role}`}>
      <label htmlFor={inputId} className="review-muted">
        {`Or a better ${role} · ${candidates.length} that fit`}
      </label>
      <EntityPicker
        inputId={inputId}
        query={query}
        onQueryChange={setQuery}
        results={results}
        onSelect={(result) => {
          setQuery("");
          const picked = candidates.find((c) => c.entityId === result.id);
          if (picked) onPick(picked);
        }}
        onClear={() => setQuery("")}
        placeholder={`Search individuals…`}
        placement="top-start"
        disabled={disabled || candidates.length === 0}
      />
    </div>
  );
}

/**
 * A better predicate, source or target for a relationship: the predicates the
 * schema allows between the ends' classes, and for each end the individuals
 * (of this proposal, accepted, or already in the dataset) of a class the
 * chosen type allows. The changes collect into a draft, accepted together.
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

  const chosenEnd = (role: "source" | "target") => {
    const id = draft[`${role}_id`];
    const picked = id ? byId.get(id) : undefined;
    if (!picked) return null;
    return (
      <div className="review-chips" data-testid={`review-draft-${role}`}>
        <span className="review-muted">{role === "source" ? "From" : "To"}</span>
        <IndividualPill
          title={picked.title}
          classId={picked.classId}
          status="your pick"
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
    <div className="review-section" data-testid="review-relationship-editor">
      <span className="review-eyebrow">Or a better predicate</span>
      {others.length === 0 ? (
        <span className="review-muted" data-testid="review-predicate-none">
          {schema.loading
            ? "Loading the schema…"
            : "The schema allows no other predicate between these classes."}
        </span>
      ) : (
        <div className="review-section" role="group" aria-label="Better predicate">
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
      <EndSearch
        role="source"
        candidates={fitting("source")}
        current={sourceId}
        disabled={busy}
        onPick={(c) => setDraft((d) => ({ ...d, source_id: c.entityId }))}
      />
      {chosenEnd("source")}
      <EndSearch
        role="target"
        candidates={fitting("target")}
        current={targetId}
        disabled={busy}
        onPick={(c) => setDraft((d) => ({ ...d, target_id: c.entityId }))}
      />
      {chosenEnd("target")}
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
        {Object.keys(draft).some((k) => draft[k as keyof Draft]) && (
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
  );
}
