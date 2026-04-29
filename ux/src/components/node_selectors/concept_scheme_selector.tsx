import { OntologyClass } from "@/api/types/ontologyClasss";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes";

export interface ConceptSchemeSelectorProps {
  onSelect?: (conceptScheme: OntologyClass | undefined) => void;
  value?: string;
  className?: string;
  "data-testid"?: string;
}

export const ConceptSchemeSelector: React.FC<ConceptSchemeSelectorProps> = ({
  onSelect,
  value,
  "data-testid": dataTestId,
}) => {
  const { data: conceptSchemes, isLoading, error } = useConceptSchemes();
  return (
    <PortalRecordSelector
      records={conceptSchemes ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as OntologyClass | undefined)}
      value={value}
      placeholder={"Select Record"}
      data-testid={dataTestId}
    />
  );
};
