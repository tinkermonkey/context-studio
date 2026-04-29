import { OntologyClass } from "@/api/types/ontology";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useDomainNodes } from "@/api/hooks/ontologyClasses";

export interface DomainSelectorProps {
  onSelect?: (domain: OntologyClass | undefined) => void;
  value?: string;
  className?: string;
  "data-testid"?: string;
}

export const DomainSelector: React.FC<DomainSelectorProps> = ({
  onSelect,
  value,
  "data-testid": dataTestId,
}) => {
  const { data: domains, isLoading, error } = useDomainNodes();
  return (
    <PortalRecordSelector
      records={domains ?? []}
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
