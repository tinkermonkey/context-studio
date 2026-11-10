import { useEffect, useId, useMemo, useState } from "react";
import {
  Button,
  EntityPicker,
  Field,
  Icon,
  TextInput,
  type EntityPickerResult,
} from "@tinkermonkey/heimdall-ui";
import { EditableField } from "@/components/ui/EditableField";
import { useToasts } from "@/components/ui/Toast";
import { useClassesByIds, useUpdateClass } from "@/api/hooks/ontology/useClasses";
import { useClassSearch } from "@/api/hooks/ontology/useEntitySearch";
import { ApiError } from "@/api/client/interceptors";
import type { components } from "@/api/types";
import "./OperationalDefinition.css";

type ClassResponse = components["schemas"]["ClassResponse"];
type ClassUpdateRequest = components["schemas"]["ClassUpdateRequest"];
type DistinguishFrom = components["schemas"]["DistinguishFromSchema"];

/**
 * Titles of the classes a distinguish_from names. A class that no longer
 * exists keeps its entry: `missing` is true for it once the lookup is done.
 */
function useDistinguishLabels(entries: DistinguishFrom[]) {
  const { data, isSuccess } = useClassesByIds(entries.map((e) => e.class_id));
  const titles = useMemo(
    () => new Map((data?.items ?? []).map((c) => [c.id, c.title || c.identifier])),
    [data],
  );
  return (classId: string) => ({
    label: titles.get(classId) ?? classId,
    missing: isSuccess && !titles.has(classId),
  });
}

function DistinguishClass({ label, missing }: { label: string; missing: boolean }) {
  return missing ? (
    <span className="class-definition__class class-definition__class--missing">
      {label} <span className="class-definition__hint">(class not found)</span>
    </span>
  ) : (
    <span className="class-definition__class">{label}</span>
  );
}

interface OperationalDefinitionProps {
  classData: ClassResponse;
}

