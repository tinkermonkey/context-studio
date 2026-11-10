import { Fragment, useMemo } from "react";
import { Select } from "@tinkermonkey/heimdall-ui";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useDatasetScope } from "@/hooks/useDatasetScope";
import { datasetsCopy } from "./copy";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

/** The "All datasets" choice (a Select item needs a non-empty value). */
export const ALL_DATASETS = "all";

interface DatasetSelectProps {
  /** Offer only this taxonomy's datasets; omit it to offer every taxonomy's. */
  taxonomyId?: string;
  "data-testid"?: string;
}

/**
 * Chooses the dataset the page shows (the `dataset` URL parameter). Renders
 * nothing unless a taxonomy in scope has two or more datasets: with one, the
 * dataset is implied. Datasets of several taxonomies are grouped by taxonomy.
 */
export function DatasetSelect({
  taxonomyId,
  "data-testid": testId = "dataset-select",
}: DatasetSelectProps) {
  const { datasets, selectedDatasetId, showSelector, setDataset } = useDatasetScope(taxonomyId);
  const taxonomyIds = useMemo(() => [...new Set(datasets.map((d) => d.taxonomy_id))], [datasets]);
  const grouped = taxonomyIds.length > 1;
  const { data: taxonomies } = useTaxonomies(
    { limit: SMALL_SET_LIMIT },
    { enabled: grouped && showSelector },
  );

  if (!showSelector) return null;

  const taxonomyTitle = new Map((taxonomies?.items ?? []).map((t) => [t.id, t.title]));
  const byTaxonomy = new Map<string, DatasetResponse[]>();
  for (const d of datasets)
    byTaxonomy.set(d.taxonomy_id, [...(byTaxonomy.get(d.taxonomy_id) ?? []), d]);

  return (
    <Select
      value={selectedDatasetId ?? ALL_DATASETS}
      onChange={(value) => setDataset(value === ALL_DATASETS ? undefined : value)}
      ariaLabel={datasetsCopy.select.ariaLabel}
      className="dataset-select"
      placement="bottom-end"
      data-testid={testId}
    >
      <Select.Item value={ALL_DATASETS}>{datasetsCopy.select.allLabel}</Select.Item>
      {taxonomyIds.map((tid) => (
        <Fragment key={tid}>
          {grouped && <Select.SectionTitle>{taxonomyTitle.get(tid) ?? tid}</Select.SectionTitle>}
          {(byTaxonomy.get(tid) ?? []).map((d) => (
            <Select.Item key={d.id} value={d.id}>
              {d.title} · {d.identifier}
            </Select.Item>
          ))}
        </Fragment>
      ))}
    </Select>
  );
}
