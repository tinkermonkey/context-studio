import { Field, Select } from "@tinkermonkey/heimdall-ui";
import type { RunDataset } from "@/hooks/useRunDataset";

export interface RunDatasetFieldProps {
  /** The dataset choice to show and change (useRunDataset). */
  run: RunDataset;
  /** Id of the select, and its test id; unique on the page. */
  id: string;
  error?: string;
  disabled?: boolean;
  /** Called after the choice changes, e.g. to clear its error. */
  onChange?: () => void;
}

export const DATASET_REQUIRED = "Select a dataset";

/** The field's error: the list could not be read, or the given validation error. */
const fieldError = (run: RunDataset, error?: string) =>
  run.loadError ? `Could not load the datasets: ${run.loadError}` : error;

/**
 * Chooses the dataset a run extracts into: its individuals are matched and
 * created there. Renders nothing while the taxonomy has one dataset (it is
 * implied) or its list is still loading; shows the error when the list could
 * not be read, since whether one must be chosen is then unknown.
 */
export function RunDatasetField({ run, id, error, disabled, onChange }: RunDatasetFieldProps) {
  if (!run.required && !run.loadError) return null;
  const errorId = `${id}-error`;
  const shown = fieldError(run, error);
  return (
    <Field label="Dataset" htmlFor={id} required error={shown} errorId={errorId}>
      <Select
        id={id}
        value={run.dataset?.id ?? ""}
        onChange={(datasetId) => {
          run.select(datasetId);
          onChange?.();
        }}
        placeholder="Select a dataset"
        ariaLabel="Dataset"
        disabled={disabled || !!run.loadError}
        error={!!shown}
        data-testid={id}
      >
        {run.datasets.map((d) => (
          <Select.Item key={d.id} value={d.id}>
            {d.identifier}
          </Select.Item>
        ))}
      </Select>
    </Field>
  );
}
