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

/**
 * Chooses the dataset a run extracts into: its individuals are matched and
 * created there. Renders nothing unless the
 * taxonomy has two or more datasets: with one, the dataset is implied.
 */
export function RunDatasetField({ run, id, error, disabled, onChange }: RunDatasetFieldProps) {
  if (!run.required) return null;
  const errorId = `${id}-error`;
  return (
    <Field label="Dataset" htmlFor={id} required error={error} errorId={errorId}>
      <Select
        id={id}
        value={run.dataset?.id ?? ""}
        onChange={(datasetId) => {
          run.select(datasetId);
          onChange?.();
        }}
        placeholder="Select a dataset"
        ariaLabel="Dataset"
        disabled={disabled}
        error={!!error}
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
