import { useCallback, useMemo } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import type { DatasetSearch } from "@/lib/datasetSearch";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

export interface DatasetScope {
  /** The taxonomy's datasets, or every dataset when no taxonomy is given. */
  datasets: DatasetResponse[];
  /**
   * The dataset the URL names, when it is one of `datasets` and its taxonomy
   * has two or more (with one, the choice is implied and nothing is scoped).
   */
  selectedDataset?: DatasetResponse;
  /**
   * The dataset to scope queries to. While the datasets load it is the URL's
   * value as is, so the first requests are already scoped.
   */
  selectedDatasetId?: string;
  /** Offer a choice only when some taxonomy in scope has two or more datasets. */
  showSelector: boolean;
  /** Choose a dataset (undefined: all data). */
  setDataset: (datasetId: string | undefined) => void;
}

/**
 * The dataset the current page shows, from the `dataset` URL parameter.
 * Pass the page's taxonomy when it has one: a dataset of another taxonomy is
 * then ignored, and the selector shows only for that taxonomy's datasets.
 * With one dataset the choice is implied, so nothing is selected or shown.
 */
/** How many datasets each taxonomy has. */
export function datasetsPerTaxonomy(datasets: DatasetResponse[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const d of datasets) counts.set(d.taxonomy_id, (counts.get(d.taxonomy_id) ?? 0) + 1);
  return counts;
}

export function useDatasetScope(taxonomyId?: string): DatasetScope {
  const navigate = useNavigate();
  const { dataset } = useSearch({ strict: false }) as DatasetSearch;
  const { data } = useDatasets();

  const datasets = useMemo(
    () => (data ?? []).filter((d) => !taxonomyId || d.taxonomy_id === taxonomyId),
    [data, taxonomyId],
  );
  const perTaxonomy = useMemo(() => datasetsPerTaxonomy(data ?? []), [data]);
  const named = dataset ? datasets.find((d) => d.id === dataset) : undefined;
  // A taxonomy's only dataset is implied: naming it scopes nothing, so a stale
  // parameter can never hide data behind a selector that isn't shown.
  const selectedDataset =
    named && (perTaxonomy.get(named.taxonomy_id) ?? 0) >= 2 ? named : undefined;
  const selectedDatasetId = data ? selectedDataset?.id : dataset;

  const showSelector = useMemo(
    () => datasets.some((d) => (perTaxonomy.get(d.taxonomy_id) ?? 0) >= 2),
    [datasets, perTaxonomy],
  );

  const setDataset = useCallback(
    (datasetId: string | undefined) => {
      navigate({
        to: ".",
        search: (prev) => ({ ...prev, dataset: datasetId }),
        replace: true,
      });
    },
    [navigate],
  );

  return { datasets, selectedDataset, selectedDatasetId, showSelector, setDataset };
}
