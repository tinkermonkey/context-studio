import { StructureNode } from "@/api/types/structureNodes";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useTaxonomies } from "@/api/hooks/taxonomies";

export interface TaxonomySelectorProps {
  onSelect?: (taxonomy: StructureNode | undefined) => void;
  value?: string;
  "data-testid"?: string;
}

export const TaxonomySelector: React.FC<TaxonomySelectorProps> = ({
  onSelect,
  value,
  "data-testid": dataTestId,
}) => {
  const { data: taxonomies, isLoading, error } = useTaxonomies();
  return (
    <PortalRecordSelector
      records={taxonomies ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as StructureNode | undefined)}
      value={value}
      data-testid={dataTestId}
    />
  );
};
