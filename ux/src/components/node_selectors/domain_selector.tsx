import { ConceptScheme } from "@/api/types/ontology";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useConceptSchemes } from "@/api/hooks/conceptSchemes";

export interface DomainSelectorProps {
  onSelect?: (domain: ConceptScheme | undefined) => void;
  value?: string;
  className?: string;
  "data-testid"?: string;
}

export const DomainSelector: React.FC<DomainSelectorProps> = ({
  onSelect,
  value,
  "data-testid": dataTestId,
}) => {
  const { data: domains, isLoading, error } = useConceptSchemes();
  return (
    <PortalRecordSelector
      records={domains ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as ConceptScheme | undefined)}
      value={value}
      placeholder={"Select Record"}
      data-testid={dataTestId}
    />
  );
};
