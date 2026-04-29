import { OntologyClass } from "@/api/types/ontology";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useTaxonomies } from "@/api/hooks/taxonomies/useTaxonomies";

export interface LayerSelectorProps {
  onSelect?: (layer: OntologyClass | undefined) => void;
  value?: string;
  "data-testid"?: string;
}

export const LayerSelector: React.FC<LayerSelectorProps> = ({
  onSelect,
  value,
  "data-testid": dataTestId,
}) => {
  const { data: taxonomies, isLoading, error } = useTaxonomies();

  // Transform taxonomies to OntologyClass-like format for compatibility
  const layers = taxonomies?.map((t) => ({
    id: t.id,
    title: t.title,
    definition: t.description || "",
  })) as OntologyClass[] | undefined;

  return (
    <PortalRecordSelector
      records={layers ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as OntologyClass | undefined)}
      value={value}
      data-testid={dataTestId}
    />
  );
};
