import { DomainOut } from "@/api/services/domains";
import { RecordSelector } from "@/components/node_selectors/record_selector";
import { useDomains } from "@/api/hooks/domains";

export interface DomainSelectorProps {
  onSelect?: (domain: DomainOut | undefined) => void;
  value?: string;
}

export const DomainSelector: React.FC<DomainSelectorProps> = ({ onSelect, value }) => {
  const { data: domains, isLoading, error } = useDomains();
  return (
    <RecordSelector
      records={domains ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={onSelect}
      value={value}
    />
  );
};
