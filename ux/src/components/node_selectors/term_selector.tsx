import { OntologyClass } from "@/api/types/ontology";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useTermNodes } from "@/api/hooks/ontologyClasses/useOntologyClasses";

export interface TermSelectorProps {
  onSelect?: (term: OntologyClass | undefined) => void;
  value?: string;
}

export const TermSelector: React.FC<TermSelectorProps> = ({
  onSelect,
  value,
}) => {
  const { data: terms, isLoading, error } = useTermNodes();
  return (
    <PortalRecordSelector
      records={terms ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as OntologyClass | undefined)}
      value={value}
    />
  );
};
