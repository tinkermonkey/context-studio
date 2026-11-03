import { useMemo, useState } from "react";
import { Button, Field, FormCallout, SegmentedControl, TextInput } from "@tinkermonkey/heimdall-ui";
import { useTaxonomyClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { ApiError } from "@/api/client/interceptors";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import type { components } from "@/api/types";
import {
  checkDrTriple,
  decisionPreview,
  drEditFields,
  drPredicateCatalog,
  drSpecOf,
  drTripleId,
  drTriplesOf,
  hasTripleErrors,
  sameDrTriple,
  type DrTriple,
} from "./decisionModel";
import type { TripleSource } from "./proposalModel";
import type { Edits } from "./useProposalActions";
import "./proposals.css";

type Taxonomy = components["schemas"]["TaxonomyResponse"];
type Part = keyof DrTriple;

const PARTS: { part: Part; label: string; hint: string }[] = [
  { part: "source", label: "Source", hint: "a dr_spec class" },
  { part: "predicate", label: "Predicate", hint: "from the catalog" },
  { part: "destination", label: "Destination", hint: "a dr_spec class" },
];

/** Server reasons an edited apply records on the operation (it stays open). */
const EDIT_FAILURE = /^(invalid_edit|refused): /;

/** A triple; with `compareTo`, the parts that differ from it are highlighted. */
function TripleText({ triple, compareTo }: { triple?: DrTriple; compareTo?: DrTriple }) {
  if (!triple) return <span className="op-edit__muted">unknown</span>;
  const changed = (part: Part) =>
    compareTo && compareTo[part] !== triple[part] ? "op-diff__changed" : undefined;
  return (
    <span>
      <span className={changed("source")}>{triple.source}</span>{" "}
      <span className={changed("predicate") ?? "op-edit__muted"}>{triple.predicate}</span>{" "}
      <span className={changed("destination")}>{triple.destination}</span>
    </span>
  );
}

interface DrTripleEditorProps {
  operation: ProposedOperation;
  proposal: ChangeProposal;
  taxonomy: Taxonomy;
  /** The target property definition as it stands now, once loaded. */
  current?: TripleSource;
  /** Apply the operation with these edits (undefined: as proposed). */
  onApply: (edits?: Edits) => Promise<{ error?: unknown }>;
  onCancel: () => void;
  busy?: boolean;
}

/**
 * Accept with edit for a DR relationship type: an update's source, predicate
 * and destination, or a replacement triple for a delete (which then applies
 * as an update). The edit is checked as it is typed against dr_spec's
 * classes, its predicate catalog and the relationship types that exist; the
 * server checks again, and its refusal shows here until the next change.
 */
export function DrTripleEditor({
  operation,
  proposal,
  taxonomy,
  current,
  onApply,
  onCancel,
  busy,
}: DrTripleEditorProps) {
  const isDelete = operation.op === "delete";
  const { classes, isError: classesFailed } = useTaxonomyClasses(taxonomy.id);
  const spec = useMemo(
    () => (classes ? drSpecOf(classes, drPredicateCatalog(taxonomy)) : undefined),
    [classes, taxonomy],
  );
  const triples = useMemo(
    () => (spec ? drTriplesOf(operation, spec, current) : {}),
    [spec, operation, current],
  );
  const start = isDelete ? triples.current : triples.proposed;

  const [mode, setMode] = useState<"replace" | "delete">("replace");
  const [draft, setDraft] = useState<DrTriple | undefined>();
  const [serverError, setServerError] = useState<string | undefined>();
  const [showReason, setShowReason] = useState(false);
  const values: DrTriple = draft ?? start ?? { source: "", predicate: "", destination: "" };
  const replacing = !isDelete || mode === "replace";

  const sourceClassId = spec?.classIdByNode.get(values.source);
  const { data: fromSource } = useProperties(
    undefined,
    { domain_class_id: sourceClassId, limit: 500 },
    { enabled: !!sourceClassId },
  );

  const errors =
    spec && replacing
      ? checkDrTriple(values, spec, {
          existing: fromSource?.items,
          operation,
          others: proposal.operations,
          current: triples.current,
        })
      : {};
  // An update edited back to the proposed triple applies as proposed (no edit).
  const edited = replacing && !(isDelete ? false : sameDrTriple(values, triples.proposed));
  const blocked = !spec || (replacing && hasTripleErrors(errors)) || busy;

  // The server's refusal of the last apply, until the reviewer changes something.
  const reason = operation.reason ?? "";
  const shownServerError =
    serverError ?? (showReason && EDIT_FAILURE.test(reason) ? reason : undefined);

  const change = (part: Part) => (event: React.ChangeEvent<HTMLInputElement>) => {
    setDraft({ ...values, [part]: event.target.value.trim() });
    setServerError(undefined);
    setShowReason(false);
  };

  const apply = async () => {
    if (blocked || !spec) return;
    setServerError(undefined);
    const edits = edited ? { [operation.id]: drEditFields(values, spec) } : undefined;
    const { error } = await onApply(edits);
    if (error) setServerError(error instanceof ApiError ? error.detail : String(error));
    else setShowReason(true);
  };

  const preview =
    replacing && hasTripleErrors(errors)
      ? `Nothing yet: fix the ${isDelete ? "replacement" : "edit"} to apply it.`
      : JSON.stringify(decisionPreview(operation, edited ? values : undefined), null, 2);

  const classOptions = spec ? [...spec.classIdByNode.keys()].sort() : [];
  const predicateOptions = spec?.predicates ? [...spec.predicates].sort() : [];
  const listId = (part: Part) =>
    part === "predicate" ? `op-edit-predicates-${operation.id}` : `op-edit-classes-${operation.id}`;

  return (
    <div className="op-edit" data-testid="operation-edit-panel">
      <dl className="op-edit__triples" data-testid="operation-edit-triples">
        <dt>Current</dt>
        <dd className="op-edit__muted">
          <TripleText triple={triples.current} />
        </dd>
        {isDelete ? (
          <>
            <dt>Proposed</dt>
            <dd className="op-edit__removed">remove it</dd>
          </>
        ) : (
          <>
            <dt>Proposed</dt>
            <dd className={edited ? "op-edit__superseded" : undefined}>
              <TripleText triple={triples.proposed} />
            </dd>
          </>
        )}
        {replacing && (
          <>
            <dt className="op-edit__yours">Your edit</dt>
            <dd data-testid="operation-edit-yours">
              <TripleText
                triple={values}
                compareTo={isDelete ? triples.current : triples.proposed}
              />
            </dd>
          </>
        )}
      </dl>

      {isDelete && (
        <SegmentedControl
          value={mode}
          onChange={(v) => {
            setMode(v as "replace" | "delete");
            setServerError(undefined);
          }}
          options={[
            { value: "delete", label: "Delete as proposed" },
            { value: "replace", label: "Replace with another triple" },
          ]}
          aria-label="Delete or replace"
          data-testid="operation-edit-mode"
        />
      )}

      {classesFailed && (
        <FormCallout variant="error" icon="alert">
          Couldn't load the dr_spec classes to check the edit.
        </FormCallout>
      )}

      {replacing && (
        <div className="op-edit__fields">
          {PARTS.map(({ part, label, hint }) => {
            const id = `op-edit-${part}-${operation.id}`;
            return (
              <Field
                key={part}
                label={label}
                hint={hint}
                htmlFor={id}
                error={errors[part]}
                errorId={`${id}-error`}
              >
                <TextInput
                  id={id}
                  mono
                  value={values[part]}
                  onChange={change(part)}
                  error={!!errors[part]}
                  list={listId(part)}
                  disabled={!spec}
                  aria-invalid={!!errors[part]}
                  aria-describedby={errors[part] ? `${id}-error` : undefined}
                  data-testid={`operation-edit-${part}`}
                />
              </Field>
            );
          })}
          <datalist id={listId("source")}>
            {classOptions.map((node) => (
              <option key={node} value={node} />
            ))}
          </datalist>
          <datalist id={listId("predicate")}>
            {predicateOptions.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </div>
      )}

      {replacing && errors.triple && (
        <FormCallout variant="error" icon="alert" data-testid="operation-edit-triple-error">
          {errors.triple}
        </FormCallout>
      )}
      {shownServerError && (
        <FormCallout variant="error" icon="alert" data-testid="operation-edit-server-error">
          {`Not applied: ${shownServerError}`}
        </FormCallout>
      )}
      {replacing && spec && !hasTripleErrors(errors) && edited && (
        <FormCallout variant="info" icon="info" data-testid="operation-edit-valid">
          {isDelete
            ? `Valid. Applies as an update: the relationship type keeps its history and becomes ${drTripleId(values)}, instead of being removed.`
            : `Valid. Applies ${drTripleId(values)} instead of the proposed triple.`}
        </FormCallout>
      )}

      <div className="op-decision__actions">
        <Button
          variant={replacing ? "primary" : "danger"}
          size="sm"
          disabled={blocked}
          aria-busy={busy}
          onClick={apply}
          data-testid="operation-edit-apply"
        >
          {isDelete ? (replacing ? "Apply replacement" : "Accept delete") : "Apply edited"}
        </Button>
        {!isDelete && (
          <Button
            variant="ghost"
            size="sm"
            disabled={!draft}
            onClick={() => {
              setDraft(undefined);
              setServerError(undefined);
            }}
            data-testid="operation-edit-reset"
          >
            Back to proposed
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onCancel} data-testid="operation-edit-cancel">
          Cancel
        </Button>
      </div>

      <div>
        <div className="op-edit__label">Decision sent back to DR</div>
        <pre className="op-edit__preview" data-testid="operation-edit-preview">
          {preview}
        </pre>
      </div>
    </div>
  );
}
