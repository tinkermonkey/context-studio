import { useState } from "react";
import { Field, NumberInput } from "@tinkermonkey/heimdall-ui";
import type { NumberBounds } from "@/api/services/pipeline";

export interface ParamNumberFieldProps {
  /** Id of the input; its test id is `${id}-input`. */
  id: string;
  label: string;
  /** What the configuration sets; null when it leaves the value to the default configuration. */
  value: number | null;
  /** The value in effect while none is set: the default configuration's, if it sets one. */
  inherited?: number | null;
  /** The range the API accepts; unchecked here when not known. */
  bounds?: NumberBounds;
  integer?: boolean;
  /** A valid value (or none) was typed. */
  onChange: (value: number | null) => void;
  /** The typed text became, or stopped being, something the API takes. */
  onValidChange?: (valid: boolean) => void;
  /** The field was left holding a valid value (or none). */
  onCommit: (value: number | null) => void;
}

/** What the typed text stands for: a number, nothing (unset), or something the API would refuse. */
function parse(text: string, integer: boolean, bounds: NumberBounds): number | null | undefined {
  if (text.trim() === "") return null;
  const value = Number(text);
  const valid =
    Number.isFinite(value) &&
    (!integer || Number.isInteger(value)) &&
    (bounds.minimum === undefined || value >= bounds.minimum) &&
    (bounds.maximum === undefined || value <= bounds.maximum);
  return valid ? value : undefined;
}

function rangeMessage(integer: boolean, { minimum, maximum }: NumberBounds): string {
  const kind = integer ? "A whole number" : "A number";
  if (minimum !== undefined && maximum !== undefined)
    return `${kind} from ${minimum} to ${maximum}`;
  if (minimum !== undefined) return `${kind}, ${minimum} or more`;
  if (maximum !== undefined) return `${kind}, ${maximum} or less`;
  return kind;
}

/**
 * A typed LLM parameter of a configuration that may be left unset. Empty means
 * unset: the run then uses the default configuration's value, which shows as
 * the placeholder ("none set" when that sets none either). Mount it with a key
 * that changes with the configuration.
 */
export function ParamNumberField({
  id,
  label,
  value,
  inherited,
  bounds = {},
  integer = false,
  onChange,
  onValidChange,
  onCommit,
}: ParamNumberFieldProps) {
  const [text, setText] = useState(value === null ? "" : String(value));
  const [error, setError] = useState<string>();
  const errorId = `${id}-error`;
  const unset = text.trim() === "";
  // The default configuration sets none either: a run is then given none.
  const nothingToInherit = inherited === null || inherited === undefined;

  return (
    <Field
      label={label}
      htmlFor={id}
      hint={unset ? (nothingToInherit ? "none set" : "inherited") : undefined}
      error={error}
      errorId={errorId}
      className="cfg-param-field"
      data-testid={id}
    >
      <NumberInput
        id={id}
        mono
        min={bounds.minimum}
        max={bounds.maximum}
        step={integer ? 1 : "any"}
        value={text}
        placeholder={nothingToInherit ? undefined : String(inherited)}
        onChange={(e) => {
          setText(e.target.value);
          setError(undefined);
          const parsed = parse(e.target.value, integer, bounds);
          onValidChange?.(parsed !== undefined);
          if (parsed !== undefined) onChange(parsed);
        }}
        onBlur={() => {
          const parsed = parse(text, integer, bounds);
          if (parsed === undefined) setError(rangeMessage(integer, bounds));
          else onCommit(parsed);
        }}
        error={!!error}
        aria-invalid={!!error}
        aria-describedby={error ? errorId : undefined}
        data-testid={`${id}-input`}
      />
    </Field>
  );
}
