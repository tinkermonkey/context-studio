import { useState } from "react";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

/** The dataset an individual-extraction run extracts into. Read by RunDatasetField. */
export interface RunDataset {
  /** The taxonomy's datasets; empty until a taxonomy is chosen and its list has loaded. */
  datasets: DatasetResponse[];
  /** The taxonomy's datasets are still being read: whether one must be named is not known yet. */
  loading: boolean;
  /** Why the taxonomy's datasets could not be read; whether one must be named is unknown. */
  loadError?: string;
  /**
   * A run may start: the list has loaded (or no taxonomy is chosen) and a
   * dataset is named where the taxonomy has several.
   */
  ready: boolean;
  /** The taxonomy has two or more datasets, so the run must name one. */
  required: boolean;
  dataset?: DatasetResponse;
  /** A dataset is required and none is chosen. */
  missing: boolean;
  select: (datasetId: string) => void;
  /** The run-request field; empty while the taxonomy's only dataset is implied. */
  fields: { dataset_id?: string };
}

/**
 * The dataset choice for a run against `taxonomyId`. With one dataset (or
 * none yet) the server takes the taxonomy's own, so nothing is chosen or sent;
 * with several it refuses a run that names none, so the user must choose.
 * Until the list is read the answer is not known, so a run is not ready:
 * taking "not loaded" for "nothing required" would send a run the server refuses.
 */
export function useRunDataset(taxonomyId?: string): RunDataset {
  const query = useDatasets(taxonomyId);
  const [choice, setChoice] = useState<string>();
  const loading = !!taxonomyId && query.isPending;
  const loadError =
    taxonomyId && query.isError
      ? query.error instanceof Error && query.error.message
        ? query.error.message
        : "Failed to load datasets"
      : undefined;
  const datasets = taxonomyId && !loadError ? (query.data ?? []) : [];
  const required = datasets.length > 1;
  // A dataset of another taxonomy is no choice for this one.
  const dataset = required ? datasets.find((d) => d.id === choice) : undefined;
  const missing = required && !dataset;
  return {
    datasets,
    loading,
    loadError,
    ready: !loading && !loadError && !missing,
    required,
    dataset,
    missing,
    select: setChoice,
    fields: dataset ? { dataset_id: dataset.id } : {},
  };
}