/** A class's operational definition, read-only: who to tell it apart from, its signals, its standard. */
export function OperationalDefinitionView({ classData }: OperationalDefinitionProps) {
  const distinguish = classData.distinguish_from ?? [];
  const signals = classData.evidence_signals ?? [];
  const standard = classData.standard_reference ?? "";
  const labelOf = useDistinguishLabels(distinguish);

  if (distinguish.length === 0 && signals.length === 0 && !standard) {
    return (
      <p className="drawer-empty-note" data-testid="class-definition-empty">
        No operational definition
      </p>
    );
  }
  return (
    <div className="class-definition" data-testid="class-definition-view">
      <div className="class-definition__group">
        <span className="form-group-label">Distinguish from</span>
        {distinguish.length === 0 ? (
          <p className="class-definition__none">—</p>
        ) : (
          <ul className="class-definition__list" data-testid="class-distinguish-list">
            {distinguish.map((entry) => (
              <li
                key={entry.class_id}
                className="class-definition__entry"
                data-testid={`class-distinguish-entry-${entry.class_id}`}
              >
                <DistinguishClass {...labelOf(entry.class_id)} />
                <span className="class-definition__when">{entry.when}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="class-definition__group">
        <span className="form-group-label">Evidence signals</span>
        {signals.length === 0 ? (
          <p className="class-definition__none">—</p>
        ) : (
          <ol
            className="class-definition__list class-definition__list--ordered"
            data-testid="class-evidence-signals-list"
          >
            {signals.map((signal, index) => (
              <li key={index} className="class-definition__entry">
                {signal}
              </li>
            ))}
          </ol>
        )}
      </div>
      <div className="class-definition__group">
        <span className="form-group-label">Standard reference</span>
        <p className="class-definition__none" data-testid="class-standard-reference">
          {standard || "—"}
        </p>
      </div>
    </div>
  );
}

interface CommitInputProps {
  value: string;
  onCommit: (value: string) => void;
  label: string;
  /** Shown when the text is cleared: an entry needs some. */
  requiredMessage: string;
  "data-testid": string;
}

/** A text input that commits its trimmed text on blur or Enter; Escape puts the saved text back. */
function CommitInput({
  value,
  onCommit,
  label,
  requiredMessage,
  "data-testid": testId,
}: CommitInputProps) {
  const [draft, setDraft] = useState(value);
  const [error, setError] = useState<string>();
  const errorId = useId();
  useEffect(() => setDraft(value), [value]);

  const commit = () => {
    const text = draft.trim();
    if (!text) {
      setError(requiredMessage);
      return;
    }
    if (text !== value) onCommit(text);
  };
  return (
    <div className="class-definition__input">
      <TextInput
        value={draft}
        aria-label={label}
        error={!!error}
        aria-invalid={!!error}
        aria-describedby={error ? errorId : undefined}
        onChange={(e) => {
          setDraft(e.target.value);
          setError(undefined);
        }}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") {
            setDraft(value);
            setError(undefined);
          }
        }}
        data-testid={testId}
      />
      {error && (
        <p id={errorId} className="class-definition__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Edit a class's operational definition. Each change saves at once: the
 * classes to tell it apart from (a sibling in its domain, plus when to use it
 * instead), the evidence signals in order, and the standard it follows.
 */
export function OperationalDefinitionEditor({ classData }: OperationalDefinitionProps) {
  const { toast } = useToasts();
  const updateMutation = useUpdateClass();
  const [distinguish, setDistinguish] = useState(classData.distinguish_from ?? []);
  const [signals, setSignals] = useState(classData.evidence_signals ?? []);
  useEffect(() => setDistinguish(classData.distinguish_from ?? []), [classData.distinguish_from]);
  useEffect(() => setSignals(classData.evidence_signals ?? []), [classData.evidence_signals]);
  const labelOf = useDistinguishLabels(distinguish);

  // The add-a-distinction row.
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<EntityPickerResult>();
  const [when, setWhen] = useState("");
  const [classError, setClassError] = useState<string>();
  const [whenError, setWhenError] = useState<string>();
  const [newSignal, setNewSignal] = useState("");
  const [signalError, setSignalError] = useState<string>();
  const ids = { picker: useId(), when: useId(), signal: useId() };

  const { data: searchResults } = useClassSearch(
    query,
    { concept_scheme_id: classData.concept_scheme_id },
    { enabled: query.trim().length > 0 },
  );
  // Siblings only: not the class itself, nor one it already names.
  const results = (searchResults?.items ?? [])
    .filter((c) => c.id !== classData.id && !distinguish.some((e) => e.class_id === c.id))
    .map((c) => ({ id: c.id, label: c.title || c.identifier }));

  const save = async (data: ClassUpdateRequest, revert: () => void) => {
    try {
      await updateMutation.mutateAsync({ id: classData.id, data });
    } catch (error) {
      revert();
      toast("error", error instanceof ApiError ? error.detail : "Failed to save the class");
    }
  };

  const saveDistinguish = (next: DistinguishFrom[]) => {
    const previous = distinguish;
    setDistinguish(next);
    void save({ distinguish_from: next }, () => setDistinguish(previous));
  };

  const saveSignals = (next: string[]) => {
    const previous = signals;
    setSignals(next);
    void save({ evidence_signals: next }, () => setSignals(previous));
  };

  const addDistinguish = () => {
    const text = when.trim();
    if (!picked) setClassError("Pick a class from this domain");
    if (!text) setWhenError("Say when to use that class instead");
    if (!picked || !text) return;
    saveDistinguish([...distinguish, { class_id: picked.id, when: text }]);
    setPicked(undefined);
    setQuery("");
    setWhen("");
  };

  const addSignal = () => {
    const text = newSignal.trim();
    if (!text) {
      setSignalError("Type a signal first");
      return;
    }
    saveSignals([...signals, text]);
    setNewSignal("");
  };

  const moveSignal = (index: number, offset: number) => {
    const next = [...signals];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    saveSignals(next);
  };

  return (
    <div className="class-definition" data-testid="class-definition-editor">
      <div className="class-definition__group">
        <span className="form-group-label">Distinguish from</span>
        {distinguish.length > 0 && (
          <ul className="class-definition__list" data-testid="class-distinguish-list">
            {distinguish.map((entry, index) => {
              const { label, missing } = labelOf(entry.class_id);
              return (
                <li
                  key={entry.class_id}
                  className="class-definition__row"
                  data-testid={`class-distinguish-entry-${entry.class_id}`}
                >
                  <div className="class-definition__row-head">
                    <DistinguishClass label={label} missing={missing} />
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove ${label}`}
                      onClick={() => saveDistinguish(distinguish.filter((_, i) => i !== index))}
                      data-testid={`class-distinguish-remove-${entry.class_id}`}
                    >
                      <Icon name="x" size={14} />
                    </Button>
                  </div>
                  <CommitInput
                    value={entry.when}
                    label={`When to use ${label} instead`}
                    requiredMessage="Say when to use that class instead"
                    onCommit={(text) =>
                      saveDistinguish(
                        distinguish.map((e, i) => (i === index ? { ...e, when: text } : e)),
                      )
                    }
                    data-testid={`class-distinguish-when-${entry.class_id}`}
                  />
                </li>
              );
            })}
          </ul>
        )}
        <div className="class-definition__add" data-testid="class-distinguish-add-row">
          <Field label="Class" htmlFor={ids.picker} error={classError}>
            <EntityPicker
              inputId={ids.picker}
              query={query}
              onQueryChange={(q) => {
                setQuery(q);
                if (q !== picked?.label) setPicked(undefined);
                setClassError(undefined);
              }}
              results={results}
              onSelect={(result) => {
                setPicked(result);
                setQuery(result.label);
                setClassError(undefined);
              }}
              onClear={() => {
                setPicked(undefined);
                setQuery("");
              }}
              placeholder="Search classes in this domain…"
              data-testid="class-distinguish-picker"
            />
          </Field>
          <Field label="Use it instead when" htmlFor={ids.when} error={whenError}>
            <TextInput
              id={ids.when}
              value={when}
              placeholder="e.g. it is deployed on its own"
              error={!!whenError}
              aria-invalid={!!whenError}
              onChange={(e) => {
                setWhen(e.target.value);
                setWhenError(undefined);
              }}
              onKeyDown={(e) => e.key === "Enter" && addDistinguish()}
              data-testid="class-distinguish-new-when"
            />
          </Field>
          <Button
            variant="ghost"
            size="sm"
            onClick={addDistinguish}
            data-testid="class-distinguish-add"
          >
            <Icon name="plus" size={13} /> Add distinction
          </Button>
        </div>
      </div>

      <div className="class-definition__group">
        <span className="form-group-label">Evidence signals</span>
        {signals.length > 0 && (
          <ol className="class-definition__list" data-testid="class-evidence-signals-list">
            {signals.map((signal, index) => (
              // Signals can repeat while being edited; the position is the identity.
              <li
                key={index}
                className="class-definition__signal"
                data-testid={`class-evidence-signal-${index}`}
              >
                <span className="class-definition__rank">{index + 1}</span>
                <CommitInput
                  value={signal}
                  label={`Evidence signal ${index + 1}`}
                  requiredMessage="A signal needs text; remove it instead"
                  onCommit={(text) => saveSignals(signals.map((s, i) => (i === index ? text : s)))}
                  data-testid={`class-evidence-signal-input-${index}`}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Move signal ${index + 1} up`}
                  disabled={index === 0}
                  onClick={() => moveSignal(index, -1)}
                  data-testid={`class-evidence-signal-up-${index}`}
                >
                  <Icon name="arrowUp" size={14} />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Move signal ${index + 1} down`}
                  disabled={index === signals.length - 1}
                  onClick={() => moveSignal(index, 1)}
                  data-testid={`class-evidence-signal-down-${index}`}
                >
                  <Icon name="arrowDown" size={14} />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove signal ${index + 1}`}
                  onClick={() => saveSignals(signals.filter((_, i) => i !== index))}
                  data-testid={`class-evidence-signal-remove-${index}`}
                >
                  <Icon name="x" size={14} />
                </Button>
              </li>
            ))}
          </ol>
        )}
        <div className="class-definition__add">
          <Field label="New signal" htmlFor={ids.signal} error={signalError}>
            <TextInput
              id={ids.signal}
              value={newSignal}
              placeholder="Something observable that marks an instance"
              error={!!signalError}
              aria-invalid={!!signalError}
              onChange={(e) => {
                setNewSignal(e.target.value);
                setSignalError(undefined);
              }}
              onKeyDown={(e) => e.key === "Enter" && addSignal()}
              data-testid="class-evidence-signal-new"
            />
          </Field>
          <Button
            variant="ghost"
            size="sm"
            onClick={addSignal}
            data-testid="class-evidence-signal-add"
          >
            <Icon name="plus" size={13} /> Add signal
          </Button>
        </div>
      </div>

      <EditableField
        label="Standard reference"
        value={classData.standard_reference ?? ""}
        placeholder="The standard it follows, e.g. ArchiMate 3.2 §9.2"
        onSave={async (value) => {
          await updateMutation.mutateAsync({
            id: classData.id,
            data: { standard_reference: value },
          });
        }}
        data-testid="class-drawer-standard-reference-field"
      />
    </div>
  );
}
