import { useCallback, useMemo } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import type { DatasetSearch } from "@/lib/datasetSearch";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

export interface DatasetScope {
  /** The taxonomy's datasets, or every dataset when no taxonomy is given. */
  datasets: DatasetResponse[];
  /** The dataset the URL names, when it is one of `datasets`. */
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
export function useDatasetScope(taxonomyId?: string): DatasetScope {
  const navigate = useNavigate();
  const { dataset } = useSearch({ strict: false }) as DatasetSearch;
  const { data } = useDatasets();

  const datasets = useMemo(
    () => (data ?? []).filter((d) => !taxonomyId || d.taxonomy_id === taxonomyId),
    [data, taxonomyId],
  );
  const selectedDataset = dataset ? datasets.find((d) => d.id === dataset) : undefined;
  const selectedDatasetId = data ? selectedDataset?.id : dataset;

  const showSelector = useMemo(() => {
    const perTaxonomy = new Map<string, number>();
    for (const d of datasets)
      perTaxonomy.set(d.taxonomy_id, (perTaxonomy.get(d.taxonomy_id) ?? 0) + 1);
    return [...perTaxonomy.values()].some((n) => n >= 2);
  }, [datasets]);

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
