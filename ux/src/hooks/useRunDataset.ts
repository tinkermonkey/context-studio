import { useState } from "react";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

/** The dataset an individual-extraction run extracts into. Read by RunDatasetField. */
export interface RunDataset {
  /** The taxonomy's datasets; empty until a taxonomy is chosen. */
  datasets: DatasetResponse[];
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
 */
export function useRunDataset(taxonomyId?: string): RunDataset {
  const { data } = useDatasets(taxonomyId);
  const [choice, setChoice] = useState<string>();
  const datasets = taxonomyId ? (data ?? []) : [];
  const required = datasets.length > 1;
  // A dataset of another taxonomy is no choice for this one.
  const dataset = required ? datasets.find((d) => d.id === choice) : undefined;
  return {
    datasets,
    required,
    dataset,
    missing: required && !dataset,
    select: setChoice,
    fields: dataset ? { dataset_id: dataset.id } : {},
  };
}
