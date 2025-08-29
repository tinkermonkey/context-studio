import { DomainOut } from "@/api/services/domains";
import { PortalRecordSelector } from "@/components/node_selectors/portal_record_selector";
import { useDomains } from "@/api/hooks/domains";

export interface DomainSelectorProps {
  onSelect?: (domain: DomainOut | undefined) => void;
  value?: string;
  className?: string;
}

export const DomainSelector: React.FC<DomainSelectorProps> = ({ onSelect, value, className }) => {
  const { data: domains, isLoading, error } = useDomains();
  return (
    <PortalRecordSelector
      records={domains ?? []}
      loading={isLoading}
      error={error ? "Failed to load records" : null}
      fieldMap={{ value: "id", title: "title", definition: "definition" }}
      onSelect={(r) => onSelect && onSelect(r as DomainOut | undefined)}
      value={value}
      placeholder={"Select Record"}
    />
  );
};
